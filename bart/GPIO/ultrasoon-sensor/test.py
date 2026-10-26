import time
import board
import digitalio

# ==============================================================================
# HC-SR04 ULTRASONE AFSTANDSSENSOR (TIME-OF-FLIGHT AKOESTIEK)
# ==============================================================================
# Concept & Elektronica:
# 1. Hoe werkt het?
#    - De Pi stuurt een korte puls van 10 µs naar de TRIG-pin.
#    - De sensor vuurt automatisch een 8-cycli sonische burst af op 40 kHz.
#    - De sensor zet de ECHO-pin op HIGH zolang de geluidsgolf onderweg is.
#    - Zodra de weerkaatste echo terugkeert bij de ontvanger, springt ECHO weer op LOW.
#
# 2. KRITIEKE HARDWARE WAARSCHUWING (5V vs 3.3V):
#    - De HC-SR04 vereist 5V voeding om krachtig ultrasoon geluid uit te zenden.
#    - Hierdoor is het retoursignaal op de ECHO-pin ook 5V!
#    - Raspberry Pi GPIO-pinnen (RP1 controller) mogen NOOIT meer dan 3.3V ontvangen.
#    - Sluit daarom ALTIJD een spanningsdeler aan tussen ECHO en de Pi GPIO pin
#      (bijv. 1kΩ en 2kΩ, of 2x 1kΩ voor 2.5V) om je Pi te beschermen tegen doorbranden!
#
# 3. Wiskunde van de Afstandsberekening:
#    - Geluidssnelheid in droge lucht bij 20°C: v = 343 m/s = 34.300 cm/s.
#    - Het geluid legt de afstand tweemaal af (heen naar het object én terug).
#    - Afstand = (Tijd * 34.300 cm/s) / 2 = Tijd * 17.150 cm/s.
# ==============================================================================

# 1. Pinnen configureren
# TRIG = Output (Pi geeft het startsein)
# ECHO = Input  (Pi luistert naar de weerkaatsing via de spanningsdeler)
TRIG_PIN = board.D24
ECHO_PIN = board.D25

trig = digitalio.DigitalInOut(TRIG_PIN)
trig.direction = digitalio.Direction.OUTPUT

echo = digitalio.DigitalInOut(ECHO_PIN)
echo.direction = digitalio.Direction.INPUT

# Begin met een stabiele, lage trigger-lijn
trig.value = False
time.sleep(0.1)


def meet_afstand():
    """
    Vuurt een ultrasone burst af en berekent de afstand in centimeters
    op basis van Time-of-Flight (vluchttijd).
    """
    # STAP 1: Stuur een triggerpuls van exact 10 microseconden (10 µs)
    trig.value = True
    time.sleep(0.00001)  # 0.000010s = 10 µs
    trig.value = False

    # STAP 2: Wacht tot de sensor het geluid uitzendt (ECHO springt van LOW naar HIGH)
    # Noodrem/Timeout van 50ms voorkomt dat het script oneindig blijft hangen als de sensor mist
    timeout_start = time.time() + 0.05
    while not echo.value:
        if time.time() > timeout_start:
            return None  # Timeout: geen startpuls ontvangen

    # We gebruiken time.perf_counter() omdat dit een monotoon tikkende microseconde-klok is
    start_tijd = time.perf_counter()

    # STAP 3: Wacht tot de echo terugkaatst (ECHO springt weer terug van HIGH naar LOW)
    timeout_echo = time.time() + 0.05
    while echo.value:
        if time.time() > timeout_echo:
            return None  # Timeout: object buiten maximaal meetbereik (~4 meter)
            
    eind_tijd = time.perf_counter()

    # STAP 4: Berekening op basis van de vluchttijd
    vluchttijd = eind_tijd - start_tijd  # Totale reistijd in seconden (heen en weer)
    
    # Afstand = (vluchttijd * 34300 cm/s) / 2
    afstand_cm = vluchttijd * 17150

    return afstand_cm


# ==============================================================================
# HOOFDPROGRAMMA
# ==============================================================================
print("--- HC-SR04 Ultrasone Afstandsmeter Gestart ---")
print("Metingen lopen elke 500 ms. Druk op Ctrl+C om te stoppen...\n")

try:
    while True:
        afstand = meet_afstand()
        
        if afstand is not None:
            print(f"Afstand: {afstand:.1f} cm")
        else:
            print("Meting mislukt (geen echo of buiten bereik > 400 cm)")
            
        time.sleep(0.5)  # Meet 2 keer per seconde

except KeyboardInterrupt:
    print("\nProgramma gestopt door gebruiker.")

finally:
    # Altijd netjes pinnen vrijgeven aan de Linux kernel
    trig.value = False
    trig.deinit()
    echo.deinit()
    print("Pinnen netjes vrijgegeven.")
