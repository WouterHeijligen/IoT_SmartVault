import time
import board
import digitalio

# ==============================================================================
# 28BYJ-48 STAPPENMOTOR - FULL STEP AANSTURING (LAB 3.2 - PRACTICE 8)
# ==============================================================================
# Concept & Elektronica:
# 1. Wat is 'Full Step' (2-fase excitatie)?
#    - Er worden steeds TWEE aangrenzende spoelen GELIJKTIJDIG bekrachtigd.
#    - Voordeel: Maximaal koppel (ongeveer 40% meer trekkracht dan Wave Drive)
#      omdat de rotor tussen twee bekrachtigde magnetische polen wordt getrokken.
#    - Nadeel: Dubbel zoveel stroomverbruik en de motor wordt warmer.
#
# 2. Hardware: 28BYJ-48 (5V unipolair met tandwielvertraging 1:64) via ULN2003
#    Darlington-driver. De Pi stuurt alleen logische signalen naar IN1..IN4.
# ==============================================================================

# 1. Pinnen configureren conform de bedrading naar de ULN2003 driver
IN1 = digitalio.DigitalInOut(board.D17)  # GPIO 17
IN1.direction = digitalio.Direction.OUTPUT

IN2 = digitalio.DigitalInOut(board.D27)  # GPIO 27
IN2.direction = digitalio.Direction.OUTPUT

IN3 = digitalio.DigitalInOut(board.D22)  # GPIO 22
IN3.direction = digitalio.Direction.OUTPUT

IN4 = digitalio.DigitalInOut(board.D23)  # GPIO 23
IN4.direction = digitalio.Direction.OUTPUT

# Bundel de pinnen in een lijst voor eenvoudige iteratie
pins = [IN1, IN2, IN3, IN4]

# 2. Full-Step matrix (2 spoelen gelijktijdig actief per stap):
# Let op: per rij staan exact twee pinnen op HIGH (1).
full_step_sequence = [
    [1, 1, 0, 0],  # Stap 1: Spoel 1 + Spoel 2 bekrachtigd
    [0, 1, 1, 0],  # Stap 2: Spoel 2 + Spoel 3 bekrachtigd
    [0, 0, 1, 1],  # Stap 3: Spoel 3 + Spoel 4 bekrachtigd
    [1, 0, 0, 1]   # Stap 4: Spoel 4 + Spoel 1 bekrachtigd
]

# Stapvertraging in seconden (10ms conform Lab 3.2):
# Bepaalt de rotatiesnelheid. Te laag (< 0.003s) kan leiden tot haperen of blokkeren.
delay = 0.01  

print("Motor gestart in Full Step modus (maximaal koppel). Druk op Ctrl+C om te stoppen.")

try:
    while True:
        # Itereer door de 4 stappen van de Full-Step sequentie
        for step in full_step_sequence:
            for i in range(4):
                pins[i].value = bool(step[i])
            # Mechanische overgangstijd per stap
            time.sleep(delay)

except KeyboardInterrupt:
    print("\nOnderbroken door gebruiker.")

finally:
    # BELANGRIJK: Schakel alle spoelen direct uit!
    # Omdat Full Step twee spoelen tegelijk bekrachtigt, trekt hij stilstaand
    # continu stroom als je dit niet opruimt.
    for pin in pins:
        pin.value = False
        pin.deinit()
    print("Spoelen uitgeschakeld en pinnen netjes vrijgegeven.")
