#!/usr/bin/env python3

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
        OLED CS   -> GPIO 5
        OLED DC   -> GPIO 6
        OLED CLK  -> SPI SCLK
        OLED DATA -> SPI MOSI

    Schermresolutie:
        128 x 64 pixels
    """

    WIDTH = 128
    HEIGHT = 64

    def __init__(
        self,
        reset_pin=board.D16,
        cs_pin=board.D5,
        dc_pin=board.D6,
        spi=None
    ):
        # Besturingspinnen
        self.oled_reset = digitalio.DigitalInOut(reset_pin)
        self.oled_cs = digitalio.DigitalInOut(cs_pin)
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
            self.oled_cs
        )

        self.font = ImageFont.load_default()
        self._closed = False

        self.clear()

    def clear(self):
        """Wis het volledige OLED-scherm."""

        if self._closed:
            return

        self.oled.fill(0)
        self.oled.show()

    def toon_tekst(self, titel, tekst):
        """
        Toon een titel en tekst op het OLED-display.

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

        Args:
            temperatuur: temperatuur in graden Celsius
            licht: lichtsterkte in lux
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
        """Teken het kluisscherm voor de huidige modus (PIN, 2FA, open, alarm)."""

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
        """Toon een Smart Vault-statusbericht."""

        self.toon_tekst(
            "SMART VAULT",
            status
        )

    def close(self):
        """Wis het scherm en geef de GPIO-resources vrij."""

        if self._closed:
            return

        self.clear()

        self.oled_cs.deinit()
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