#!/usr/bin/env python3
"""
================================================================================
BESTAND: main.py
DOEL:    Het hoofdprogramma ("het brein") van de Smart Vault op de Raspberry Pi 5.
         Thomas More Geel - IoT Essentials Groepsproject
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
`main.py` is de dirigent van het hele project. Hij importeert al onze andere
Python-bestanden en laat ze samenwerken:
- `vault_state.py`  -> Alle instellingen en het gedeelde notitiebord (`state`)
- `sensors.py`      -> Draaiknop (potmeter), temperatuursensor (LM35) en lichtsensor (BH1750)
- `display.py`      -> Het OLED-schermpje (128x64 pixels)
- `vault_lock.py`   -> Het fysieke slot (Relais + Stappenmotor)
- `zwaailicht.py`   -> De RGB-LED (blauw, oranje, groen, rood knipperend)
- `mqtt_client.py`  -> Sturen naar ThingSpeak (cloud) + ontvangen van de Pico 2 W (afstand)
- `notificaties.py` -> Pushberichten naar je smartphone (`ntfy.sh`) + Bluetooth-sirene
- `voice.py`        -> Offline spraakherkenning voor stap 2 van de beveiliging (Vosk)

💡 DE TWEE BELANGRIJKSTE CONCEPTEN VOOR JE PRESENTATIE:
1. "Wat is een State Machine (Toestandsmachine)?"
   De kluis bevindt zich altijd in precies één duidelijke toestand (`state.mode`):
   - `PIN_INPUT`: Kluis zit op slot en wacht op de 3-cijferige pincode (Factor 1).
   - `VOICE_2FA`: Pincode was juist! Wacht nu op het gesproken wachtwoord (Factor 2).
   - `UNLOCKED`:  Beide factoren kloppen -> de stappenmotor draait het slot open!
   - `LOCKOUT`:   3x een foute pincode ingevoerd -> je moet even wachten (met aftelklok).
   - `ALARM`:     Brand, inbraak (licht in gesloten kluis) of iemand blijft verdacht
                  lang voor de kluis hangen (loitering) -> Sirene + Pushbericht + Rood licht!

2. "Waarom gebruiken we 5 Threads (achtergrondtaken)?"
   Als we maar 1 gewone `while`-lus zouden hebben, zou het hele scherm en de drukknop
   30 seconden lang bevriezen terwijl de stappenmotor draait of terwijl de microfoon luistert!
   Door het werk te verdelen over 5 losse threads, blijft alles altijd soepel reageren:
   - Thread 1 (`thread_button`):              Controleert 50x per seconde de drukknop.
   - Thread 2 (`thread_sensors_and_display`): Leest 10x per seconde de sensoren en tekent het OLED-scherm.
   - Thread 3 (`thread_actuators`):           Stuurt de RGB-LED, stappenmotor en sirene aan.
   - Thread 4 (`thread_cloud`):               Stuurt pushmeldingen en elke 15s data naar ThingSpeak.
   - Thread 5 (`thread_voice`):               Luistert naar het spraakwachtwoord zodra de pincode klopt.
"""

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

# ==============================================================================
# OPSTARTEN VAN ALLE ONDERDELEN (Objecten aanmaken)
# ==============================================================================

# 1. Maak het centrale "notitiebord" aan waarin alle threads hun gegevens delen
state = VaultState()

# 2. Zet de fysieke drukknop op GPIO 4 klaar.
# We gebruiken een interne Pull-Up weerstand (`Pull.UP`):
# - Knop NIET ingedrukt = True (3.3V)
# - Knop WEL ingedrukt  = False (0V, verbonden met GND)
button = digitalio.DigitalInOut(board.D4)
button.switch_to_input(pull=digitalio.Pull.UP)

# 3. Maak alle hardware- en hulpmiddelen aan
licht = Zwaailicht()
sensors = Sensors()
vault = VaultLock()
display = Display()
voice = VoiceRecognition()
notificaties = Notificaties()
# Start de achtergrondcontrole die de Bluetooth-speaker verbonden houdt
notificaties.start_speaker_verbinding()

