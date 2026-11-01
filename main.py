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

Rol van dit bestand in de architectuur
--------------------------------------
main.py is het centrale opstartpunt en de "orchestrator". Het bestand:

1. Maakt op moduleniveau één gedeeld ``VaultState``-object (``state``) en alle
   hardware-/service-objecten aan (knop, zwaailicht, sensoren, kluisslot,
   display, spraak, notificaties, MQTT).
2. Definieert vijf worker-threads die elk één verantwoordelijkheid hebben:
   knop (50 Hz), sensoren + OLED (10 Hz), actuatoren (~33 Hz), cloud (2 Hz,
   telemetrie elke 15 s) en spraakherkenning (Factor 2).
3. Bevat de state machine-logica: modi PIN_INPUT -> VOICE_2FA -> UNLOCKED,
   plus ALARM en LOCKOUT. De modus staat in ``state.mode``.
4. Start alles in ``main()`` en ruimt bij afsluiten netjes de hardware op.

Threading-model en locks
------------------------
- ``state.lock``     beschermt alle velden van ``VaultState`` (mode, pin,
                     sensorwaarden, vlaggen). Houd deze lock KORT: nooit tijdens
                     trage I/O (motor, netwerk, SPI, spraak).
- ``state.spi_lock`` serialiseert toegang tot de gedeelde SPI0-bus (MCP3008-ADC
                     en SSD1306-OLED gebruiken dezelfde bus). Wordt nooit
                     tegelijk met ``state.lock`` vastgehouden om deadlocks te
                     vermijden.
- Eenmalige acties (motor open/dicht, push, sirene) worden met vlaggen in de
  state ("unlock_executed", "alarm_notified", ...) aangevraagd onder de lock en
  daarna buiten de lock uitgevoerd, zodat ze precies één keer gebeuren.
- Alle threads zijn daemon-threads en stoppen zodra ``state.running`` False is.
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
notificaties.start_speaker_verbinding()

try:
    mqtt = MQTTClient()
except RuntimeError as e:
    print(f"[THINGSPEAK] {e} Telemetrie wordt alleen geprint.")
    mqtt = None


# ==============================================================================
# THREAD 1: DRUKKNOP (50 Hz)
# ==============================================================================
def thread_button():
    """Thread 1: verwerkt op 50 Hz de bevestigingsknop (GPIO 4) en de PIN-logica.

    Doel:
        Elke druk op de knop bevestigt het cijfer dat via de potmeter is
        gekozen (Factor 1) of stuurt de kluis terug naar de vergrendelde modus.

    Werking (stap voor stap):
        1. Lees ``button.is_pressed`` (gpiozero, pull-up: ingedrukt = actief).
        2. Flankdetectie: alleen de overgang losgelaten -> ingedrukt telt, zodat
           vasthouden niet meerdere cijfers invoert.
        3. Onder ``state.lock`` wordt afhankelijk van ``state.mode`` gehandeld:
           - PIN_INPUT: voeg ``current_digit`` toe aan ``entered_pin``. Bij 3
             cijfers: vergelijk met SECRET_PIN. Goed -> ``failed_attempts`` = 0
             en modus VOICE_2FA (of direct UNLOCKED bij BYPASS_VOICE_2FA).
             Fout -> teller +1, pin leeg, ``wrong_pin_until`` zet de
             "foute code"-weergave/zwaailicht aan; bij MAX_PIN_ATTEMPTS volgt
             modus LOCKOUT met ``lockout_until`` en de vlaggen voor push en
             sirene.
           - LOCKOUT: invoer wordt genegeerd.
           - UNLOCKED/ALARM: reset naar PIN_INPUT; bij UNLOCKED wordt
             ``lock_executed`` False gezet zodat de motor de kluis weer sluit.
        4. ``time.sleep(0.25)`` na een druk is de software-debounce; daarna
           ``time.sleep(0.02)`` per lus geeft de 50 Hz polling.

    Parameters: geen.
    Retourwaarde: geen (loopt tot ``state.running`` False wordt).

    Gedeelde state / threads:
        Schrijft last_activity, entered_pin, failed_attempts, mode,
        wrong_pin_until, lockout_*, alarm_*, unlock_executed, lock_executed
        onder ``state.lock``. Wordt gelezen door de sensor-, actuator- en
        cloud-thread. Geen SPI-gebruik.

    Hardware/bibliotheek:
        gpiozero.Button met interne pull-up (knop schakelt naar GND).

    Ontwerpkeuzes:
        De debounce-sleep gebeurt buiten de lock zodat andere threads niet
        worden geblokkeerd. Fouten worden afgevangen zodat de thread blijft
        draaien.
    """
    last_pressed = False

    while state.running:
        try:
            pressed = button.is_pressed

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


