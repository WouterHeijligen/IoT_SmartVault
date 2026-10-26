import time
import board
import digitalio

# ==============================================================================
# DIGITALE INPUT MET INTERNE PULL-UP & KNIPPERENDE LED BIJ DRUKKEN
# ==============================================================================
# Concept:
# - Zelfde hardware-opstelling als input.py (Active Low schakelaar op GPIO 18, LED op GPIO 12).
# - Verschil in werking:
#   * In plaats van continu aan te blijven zolang de knop ingedrukt is, knippert de LED
#     snel achter elkaar (100 ms aan, 100 ms uit).
#   * Zodra de knop wordt losgelaten, gaat de LED direct uit.
# ==============================================================================

# 1. Pinnen initialiseren
pinLED = digitalio.DigitalInOut(board.D12)       # GPIO 12 (LED)
pinswitch = digitalio.DigitalInOut(board.D18)   # GPIO 18 (Knop)

pinLED.direction = digitalio.Direction.OUTPUT
pinswitch.direction = digitalio.Direction.INPUT
pinswitch.pull = digitalio.Pull.UP              # Interne pull-up: knop naar GND = Active Low

print("--- Knipperen bij Knopdruk Gestart ---")
print("Houd de knop ingedrukt om de LED te laten knipperen (Ctrl+C om af te sluiten)...")

try:
    while True:
        # Controleer of de knop is ingedrukt (not pinswitch.value == True bij 0V/GND)
        if not pinswitch.value:
            # Voer 1 knippercyclus uit
            pinLED.value = True       # LED aan
            time.sleep(0.1)           # 100 milliseconden wachten
            pinLED.value = False      # LED uit
            time.sleep(0.1)           # 100 milliseconden wachten
        else:
            # Knop is niet ingedrukt: zorg dat de LED gegarandeerd uit staat
            pinLED.value = False
            time.sleep(0.1)           # Korte pauze tegen onnodig polling CPU-verbruik

except KeyboardInterrupt:
    print("\nOnderbroken door gebruiker.")

finally:
    # Netjes opruimen van de hardware resources
    pinLED.value = False
    pinLED.deinit()
    pinswitch.deinit()
    print("GPIO resources netjes vrijgegeven.")
