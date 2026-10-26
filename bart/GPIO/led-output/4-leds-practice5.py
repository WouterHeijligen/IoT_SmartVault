import time
import board
import digitalio

# ==============================================================================
# ALTERNEREND DUBBEL KNIPPERLICHT (LAB 3.1 - PRACTICE 5)
# ==============================================================================
# Concept & Logica:
# - Patroon: Wisselend knipperen tussen oneven en even LEDs:
#   * Fase A: LED1 + LED3 gaan tegelijk AAN (0.5s), daarna UIT (1.0s pauze)
#   * Fase B: LED2 + LED4 gaan tegelijk AAN (0.5s), daarna UIT (1.0s pauze)
# - Gebruikt interactieve invoer (input()) om het aantal herhalingen (cycli) te bepalen.
# - Sluit netjes af met .deinit() op alle gebruikte pinnen.
# ==============================================================================

print("Hello blinkynators!")

# Vraag de gebruiker interactief om een geheel getal
try:
    cycles = int(input("Hoeveel keer moet dit script runnen? "))
except ValueError:
    print("Ongeldige invoer! Voer een geheel getal in.")
    exit(1)

# Pinnen toewijzen als digitale outputs
led1 = digitalio.DigitalInOut(board.D12)
led1.direction = digitalio.Direction.OUTPUT

led2 = digitalio.DigitalInOut(board.D16)
led2.direction = digitalio.Direction.OUTPUT

led3 = digitalio.DigitalInOut(board.D1)
led3.direction = digitalio.Direction.OUTPUT

led4 = digitalio.DigitalInOut(board.D25)
led4.direction = digitalio.Direction.OUTPUT

# Bundel in een lijst voor collectief beheer
led_group = [led1, led2, led3, led4]

try:
    # Voer het alternerende patroon het gevraagde aantal keren uit
    for i in range(0, cycles):
        print(f"Cyclus {i + 1} van {cycles} bezig...")

        # --- FASE 1: LED 1 en LED 3 (Oneven paar) ---
        led1.value = True
        led3.value = True
        time.sleep(0.5)        # 0.5s branden
        led1.value = False
        led3.value = False
        time.sleep(1.0)        # 1.0s donker

        # --- FASE 2: LED 2 en LED 4 (Even paar) ---
        led2.value = True
        led4.value = True
        time.sleep(0.5)        # 0.5s branden
        led2.value = False
        led4.value = False
        time.sleep(1.0)        # 1.0s donker

except KeyboardInterrupt:
    print("\nVoortijdig gestopt door de gebruiker.")

finally:
    # CLEANUP: Geef alle 4 de GPIO-pinnen netjes terug aan de kernel
    for led in led_group:
        led.value = False
        led.deinit()
    print("Programma afgerond. Alle pinnen gedeïnitialiseerd.")