# ==============================================================================
# THREAD 2: SENSOREN (BH1750, LM35, POTMETER) & OLED (10 Hz)
# ==============================================================================
def thread_sensors_and_display():
    """Thread 2: leest op 10 Hz de sensoren, bewaakt alarmen en ververst het OLED.

    Doel:
        Meetwaarden verzamelen (potmeter, LM35-temperatuur, BH1750-licht),
        daaruit het gekozen cijfer afleiden, alarmcondities detecteren
        (brand, sabotage, loitering), de LOCKOUT laten aflopen en het
        scherm bijwerken.

    Werking (stap voor stap):
        1. Onder ``state.spi_lock``: lees de potmeter (MCP3008, 10 bit) en 5x de
           LM35; de MEDIAAN van de 5 samples wordt gebruikt omdat de
           stappenmotor stroompieken veroorzaakt die een gemiddelde zouden
           vertekenen.
        2. Zet de ruwe waarde om naar cijfer 0-9 (``raw*10//1024``, max 9).
        3. Hysteresis: een nieuw cijfer wordt pas overgenomen als de waarde
           minstens HYSTERESIS_10BIT voorbij de grens tussen twee cijfers ligt.
           Dit voorkomt flikkeren door ruis rond een grens.
        4. Lees de lichtsensor (I2C, geen SPI-lock nodig).
        5. Onder ``state.lock``: update current_digit/temp_c/lux en
           last_activity bij een draai. Brand: ``fire_count`` telt opeenvolgende
           metingen boven TEMP_FIRE_THRESHOLD_C (genegeerd terwijl
           ``motor_busy``) en bij FIRE_CONFIRM_READINGS volgt ALARM.
           Sabotage: lux boven LUX_SABOTAGE_THRESHOLD in een gesloten kluis
           (niet UNLOCKED/ALARM) -> ALARM. Loitering: perimeterafstand is
           recent (niet ouder dan PERIMETER_STALE_S) en dichtbij, modus
           PIN_INPUT, en geen activiteit gedurende LOITER_ALARM_S -> ALARM.
           Verlopen LOCKOUT -> terug naar PIN_INPUT.
        6. Maak een snapshot van de benodigde waarden (kopie van de pin) zodat
           de lock vrijkomt vóór het trage tekenen.
        7. Onder ``state.spi_lock``: ``display.toon_kluisscherm(...)``.

    Parameters: geen.
    Retourwaarde: geen (loopt tot ``state.running`` False wordt).

    Gedeelde state / threads:
        Leest en schrijft veel velden van VaultState onder ``state.lock``;
        gebruikt ``state.spi_lock`` rond ADC en OLED (zelfde SPI0-bus). De twee
        locks worden nooit genest gehouden.

    Hardware/bibliotheek:
        MCP3008 (SPI0), LM35 via ADC, BH1750 (I2C), SSD1306 OLED (SPI0).

    Ontwerpkeuzes:
        Mediaanfilter, hysteresis, bevestigingsteller voor brand en een
        verouderingsgrens voor perimeterdata (Pico offline = negeren).
    """
    last_digit = 0
    fire_count = 0

    while state.running:
        try:
            with state.spi_lock:
                raw_10bit = sensors.lees_potmeter_raw()
                temp_samples = sorted(sensors.lees_temperatuur() for _ in range(5))
                temp_c = temp_samples[2]  # Mediaan filtert pieken door motorstroom
                # Zonder OLED-CS verschijnen ADC-transacties kort op het scherm.
                display.refresh()

            candidate_digit = min((raw_10bit * 10) // 1024, 9)

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

                # Tijdens de motorbeweging is de voeding onstabiel: negeer en eis ~1s aanhoudende overschrijding
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

                # Loitering: iemand staat te lang voor de kluis zonder de draaiknop of knop te gebruiken
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
                    wachttijd_s=wachttijd_s,
                    afstand_cm=afstand_cm
                )

        except Exception as e:
            print(f"[FOUT in Sensor/OLED Thread]: {e}")

        time.sleep(0.10)


