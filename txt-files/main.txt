#!/usr/bin/env python3
import threading
import time

import board
import digitalio

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
    FIRE_CONFIRM_READINGS,
    LUX_SABOTAGE_THRESHOLD,
    TEMP_FIRE_THRESHOLD_C,
    HYSTERESIS_10BIT,
    MAX_PIN_ATTEMPTS,
    WRONG_PIN_BLINK_S,
    PIN_LOCKOUT_S,
    LOITER_DISTANCE_CM,
    LOITER_ALARM_S,
    PERIMETER_STALE_S,
    TELEMETRY_INTERVAL_S,
    ALARM_PUSH_INTERVAL_S,
    MODE_CODES,
)

state = VaultState()

button = digitalio.DigitalInOut(board.D4)
button.switch_to_input(pull=digitalio.Pull.UP)

licht = Zwaailicht()
sensors = Sensors()
vault = VaultLock()
display = Display()
voice = VoiceRecognition()
notificaties = Notificaties()
notificaties.start_speaker_verbinding()

try:
    mqtt = MQTTClient()
except RuntimeError as e:
    print(f"[THINGSPEAK] {e} Telemetrie wordt alleen geprint.")
    mqtt = None


def thread_button():
    last_pressed = False

    while state.running:
        try:
            pressed = not button.value

            if pressed and not last_pressed:
                with state.lock:
                    state.last_activity = time.monotonic()

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


def thread_sensors_and_display():
    last_digit = 0
    fire_count = 0

    while state.running:
        try:
            raw_10bit = sensors.lees_potmeter_raw()
            temp_samples = sorted(sensors.lees_temperatuur() for _ in range(5))
            temp_c = temp_samples[2]  # Mediaan filtert pieken door motorstroom

            candidate_digit = min((raw_10bit * 10) // 1024, 9)

            # Hysteresis tegen verspringen op cijfergrenzen
            if candidate_digit != last_digit:
                border_raw = (max(candidate_digit, last_digit) * 1024) // 10
                if abs(raw_10bit - border_raw) >= HYSTERESIS_10BIT:
                    last_digit = candidate_digit

            lux = sensors.lees_licht()

            with state.lock:
                if last_digit != state.current_digit:
                    state.last_activity = time.monotonic()
                state.current_digit = last_digit
                state.temp_c = temp_c
                state.lux = lux

                # Negeren tijdens motorstroompieken
                if temp_c > TEMP_FIRE_THRESHOLD_C and not state.motor_busy:
                    fire_count += 1
                else:
                    fire_count = 0

                if fire_count >= FIRE_CONFIRM_READINGS and state.mode != "ALARM":
                    state.mode = "ALARM"
                    state.alarm_reason = f"BRAND! T={temp_c:.1f}C"

                if lux > LUX_SABOTAGE_THRESHOLD and state.mode not in ("UNLOCKED", "ALARM"):
                    print(f"[SABOTAGE] Licht gedetecteerd in gesloten kluis ({lux:.1f} lux)!")
                    state.mode = "ALARM"
                    state.alarm_reason = f"BRAAK! ({int(lux)} lx)"

                nu = time.monotonic()
                dichtbij = state.loitering_alert and (nu - state.perimeter_ts) < PERIMETER_STALE_S
                if not dichtbij or state.mode != "PIN_INPUT":
                    state.loiter_since = None
                else:
                    if state.loiter_since is None:
                        state.loiter_since = nu
                    if nu - max(state.loiter_since, state.last_activity) >= LOITER_ALARM_S:
                        print(f"[LOITER] Persoon > {LOITER_ALARM_S:.0f}s zonder actie voor de kluis!")
                        state.mode = "ALARM"
                        state.alarm_reason = "LOITER > 1 MIN"
                        state.loiter_since = None

                mode = state.mode
                digit = state.current_digit
                pin_so_far = list(state.entered_pin)
                loitering = state.loitering_alert
                afstand_cm = state.perimeter_cm if (time.monotonic() - state.perimeter_ts) < PERIMETER_STALE_S else None
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
                wachttijd_s=wachttijd_s,
                afstand_cm=afstand_cm
            )

        except Exception as e:
            print(f"[FOUT in Sensor/OLED Thread]: {e}")

        time.sleep(0.10)


def thread_actuators():
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

        # Motor buiten state.lock uitvoeren zodat UI/sensoren niet blokkeren
        if need_unlock_motion:
            licht.kleur_procent(0, 100, 0)
            with state.lock:
                state.motor_busy = True
            vault.open()
            with state.lock:
                state.lock_executed = False
                state.motor_busy = False

        if need_lock_motion:
            licht.kleur_procent(0, 0, 80)
            with state.lock:
                state.motor_busy = True
            vault.sluit()
            with state.lock:
                state.motor_busy = False

        if mode in ("PIN_INPUT", "LOCKOUT"):
            vault.stroomloos()
            with state.lock:
                foute_code = time.monotonic() < state.wrong_pin_until
            if foute_code:
                licht.knipper_rood()
            elif mode == "LOCKOUT":
                licht.kleur_procent(30, 0, 0)
            else:
                licht.kleur_procent(0, 0, 80)

        elif mode == "VOICE_2FA":
            licht.kleur_procent(80, 30, 0)

        elif mode == "UNLOCKED":
            licht.kleur_procent(0, 100, 0)

        elif mode == "ALARM":
            vault.stroomloos()
            licht.knipper_rood()

            if time.time() - last_siren_time > 4.0:
                notificaties.sirene()
                last_siren_time = time.time()

        if mode == "PIN_INPUT" and last_siren_time:
            notificaties.stop_sirene()
            last_siren_time = 0.0

        time.sleep(0.03)


def thread_cloud():
    last_push = 0.0
    last_alarm_push = None

    while state.running:
        with state.lock:
            mode = state.mode
            lux = state.lux
            temp_c = state.temp_c
            dist = state.perimeter_cm
            digit = state.current_digit
            reason = state.alarm_reason
            now = time.monotonic()
            should_alert = mode == "ALARM" and (
                last_alarm_push is None
                or now - last_alarm_push >= ALARM_PUSH_INTERVAL_S
            )
            if should_alert:
                state.alarm_notified = True

            lockout_alert = state.lockout_push_pending
            state.lockout_push_pending = False

        if lockout_alert:
            notificaties.stuur_push(
                f"SMART VAULT: {MAX_PIN_ATTEMPTS}x foute pincode. "
                f"Kluis {PIN_LOCKOUT_S} seconden geblokkeerd."
            )

        if should_alert:
            last_alarm_push = time.monotonic()
            notificaties.stuur_push(
                f"SMART VAULT ALARM: {reason} (Lux={lux:.1f}, Temp={temp_c:.1f}C)"
            )

        if time.time() - last_push >= TELEMETRY_INTERVAL_S:
            if mqtt is not None:
                mqtt.stuur_telemetrie(
                    lux, temp_c, dist, MODE_CODES.get(mode, 0), mode, digit
                )
            else:
                print(
                    f"[THINGSPEAK - Geen .env credentials] Lux={lux:.1f}, "
                    f"Temp={temp_c:.1f}C, Afstand={dist:.1f}cm, Mode={mode}, Cijfer={digit}"
                )
            last_push = time.time()

        time.sleep(0.5)


def thread_voice():
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
        state.perimeter_ts = time.monotonic()
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
        button.deinit()

        print("[SHUTDOWN] Voltooid.")


if __name__ == "__main__":
    main()
