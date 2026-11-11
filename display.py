#!/usr/bin/env python3
import textwrap

import board
import busio
import digitalio
import adafruit_ssd1306

from PIL import Image, ImageDraw, ImageFont


class Display:
    WIDTH = 128
    HEIGHT = 64

    def __init__(
        self,
        reset_pin=board.D16,
        dc_pin=board.D6,
        spi=None
    ):
        self.oled_reset = digitalio.DigitalInOut(reset_pin)
        self.oled_dc = digitalio.DigitalInOut(dc_pin)

        self._owns_spi = spi is None
        self.spi = spi if spi is not None else busio.SPI(
            clock=board.D21, MOSI=board.D20
        )

        self.oled = adafruit_ssd1306.SSD1306_SPI(
            self.WIDTH,
            self.HEIGHT,
            self.spi,
            self.oled_dc,
            self.oled_reset,
            None  # Geen CS-pin
        )

        self.font = ImageFont.load_default()
        self._closed = False

        self.clear()

    def clear(self):
        if self._closed:
            return

        self.oled.fill(0)
        self.oled.show()

    def toon_tekst(self, titel, tekst):
        if self._closed:
            return

        image = Image.new(
            "1",
            (self.oled.width, self.oled.height),
            0
        )

        draw = ImageDraw.Draw(image)

        draw.text(
            (2, 1),
            str(titel),
            font=self.font,
            fill=255
        )

        draw.line(
            (0, 13, self.oled.width - 1, 13),
            fill=255
        )

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
        if self._closed:
            return

        image = Image.new(
            "1",
            (self.oled.width, self.oled.height),
            0
        )

        draw = ImageDraw.Draw(image)

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
        self.toon_tekst(
            "SMART VAULT",
            status
        )

    def close(self):
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