# ==============================================================================
# THREAD 3: ACTUATOREN (RELAIS, STAPPENMOTOR, RGB LED & SIRENE)
# ==============================================================================
def thread_actuators():
    """Thread 3: stuurt RGB-LED, relais-interlock, stappenmotor en sirene aan.

    Doel:
        De fysieke uitgangen laten volgen op ``state.mode``.

    Werking (stap voor stap):
        1. Onder ``state.lock``: kopieer de modus, haal de eenmalige
           sirene-aanvraag op (en wis die) en bepaal of een open- of
           sluitbeweging nodig is via ``unlock_executed``/``lock_executed``.
           De vlag wordt meteen gezet zodat de beweging slechts 1x start.
        2. Buiten de lock (trage acties): lockout-sirene afspelen; bij
           ontgrendelen groen licht, ``motor_busy`` aan, ``vault.open()``
           (relais aan + 28BYJ-48 draait), daarna ``motor_busy`` uit;
           bij vergrendelen blauw licht en ``vault.sluit()``.
        3. Per modus: PIN_INPUT/LOCKOUT -> ``vault.stroomloos()`` (relais uit),
           zwaailicht bij foute code, zacht rood in LOCKOUT, anders blauw.
           VOICE_2FA -> oranje. UNLOCKED -> groen. ALARM -> stroomloos,
           zwaailicht en elke 4 s de sirene.
        4. Terug in PIN_INPUT na een alarm: sirene stoppen.
        5. Slaap 30 ms tussen updates.

    Parameters: geen.
    Retourwaarde: geen (loopt tot ``state.running`` False wordt).

    Gedeelde state / threads:
        Leest mode, wrong_pin_until; schrijft unlock_executed, lock_executed,
        motor_busy, lockout_siren_pending onder ``state.lock``. Geen SPI.
        ``motor_busy`` laat de sensor-thread voedingsstoringen negeren.

    Hardware/bibliotheek:
        VaultLock (active-low relais als motor-interlock: de motor krijgt
        alleen stroom tijdens een beweging, anders is hij stroomloos),
        Zwaailicht (RGB LED), Notificaties (sirene).

    Ontwerpkeuzes:
        Na het openen wordt ``lock_executed`` weer False gezet, zodat een alarm
        of reset tijdens de beweging de sluitbeweging niet overslaat. Het
        langzame motorwerk gebeurt nooit onder de lock.
    """
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
            with state.lock:
                state.motor_busy = True
            vault.open()
            # Een alarm of reset tijdens het openen mag de sluitbeweging niet overslaan
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
                licht.kleur_procent(30, 0, 0)  # Zacht rood tijdens wachtperiode
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


