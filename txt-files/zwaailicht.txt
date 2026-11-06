#!/usr/bin/env python3
"""
================================================================================
BESTAND: zwaailicht.py
DOEL:    Aansturing van het RGB-LED licht op de kluis (statuslampje & zwaailicht).
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
Een RGB-LED bestaat eigenlijk uit drie kleine LED'jes in één behuizing:
Rood (GPIO 12), Groen (GPIO 13) en Blauw (GPIO 26). Door die drie kleuren
te mengen, kunnen we elke kleur maken die we willen:
- Blauw:  Kluis is op slot (wacht op pincode)
- Oranje: Pincode is goed, wacht op spraak (Rood + beetje Groen)
- Groen:  Kluis is geopend!
- Rood:   Foute code of Alarm!

💡 TIP VOOR JE PRESENTATIE (Wat is PWM?):
De Raspberry Pi kan op een pin normaal alleen 0V (uit) of 3.3V (aan) zetten.
Om een LED te dimmen of kleuren te mengen (zoals oranje), gebruiken we PWM
(Pulse Width Modulation). De Pi zet de LED dan supersnel aan en uit. Als hij
50% van de tijd aan is en 50% uit, ziet ons oog een half-felle LED!
De bibliotheek `gpiozero` regelt dit automatisch voor ons met `pwm=True`.
"""

import time
from gpiozero import RGBLED


class Zwaailicht:
    """
    Klasse om de RGB-LED eenvoudig van kleur te laten veranderen of te laten knipperen.
    """

    def __init__(self, red_pin=12, green_pin=13, blue_pin=26):
        """
        Verbindt de RGB-LED met de juiste GPIO-pinnen op de Raspberry Pi.
        Met `pwm=True` kunnen we de helderheid per kleur instellen van 0.0 tot 1.0.
        """
        self.led = RGBLED(
            red=red_pin,
            green=green_pin,
            blue=blue_pin,
            pwm=True
        )

    def rood(self):
        """Zet de LED op 100% rood: (Rood=1, Groen=0, Blauw=0)."""
        self.led.color = (1, 0, 0)

    def groen(self):
        """Zet de LED op 100% groen: (Rood=0, Groen=1, Blauw=0)."""
        self.led.color = (0, 1, 0)

    def blauw(self):
        """Zet de LED op 100% blauw: (Rood=0, Groen=0, Blauw=1)."""
        self.led.color = (0, 0, 1)

    def uit(self):
        """Zet alle drie de kleuren helemaal uit."""
        self.led.off()

    def kleur_procent(self, rood, groen, blauw):
        """
        Stel zelf een kleur in met percentages van 0 tot 100.
        Voorbeeld: `kleur_procent(80, 30, 0)` maakt oranje (80% rood + 30% groen).
        Omdat `gpiozero` getallen tussen 0.0 en 1.0 verwacht, delen we door 100.
        """
        self.led.color = (rood / 100.0, groen / 100.0, blauw / 100.0)

    def knipper_rood(self):
        """
        Laat het rode licht vloeiend opkomen en weer zachtjes uitdoven (zoals een echt zwaailicht).

        💡 SLIMME TRUC (voor je verdediging):
        We gebruiken hier GEEN `time.sleep()`, omdat de hoofdapplicatie dan zou moeten wachten.
        In plaats daarvan kijken we naar de klok (`time.monotonic()`). Elke 2 seconden
        loopt de helderheid vloeiend van 0.0 -> 1.0 -> 0.0.
        """
        fase = time.monotonic() % 2.0
        helderheid = 1.0 - abs(fase - 1.0)
        self.led.color = (helderheid, 0, 0)

    def alarm(self, aantal=5, snelheid=0.2):
        """
        Laat de LED een vast aantal keer snel rood aan en uit knipperen.
        Handig als losse testfunctie (gebruikt `time.sleep`, dus wacht echt tijdens het knipperen).
        """
        for _ in range(aantal):
            self.led.color = (1, 0, 0)
            time.sleep(snelheid)

            self.uit()
            time.sleep(snelheid)

        self.uit()

    def close(self):
        """
        Zet de LED netjes uit en geef de GPIO-pinnen weer vrij als het programma stopt.
        """
        self.led.off()
        self.led.close()


# ==============================================================================
# LOSSE TEST: Wordt alleen uitgevoerd als je `python3 zwaailicht.py` typt
# ==============================================================================
if __name__ == "__main__":
    licht = Zwaailicht()

    try:
        print("Zwaailicht test gestart...")
        licht.alarm(aantal=10, snelheid=0.2)
        print("Test klaar.")

    finally:
        # `finally` zorgt dat de pinnen ALTIJD worden vrijgegeven, ook bij Ctrl+C
        licht.close()