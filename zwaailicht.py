#!/usr/bin/env python3

import math
import time
from gpiozero import RGBLED


class Zwaailicht:
    def __init__(self, red_pin=12, green_pin=13, blue_pin=26):
        self.led = RGBLED(
            red=red_pin,
            green=green_pin,
            blue=blue_pin,
            pwm=True
        )

    def rood(self):
        self.led.color = (1, 0, 0)

    def groen(self):
        self.led.color = (0, 1, 0)

    def blauw(self):
        self.led.color = (0, 0, 1)

    def uit(self):
        self.led.off()

    def kleur_procent(self, rood, groen, blauw):
        """Zet de kleur in procenten (0..100)."""
        self.led.color = (rood / 100.0, groen / 100.0, blauw / 100.0)

    def zwaai(self, periode=2.0, helderheid=0.6):
        """
        Zwaailicht-effect: vloeit zacht van blauw naar rood en terug.

        Roep dit vaak aan (bv. elke 30 ms); de kleur volgt de klok,
        dus de snelheid hangt niet af van hoe vaak je het aanroept.

        Args:
            periode: seconden voor een volledige blauw -> rood -> blauw cyclus
            helderheid: maximale helderheid (0..1), lager = gedimd
        """
        fase = (time.monotonic() % periode) / periode
        mix = 0.5 - 0.5 * math.cos(2 * math.pi * fase)

        self.led.color = (
            mix * helderheid,
            0,
            (1 - mix) * helderheid
        )

    def alarm(self, aantal=5, snelheid=0.2):
        """Wissel rood en blauw af als zwaailicht."""
        for _ in range(aantal):
            self.led.color = (1, 0, 0)
            time.sleep(snelheid)

            self.led.color = (0, 0, 1)
            time.sleep(snelheid)

        self.uit()

    def close(self):
        self.led.off()
        self.led.close()


# Hiermee kun je zwaailicht.py ook rechtstreeks testen
if __name__ == "__main__":
    licht = Zwaailicht()

    try:
        print("Zwaailicht test gestart...")
        licht.alarm(aantal=10, snelheid=0.2)
        print("Test klaar.")

    finally:
        licht.close()