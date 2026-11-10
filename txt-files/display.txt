#!/usr/bin/env python3
"""
================================================================================
BESTAND: display.py
DOEL:    Aansturing van het kleine OLED-schermpje (128x64 pixels) op de kluis.
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
Dit bestand zorgt voor alles wat je op het OLED-schermpje (type SSD1306) ziet:
- Bovenaan een handige statusbalk met Licht (L), Temperatuur (T) en Afstand (A).
- Daaronder de huidige status van de kluis (Pincode invoeren, Spraakwachtwoord,
  Kluis Geopend, Foute Code of Alarm).

Hoe werkt het tekenen op zo'n schermpje?
We tekenen niet rechtstreeks pixel voor pixel op het scherm (want dan zou het
beeld flikkeren). In plaats daarvan maken we met de Python-bibliotheek `PIL`
(Pillow) eerst een zwart-wit plaatje in het geheugen van de Raspberry Pi.
Pas als alle tekst en lijntjes op dat plaatje staan, sturen we het hele
plaatje in één keer naar het scherm met `self.oled.show()`!

De OLED gebruikt SPI1: klok GPIO21, data GPIO20, reset GPIO16 en DC GPIO6.
Het scherm heeft geen CS- of MISO-aansluiting. De MCP3008 gebruikt SPI0.
"""

import textwrap

import board
import busio
import digitalio
import adafruit_ssd1306

from PIL import Image, ImageDraw, ImageFont


