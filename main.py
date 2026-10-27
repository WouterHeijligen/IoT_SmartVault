#!/usr/bin/env python3
"""
SMART VAULT CONTROLLER (v1.3) - Raspberry Pi 5
Thomas More Geel - IoT Essentials Groepsproject
Architectuur: Multithreaded State Machine met SPI0 (MCP3008 + SSD1306 OLED),
              I2C (BH1750), Active-Low Relais Motor-Interlock,
              28BYJ-48 Full-Step Pusher, RGB LED & MQTT.

Modules:
    vault_state.py  -> configuratie en gedeelde status
    sensors.py      -> potmeter, LM35, BH1750
    display.py      -> SSD1306 OLED
    vault_lock.py   -> relais + stappenmotor
    zwaailicht.py   -> RGB LED
    mqtt_client.py  -> ThingSpeak telemetrie + lokale perimeter-subscriber
    notificaties.py -> ntfy push + sirene
    voice.py        -> spraakherkenning (Factor 2)
"""

import threading
import time

from gpiozero import Button

from zwaailicht import Zwaailicht
from sensors import Sensors
from mqtt_client import MQTTClient, PerimeterListener
from notificaties import Notificaties
from vault_lock import VaultLock
from display import Display
from voice import VoiceRecognition
from vault_state import (
    VaultState,
    SECRET_PIN,
    BYPASS_VOICE_2FA,
    VOICE_PASSPHRASE,
    VOICE_TIMEOUT_S,
    LUX_SABOTAGE_THRESHOLD,
    TEMP_FIRE_THRESHOLD_C,
    HYSTERESIS_10BIT,
    MAX_PIN_ATTEMPTS,
    WRONG_PIN_BLINK_S,
    PIN_LOCKOUT_S,
    LOITER_DISTANCE_CM,
    TELEMETRY_INTERVAL_S,
    MODE_CODES,
)

state = VaultState()

button = Button(4, pull_up=True)

licht = Zwaailicht()
sensors = Sensors()
vault = VaultLock()
display = Display(spi=sensors.spi)
voice = VoiceRecognition()
notificaties = Notificaties()

try:
    mqtt = MQTTClient()
except RuntimeError as e:
    print(f"[THINGSPEAK] {e} Telemetrie wordt alleen geprint.")
    mqtt = None


# ==============================================================================
# THREAD 1: DRUKKNOP (50 Hz)
# ==============================================================================
def thread_button():
    """Controleert op 50 Hz de bevestigingsknop met flankdetectie en debounce."""
    last_pressed = False

    while state.running:
        try:
            pressed = button.is_pressed

            if pressed and not last_pressed:
                with state.lock:
                    if state.mode == "PIN_INPUT":
                        state.entered_pin.append(state.current_digit)
                        print(f"[CIJFERSLOT] Cijfer bevestigd: {state.current_digit} -> Invoer: {state.entered_pin}")

                        if len(state.entered_pin) == 3:
                            if state.entered_pin == SECRET_PIN:
                                state.failed_attempts = 0
                                if BYPASS_VOICE_2FA:
                                    print("[AUTH] Pincode correct! (Voice 2FA bypass actief -> UNLOCKED)")
                                    state.mode = "UNLOCKED"
                                    state.unlock_executed = False
                                else:
                                    print("[AUTH] Factor 1 (PIN) correct! Wachten op Factor 2 (Vosk Spraak)...")
                                    state.mode = "VOICE_2FA"
                            else:
                                state.failed_attempts += 1
                                state.entered_pin = []
                                state.wrong_pin_until = time.monotonic() + WRONG_PIN_BLINK_S
                                retries_left = MAX_PIN_ATTEMPTS - state.failed_attempts
                                if retries_left > 0:
                                    print(f"[AUTH] Foute code! Nog {retries_left} pogingen over.")
                                else:
                                    print(f"[AUTH] Foute code! Geen pogingen meer. Wacht {PIN_LOCKOUT_S // 60} minuten.")
                                    state.mode = "LOCKOUT"
                                    state.lockout_until = time.monotonic() + PIN_LOCKOUT_S
                                    state.lockout_push_pending = True
                                    state.lockout_siren_pending = True

                    elif state.mode == "LOCKOUT":
                        print("[AUTH] Wachtperiode actief, invoer geblokkeerd.")

                    elif state.mode in ("UNLOCKED", "ALARM"):
                        if state.mode == "UNLOCKED":
                            state.lock_executed = False
                        print("[SYSTEEM] Reset naar vergrendelde modus (PIN_INPUT).")
                        state.mode = "PIN_INPUT"
                        state.entered_pin = []
                        state.failed_attempts = 0
                        state.alarm_reason = ""
                        state.alarm_notified = False
                        state.unlock_executed = False

                time.sleep(0.25)  # Debounce

            last_pressed = pressed

        except Exception as e:
            print(f"[FOUT in Knop Thread]: {e}")

        time.sleep(0.02)


