import time
import board
import digitalio

# ==============================================================================
# 28BYJ-48 STAPPENMOTOR - WAVE DRIVE AANSTURING (LAB 3.2 - PRACTICE 7)
# ==============================================================================
# Concept & Elektronica:
# 1. Waarom een ULN2003 Driver bordje?
#    - Een GPIO-pin van de Pi levert maximaal ~16mA bij 3.3V.
#    - De spoelen van de 28BYJ-48 motor hebben veel meer stroom nodig (~100-200mA) én
#      veroorzaken inductieve piekspanningen (tegen-EMK) bij het uitschakelen.
#    - De ULN2003 Darlington-transistorarray versterkt het signaal en beschermt de Pi
#      met ingebouwde vrijloopdiodes (flyback diodes).
#
# 2. Wat is 'Wave Drive' (1-fase excitatie)?
#    - Er wordt steeds SLECHTS ÉÉN spoel tegelijk bekrachtigd.
#    - Voordeel: Laagste stroomverbruik en de motor blijft koel.
#    - Nadeel: Lager koppel (trekkracht) dan Full-Step aansturing.
# ==============================================================================

# 1. Pinnen configureren naar de IN1-IN4 ingangen van het ULN2003 driverbordje
IN1 = digitalio.DigitalInOut(board.D17)  # GPIO 17
IN1.direction = digitalio.Direction.OUTPUT

IN2 = digitalio.DigitalInOut(board.D27)  # GPIO 27
IN2.direction = digitalio.Direction.OUTPUT

IN3 = digitalio.DigitalInOut(board.D22)  # GPIO 22
IN3.direction = digitalio.Direction.OUTPUT

IN4 = digitalio.DigitalInOut(board.D23)  # GPIO 23
IN4.direction = digitalio.Direction.OUTPUT

# Bundel de pinnen in een array zodat we er met een index [0 t/m 3] bij kunnen
pins = [IN1, IN2, IN3, IN4]

# 2. Wave Drive stappenmatrix:
# Telkens staat exact 1 pin op HIGH (1) en de rest op LOW (0).
# De rotor volgt het magnetische veld stap voor stap van spoel 1 naar 4.
wave_sequence = [
    [1, 0, 0, 0],  # Stap 1: Alleen spoel 1 bekrachtigd
    [0, 1, 0, 0],  # Stap 2: Alleen spoel 2 bekrachtigd
    [0, 0, 1, 0],  # Stap 3: Alleen spoel 3 bekrachtigd
    [0, 0, 0, 1]   # Stap 4: Alleen spoel 4 bekrachtigd
]

# Stapvertraging in seconden (10ms conform labomanual):
# - Kleiner (bijv. 0.005s) = motor draait sneller (tot het punt van stappenverlies)
# - Groter  (bijv. 1.0s)   = motor stapt traag en schokkerig zichtbaar door de stappen
delay = 0.01  

print("Motor gestart in Wave Drive modus. Druk op Ctrl+C om te stoppen.")

try:
    while True:
        # Loop door de 4 stappen van de sequentie
        for step in wave_sequence:
            # Zet de 4 fysieke pinnen overeenkomstig de rij in de matrix
            for i in range(4):
                pins[i].value = bool(step[i])
            # Geef de rotor mechanisch de tijd om fysiek naar de nieuwe positie te bewegen
            time.sleep(delay)

except KeyboardInterrupt:
    print("\nOnderbroken door gebruiker.")

finally:
    # CRUCIAAL BIJ STAPPENMOTOREN:
    # Als een script stopt terwijl een spoel nog op HIGH staat, blijft er continu
    # stroom vloeien. Hierdoor wordt de motor en driver gloeiend heet!
    # We zetten daarom expliciet alle pinnen op False en roepen deinit() aan.
    for pin in pins:
        pin.value = False
        pin.deinit()
    print("Spoelen uitgeschakeld en pinnen netjes vrijgegeven.")