# 4. Probeer de ThingSpeak MQTT-client klaar te zetten (werkt ook als `.env` nog niet is ingevuld)
try:
    mqtt = MQTTClient()
except RuntimeError as e:
    print(f"[THINGSPEAK] {e} Telemetrie wordt alleen geprint.")
    mqtt = None


# ==============================================================================
# THREAD 1: DRUKKNOP & PINCODE-LOGICA (Controleert 50x per seconde)
# ==============================================================================
def thread_button():
    """
    Deze achtergrondtaak let op de drukknop (op GPIO 4) en controleert de pincode.

    Wat gebeurt er als je op de knop drukt?
    - In modus `PIN_INPUT`:
      Het cijfer waar de draaiknop nu op staat (`state.current_digit`) wordt toegevoegd
      aan je ingevoerde pincode (`state.entered_pin`).
      Heb je 3 cijfers ingevoerd? Dan vergelijken we die met `SECRET_PIN`:
      * GOED -> We gaan door naar stap 2 (`VOICE_2FA`, of direct `UNLOCKED` als bypass aan staat).
      * FOUT -> Je krijgt een foutmelding. Na 3 fouten gaat de kluis in `LOCKOUT` (wachttijd)
                en sturen we een pushbericht + sirene!
    - In modus `UNLOCKED`:
      Een druk op de knop sluit de kluis weer terug naar `PIN_INPUT`.
    - In modus `ALARM`:
      Resetten naar `PIN_INPUT` kan alleen na een stabiele, veilige herstelperiode.
    """
    last_pressed = False

    while state.running:
        try:
            # Omdat de knop een Pull-Up weerstand heeft, betekent `not button.value` dat hij ingedrukt is!
            pressed = not button.value

            # Flankdetectie (`pressed and not last_pressed`):
            # We reageren alleen op het moment dat je de knop INDRUKT. Als je de knop
            # ingedrukt houdt, telt dat dus maar als 1 druk (en niet 50 drukken per seconde!).
            if pressed and not last_pressed:
                with state.lock:
                    # Onthoud dat de gebruiker net actief is geweest (zodat het loiter-alarm niet afgaat)
                    state.last_activity = time.monotonic()

                    # --- SITUATIE A: Gebruiker is de pincode aan het invoeren ---
                    if state.mode == "PIN_INPUT":
                        state.entered_pin.append(state.current_digit)
                        print(f"[CIJFERSLOT] Cijfer bevestigd: {state.current_digit} -> Invoer: {state.entered_pin}")

                        # Zijn er nu 3 cijfers ingevoerd? Controleer dan of de code klopt!
                        if len(state.entered_pin) == 3:
                            if state.entered_pin == SECRET_PIN:
                                # Pincode is JUIST!
                                state.failed_attempts = 0
                                if BYPASS_VOICE_2FA:
                                    print("[AUTH] Pincode correct! (Voice 2FA bypass actief -> UNLOCKED)")
                                    state.mode = "UNLOCKED"
                                    state.unlock_executed = False
                                else:
                                    print("[AUTH] Factor 1 (PIN) correct! Wachten op Factor 2 (Vosk Spraak)...")
                                    state.mode = "VOICE_2FA"
                            else:
                                # Pincode is FOUT!
                                state.failed_attempts += 1
                                # Maak de ingevoerde cijfers weer leeg
                                state.entered_pin = []
                                state.wrong_pin_until = time.monotonic() + WRONG_PIN_BLINK_S
                                retries_left = MAX_PIN_ATTEMPTS - state.failed_attempts
                                if retries_left > 0:
                                    print(f"[AUTH] Foute code! Nog {retries_left} pogingen over.")
                                else:
                                    # 3x fout -> Blokkering (LOCKOUT) + Pushbericht + Sirene!
                                    print(f"[AUTH] Foute code! Geen pogingen meer. Wacht {PIN_LOCKOUT_S // 60} minuten.")
                                    state.mode = "LOCKOUT"
                                    state.lockout_until = time.monotonic() + PIN_LOCKOUT_S
                                    state.lockout_push_pending = True
                                    state.lockout_siren_pending = True

                    # --- SITUATIE B: Kluis is tijdelijk geblokkeerd na 3 fouten ---
                    elif state.mode == "LOCKOUT":
                        print("[AUTH] Wachtperiode actief, invoer geblokkeerd.")

                    elif state.mode == "ALARM" and not state.alarm_reset_allowed(time.monotonic()):
                        print("[ALARM] Reset geblokkeerd: wacht op stabiele, veilige metingen.")

                    elif state.mode in ("UNLOCKED", "ALARM"):
                        if state.mode == "UNLOCKED":
                            # Zorg dat de motor-thread weet dat het slot weer dichtgedraaid moet worden
                            state.lock_executed = False
                        print("[SYSTEEM] Reset naar vergrendelde modus (PIN_INPUT).")
                        state.mode = "PIN_INPUT"
                        state.entered_pin = []
                        state.failed_attempts = 0
                        state.alarm_reason = ""
                        state.alarm_requires_perimeter = False
                        state.alarm_safe_since = None
                        state.alarm_notified = False
                        state.unlock_executed = False

                # Korte pauze (0,25 seconde) na een knopdruk tegen contactdender ("debounce"):
                # de metalen veertjes in een drukknop trillen heel even bij het indrukken.
                time.sleep(0.25)  # Debounce

            last_pressed = pressed

        except Exception as e:
            print(f"[FOUT in Knop Thread]: {e}")

        # Wacht 0,02 seconde (50 keer per seconde controleren)
        time.sleep(0.02)


