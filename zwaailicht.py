#!/usr/bin/env python3
"""
Zwaailicht (RGB-LED) van de Smart Vault.

Rol van dit bestand:
    Bevat ``Zwaailicht``, dat een RGB-LED aanstuurt voor statusfeedback:
    effen kleuren, een zacht pulserend blauw/rood zwaailicht (alarm/wachttijd)
    en een snel afwisselend alarm. Draait ook los als testprogramma.

Hardware en bibliotheken:
    ``gpiozero.RGBLED`` met ``pwm=True`` op GPIO 12 (rood), 13 (groen) en
    26 (blauw). PWM geeft per kleurkanaal een instelbare helderheid, nodig
    voor vloeiende overgangen en gedimde kleuren.

Threads en gedeelde toestand:
    Geen eigen threads of locks; raakt ``VaultState`` niet. De aanroeper
    (actuator-thread van main.py) roept de methoden aan; wordt één thread
    tegelijk gebruikt, dan is dat veilig.
"""

import math
import time
from gpiozero import RGBLED


class Zwaailicht:
    """
    RGB-zwaailicht voor statusweergave van de kluis.

    Doel:
        Visuele feedback: rood/blauw voor alarm of foute code, groen/uit voor
        normaal gedrag.

    Werking:
        Elke methode zet ``led.color`` als (rood, groen, blauw) met waarden
        0..1 (PWM-duty-cycle).

    Ontwerpkeuzes:
        * Fading PWM: zwaai() gebruikt een cosinus op de klok voor een zachte,
          vloeiende overgang in plaats van hard schakelen.
        * Tijdgebaseerd i.p.v. stapgebaseerd: de snelheid blijft gelijk,
          ongeacht hoe vaak de aanroeper de methode oproept.
    """

    def __init__(self, red_pin=12, green_pin=13, blue_pin=26):
        """
        Maakt de PWM-RGB-LED.

        Parameters:
            red_pin (int): GPIO-nummer voor rood (standaard 12, hardware-PWM-pin).
            green_pin (int): GPIO-nummer voor groen (standaard 13).
            blue_pin (int): GPIO-nummer voor blauw (standaard 26).

        Returns:
            None. Zet ``self.led``.

        Hardware/bibliotheken:
            gpiozero.RGBLED met pwm=True voor traploze helderheid.
        """
        self.led = RGBLED(
            red=red_pin,
            green=green_pin,
            blue=blue_pin,
            pwm=True
        )

    def rood(self):
        """Zet de LED op volledig rood (1, 0, 0); geen parameters, geen returnwaarde. Gebruikt gpiozero RGBLED-PWM; geen locks."""
        self.led.color = (1, 0, 0)

    def groen(self):
        """Zet de LED op volledig groen (0, 1, 0), bv. voor 'ontgrendeld'; geen parameters, geen returnwaarde. Gebruikt gpiozero RGBLED-PWM; geen locks."""
        self.led.color = (0, 1, 0)

    def blauw(self):
        """Zet de LED op volledig blauw (0, 0, 1); geen parameters, geen returnwaarde. Gebruikt gpiozero RGBLED-PWM; geen locks."""
        self.led.color = (0, 0, 1)

    def uit(self):
        """Zet de LED uit (alle kanalen 0); geen parameters, geen returnwaarde. Gebruikt gpiozero RGBLED; geen locks."""
        self.led.off()

    def kleur_procent(self, rood, groen, blauw):
        """
        Zet de kleur in procenten (0..100).

        Werking:
            Deelt elk kanaal door 100 naar de 0..1 die gpiozero verwacht, zodat
            helderheid per kleur traploos via PWM instelbaar is.

        Parameters:
            rood (float): roodintensiteit 0..100.
            groen (float): groenintensiteit 0..100.
            blauw (float): blauwintensiteit 0..100.

        Returns:
            None

        Threads/locks:
            Geen locks; één thread tegelijk aanroepen.
        """
        self.led.color = (rood / 100.0, groen / 100.0, blauw / 100.0)

    def zwaai(self, periode=2.0, helderheid=0.6):
        """
        Zwaailicht-effect: vloeit zacht van blauw naar rood en terug.

        Roep dit vaak aan (bv. elke 30 ms); de kleur volgt de klok,
        dus de snelheid hangt niet af van hoe vaak je het aanroept.

        Werking, stap voor stap:
            1. ``fase`` = positie in de cyclus (0..1) uit ``time.monotonic()``
               modulo ``periode``.
            2. ``mix`` = 0.5 - 0.5*cos(2*pi*fase): een vloeiende golf 0 -> 1 -> 0
               met zachte begin- en eindpunten (geen schokkerige overgang).
            3. Rood = mix x helderheid, blauw = (1 - mix) x helderheid, groen 0.

        Args:
            periode: seconden voor een volledige blauw -> rood -> blauw cyclus
            helderheid: maximale helderheid (0..1), lager = gedimd

        Returns:
            None

        Threads/locks:
            Geen locks; leest alleen de monotone klok. Niet blokkerend.

        Hardware/bibliotheken:
            gpiozero RGBLED met PWM voor het fadende effect; ``math`` voor de
            cosinus.
        """
        fase = (time.monotonic() % periode) / periode
        mix = 0.5 - 0.5 * math.cos(2 * math.pi * fase)

        self.led.color = (
            mix * helderheid,
            0,
            (1 - mix) * helderheid
        )

    def alarm(self, aantal=5, snelheid=0.2):
        """
        Wissel rood en blauw af als zwaailicht.

        Werking:
            Per herhaling: rood, wacht ``snelheid`` s, blauw, wacht
            ``snelheid`` s. Na afloop gaat de LED uit.

        Parameters:
            aantal (int): aantal rood/blauw-cycli (standaard 5).
            snelheid (float): seconden per kleur (standaard 0.2).

        Returns:
            None

        Threads/locks:
            Blokkeert de aanroepende thread (aantal x 2 x snelheid s); geen
            locks. Gebruik daarom alleen waar blokkeren acceptabel is, bv. in
            het testprogramma.

        Hardware/bibliotheken:
            gpiozero RGBLED; ``time.sleep`` voor de timing.
        """
        for _ in range(aantal):
            self.led.color = (1, 0, 0)
            time.sleep(snelheid)

            self.led.color = (0, 0, 1)
            time.sleep(snelheid)

        self.uit()

    def close(self):
        """
        Zet de LED uit en geef de GPIO-pinnen vrij.

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Aanroepen bij afsluiten, na de actuator-thread; geen locks.

        Hardware/bibliotheken:
            gpiozero RGBLED.close() geeft de PWM-pinnen terug aan het systeem.
        """
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