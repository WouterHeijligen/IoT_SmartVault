#!/usr/bin/env python3
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
        self.led.color = (rood / 100.0, groen / 100.0, blauw / 100.0)

    def knipper_rood(self):
        fase = time.monotonic() % 2.0
        helderheid = 1.0 - abs(fase - 1.0)
        self.led.color = (helderheid, 0, 0)

    def alarm(self, aantal=5, snelheid=0.2):
        for _ in range(aantal):
            self.led.color = (1, 0, 0)
            time.sleep(snelheid)

            self.uit()
            time.sleep(snelheid)

        self.uit()

    def close(self):
        self.led.off()
        self.led.close()


if __name__ == "__main__":
    licht = Zwaailicht()

    try:
        print("Zwaailicht test gestart...")
        licht.alarm(aantal=10, snelheid=0.2)
        print("Test klaar.")

    finally:
        licht.close()
