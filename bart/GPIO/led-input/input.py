import time
import board
import digitalio

# ==============================================================================
# DIGITALE INPUT MET INTERNE PULL-UP & DIRECTE LED AANSTURING
# ==============================================================================
# Concept & Elektronica:
# - Knop / Switch: Verbonden tussen GPIO 18 en GND (Massa).
# - Waarom een Pull-Up weerstand?
#   Een loshangende GPIO-pin vangt elektromagnetische ruis op en gaat 'zweven' (floating),
#   waardoor de waarde willekeurig tussen True en False verspringt.
# - Interne Pull-Up (digitalio.Pull.UP):
#   De Raspberry Pi activeert intern een weerstand naar 3.3V.
#   * Knop NIET ingedrukt (open) -> Pin wordt omhoog getrokken naar 3.3V -> value is True.
#   * Knop WEL ingedrukt (gesloten) -> Pin wordt direct met GND verbonden -> value is False.
#   Dit heet 'Active Low' logica: actie vindt plaats wanneer het signaal Laag (False) is.
# ==============================================================================

# 1. Pinnen configureren
pinLED = digitalio.DigitalInOut(board.D12)       # GPIO 12 als output voor de LED
pinLED.direction = digitalio.Direction.OUTPUT

pinswitch = digitalio.DigitalInOut(board.D18)   # GPIO 18 als input voor de schakelaar
pinswitch.direction = digitalio.Direction.INPUT
pinswitch.pull = digitalio.Pull.UP              # Activeer de interne pull-up weerstand (Active Low)

print("--- Knop & LED Programma Gestart ---")
print("Druk op de knop om de LED te laten branden (Ctrl+C om af te sluiten)...")

try:
    while True:
        # Omdat de knop Active Low is, betekent 'not pinswitch.value' dat de knop is ingedrukt (False wordt True)
        if not pinswitch.value:
            pinLED.value = True   # Knop ingedrukt (0V / LOW) -> LED aan (3.3V / HIGH)
        else:
            pinLED.value = False  # Knop losgelaten (3.3V / HIGH) -> LED uit (0V / LOW)
            
        # Korte debounce/rusttijd om CPU-gebruik minimaal te houden
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nOnderbroken door gebruiker.")

finally:
    # Beide pinnen netjes vrijgeven bij het afsluiten
    pinLED.value = False
    pinLED.deinit()
    pinswitch.deinit()
    print("GPIO resources netjes vrijgegeven.")
