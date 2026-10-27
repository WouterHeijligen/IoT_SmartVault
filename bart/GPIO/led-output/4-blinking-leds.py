import time
import board
import digitalio

# ==============================================================================
# 4 LEDS GELIJKTIJDIG KNIPPEREN (SYNTROON KNIPPERLICHT)
# ==============================================================================
# Concept:
# - Stuurt 4 verschillende GPIO pinnen tegelijk aan.
# - Let op pinselectie:
#   * GPIO 1  (board.D1)  = Pin 28 op de 40-pins header (I2C-0 ID_SC gereserveerd op Pi, maar bruikbaar als GPIO)
#   * GPIO 16 (board.D16) = Pin 36
#   * GPIO 12 (board.D12) = Pin 32
#   * GPIO 25 (board.D25) = Pin 22
# - Alle 4 de pinnen worden achtereenvolgens op True gezet binnen enkele microseconden,
#   waardoor het voor het menselijk oog lijkt alsof ze exact tegelijk aanspringen.
# ==============================================================================

print("Hello blinkynators!")

# Initialiseer de 4 pinnen als output
led1 = digitalio.DigitalInOut(board.D1)
led1.direction = digitalio.Direction.OUTPUT

led2 = digitalio.DigitalInOut(board.D16)
led2.direction = digitalio.Direction.OUTPUT

led3 = digitalio.DigitalInOut(board.D12)
led3.direction = digitalio.Direction.OUTPUT

led4 = digitalio.DigitalInOut(board.D25)
led4.direction = digitalio.Direction.OUTPUT

leds = [led1, led2, led3, led4]

try:
    while True:
        # Stap 1: Schakel alle 4 de LEDs in
        for led in leds:
            led.value = True
        time.sleep(0.5)  # Laat ze 0.5s gelijktijdig branden

        # Stap 2: Schakel alle 4 de LEDs uit
        for led in leds:
            led.value = False
        time.sleep(0.5)  # Laat ze 0.5s gelijktijdig uit staan

except KeyboardInterrupt:
    print("\nOnderbroken door gebruiker.")

finally:
    # Zorg dat alle LEDs uit zijn en de pinnen netjes worden vrijgegeven
    for led in leds:
        led.value = False
        led.deinit()
    print("Alle GPIO pinnen netjes vrijgegeven.")