class Display:
    """
    Klasse om eenvoudig tekst en het kluisscherm op het 128x64 OLED-display te zetten.

    Aansluitingen op de Raspberry Pi:
        - OLED RST (Reset)        -> GPIO 16
        - OLED DC  (Data/Command) -> GPIO 6
        - OLED CLK / SCL (Klok)   -> SPI1 SCLK (GPIO 21, fysieke pin 40)
        - OLED DATA / SDA         -> SPI1 MOSI (GPIO 20, fysieke pin 38)
    """

    # Het schermpje is 128 pixels breed en 64 pixels hoog
    WIDTH = 128
    HEIGHT = 64

    def __init__(
        self,
        reset_pin=board.D16,
        dc_pin=board.D6,
        spi=None
    ):
        """
        Zet het OLED-schermpje klaar voor gebruik en maakt het scherm leeg (zwart).
        Standaard opent het scherm de eigen SPI1-bus. Een meegegeven
        SPI-verbinding blijft eigendom van de aanroeper.
        """
        # Maak de twee stuurpinnen aan (Reset en Data/Command)
        self.oled_reset = digitalio.DigitalInOut(reset_pin)
        self.oled_dc = digitalio.DigitalInOut(dc_pin)

        self._owns_spi = spi is None
        self.spi = spi if spi is not None else busio.SPI(
            clock=board.D21, MOSI=board.D20
        )

        # Start het SSD1306 OLED-scherm op via SPI (de laatste `None` betekent: geen CS-pin)
        self.oled = adafruit_ssd1306.SSD1306_SPI(
            self.WIDTH,
            self.HEIGHT,
            self.spi,
            self.oled_dc,
            self.oled_reset,
            None
        )

        # Laad het standaard ingebouwde lettertype
        self.font = ImageFont.load_default()
        # Houdt bij of het scherm bij het afsluiten al is uitgezet
        self._closed = False

        # Begin met een helemaal leeg (zwart) scherm
        self.clear()

    def clear(self):
        """
        Maakt het hele scherm zwart (`fill(0)`) en ververst de weergave (`show()`).
        """
        if self._closed:
            return

        self.oled.fill(0)
        self.oled.show()

    def toon_tekst(self, titel, tekst):
        """
        Toont een algemene titel bovenaan met een horizontale lijn eronder,
        en daaronder maximaal 4 regels gewone tekst.
        Lange zinnen worden met `textwrap.wrap` automatisch afgebroken op 20 tekens.
        """
        if self._closed:
            return

        # 1. Maak een nieuw zwart-wit plaatje ("1" = 1-bit kleur: 0 is zwart, 255 is wit)
        image = Image.new(
            "1",
            (self.oled.width, self.oled.height),
            0
        )

        # `draw` is ons virtuele "potlood" om op het plaatje te tekenen
        draw = ImageDraw.Draw(image)

        # 2. Schrijf de titel linksboven op coördinaat (x=2, y=1) in het wit (fill=255)
        draw.text(
            (2, 1),
            str(titel),
            font=self.font,
            fill=255
        )

        # 3. Teken een horizontale scheidingslijn onder de titel op hoogte y=13
        draw.line(
            (0, 13, self.oled.width - 1, 13),
            fill=255
        )

        # 4. Knip lange tekst op in stukjes van maximaal 20 letters per regel
        regels = textwrap.wrap(
            str(tekst),
            width=20
        )

        # Teken maximaal 4 regels onder elkaar (telkens 11 pixels lager)
        y = 18
        for regel in regels[:4]:
            draw.text(
                (2, y),
                regel,
                font=self.font,
                fill=255
            )
            y += 11

        # 5. Stuur het kant-en-klare plaatje in één keer naar het OLED-scherm
        self.oled.image(image)
        self.oled.show()

    def toon_sensorwaarden(self, temperatuur, licht):
        """
        Eenvoudig testschermpje dat alleen de temperatuur en lichtsterkte toont.
        Wordt gebruikt als je `display.py` los test.
        """
        if self._closed:
            return

        image = Image.new(
            "1",
            (self.oled.width, self.oled.height),
            0
        )

        draw = ImageDraw.Draw(image)

        # Titel en scheidingslijn
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

        # Toon temperatuur en licht met 1 cijfer achter de komma (`:.1f`)
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
        """
        HET HOOFDSCHERM VAN DE KLUIS (wordt 10x per seconde ververst vanuit `main.py`).

        Wat tekent deze functie?
        1. Bovenaan altijd de statusbalk:
           Bijv. `L:12 T:21.5C A:85cm` (met een `!` erachter als iemand heel dichtbij staat).
        2. Daaronder een scherm dat past bij de huidige `mode` (toestand) van de kluis:
           - `PIN_INPUT` (met fout):  Toont "FOUTE CODE!" en hoeveel pogingen je nog hebt.
           - `LOCKOUT`:               Toont "Geblokkeerd" met een aftoklokje (minuten:seconden).
           - `PIN_INPUT` (normaal):   Toont de ingevoerde cijfers (bijv. `4  7  _`) en het draaicijfer.
           - `VOICE_2FA`:             Vraagt de gebruiker om het geheime woord in de microfoon te zeggen.
           - `UNLOCKED`:              Meldt dat de kluis open is!
           - `ALARM`:                 Tekent een opvallend kader met de reden van het alarm (bijv. BRAND of BRAAK).
        """
        if self._closed:
            return

        # Maak weer een vers zwart plaatje in het geheugen
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        font = self.font

        # --- STAP 1: Bovenste statusbalk tekenen ---
        top_bar = f"L:{int(lux)} T:{temp_c:.1f}C "
        # Als we een recente afstandsmeting hebben van de Pico, toon die in cm (anders "--")
        top_bar += f"A:{afstand_cm:.0f}cm" if afstand_cm is not None else "A:--cm"
        # Staat er iemand binnen 40 cm? Zet er een uitroepteken achter!
        if loitering:
            top_bar += "!"
        draw.text((2, 0), top_bar, font=font, fill=255)
        draw.line((0, 12, 127, 12), fill=255)

        # --- STAP 2: Kies het juiste scherm op basis van de modus (`mode`) ---
        if mode == "PIN_INPUT" and toon_fout:
            # Iemand heeft net een foute pincode ingevoerd (wordt 5 seconden getoond)
            draw.text((2, 20), "FOUTE CODE!", font=font, fill=255)
            draw.text((2, 36), f"Nog {pogingen_over} pogingen over", font=font, fill=255)

        elif mode == "LOCKOUT":
            # 3x een foute code ingevoerd: kluis is tijdelijk geblokkeerd met aftelklok
            draw.text((2, 18), "FOUTE CODE!", font=font, fill=255)
            draw.text((2, 32), "Geblokkeerd, wacht:", font=font, fill=255)
            # Reken seconden om naar minuten:seconden (bijv. 0:09)
            draw.text(
                (2, 46),
                f"{wachttijd_s // 60}:{wachttijd_s % 60:02d}",
                font=font,
                fill=255
            )

        elif mode == "PIN_INPUT":
            # Normaal startscherm: toon de 3 plekken voor de pincode (ingevuld cijfer of `_`)
            draw.text((2, 16), "STATUS: VERGRENDELD", font=font, fill=255)
            slots = [
                str(pin_so_far[i]) if i < len(pin_so_far) else "_"
                for i in range(3)
            ]
            draw.text((2, 30), f"PIN: {'  '.join(slots)}", font=font, fill=255)
            draw.text((2, 46), f"Draai: [ {digit} ] (Druk=OK)", font=font, fill=255)

        elif mode == "VOICE_2FA":
            # Stap 1 (Pincode) is gelukt! Nu vragen we om het gesproken wachtwoord (Stap 2)
            draw.text((2, 18), "FACTOR 1 (PIN): OK!", font=font, fill=255)
            draw.text((2, 34), "SPREEK WACHTWOORD IN:", font=font, fill=255)
            draw.text((2, 48), f'"{voice_passphrase.upper()}"', font=font, fill=255)

        elif mode == "UNLOCKED":
            # De kluis is open!
            draw.text((10, 22), "** KLUIS GEOPEND **", font=font, fill=255)
            draw.text((4, 42), "Druk knop om te sluiten", font=font, fill=255)

        elif mode == "ALARM":
            # Alarm! Teken een witte rechthoek (`rectangle`) rondom de alarmmelding
            draw.rectangle((0, 14, 127, 63), outline=255, fill=0)
            draw.text((14, 16), "!!! ALARM ACTIEF !!!", font=font, fill=255)
            draw.text((6, 30), reason[:20], font=font, fill=255)
            # De knop en het scherm gebruiken dezelfde herstelcontrole.
            if alarm_veilig:
                draw.text((6, 46), "Veilig -> Druk=Reset", font=font, fill=255)
            else:
                draw.text((6, 46), "Reset geblokkeerd", font=font, fill=255)

        # --- STAP 3: Stuur het getekende plaatje naar het OLED-scherm ---
        self.oled.image(image)
        self.oled.show()

    def toon_status(self, status):
        """
        Korte hulpfunctie om snel een statusbericht onder de titel "SMART VAULT" te tonen.
        """
        self.toon_tekst(
            "SMART VAULT",
            status
        )

    def close(self):
        """
        Maakt het scherm zwart en geeft de GPIO-pinnen netjes vrij bij het afsluiten.
        """
        if self._closed:
            return

        try:
            self.clear()
        finally:
            self.oled_dc.deinit()
            self.oled_reset.deinit()
            if self._owns_spi:
                self.spi.deinit()
            self._closed = True

        print("OLED-display afgesloten.")


# ==============================================================================
# LOSSE TEST: Wordt alleen uitgevoerd als je `python3 display.py` typt
# ==============================================================================
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