import time
import board
import digitalio

# ==============================================================================
# 4 LEDS LOOPLICHT / RUNNING LIGHT (TIME-BY-TIME CHASER)
# ==============================================================================
# Concept & Werking:
# - In plaats van alle LEDs tegelijk aan te sturen, lopen we sequentieel door een
#   Python lijst (array) van LED-objecten.
# - Sequentie:
#   1. Zet huidige LED aan (value = True)
#   2. Wacht 200 ms (0.2s)
#   3. Zet huidige LED direct weer uit (value = False)
#   4. Ga door naar de volgende LED in de lijst.
# - Dit creëert een vloeiend looplicht-effect (chaser).
# ==============================================================================

print("Hello blinkynators!")

# Initialiseer de 4 pinnen als digitale uitgangen
led1 = digitalio.DigitalInOut(board.D1)
led1.direction = digitalio.Direction.OUTPUT

led2 = digitalio.DigitalInOut(board.D16)
led2.direction = digitalio.Direction.OUTPUT

led3 = digitalio.DigitalInOut(board.D12)
led3.direction = digitalio.Direction.OUTPUT

led4 = digitalio.DigitalInOut(board.D25)
led4.direction = digitalio.Direction.OUTPUT

# Bundel alle LED-objecten in één iterabele lijst
leds = [led1, led2, led3, led4]

try:
    while True:
        # Loop één voor één door de lijst van pinnen heen
        for led in leds:
            led.value = True      # Zet de huidige led aan
            time.sleep(0.2)       # Wacht 200 ms terwijl deze brandt
            led.value = False     # Doof de huidige led voordat de volgende start

except KeyboardInterrupt:
    print("\nOnderbroken door de gebruiker.")

finally:
    # Veilige cleanup: doof alle LEDs en deinit() de pinnen
    for led in leds:
        led.value = False
        led.deinit()
    print("Alle GPIO resources netjes afgesloten.")
