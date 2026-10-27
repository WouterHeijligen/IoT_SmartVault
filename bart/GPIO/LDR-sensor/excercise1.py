import time
import board
import digitalio

# ==============================================================================
# LDR LICHTSENSOR (DIGITALE UITLEZING VIA SPANNINGSDELER)
# ==============================================================================
# Concept & Elektronica:
# - Een LDR (Light Dependent Resistor) verandert van weerstand afhankelijk van het licht:
#   * Veel licht  -> Lage weerstand (enkele honderden ohms)
#   * Donker      -> Hoge weerstand (enkele honderden kilo-ohms / mega-ohms)
# - Omdat een Raspberry Pi (RP1 controller) GEEN interne analoge ADC heeft, kan een
#   GPIO-pin alleen digitaal kijken: LOW (0V tot ~1.2V) of HIGH (~1.8V tot 3.3V).
# - We bouwen daarom een spanningsdeler (voltage divider) met een vaste weerstand (bijv. 1k tot 10k ohm):
#   * 3.3V -> LDR -> [Knooppunt naar GPIO 23] -> Weerstand -> GND
#   * In het licht vloeit de stroom gemakkelijk en stijgt de spanning op het knooppunt boven de drempel (HIGH).
#   * In het donker blokkeert de LDR de stroom en trekt de weerstand het knooppunt naar 0V (LOW).
# ==============================================================================

# Configureer GPIO 23 (fysieke pin 16 op de Pi header) als digitale ingang
ldr = digitalio.DigitalInOut(board.D23)
ldr.direction = digitalio.Direction.INPUT

print("--- LDR Test Actief ---")
print("Houd je vinger over de LDR om donker te simuleren (Ctrl+C om te stoppen)...")

try:
    # Oneindige meetlus
    while True:
        # ldr.value leest de logische status van de pin:
        # True  (HIGH / ~3.3V) = Voldoende licht op de sensor
        # False (LOW  / 0V)    = Te weinig licht (donker)
        if ldr.value:
            print("💡 LICHT gedetecteerd (GPIO 23 = HIGH)")
        else:
            print("🌙 DONKER gedetecteerd (GPIO 23 = LOW)")
        
        # Wacht 500 ms tussen controles om de CPU niet onnodig te belasten
        time.sleep(0.5)

except KeyboardInterrupt:
    # Vangt Ctrl+C af voor een nette exit
    print("\nProgramma wordt afgesloten...")

finally:
    # Resource management: deinit() geeft de GPIO-pin netjes vrij aan de Linux kernel.
    # Dit voorkomt dat pinnen geblokkeerd blijven voor volgende scripts.
    ldr.deinit()
    print("GPIO 23 vrijgegeven. Programma netjes beëindigd.")
