#!/usr/bin/env python3
"""SSD1306 OLED-aansturing (128x64, SPI) voor de Smart Vault.

Rol in de architectuur:
    Dit bestand is de enige weergavelaag. ``main.py`` roept
    ``Display.toon_kluisscherm`` aan vanuit de sensor-/OLED-thread (10 Hz) met
    een snapshot van de ``VaultState`` (modus, lux, temperatuur, pin, ...).
    Dit bestand leest zelf NOOIT ``VaultState`` en gebruikt geen
    ``state.lock``: alle gegevens komen als parameters binnen zodat de lock
    kort kan blijven.

Hardware en bibliotheken:
    - adafruit_ssd1306 (SSD1306_SPI) stuurt het OLED via SPI0 aan, met
      GPIO-pinnen voor RST (GPIO 16) en DC (GPIO 6). Het OLED heeft geen CS;
      de module houdt de SPI-ingang permanent geselecteerd.
    - digitalio/board (Adafruit Blinka) leveren de pinabstractie op de Pi 5.
    - Pillow (PIL) tekent in een 1-bit beeld in het geheugen; pas daarna wordt
      het in één keer naar het scherm gestuurd (geen flikkering).
    - textwrap breekt lange tekst af op de 128 px brede display.

Threading / SPI-lock:
    De SPI0-bus wordt gedeeld met de MCP3008-ADC (zie ``sensors.py``). Deze
    klasse is zelf NIET thread-safe en neemt de lock niet; de aanroeper
    (main.py) moet ``state.spi_lock`` vasthouden rond elke aanroep die naar
    het scherm schrijft (``show()``), anders kunnen ADC- en OLED-verkeer
    elkaar corrumperen.
"""

import textwrap

import board
import digitalio
import adafruit_ssd1306

from PIL import Image, ImageDraw, ImageFont


