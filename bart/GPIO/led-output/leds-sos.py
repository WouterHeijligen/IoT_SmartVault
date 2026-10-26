import board
import digitalio
import time

# ==============================================================================
# PARAMETRISCH LED KNIPPEREN VIA DUTY CYCLE & PERIODE (LAB 3.1 - PRACTICE 7)
# ==============================================================================
# Concept & Berekening:
# - Periode (T): De totale tijdsduur van één volledige cyclus (Aan + Uit) in seconden.
#   Bijv. T = 0.5s betekent een frequentie van f = 1/T = 2 Hz (2 knipperingen per seconde).
# - Duty Cycle (%): Het percentage van de periode dat het signaal HIGH (actief) is.
#   * 50% duty cycle bij T = 0.5s -> 0.25s AAN, 0.25s UIT (symmetrisch).
#   * 75% duty cycle bij T = 0.5s -> 0.375s AAN, 0.125s UIT (langer fel dan donker).
# - Wiskundige uitsplitsing in code:
#   time_high = period * (duty_cycle / 100)
#   time_low  = period - time_high
# ==============================================================================

# Wijs de GPIO pin toe (hier GPIO 1 / board.D1)
LED_PIN = board.D1

# Initialiseer de pin als digitale uitgang
led = digitalio.DigitalInOut(LED_PIN)
led.direction = digitalio.Direction.OUTPUT

def blink(led_obj, number_blinks, period, duty_cycle):
    """
    Laat een LED een specifiek aantal keren knipperen met instelbare periode en duty cycle.

    :param led_obj:       Het DigitalInOut object van de LED
    :param number_blinks: Aantal gewenste knipperingen
    :param period:        Totale duur van 1 cyclus in seconden (AAN + UIT tijd)
    :param duty_cycle:    Percentage (0 t/m 100) dat de LED AAN moet staan
    """
    # 1. Bereken de absolute tijden in seconden voor HIGH en LOW
    time_high = period * (duty_cycle / 100)
    time_low = period - time_high
    
    # 2. Voer de knippercyclus uit
    for i in range(number_blinks):
        led_obj.value = True       # LED AAN
        time.sleep(time_high)      # Wacht de berekende tijd_high
        led_obj.value = False      # LED UIT
        time.sleep(time_low)       # Wacht de berekende tijd_low

try:
    print("Starten met knipperen: 20 keer, periode 0.5s, duty cycle 75%...")
    # 20 knipperingen, 0.5 seconde per knippering, 75% van de tijd AAN (0.375s AAN / 0.125s UIT)
    blink(led, 20, 0.5, 75)

except KeyboardInterrupt:
    print("\nVoortijdig gestopt door gebruiker.")

finally:
    # Proper resource beheer: geef de hardware pin altijd terug aan het OS
    led.value = False
    led.deinit()
    print("Pin vrijgegeven. Program executed.")