# ==============================================================================
# THREAD 2: SENSOREN (BH1750, LM35, POTMETER) & OLED (10 Hz)
# ==============================================================================
def thread_sensors_and_display():
    """Leest op 10 Hz de sensoren uit en ververst het OLED-scherm."""
    last_digit = 0

    while state.running:
        try:
            with state.spi_lock:
                raw_10bit = sensors.lees_potmeter_raw()
                temp_c = sensors.lees_temperatuur()

            candidate_digit = min((raw_10bit * 10) // 1024, 9)

            if candidate_digit != last_digit:
                border_raw = (max(candidate_digit, last_digit) * 1024) // 10
                if abs(raw_10bit - border_raw) >= HYSTERESIS_10BIT:
                    last_digit = candidate_digit

            lux = sensors.lees_licht()

            with state.lock:
                state.current_digit = last_digit
                state.temp_c = temp_c
                state.lux = lux

                if temp_c > TEMP_FIRE_THRESHOLD_C and state.mode != "ALARM":
                    state.mode = "ALARM"
                    state.alarm_reason = f"BRAND! T={temp_c:.1f}C"

                if lux > LUX_SABOTAGE_THRESHOLD and state.mode not in ("UNLOCKED", "ALARM"):
                    print(f"[SABOTAGE] Licht gedetecteerd in gesloten kluis ({lux:.1f} lux)!")
                    state.mode = "ALARM"
                    state.alarm_reason = f"BRAAK! ({int(lux)} lx)"

                mode = state.mode
                digit = state.current_digit
                pin_so_far = list(state.entered_pin)
                loitering = state.loitering_alert
                reason = state.alarm_reason
                now = time.monotonic()
                if state.mode == "LOCKOUT" and now >= state.lockout_until:
                    print("[AUTH] Wachtperiode voorbij, opnieuw proberen mogelijk.")
                    state.mode = "PIN_INPUT"
                    state.failed_attempts = 0
                    mode = "PIN_INPUT"
                toon_fout = now < state.wrong_pin_until
                pogingen_over = MAX_PIN_ATTEMPTS - state.failed_attempts
                wachttijd_s = max(0, int(state.lockout_until - now))

            with state.spi_lock:
                display.toon_kluisscherm(
                    mode=mode,
                    lux=lux,
                    temp_c=temp_c,
                    digit=digit,
                    pin_so_far=pin_so_far,
                    loitering=loitering,
                    reason=reason,
                    voice_passphrase=VOICE_PASSPHRASE,
                    alarm_veilig=(temp_c <= TEMP_FIRE_THRESHOLD_C and lux <= LUX_SABOTAGE_THRESHOLD),
                    toon_fout=toon_fout,
                    pogingen_over=pogingen_over,
                    wachttijd_s=wachttijd_s
                )

        except Exception as e:
            print(f"[FOUT in Sensor/OLED Thread]: {e}")

        time.sleep(0.10)


# ==============================================================================
# THREAD 3: ACTUATOREN (RELAIS, STAPPENMOTOR, RGB LED & SIRENE)
# ==============================================================================
def thread_actuators():
    """Stuurt RGB LED, relais-interlock en stappenmotor aan."""
    last_siren_time = 0.0

    while state.running:
        with state.lock:
            mode = state.mode
            siren_once = state.lockout_siren_pending
            state.lockout_siren_pending = False
            need_unlock_motion = (mode == "UNLOCKED" and not state.unlock_executed)
            if need_unlock_motion:
                state.unlock_executed = True

            need_lock_motion = (mode == "PIN_INPUT" and not state.lock_executed)
            if need_lock_motion:
                state.lock_executed = True

        if siren_once:
            notificaties.sirene()

        if need_unlock_motion:
            licht.kleur_procent(0, 100, 0)
            vault.open()
            # Een alarm of reset tijdens het openen mag de sluitbeweging niet overslaan
            with state.lock:
                state.lock_executed = False

        if need_lock_motion:
            licht.kleur_procent(0, 0, 80)
            vault.sluit()

        if mode in ("PIN_INPUT", "LOCKOUT"):
            vault.stroomloos()
            with state.lock:
                foute_code = time.monotonic() < state.wrong_pin_until
            if foute_code:
                licht.zwaai()
            elif mode == "LOCKOUT":
                licht.kleur_procent(30, 0, 0)  # Zacht rood tijdens wachtperiode
            else:
                licht.kleur_procent(0, 0, 80)

        elif mode == "VOICE_2FA":
            licht.kleur_procent(80, 30, 0)

        elif mode == "UNLOCKED":
            licht.kleur_procent(0, 100, 0)

        elif mode == "ALARM":
            vault.stroomloos()
            licht.zwaai()

            if time.time() - last_siren_time > 4.0:
                notificaties.sirene()
                last_siren_time = time.time()

        time.sleep(0.03)  # Snel genoeg voor een vloeiend zwaailicht


# ==============================================================================
# THREAD 4: CLOUD (THINGSPEAK TELEMETRIE & NTFY PUSH)
# ==============================================================================
def thread_cloud():
    """ThingSpeak updates (elke 15 s) en directe ntfy-push bij alarm."""
    last_push = 0.0

    while state.running:
        with state.lock:
            mode = state.mode
            lux = state.lux
            temp_c = state.temp_c
            dist = state.perimeter_cm
            reason = state.alarm_reason
            should_alert = (mode == "ALARM" and not state.alarm_notified)
            if should_alert:
                state.alarm_notified = True
            lockout_alert = state.lockout_push_pending
            state.lockout_push_pending = False

        if lockout_alert:
            notificaties.stuur_push(
                f"SMART VAULT: {MAX_PIN_ATTEMPTS}x foute pincode. "
                f"Kluis {PIN_LOCKOUT_S // 60} minuten geblokkeerd."
            )

        if should_alert:
            notificaties.stuur_push(
                f"SMART VAULT ALARM: {reason} (Lux={lux:.1f}, Temp={temp_c:.1f}C)"
            )

        if time.time() - last_push >= TELEMETRY_INTERVAL_S:
            if mqtt is not None:
                mqtt.stuur_telemetrie(lux, temp_c, dist, MODE_CODES.get(mode, 0), mode)
            else:
                print(
                    f"[THINGSPEAK - Geen .env credentials] Lux={lux:.1f}, "
                    f"Temp={temp_c:.1f}C, Afstand={dist:.1f}cm, Mode={mode}"
                )
            last_push = time.time()

        time.sleep(0.5)


# ==============================================================================
# PERIMETER (PICO WH VIA LOKALE MQTT BROKER)
# ==============================================================================
# ==============================================================================
# THREAD 5: SPRAAKHERKENNING (FACTOR 2)
# ==============================================================================
def thread_voice():
    """Laadt het model direct bij het opstarten en luistert daarna zolang de kluis op Factor 2 wacht."""
    try:
        voice.laad()
    except Exception as e:
        print(f"[VOICE FOUT] Model laden mislukt: {e}")

    while state.running:
        with state.lock:
            wacht_op_spraak = (state.mode == "VOICE_2FA")

        if not wacht_op_spraak:
            time.sleep(0.2)
            continue

        print(f"[VOICE] Luisteren naar '{VOICE_PASSPHRASE}' ({VOICE_TIMEOUT_S:.0f}s)...")
        try:
            gehoord = voice.luister(
                timeout_s=VOICE_TIMEOUT_S,
                stop=lambda: not state.running or state.mode != "VOICE_2FA",
                doelzin=VOICE_PASSPHRASE.lower(),
            )
        except Exception as e:
            print(f"[VOICE FOUT] {e}")
            gehoord = ""
            time.sleep(1.0)

        with state.lock:
            if state.mode != "VOICE_2FA":
                continue

            if VOICE_PASSPHRASE.lower() in gehoord.lower():
                print("[AUTH] Factor 2 (spraak) correct! -> UNLOCKED")
                state.mode = "UNLOCKED"
                state.unlock_executed = False
            else:
                print("[AUTH] Passphrase niet herkend, terug naar PIN-invoer.")
                state.mode = "PIN_INPUT"
                state.entered_pin = []


def on_perimeter_afstand(dist_cm):
    with state.lock:
        state.perimeter_cm = dist_cm
        state.loitering_alert = (dist_cm < LOITER_DISTANCE_CM)


def main():

    print("=====================================================")
    print(" SMART VAULT CONTROLLER v1.3 OPSTARTEN...")
    print(f"    Geheime Pincode : {SECRET_PIN}")
    print(f"    Voice 2FA Bypass: {BYPASS_VOICE_2FA}")
    print("=====================================================")

    perimeter = PerimeterListener(on_perimeter_afstand)
    perimeter.connect()

    if mqtt is not None:
        try:
            mqtt.connect()
        except Exception as e:
            print(f"[THINGSPEAK WAARSCHUWING] Broker niet bereikbaar: {e}")

    threads = [
        threading.Thread(target=thread_button, name="Button", daemon=True),
        threading.Thread(target=thread_sensors_and_display, name="Sensors-OLED", daemon=True),
        threading.Thread(target=thread_actuators, name="Actuators", daemon=True),
        threading.Thread(target=thread_cloud, name="Cloud", daemon=True),
    ]
    if not BYPASS_VOICE_2FA:
        threads.append(threading.Thread(target=thread_voice, name="Voice", daemon=True))

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Bezig met veilig afsluiten en vrijgeven van GPIO-pinnen...")

    finally:
        state.running = False
        time.sleep(0.3)

        perimeter.close()
        if mqtt is not None:
            mqtt.close()

        vault.stroomloos()
        vault.close()
        licht.close()
        display.close()
        sensors.close()
        voice.close()
        button.close()

        print("[SHUTDOWN] Voltooid.")


if __name__ == "__main__":
    main()