class Display:
    """
    Aansturing van een SSD1306 OLED-display via SPI.

    Aansluitingen:
        OLED RST  -> GPIO 16
        OLED DC   -> GPIO 6
        OLED CLK  -> SPI SCLK
        OLED DATA -> SPI MOSI
        OLED CS   -> Niet aanwezig (permanent geselecteerd)

    Schermresolutie:
        128 x 64 pixels

    Doel:
        Verbergt de SSD1306-details achter eenvoudige methodes
        (``toon_tekst``, ``toon_sensorwaarden``, ``toon_kluisscherm``,
        ``toon_status``) en beheert de levenscyclus van de GPIO-pinnen.

    Werking:
        Elke ``toon_*``-methode maakt een nieuw 1-bit Pillow-beeld, tekent
        daarop tekst/lijnen en stuurt het via ``oled.image()`` en
        ``oled.show()`` naar het scherm.

    Gedeelde state / threads:
        Geen eigen locks en geen toegang tot ``VaultState``. De aanroeper moet
        ``state.spi_lock`` nemen omdat de SPI-bus met de MCP3008 gedeeld wordt.
        De vlag ``_closed`` maakt alle methodes na ``close()`` veilige no-ops,
        zodat een late aanroep van een thread tijdens het afsluiten niet
        crasht op vrijgegeven pinnen.
    """

    WIDTH = 128
    HEIGHT = 64

    def __init__(
        self,
        reset_pin=board.D16,
        dc_pin=board.D6,
        spi=None
    ):
        """Initialiseert het OLED en wist het scherm.

        Werking (stap voor stap):
            1. Maak digitale uitgangen voor RST en DC (digitalio).
            2. Kies de SPI-bus: de meegegeven gedeelde bus of anders
               ``board.SPI()`` (hardware SPI0 van de Pi).
            3. Maak het ``SSD1306_SPI``-object (128x64) aan zonder CS-pin.
            4. Laad het standaard Pillow-lettertype en wis het scherm.

        Parameters:
            reset_pin: pin voor OLED RST (standaard ``board.D16``).
            dc_pin: pin voor data/command (standaard ``board.D6``).
            spi: optionele bestaande SPI-bus. main.py geeft ``sensors.spi``
                mee zodat ADC en OLED dezelfde busobject delen; toegang
                wordt daarbij met ``state.spi_lock`` geserialiseerd.

        Retourwaarde: geen (constructor).

        Gedeelde state: geen ``VaultState``; wel de gedeelde SPI-bus.
        """
        # Besturingspinnen
        self.oled_reset = digitalio.DigitalInOut(reset_pin)
        self.oled_dc = digitalio.DigitalInOut(dc_pin)

        # Gedeelde SPI-bus (met de MCP3008) of de hardware SPI van de Pi
        self.spi = spi if spi is not None else board.SPI()

        # SSD1306 initialiseren via SPI
        self.oled = adafruit_ssd1306.SSD1306_SPI(
            self.WIDTH,
            self.HEIGHT,
            self.spi,
            self.oled_dc,
            self.oled_reset,
            None
        )

        self.font = ImageFont.load_default()
        self._closed = False

        self.clear()

    def clear(self):
        """Wis het volledige OLED-scherm.

        Werking: vult de framebuffer met 0 (zwart) en stuurt die met
        ``show()`` over SPI naar het scherm. Doet niets na ``close()``.

        Parameters: geen.
        Retourwaarde: geen.
        Gedeelde state: schrijft naar de gedeelde SPI-bus; de aanroeper
        hoort ``state.spi_lock`` vast te houden (behalve tijdens init/close
        wanneer geen andere thread draait).
        """

        if self._closed:
            return

        self.oled.fill(0)
        self.oled.show()

    def refresh(self):
        """Stuur de framebuffer opnieuw om SPI-ruis van de ADC te overschrijven."""
        if not self._closed:
            self.oled.show()

    def toon_tekst(self, titel, tekst):
        """
        Toon een titel en tekst op het OLED-display.

        Werking (stap voor stap):
            1. Maak een zwart 1-bit beeld van 128x64.
            2. Teken de titel linksboven en een scheidingslijn op y=13.
            3. Breek de tekst af op 20 tekens per regel (textwrap) en toon
               maximaal 4 regels, 11 px onder elkaar vanaf y=18.
            4. Stuur het beeld naar het scherm (``image()`` + ``show()``).

        Parameters:
            titel: titeltekst (wordt met ``str()`` omgezet).
            tekst: bodytekst; langer dan 4 regels wordt afgekapt.

        Retourwaarde: geen. Doet niets na ``close()``.

        Gedeelde state: schrijft naar de SPI-bus; aanroeper houdt
        ``state.spi_lock`` vast. Geen ``VaultState``.

        Voorbeeld:
            display.toon_tekst(
                "SMART VAULT",
                "Systeem gereed"
            )
        """

        if self._closed:
            return

        # Nieuw zwart beeld van 128 x 64 pixels
        image = Image.new(
            "1",
            (self.oled.width, self.oled.height),
            0
        )

        draw = ImageDraw.Draw(image)

        # Titel
        draw.text(
            (2, 1),
            str(titel),
            font=self.font,
            fill=255
        )

        # Scheidingslijn
        draw.line(
            (0, 13, self.oled.width - 1, 13),
            fill=255
        )

        # Tekst afbreken over meerdere regels
        regels = textwrap.wrap(
            str(tekst),
            width=20
        )

        y = 18

        for regel in regels[:4]:
            draw.text(
                (2, y),
                regel,
                font=self.font,
                fill=255
            )

            y += 11

        self.oled.image(image)
        self.oled.show()

    def toon_sensorwaarden(self, temperatuur, licht):
        """
        Toon temperatuur en lichtsterkte.

        Werking: tekent op een zwart beeld de titel "SMART VAULT", een
        scheidingslijn, de temperatuur (1 decimaal), de lichtsterkte
        (1 decimaal) en de vaste regel "Status: actief", en toont dit.
        Bedoeld als eenvoudige teststand (gebruikt in de losse OLED-test).

        Args:
            temperatuur: temperatuur in graden Celsius
            licht: lichtsterkte in lux

        Retourwaarde: geen. Doet niets na ``close()``.

        Gedeelde state: schrijft naar de SPI-bus; aanroeper houdt
        ``state.spi_lock`` vast. Geen ``VaultState``.
        """

        if self._closed:
            return

        image = Image.new(
            "1",
            (self.oled.width, self.oled.height),
            0
        )

        draw = ImageDraw.Draw(image)

        # Titel
        draw.text(
            (2, 1),
            "SMART VAULT",
            font=self.font,
            fill=255
        )

        draw.line(
            (0, 13, self.oled.width - 1, 13),
            fill=255
        )

        # Sensorwaarden
        draw.text(
            (2, 21),
            f"Temp: {temperatuur:.1f} C",
            font=self.font,
            fill=255
        )

        draw.text(
            (2, 36),
            f"Licht: {licht:.1f} lux",
            font=self.font,
            fill=255
        )

        draw.text(
            (2, 52),
            "Status: actief",
            font=self.font,
            fill=255
        )

        self.oled.image(image)
        self.oled.show()

    def toon_kluisscherm(
        self,
        mode,
        lux,
        temp_c,
        digit,
        pin_so_far,
        loitering,
        reason,
        voice_passphrase,
        alarm_veilig,
        toon_fout=False,
        pogingen_over=0,
        wachttijd_s=0,
        afstand_cm=None
    ):
        """Teken het kluisscherm voor de huidige modus (PIN, 2FA, open, alarm).

        Doel:
            Hoofdscherm van de kluis; wordt 10 Hz ververst door de
            sensor-/OLED-thread in main.py.

        Werking (stap voor stap):
            1. Maak een nieuw 1-bit beeld.
            2. Teken bovenaan een statusbalk: ``L:`` lux, ``T:`` temperatuur,
               ``A:`` perimeterafstand (``--`` als de meting verouderd is, dus
               ``afstand_cm`` None) en een ``!`` bij loitering, plus lijn y=12.
            3. Kies op basis van ``mode`` de inhoud:
               - PIN_INPUT + toon_fout: "FOUTE CODE!" en resterende pogingen.
               - LOCKOUT: geblokkeerd met aftelling m:ss.
               - PIN_INPUT: vergrendeld, PIN-slots (ingevoerde cijfers of
                 ``_``) en het huidige draaicijfer.
               - VOICE_2FA: Factor 1 OK en de uit te spreken passphrase.
               - UNLOCKED: kluis geopend, knop om te sluiten.
               - ALARM: kader, alarmreden (max 20 tekens) en resetinstructie.
            4. Stuur het beeld naar het scherm.

        Parameters:
            mode (str): "PIN_INPUT", "VOICE_2FA", "UNLOCKED", "ALARM" of
                "LOCKOUT" (zie ``vault_state.MODE_CODES``).
            lux (float): lichtsterkte (BH1750), getoond als geheel getal.
            temp_c (float): temperatuur in graden Celsius (LM35, mediaan).
            digit (int): huidig met de potmeter gekozen cijfer 0-9.
            pin_so_far (list[int]): reeds bevestigde cijfers (kopie).
            loitering (bool): True als iemand dichtbij de kluis staat.
            reason (str): reden van het alarm.
            voice_passphrase (str): geheime zin, getoond in hoofdletters.
            alarm_veilig (bool): True als temperatuur en licht weer normaal
                zijn, zodat de reset zinvol is.
            toon_fout (bool): toon "foute code"-melding na een foute PIN.
            pogingen_over (int): resterende PIN-pogingen.
            wachttijd_s (int): resterende lockout-tijd in seconden.
            afstand_cm (float | None): perimeterafstand of None indien
                verouderd/onbekend.

        Retourwaarde: geen. Doet niets na ``close()``.

        Gedeelde state / threads:
            Leest zelf geen ``VaultState``; alle waarden zijn een snapshot die
            main.py onder ``state.lock`` maakte. De aanroeper moet
            ``state.spi_lock`` vasthouden (SPI0 gedeeld met de MCP3008).

        Ontwerpkeuzes:
            Tekenen in geheugen en slechts één ``show()`` per frame geeft een
            rustig beeld; de snapshot-parameters houden de state-lock kort.
        """

        if self._closed:
            return

        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        font = self.font

        top_bar = f"L:{int(lux)} T:{temp_c:.1f}C "
        top_bar += f"A:{afstand_cm:.0f}cm" if afstand_cm is not None else "A:--cm"
        if loitering:
            top_bar += "!"
        draw.text((2, 0), top_bar, font=font, fill=255)
        draw.line((0, 12, 127, 12), fill=255)

        if mode == "PIN_INPUT" and toon_fout:
            draw.text((2, 20), "FOUTE CODE!", font=font, fill=255)
            draw.text((2, 36), f"Nog {pogingen_over} pogingen over", font=font, fill=255)

        elif mode == "LOCKOUT":
            draw.text((2, 18), "FOUTE CODE!", font=font, fill=255)
            draw.text((2, 32), "Geblokkeerd, wacht:", font=font, fill=255)
            draw.text(
                (2, 46),
                f"{wachttijd_s // 60}:{wachttijd_s % 60:02d}",
                font=font,
                fill=255
            )

        elif mode == "PIN_INPUT":
            draw.text((2, 16), "STATUS: VERGRENDELD", font=font, fill=255)
            slots = [
                str(pin_so_far[i]) if i < len(pin_so_far) else "_"
                for i in range(3)
            ]
            draw.text((2, 30), f"PIN: {'  '.join(slots)}", font=font, fill=255)
            draw.text((2, 46), f"Draai: [ {digit} ] (Druk=OK)", font=font, fill=255)

        elif mode == "VOICE_2FA":
            draw.text((2, 18), "FACTOR 1 (PIN): OK!", font=font, fill=255)
            draw.text((2, 34), "SPREEK WACHTWOORD IN:", font=font, fill=255)
            draw.text((2, 48), f'"{voice_passphrase.upper()}"', font=font, fill=255)

        elif mode == "UNLOCKED":
            draw.text((10, 22), "** KLUIS GEOPEND **", font=font, fill=255)
            draw.text((4, 42), "Druk knop om te sluiten", font=font, fill=255)

        elif mode == "ALARM":
            draw.rectangle((0, 14, 127, 63), outline=255, fill=0)
            draw.text((14, 16), "!!! ALARM ACTIEF !!!", font=font, fill=255)
            draw.text((6, 30), reason[:20], font=font, fill=255)
            if alarm_veilig:
                draw.text((6, 46), "Veilig -> Druk=Reset", font=font, fill=255)
            else:
                draw.text((6, 46), "Druk knop voor Reset", font=font, fill=255)

        self.oled.image(image)
        self.oled.show()

    def toon_status(self, status):
        """Toon een Smart Vault-statusbericht.

        Werking: roept ``toon_tekst`` aan met de vaste titel "SMART VAULT".

        Parameters:
            status: statustekst (wordt afgebroken op 20 tekens per regel).

        Retourwaarde: geen.
        Gedeelde state: zie ``toon_tekst`` (``state.spi_lock`` door aanroeper).
        """

        self.toon_tekst(
            "SMART VAULT",
            status
        )

    def close(self):
        """Wis het scherm en geef de GPIO-resources vrij.

        Werking (stap voor stap):
            1. Doe niets als al gesloten (idempotent).
            2. Wis het scherm via ``clear()``.
            3. ``deinit()`` van DC- en RST-pinnen zodat de GPIO's weer
               vrij zijn voor een volgende start.
            4. Zet ``_closed`` zodat latere ``toon_*``-aanroepen no-ops zijn.

        Parameters: geen.
        Retourwaarde: geen.
        Gedeelde state: wordt door main.py in de ``finally`` van ``main()``
        aangeroepen nadat de threads zijn gestopt; de gedeelde SPI-bus zelf
        wordt hier niet gesloten (die is eigendom van ``sensors.py``).
        """

        if self._closed:
            return

        self.clear()

        self.oled_dc.deinit()
        self.oled_reset.deinit()

        self._closed = True

        print("OLED-display afgesloten.")


# Hiermee kan display.py ook afzonderlijk worden getest
if __name__ == "__main__":
    import time

    display = Display()

    try:
        print("OLED-test gestart")

        display.toon_status("Systeem starten...")
        time.sleep(2)

        display.toon_sensorwaarden(
            temperatuur=22.5,
            licht=245.8
        )
        time.sleep(4)

        display.toon_status("Test geslaagd")
        time.sleep(2)

    except KeyboardInterrupt:
        print("\nOLED-test gestopt.")

    finally:
        display.close()