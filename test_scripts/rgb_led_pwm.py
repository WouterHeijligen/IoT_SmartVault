#!/usr/bin/env python3
"""
RGB LED PWM Aansturing via gpiozero.RGBLED op Raspberry Pi 5

Rood:  GPIO 12
Groen: GPIO 13
Blauw: GPIO 26
Knop:  GPIO 4
"""

from gpiozero import Button, RGBLED

# 1. Drukknop op GPIO 4 met interne pull-up
button = Button(4, pull_up=True)

# 2. RGB LED
led = RGBLED(
    red=12,
    green=13,
    blue=26,
    pwm=True
)

# Kleurenvolgorde:
# RGBLED gebruikt waarden van 0.0 t/m 1.0
kleuren = [
    ("GROEN", (0.0, 0.5, 0.0)),
    ("ROOD",  (0.5, 0.0, 0.0)),
    ("BLAUW", (0.0, 0.0, 0.5)),
    ("WIT",   (0.5, 0.5, 0.5))
]


def main():
    huidige_kleur_index = 0

    # Startkleur instellen
    naam, kleur = kleuren[huidige_kleur_index]
    led.color = kleur

    print(f"Startkleur: {naam}")
    print("Druk op de knop om te wisselen van kleur.")
    print("Druk op CTRL+C om te stoppen.")

    try:
        while True:
            # Wacht op knopdruk
            button.wait_for_press()

            # Volgende kleur
            huidige_kleur_index = (
                huidige_kleur_index + 1
            ) % len(kleuren)

            naam, kleur = kleuren[huidige_kleur_index]

            # RGBLED direct de nieuwe kleur geven
            led.color = kleur

            print(f"Knop ingedrukt! Nieuwe kleur: {naam}")

            # Voorkomt meerdere triggers tijdens één knopdruk
            button.wait_for_release()

    except KeyboardInterrupt:
        print("\nAfsluiten...")

    finally:
        led.off()
        led.close()
        button.close()

        print("RGB LED uitgeschakeld.")
        print("Hardware netjes vrijgegeven.")

if __name__ == "__main__":
    main()