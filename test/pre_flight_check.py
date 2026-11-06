#!/usr/bin/env python3
"""
================================================================================
BESTAND: test/pre_flight_check.py
DOEL:    Snelle hardware-zelftest (30 seconden) vóórdat je de video-opname of demo doet!
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
Met dit script kun je vlak voor je presentatie of video-opname in één keer
controleren of alle draadjes en onderdelen op de Raspberry Pi 5 nog goed vastzitten:
1. Zijn alle Python-bibliotheken aanwezig?
2. Werkt de BH1750 lichtsensor via de I2C-bus?
3. Werken de draaiknop (potmeter) en LM35 temperatuursensor via de MCP3008 (SPI)?
4. Werkt het OLED-schermpje?
5. Doen alle drie de kleuren (Rood, Groen, Blauw) van de RGB-LED het?
6. Klikt het relais aan en draait de stappenmotor een klein stukje heen en terug?
7. Reageert de fysieke drukknop op GPIO 4?
"""

import time
import sys

print("=" * 65)
print("🔍 SMART VAULT — PRE-FLIGHT HARDWARE DIAGNOSE")
print("=" * 65)

# ------------------------------------------------------------------------------
# STAP 1: Controleer of alle Python-bestanden en bibliotheken ingeladen kunnen worden
# ------------------------------------------------------------------------------
print("\n[1/7] Python modules & Adafruit Blinka laden...")
try:
    import board
    import busio
    import digitalio
    from sensors import Sensors
    from display import Display
    from vault_lock import VaultLock
    from zwaailicht import Zwaailicht
    from notificaties import Notificaties
    print("  ✅ Alle modules succesvol geladen.")
except Exception as e:
    print(f"  ❌ Fout bij laden van modules: {e}")
    sys.exit(1)

# ------------------------------------------------------------------------------
# STAP 2: Test de digitale BH1750 Lichtsensor (via de I2C-kabel op GPIO 2 en 3)
# ------------------------------------------------------------------------------
print("\n[2/7] I2C Bus: BH1750 Lichtsensor (0x23) testen...")
try:
    sensors = Sensors()
    lux = sensors.lees_licht()
    print(f"  ✅ I2C communicatie OK. Huidige lichtmeting: {lux:.1f} Lux")
    if lux > 50.0:
        print("  ⚠️ Let op: Lichtsterkte is > 50 Lux! (Kluisdoos is open of staat in vol licht)")
    else:
        print("  ℹ️ Lichtsterkte is < 50 Lux (Kluisdoos is gesloten/donker).")
except Exception as e:
    print(f"  ❌ Fout bij I2C / BH1750: {e}")

# ------------------------------------------------------------------------------
# STAP 3: Test de analoge sensoren (Potmeter & LM35) via de MCP3008 ADC-chip (SPI)
# ------------------------------------------------------------------------------
print("\n[3/7] SPI0 Bus: MCP3008 ADC (Potmeter & LM35) testen...")
try:
    raw_pot = sensors.lees_potmeter_raw()
    # Reken de ruwe waarde (0..1023) om naar een kluiscijfer van 0 t/m 9
    digit = min((raw_pot * 10) // 1024, 9)
    temp_c = sensors.lees_temperatuur()
    print(f"  ✅ MCP3008 ADC communicatie OK.")
    print(f"     • Potmeter CH0: raw={raw_pot}/1023 -> Cijfer: [{digit}]")
    print(f"     • LM35 Temp CH1: {temp_c:.2f} °C")
except Exception as e:
    print(f"  ❌ Fout bij MCP3008 ADC: {e}")

# ------------------------------------------------------------------------------
# STAP 4: Test het SSD1306 OLED-schermpje (deelt dezelfde SPI-bus als de MCP3008)
# ------------------------------------------------------------------------------
print("\n[4/7] SSD1306 SPI OLED Display testen...")
try:
    disp = Display(spi=sensors.spi)
    disp.toon_tekst("SMART VAULT\nPre-Flight OK!", grootte=14)
    print("  ✅ OLED scherm aangestuurd ('SMART VAULT Pre-Flight OK!').")
    time.sleep(1.5)
except Exception as e:
    print(f"  ❌ Fout bij OLED display: {e}")

# ------------------------------------------------------------------------------
# STAP 5: Test de RGB-LED (Rood op GPIO 12, Groen op GPIO 13, Blauw op GPIO 26)
# ------------------------------------------------------------------------------
print("\n[5/7] RGB LED PWM kanalen testen...")
try:
    rgb = Zwaailicht()
    print("     • Rood (GPIO 12)...")
    rgb.rood()
    time.sleep(0.6)
    print("     • Groen (GPIO 13)...")
    rgb.groen()
    time.sleep(0.6)
    print("     • Blauw (GPIO 26)...")
    rgb.blauw()
    time.sleep(0.6)
    rgb.uit()
    print("  ✅ RGB LED cyclus succesvol afgerond.")
except Exception as e:
    print(f"  ❌ Fout bij RGB LED: {e}")

# ------------------------------------------------------------------------------
# STAP 6: Test het Relais (Active-Low op GPIO 24) en de 28BYJ-48 Stappenmotor
# ------------------------------------------------------------------------------
print("\n[6/7] Relais & 28BYJ-48 Stappenmotor testen...")
try:
    lock = VaultLock()
    print("     • Relais AAN schakelen (GPIO 24 = False)...")
    lock.relais.value = False
    time.sleep(0.4)
    print("     • Motor testpuls: 64 stappen vooruit...")
    lock._draai(stappen=64, vooruit=True)
    time.sleep(0.2)
    print("     • Motor testpuls: 64 stappen achteruit...")
    lock._draai(stappen=64, vooruit=False)
    time.sleep(0.2)
    print("     • Relais UIT schakelen (Active-Low: True)...")
    lock.relais.value = True
    lock.stroomloos()
    print("  ✅ Relais Safety Interlock en stappenmotor functioneren correct.")
except Exception as e:
    print(f"  ❌ Fout bij Relais of Stappenmotor: {e}")

# ------------------------------------------------------------------------------
# STAP 7: Test de fysieke drukknop op GPIO 4 (wacht maximaal 5 seconden op een druk)
# ------------------------------------------------------------------------------
print("\n[7/7] Fysieke drukknop (GPIO 4) testen...")
try:
    btn = digitalio.DigitalInOut(board.D4)
    btn.switch_to_input(pull=digitalio.Pull.UP)
    print("  👉 Druk NU binnen 5 seconden op de fysieke bevestigingsknop...")
    ingedrukt = False
    t_start = time.time()
    while time.time() - t_start < 5.0:
        # Door de Pull-Up weerstand wordt `btn.value` False zodra je de knop indrukt
        if not btn.value:
            ingedrukt = True
            break
        time.sleep(0.05)
    btn.deinit()
    if ingedrukt:
        print("  ✅ Knopdruk succesvol gedetecteerd (GPIO 4 actief-laag)!")
    else:
        print("  ⚠️ Geen knopdruk gedetecteerd (controleer bedrading indien je wel drukte).")
except Exception as e:
    print(f"  ❌ Fout bij knoptest: {e}")

# ------------------------------------------------------------------------------
# AFRONDING: Geef alle gebruikte GPIO-pinnen weer netjes vrij
# ------------------------------------------------------------------------------
try:
    disp.close()
    sensors.close()
    rgb.close()
    lock.close()
except Exception:
    pass

print("\n" + "=" * 65)
print("🏁 PRE-FLIGHT CHECK VOLTOOID!")
print("Als alle stappen hierboven groen zijn, is de hardware 100% gereed.")
print("=" * 65)
