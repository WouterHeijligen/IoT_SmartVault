import time
import board
import digitalio

# ==============================================================================
# BASIS LED KNIPPERLICHT (GPIO DIGITALE OUTPUT)
# ==============================================================================
# Concept & Elektronica:
# - Een LED (Light Emitting Diode) is een halfgeleider die stroom slechts in één
#   richting doorlaat (van Anode [+] naar Kathode [-]).
# - Voorschakelweerstand: Een GPIO pin van de Pi levert 3.3V. Zonder weerstand zou
#   er te veel stroom vloeien en brandt de LED of de Pi GPIO poort door (Wet van Ohm: I = U/R).
#   Een weerstand van 220 tot 330 ohm is ideaal.
# ==============================================================================

print("Hello blinky!")

# 1. Configureer GPIO 17 (fysieke pin 11 op de Pi header) als digitale output
led = digitalio.DigitalInOut(board.D17)
led.direction = digitalio.Direction.OUTPUT

try:
    # Oneindige lus om de LED afwisselend aan en uit te zetten
    while True:
        led.value = True   # Zet pin op HIGH (3.3V) -> stroom vloeit -> LED brandt
        time.sleep(0.5)    # Wacht 500 milliseconden (0.5s)
        
        led.value = False  # Zet pin op LOW (0V) -> geen stroom -> LED dooft
        time.sleep(0.5)    # Wacht 500 milliseconden (0.5s)

except KeyboardInterrupt:
    print("\nOnderbroken door gebruiker.")

finally:
    # Schakel de LED uit en geef de pin netjes vrij aan het Linux OS
    led.value = False
    led.deinit()
    print("GPIO 17 vrijgegeven. Einde programma.")