# ==============================================================================
# THREAD 2: SENSOREN UITLEZEN, ALARM-CONTROLE & OLED-SCHERM (10x per seconde)
# ==============================================================================
def thread_sensors_and_display():
    """
    Deze achtergrondtaak doet 10 keer per seconde drie belangrijke dingen:
    1. Leest de draaiknop (potmeter), temperatuursensor (LM35) en lichtsensor (BH1750) uit.
    2. Controleert of er een alarm moet afgaan (Brand, Inbraak/Sabotage, of Loitering).
    3. Tekent alle actuele waarden en de juiste scherminhoud op het OLED-display.

    💡 SLIMME TRUCS VOOR JE PRESENTATIE:
    - Waarom meten we de temperatuur 5 keer en nemen we het middelste getal (`temp_samples[2]`, de mediaan)?
      Als de stappenmotor draait, kan er heel even een stroompiekje op de kabel zitten waardoor
      één meting ineens 45°C lijkt. Door 5 metingen op volgorde te zetten en de middelste te kiezen,
      vallen zulke uitschieters er altijd uit!
    - Waarom gebruiken we `HYSTERESIS_10BIT` bij de draaiknop?
      Zodat het gekozen cijfer (0 t/m 9) niet zenuwachtig heen en weer flikkert als de knop
      precies op het randje tussen twee cijfers staat.
    """
    last_digit = 0
    fire_count = 0

    while state.running:
        try:
            # --- STAP 1: Analoge sensoren uitlezen via de SPI-bus ---
            raw_10bit = sensors.lees_potmeter_raw()
            # Lees 5x snel de temperatuur, sorteer van klein naar groot en pak de middelste (index 2)
            temp_samples = sorted(sensors.lees_temperatuur() for _ in range(5))
            temp_c = temp_samples[2]  # Mediaan filtert pieken door motorstroom

            # Reken de potmeterwaarde (0..1023) om naar een cijfer van 0 t/m 9
            candidate_digit = min((raw_10bit * 10) // 1024, 9)

            # Hysteresis-controle: pas veranderen van cijfer als we duidelijk (minstens 12 punten)
            # over de grens tussen het oude en het nieuwe cijfer heen zijn gedraaid.
            if candidate_digit != last_digit:
                border_raw = (max(candidate_digit, last_digit) * 1024) // 10
                if abs(raw_10bit - border_raw) >= HYSTERESIS_10BIT:
                    last_digit = candidate_digit

            # Lees de digitale lichtsensor uit via I2C
            lux = sensors.lees_licht()

            # --- STAP 2: Status bijwerken en Alarm-regels controleren ---
            with state.lock:
                # Heeft de gebruiker aan de knop gedraaid? Noteer dat er activiteit was!
                if last_digit != state.current_digit:
                    state.last_activity = time.monotonic()
                state.current_digit = last_digit
                state.temp_c = temp_c
                state.lux = lux

                # ALARM-CHECK 1: Brandalarm (Temperatuur > 30°C gedurende 10 metingen = 1 seconde)
                # (Terwijl de motor draait negeren we dit even vanwege mogelijke stroomschommelingen)
                if temp_c > TEMP_FIRE_THRESHOLD_C and not state.motor_busy:
                    fire_count += 1
                else:
                    fire_count = 0

                if fire_count >= FIRE_CONFIRM_READINGS and state.mode != "ALARM":
                    state.mode = "ALARM"
                    state.alarm_reason = f"BRAND! T={temp_c:.1f}C"

                # ALARM-CHECK 2: Inbraak / Sabotage (Veel licht in de kluis terwijl hij op slot zit!)
                if lux > LUX_SABOTAGE_THRESHOLD and state.mode not in ("UNLOCKED", "ALARM"):
                    print(f"[SABOTAGE] Licht gedetecteerd in gesloten kluis ({lux:.1f} lux)!")
                    state.mode = "ALARM"
                    state.alarm_reason = f"BRAAK! ({int(lux)} lx)"

                # ALARM-CHECK 3: Loitering (Iemand staat te lang vlak voor de kluis zonder iets te doen)
                nu = time.monotonic()
                dichtbij = state.loitering_alert and (nu - state.perimeter_ts) < PERIMETER_STALE_S
                if not dichtbij or state.mode != "PIN_INPUT":
                    state.loiter_since = None
                else:
                    if state.loiter_since is None:
                        state.loiter_since = nu
                    # Staat de persoon er al langer dan LOITER_ALARM_S (15 sec) zonder te draaien/drukken?
                    if nu - max(state.loiter_since, state.last_activity) >= LOITER_ALARM_S:
                        print(f"[LOITER] Persoon > {LOITER_ALARM_S:.0f}s zonder actie voor de kluis!")
                        state.mode = "ALARM"
                        state.alarm_reason = "LOITER > 1 MIN"
                        state.alarm_requires_perimeter = True
                        state.loiter_since = None

                state.update_alarm_recovery(nu, sensors.laatste_lux_ts)
                alarm_veilig = state.alarm_reset_allowed(nu)

                # Maak een kopietje (snapshot) van alle waarden voor het OLED-scherm,
                # zodat we het slotje (`state.lock`) weer snel kunnen loslaten.
                mode = state.mode
                digit = state.current_digit
                pin_so_far = list(state.entered_pin)
                loitering = state.loitering_alert
                afstand_cm = state.perimeter_cm if (time.monotonic() - state.perimeter_ts) < PERIMETER_STALE_S else None
                reason = state.alarm_reason
                now = time.monotonic()

                # Controleer of de blokkeertijd (`LOCKOUT`) na 3 foute pincodes inmiddels voorbij is
                if state.mode == "LOCKOUT" and now >= state.lockout_until:
                    print("[AUTH] Wachtperiode voorbij, opnieuw proberen mogelijk.")
                    state.mode = "PIN_INPUT"
                    state.failed_attempts = 0
                    mode = "PIN_INPUT"

                toon_fout = now < state.wrong_pin_until
                pogingen_over = MAX_PIN_ATTEMPTS - state.failed_attempts
                wachttijd_s = max(0, int(state.lockout_until - now))

            # --- STAP 3: Teken het bijgewerkte scherm op het OLED-display ---
            display.toon_kluisscherm(
                mode=mode,
                lux=lux,
                temp_c=temp_c,
                digit=digit,
                pin_so_far=pin_so_far,
                loitering=loitering,
                reason=reason,
                voice_passphrase=VOICE_PASSPHRASE,
                alarm_veilig=alarm_veilig,
                toon_fout=toon_fout,
                pogingen_over=pogingen_over,
                wachttijd_s=wachttijd_s,
                afstand_cm=afstand_cm
            )

        except Exception as e:
            with state.lock:
                state.sensor_ts = None
                state.alarm_safe_since = None
            print(f"[FOUT in Sensor/OLED Thread]: {e}")

        # Wacht 0,10 seconde (10 keer per seconde verversen)
        time.sleep(0.10)


# ==============================================================================
# THREAD 3: ACTUATOREN (STAPPENMOTOR, RELAIS, RGB-LED & SIRENE)
# ==============================================================================
def thread_actuators():
    """
    Deze achtergrondtaak kijkt naar de huidige modus (`state.mode`) en stuurt
    alle "doe-dingen" (actuatoren) aan:
    - Moet de kluis open? -> Zet de LED groen en laat de stappenmotor het slot openen.
    - Moet de kluis dicht? -> Zet de LED blauw en laat de stappenmotor het slot sluiten.
    - Welke kleur moet de RGB-LED hebben?
      * Blauw:          Kluis vergrendeld (`PIN_INPUT`)
      * Oranje:         Wachten op spraakwachtwoord (`VOICE_2FA`)
      * Groen:          Kluis is geopend (`UNLOCKED`)
      * Zacht rood:     Kluis is tijdelijk geblokkeerd (`LOCKOUT`)
      * Rood knipperen: Foute code ingevoerd of `ALARM` (bij alarm loeit ook de sirene!)
    """
    last_siren_time = 0.0

    while state.running:
        # Kijk kort op het notitiebord (`state`) welke acties er nodig zijn
        with state.lock:
            mode = state.mode
            siren_once = state.lockout_siren_pending
            state.lockout_siren_pending = False

            # Moet de motor de kluis voor het eerst opendraaien?
            need_unlock_motion = (mode == "UNLOCKED" and not state.unlock_executed)
            if need_unlock_motion:
                state.unlock_executed = True

            # Moet de motor de kluis weer op slot draaien?
            need_lock_motion = (mode == "PIN_INPUT" and not state.lock_executed)
            if need_lock_motion:
                state.lock_executed = True

        # Speel 1x de sirene af als de kluis net geblokkeerd is na 3 foute pogingen
        if siren_once:
            notificaties.sirene()

        # --- Motor-actie 1: Kluis OPENEN ---
        # Let op: we draaien de motor BUITEN `with state.lock:`, zodat het scherm en
        # de sensoren niet 30 seconden op ons hoeven te wachten terwijl de motor draait!
        if need_unlock_motion:
            # Groen licht
            licht.kleur_procent(0, 100, 0)
            with state.lock:
                state.motor_busy = True
            vault.open()
            with state.lock:
                state.lock_executed = False
                state.motor_busy = False

        # --- Motor-actie 2: Kluis SLUITEN ---
        if need_lock_motion:
            # Blauw licht
            licht.kleur_procent(0, 0, 80)
            with state.lock:
                state.motor_busy = True
            vault.sluit()
            with state.lock:
                state.motor_busy = False

        # --- RGB-LED en Sirene aansturen op basis van de huidige modus ---
        if mode in ("PIN_INPUT", "LOCKOUT"):
            # Zorg dat het motor-relais veilig uit staat
            vault.stroomloos()
            with state.lock:
                foute_code = time.monotonic() < state.wrong_pin_until
            if foute_code:
                licht.knipper_rood()
            elif mode == "LOCKOUT":
                licht.kleur_procent(30, 0, 0)  # Zacht rood tijdens wachtperiode
            else:
                # Rustig blauw in normale wachtstand
                licht.kleur_procent(0, 0, 80)

        elif mode == "VOICE_2FA":
            # Oranje tijdens wachten op spraak
            licht.kleur_procent(80, 30, 0)

        elif mode == "UNLOCKED":
            # Fel groen als de kluis open is
            licht.kleur_procent(0, 100, 0)

        elif mode == "ALARM":
            vault.stroomloos()
            # Rood zwaailicht!
            licht.knipper_rood()

            # Start elke 4 seconden de sirene opnieuw zolang het alarm actief is
            if time.time() - last_siren_time > 4.0:
                notificaties.sirene()
                last_siren_time = time.time()

        # Is het alarm net gereset (terug naar `PIN_INPUT`)? Stop dan meteen de sirene!
        if mode == "PIN_INPUT" and last_siren_time:
            notificaties.stop_sirene()
            last_siren_time = 0.0

        time.sleep(0.03)


# ==============================================================================
# THREAD 4: CLOUD & SMARTPHONE MELDINGEN (ThingSpeak & ntfy.sh)
# ==============================================================================
def thread_cloud():
    """
    Deze achtergrondtaak regelt al het internetverkeer:
    1. Bij een alarm stuurt hij een pushbericht via `ntfy.sh`, maximaal elke
       `ALARM_PUSH_INTERVAL_S` seconden. Een reset wist die wachttijd niet.
       Na 3x een foute pincode stuurt hij een afzonderlijk lockoutbericht.
    2. Elke 15 seconden (`TELEMETRY_INTERVAL_S`) stuurt hij alle meetwaarden
       door naar het online ThingSpeak-dashboard via MQTT.

    Waarom in een aparte thread?
    Als het internet traag is, heeft de rest van de kluis (knop, scherm, motor)
    daar helemaal geen last van!
    """
    last_push = 0.0
    last_alarm_push = None

    while state.running:
        # Haal de laatste gegevens op van het centrale notitiebord (`state`)
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

        # Stuur smartphone-melding bij 3x foute pincode
        if lockout_alert:
            notificaties.stuur_push(
                f"SMART VAULT: {MAX_PIN_ATTEMPTS}x foute pincode. "
                f"Kluis {PIN_LOCKOUT_S} seconden geblokkeerd."
            )

        # Stuur smartphone-melding bij een Alarm (Brand, Inbraak of Loitering)
        if should_alert:
            last_alarm_push = time.monotonic()
            notificaties.stuur_push(
                f"SMART VAULT ALARM: {reason} (Lux={lux:.1f}, Temp={temp_c:.1f}C)"
            )

        # Stuur elke 15 seconden een update naar de ThingSpeak-grafieken
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


# ==============================================================================
# THREAD 5: SPRAAKHERKENNING VOOR STAP 2 (Factor 2 - Vosk)
# ==============================================================================
def thread_voice():
    """
    Deze achtergrondtaak verzorgt de tweede beveiligingsstap (Factor 2: Spraak).
    Zodra de pincode goed is ingevoerd, verandert `state.mode` naar `"VOICE_2FA"`.
    Deze thread ziet dat en zet direct de microfoon maximaal 20 seconden aan:
    - Hoort hij het geheime woord (`VOICE_PASSPHRASE`, standaard `"open"`)?
      Dan zet hij de kluis op `"UNLOCKED"` en draait de motor het slot open!
    - Hoort hij na 20 seconden niets (of het verkeerde woord)?
      Dan valt de kluis weer veilig terug op slot (`"PIN_INPUT"`).
    """
    try:
        # Laad bij het opstarten alvast het Vosk-taalmodel in het geheugen,
        # zodat de microfoon straks zonder vertraging kan beginnen met luisteren.
        voice.laad()
    except Exception as e:
        print(f"[VOICE FOUT] Model laden mislukt: {e}")

    while state.running:
        # Kijk of we al in de `VOICE_2FA` modus zitten
        with state.lock:
            wacht_op_spraak = (state.mode == "VOICE_2FA")

        # Nog niet aan de beurt? Wacht 0,2 seconde en kijk opnieuw.
        if not wacht_op_spraak:
            time.sleep(0.2)
            continue

        # We zijn in `VOICE_2FA`! Start het luisteren via de USB-microfoon.
        print(f"[VOICE] Luisteren naar '{VOICE_PASSPHRASE}' ({VOICE_TIMEOUT_S:.0f}s)...")
        try:
            gehoord = voice.luister(
                timeout_s=VOICE_TIMEOUT_S,
                # Stop meteen met luisteren als het programma sluit of als er intussen een alarm afgaat
                stop=lambda: not state.running or state.mode != "VOICE_2FA",
                doelzin=VOICE_PASSPHRASE.lower(),
            )
        except Exception as e:
            print(f"[VOICE FOUT] {e}")
            gehoord = ""
            time.sleep(1.0)

        # Controleer het resultaat
        with state.lock:
            # Als de modus tijdens het luisteren al veranderd is (bijv. door een alarm), doe dan niets
            if state.mode != "VOICE_2FA":
                continue

            # Zit het geheime wachtwoord in de herkende tekst?
            if VOICE_PASSPHRASE.lower() in gehoord.lower():
                print("[AUTH] Factor 2 (spraak) correct! -> UNLOCKED")
                state.mode = "UNLOCKED"
                state.unlock_executed = False
            else:
                print("[AUTH] Passphrase niet herkend, terug naar PIN-invoer.")
                state.mode = "PIN_INPUT"
                state.entered_pin = []


# ==============================================================================
# ONTVANGSTFUNCTIE VOOR DE PICO 2 W AFSTANDSSENSOR (Lokale MQTT)
# ==============================================================================
def on_perimeter_afstand(dist_cm):
    """
    Wordt automatisch aangeroepen telkens als de Pico 2 W (via lokale MQTT)
    een nieuwe afstandsmeting in centimeters doorstuurt.
    Slaat de afstand en het huidige tijdstip op, en zet `loitering_alert` op True
    als er iemand dichterbij staat dan 40 cm (`LOITER_DISTANCE_CM`).
    """
    with state.lock:
        state.perimeter_cm = dist_cm
        state.perimeter_ts = time.monotonic()
        state.loitering_alert = (dist_cm < LOITER_DISTANCE_CM)
        if state.alarm_requires_perimeter and not state.alarm_conditions_safe(state.perimeter_ts):
            state.alarm_safe_since = None


# ==============================================================================
# HOOFDFUNCTIE: ALLES OPSTARTEN EN BIJ AFSLUITEN NETJES OPRUIMEN
# ==============================================================================
def main():
    """
    Start alle verbindingen en achtergrondtaken (threads) op, en zorgt ervoor
    dat bij het stoppen (Ctrl+C) alle motoren, lampjes en GPIO-pinnen veilig
    worden uitgeschakeld.
    """
    print("=====================================================")
    print(" SMART VAULT CONTROLLER v1.3 OPSTARTEN...")
    print(f"    Geheime Pincode : {SECRET_PIN}")
    print(f"    Voice 2FA Bypass: {BYPASS_VOICE_2FA}")
    print("=====================================================")

    # 1. Start het luisteren naar de Pico 2 W afstandssensor op de lokale MQTT-broker
    perimeter = PerimeterListener(on_perimeter_afstand)
    perimeter.connect()

    # 2. Verbind met ThingSpeak in de cloud (als de inloggegevens in `.env` staan)
    if mqtt is not None:
        try:
            mqtt.connect()
        except Exception as e:
            print(f"[THINGSPEAK WAARSCHUWING] Broker niet bereikbaar: {e}")

    # 3. Maak onze achtergrondtaken (threads) aan.
    # `daemon=True` betekent: als het hoofdprogramma stopt, stoppen deze taken automatisch mee.
    threads = [
        threading.Thread(target=thread_button, name="Button", daemon=True),
        threading.Thread(target=thread_sensors_and_display, name="Sensors-OLED", daemon=True),
        threading.Thread(target=thread_actuators, name="Actuators", daemon=True),
        threading.Thread(target=thread_cloud, name="Cloud", daemon=True),
    ]
    # Start de spraak-thread alleen als we de microfoon echt gebruiken
    if not BYPASS_VOICE_2FA:
        threads.append(threading.Thread(target=thread_voice, name="Voice", daemon=True))

    # Start alle threads!
    for t in threads:
        t.start()

    # 4. Houd het hoofdprogramma levend tot de gebruiker op Ctrl+C drukt
    try:
        while True:
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Bezig met veilig afsluiten en vrijgeven van GPIO-pinnen...")

    finally:
        # 5. VEILIG AFSLUITEN: Dit blok wordt ALTIJD uitgevoerd als het programma stopt.
        # Geef alle threads het signaal om te stoppen en wacht 0,3 seconde.
        state.running = False
        time.sleep(0.3)

        # Sluit de MQTT-verbindingen
        perimeter.close()
        if mqtt is not None:
            mqtt.close()

        # Zet de motor stroomloos en geef alle GPIO-pinnen netjes vrij
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
