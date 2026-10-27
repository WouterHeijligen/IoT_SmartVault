#!/usr/bin/env python3
"""
RGB LED PWM Aansturing via gpiozero op Raspberry Pi 5
Rood: GPIO 12 | Groen: GPIO 13 | Blauw: GPIO 26 | Knop: GPIO 4
"""

import time
from gpiozero import Button, PWMLED

# 1. Drukknop op GPIO 4 (pull-up actief)
button = Button(4, pull_up=True)

# 2. RGB LED pinnen met software PWM (0.0 tot 1.0)
led_r = PWMLED(12)
led_g = PWMLED(13)
led_b = PWMLED(26)

def set_rgb(r: float, g: float, b: float):
    """Zet de PWM-intensiteit van elke kleur (0.0 = uit, 1.0 = vol aan)."""
    led_r.value = r
    led_g.value = g
    led_b.value = b

# Kleurenvolgorde: Groen -> Rood -> Blauw -> Wit (met 50% PWM-waarde)
kleuren = [
    ("GROEN",  (0.0, 0.5, 0.0)),
    ("ROOD",   (0.5, 0.0, 0.0)),
    ("BLAUW",  (0.0, 0.0, 0.5)),
    ("WIT",    (0.5, 0.5, 0.5))
]

def main():
    huidige_kleur_index = 0
    
    # Startkleur instellen
    naam, vals = kleuren[huidige_kleur_index]
    set_rgb(*vals)
    print(f"Startkleur: {naam}")
    print("Druk op de knop om te wisselen van kleur. (CTRL+C om te stoppen)")

    try:
        while True:
            # Wacht op knopdruk
            button.wait_for_press()
            
            # Schakel door naar volgende kleur
            huidige_kleur_index = (huidige_kleur_index + 1) % len(kleuren)
            naam, vals = kleuren[huidige_kleur_index]
            set_rgb(*vals)
            print(f"Knop ingedrukt! Nieuwe kleur: {naam}")
            
            # Wacht tot knop wordt losgelaten + debounce
            button.wait_for_release()
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nAfsluiten...")
    finally:
        set_rgb(0.0, 0.0, 0.0)
        led_r.close()
        led_g.close()
        led_b.close()
        button.close()
        print("Hardware netjes vrijgegeven.")

if __name__ == "__main__":
    main()