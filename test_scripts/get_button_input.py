#!/usr/bin/env python3
"""
RGB LED kleurencirkel met 2-pins push button
Rood: GPIO 12 | Groen: GPIO 13 | Blauw: GPIO 26 | Knop: GPIO 4
"""

import time
from gpiozero import Button, PWMLED

# 1. Drukknop initialiseren op GPIO 4 (Active-Low)
button = Button(4, pull_up=True)

# 2. RGB LED pinnen (Rood, Groen, Blauw)
led_r = PWMLED(12)
led_g = PWMLED(13)
led_b = PWMLED(26)

def set_rgb(r: float, g: float, b: float):
    led_r.value = r
    led_g.value = g
    led_b.value = b

# Kleurencyclus: Groen -> Rood -> Blauw -> Wit
kleuren = [
    ("GROEN",  (0.0, 0.5, 0.0)),
    ("ROOD",   (0.5, 0.0, 0.0)),
    ("BLAUW",  (0.0, 0.0, 0.5)),
    ("WIT",    (0.5, 0.5, 0.5))
]

def main():
    huidige_kleur_index = 0
    
    # 1. Start gegarandeerd met GROEN
    naam, vals = kleuren[huidige_kleur_index]
    set_rgb(*vals)
    print(f"Systeem gestart. Startkleur: {naam}")
    print("Druk op de knop om naar de volgende kleur te gaan (CTRL+C om te stoppen)...")

    # Wacht even 0.5s bij het opstarten zodat eventuele contactdender genegeerd wordt
    time.sleep(0.5)

    try:
        while True:
            # Wacht tot de knop daadwerkelijk wordt ingedrukt
            button.wait_for_press()
            
            # Schakel direct door naar de volgende kleur
            huidige_kleur_index = (huidige_kleur_index + 1) % len(kleuren)
            naam, vals = kleuren[huidige_kleur_index]
            set_rgb(*vals)
            print(f"-> Knop ingedrukt! Nieuwe kleur: {naam}")
            
            # Wacht tot de gebruiker de knop weer loslaat + kleine ontpreltijd
            button.wait_for_release()
            time.sleep(0.15)

    except KeyboardInterrupt:
        print("\nProgramma gestopt.")
    finally:
        set_rgb(0.0, 0.0, 0.0)
        led_r.close()
        led_g.close()
        led_b.close()
        button.close()
        print("Hardware netjes afgesloten.")

if __name__ == "__main__":
    main()