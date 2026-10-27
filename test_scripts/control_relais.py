#!/usr/bin/env python3
"""
Relais 1 schakelen via Push Button op Raspberry Pi 5
Thomas More Geel - IoT Essentials
Knop op GPIO 4 | Relais IN op GPIO 24 (Active-Low)
"""

import time
from gpiozero import Button, OutputDevice

# 1. Drukknop initialiseren op GPIO 4 (Active-Low met interne pull-up)
button = Button(4, pull_up=True)

# 2. Relais initialiseren op GPIO 24
# active_high=False zorgt ervoor dat:
#   .on()  -> pin wordt LOW (0V) -> Relais klikt AAN
#   .off() -> pin wordt HIGH (3.3V) -> Relais klikt UIT
# initial_value=False zorgt dat het relais bij het opstarten veilig UIT staat
relais = OutputDevice(24, active_high=False, initial_value=False)

def main():
    relais_aan = False
    print("-------------------------------------------------------")
    print(" Relais testprogramma gestart op Raspberry Pi 5")
    print(" Huidige status: RELAIS UIT (Contact open)")
    print(" Druk op de knop om het relais om te schakelen (toggle).")
    print(" Druk op CTRL+C om te stoppen.")
    print("-------------------------------------------------------")

    # Korte pauze tegen opstartdender
    time.sleep(0.3)

    try:
        while True:
            # Wacht tot de knop wordt ingedrukt
            button.wait_for_press()

            # Wissel de status om (toggle)
            relais_aan = not relais_aan

            if relais_aan:
                relais.on()
                print(">> KLIK! Relais 1 ingeschakeld (AAN) -> 5V vrijgegeven op NO-contact")
            else:
                relais.off()
                print(">> KLIK! Relais 1 uitgeschakeld (UIT) -> Stroom onderbroken")

            # Wacht tot de knop weer losgelaten wordt + ontpreltijd
            button.wait_for_release()
            time.sleep(0.15)

    except KeyboardInterrupt:
        print("\nProgramma afgebroken door gebruiker.")
    finally:
        # Zorg dat het relais gegarandeerd stroomloos achterblijft
        relais.off()
        relais.close()
        button.close()
        print("Relais veilig uitgeschakeld en hardware vrijgegeven.")

if __name__ == "__main__":
    main()