# ==============================================================================
# THREAD 4: CLOUD (THINGSPEAK TELEMETRIE & NTFY PUSH)
# ==============================================================================
def thread_cloud():
    """Thread 4: stuurt ThingSpeak-telemetrie (elke 15 s) en ntfy-pushberichten.

    Doel:
        Cloudcommunicatie loskoppelen van de realtime threads, zodat netwerk-
        vertraging de besturing niet blokkeert.

    Werking (stap voor stap):
        1. Onder ``state.lock``: snapshot van mode, lux, temp_c, afstand en
           alarmreden. Bij ALARM zonder ``alarm_notified`` wordt die vlag gezet
           (push slechts 1x per alarm); ``lockout_push_pending`` wordt gelezen
           en gewist.
        2. Buiten de lock: push bij lockout en/of alarm via ``notificaties``.
        3. Elke TELEMETRY_INTERVAL_S (ThingSpeak-limiet 15 s): ``mqtt.stuur_telemetrie``
           of, zonder credentials (``mqtt`` is None), alleen printen.
        4. Slaap 0,5 s.

    Parameters: geen.
    Retourwaarde: geen (loopt tot ``state.running`` False wordt).

    Gedeelde state / threads:
        Leest mode/lux/temp_c/perimeter_cm/alarm_reason, schrijft alarm_notified
        en lockout_push_pending onder ``state.lock``. Geen SPI.

    Hardware/bibliotheek:
        paho-mqtt via MQTTClient (ThingSpeak), ntfy via Notificaties.

    Ontwerpkeuzes:
        Eénmalige push-vlaggen; MODE_CODES vertaalt de modus naar een getal
        voor ThingSpeak.
    """
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
    """Thread 5: spraakherkenning voor Factor 2 (alleen gestart zonder bypass).

    Doel:
        Na een correcte PIN moet de gebruiker de geheime passphrase uitspreken.

    Werking (stap voor stap):
        1. Laad direct het (zware) Vosk-model zodat de eerste poging snel is.
        2. Poll elke 0,2 s of ``state.mode == "VOICE_2FA"``.
        3. Zo ja: ``voice.luister`` met timeout VOICE_TIMEOUT_S. De ``stop``-
           callback breekt het luisteren af bij afsluiten of moduswissel
           (bv. alarm of knop-reset). Fouten geven een lege tekst.
        4. Onder ``state.lock``: als de modus nog VOICE_2FA is en de passphrase
           in de herkende tekst zit -> UNLOCKED (``unlock_executed`` False),
           anders terug naar PIN_INPUT met lege pin.

    Parameters: geen.
    Retourwaarde: geen (loopt tot ``state.running`` False wordt).

    Gedeelde state / threads:
        Leest/schrijft mode, entered_pin, unlock_executed onder ``state.lock``;
        de ``stop``-lambda leest state zonder lock (enkel lezen van een
        string/bool). Het luisteren zelf gebeurt buiten de lock.

    Hardware/bibliotheek:
        USB-microfoon + Vosk via VoiceRecognition.

    Ontwerpkeuzes:
        De modus wordt opnieuw gecontroleerd na het luisteren, zodat een
        tussentijdse alarm/reset niet wordt overschreven.
    """
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
    """Callback voor nieuwe afstandsmetingen van de Pico WH (perimetersensor).

    Doel:
        Bewaart de laatste afstand en bepaalt of er iemand dichtbij staat.

    Werking:
        Wordt aangeroepen vanuit de MQTT-netwerkthread van ``PerimeterListener``.
        Onder ``state.lock`` worden ``perimeter_cm``, ``perimeter_ts``
        (monotonic tijdstip, voor veroudering) en ``loitering_alert``
        (afstand < LOITER_DISTANCE_CM) gezet. De sensor-thread beslist
        daarna of dit tot een loiter-alarm leidt.

    Parameters:
        dist_cm (float): gemeten afstand in centimeter.

    Retourwaarde: geen.

    Gedeelde state: schrijft perimeter_cm, perimeter_ts, loitering_alert
    onder ``state.lock``. Houd deze callback kort (blokkeert MQTT-thread).
    """
    with state.lock:
        state.perimeter_cm = dist_cm
        state.perimeter_ts = time.monotonic()
        state.loitering_alert = (dist_cm < LOITER_DISTANCE_CM)


def main():
    """Startpunt: verbindt MQTT, start alle threads en ruimt netjes op.

    Doel:
        Het hele systeem opstarten en bij Ctrl+C of afsluiten alle hardware
        veilig vrijgeven.

    Werking (stap voor stap):
        1. Toon een opstartbanner met pincode en bypass-status.
        2. Start de ``PerimeterListener`` (lokale broker, Pico WH) met
           ``on_perimeter_afstand`` als callback.
        3. Verbind ThingSpeak-MQTT indien er credentials zijn; een
           onbereikbare broker is slechts een waarschuwing.
        4. Maak de daemon-threads Button, Sensors-OLED, Actuators, Cloud en
           (indien geen bypass) Voice, en start ze.
        5. Hoofdlus slaapt tot KeyboardInterrupt.
        6. ``finally``: ``state.running`` = False, kort wachten zodat threads
           stoppen, dan MQTT sluiten, motor stroomloos (relais uit), en
           LED, display, sensoren, microfoon en knop vrijgeven (GPIO/SPI).

    Parameters: geen.
    Retourwaarde: geen.

    Gedeelde state / threads:
        Schrijft alleen ``state.running`` (zonder lock; enkelvoudige bool als
        stopsignaal). De hoofdthread doet verder geen werk.

    Ontwerpkeuzes:
        Daemon-threads zodat het proces nooit blijft hangen; ``stroomloos()``
        vóór ``close()`` zodat de motor nooit onder spanning blijft staan.
    """

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
