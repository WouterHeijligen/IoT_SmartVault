#!/usr/bin/env python3
"""
Testprogramma: Relais Interlock + 28BYJ-48 Stappenmotor via Drukknop
Thomas More Geel - IoT Essentials Groepsproject
"""

import time
from gpiozero import Button, OutputDevice

# 1. Drukknop op GPIO 4 (Active-Low met pull-up)
button = Button(4, pull_up=True)

# 2. 5V Relais op GPIO 24 (Active-Low: active_high=False)
relais = OutputDevice(24, active_high=False, initial_value=False)

# 3. Vier spoelen van de stappenmotor via het ULN2003 driverbordje
coil_in1 = OutputDevice(17, initial_value=False)
coil_in2 = OutputDevice(27, initial_value=False)
coil_in3 = OutputDevice(22, initial_value=False)
coil_in4 = OutputDevice(23, initial_value=False)

coils = [coil_in1, coil_in2, coil_in3, coil_in4]

# Full-Step sequentie (2 spoelen tegelijk aan voor maximaal koppel)
# Conform IoT Essentials H3 Slide 52/53
FULL_STEP_SEQ = [
    [1, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 1],
    [1, 0, 0, 1]
]

STEP_DELAY = 0.010  # 10 ms delay per stap (cfr. cursus)
STEPS_HALF_ROTATION = 1024  # 256 full-steps = 180 graden draaien

def draai_stappenmotor(stappen: int, vooruit: bool = True):
    """Laat de stappenmotor een specifiek aantal stappen draaien."""
    seq = FULL_STEP_SEQ if vooruit else list(reversed(FULL_STEP_SEQ))
    
    for stap_idx in range(stappen):
        patroon = seq[stap_idx % 4]
        for coil, state in zip(coils, patroon):
            coil.value = state
        time.sleep(STEP_DELAY)
        
    # Zet na beweging alle spoelen direct uit tegen opwarming
    for coil in coils:
        coil.off()

def main():
    print("=======================================================")
    print(" SMART VAULT: RELAIS & STAPPENMOTOR TESTER")
    print(" Druk op de knop om de kluis-ontgrendeling te simuleren:")
    print(" 1. Relais klikt AAN (geeft 5V stroom aan de motor)")
    print(" 2. Motor draait 180° vooruit en 180° terug")
    print(" 3. Relais klikt UIT (motor blijft stroomloos)")
    print(" Druk op CTRL+C om te stoppen.")
    print("=======================================================")

    time.sleep(0.3)

    try:
        while True:
            # Wacht op knopdruk
            button.wait_for_press()
            print("\n>> Knop ingedrukt! Cyclus start...")

            # 1. Relais inschakelen
            relais.on()
            print("   [1/3] KLIK! Relais AAN -> Motor krijgt 5V voeding")
            time.sleep(0.25)  # Korte pauze om het relais mechanisch te laten sluiten

            # 2. Motor laten draaien
            print(f"   [2/3] Stappenmotor draait 180° VOORUIT ({STEPS_HALF_ROTATION} stappen)...")
            draai_stappenmotor(STEPS_HALF_ROTATION, vooruit=True)

            time.sleep(0.5)

            print(f"   [2/3] Stappenmotor draait 180° TERUG...")
            draai_stappenmotor(STEPS_HALF_ROTATION, vooruit=False)

            # 3. Relais weer uitschakelen
            relais.off()
            print("   [3/3] KLIK! Relais UIT -> Motor is weer fysiek stroomloos (Safety Interlock)")

            # Wacht tot de knop weer losgelaten is
            button.wait_for_release()
            time.sleep(0.2)
            print(">> Klaar voor de volgende test.")

    except KeyboardInterrupt:
        print("\nTestprogramma afgebroken door gebruiker.")
    finally:
        relais.off()
        for coil in coils:
            coil.off()
            coil.close()
        relais.close()
        button.close()
        print("Hardware netjes en veilig afgesloten.")

if __name__ == "__main__":
    main()