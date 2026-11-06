#!/usr/bin/env python3
"""
================================================================================
BESTAND: vault_state.py
DOEL:    Alle instellingen (constanten) en het "gedeelde geheugen" van de kluis.
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
Ons project gebruikt meerdere "threads" (taken die tegelijkertijd op de
achtergrond draaien, zoals sensoren uitlezen én op de knop letten).
Omdat al die taken met elkaar moeten kunnen praten, bewaren we alle
informatie op één centrale plek: de klasse `VaultState`. Zie dit als het
"notitiebord" van de kluis waar elke taak op kan kijken en schrijven.

💡 TIP VOOR JE PRESENTATIE (Waarom een Lock?):
Als twee taken op exact hetzelfde moment op hetzelfde notitiebord schrijven,
krijg je fouten (dat heet een 'race condition'). Daarom gebruiken we een
slotje (`state.lock`). Met `with state.lock:` zegt een taak eigenlijk:
"Ik heb nu even de praatstok, wacht heel even tot ik klaar ben met lezen
of schrijven."
"""

import threading

# ==============================================================================
# 1. ALGEMENE INSTELLINGEN & DREMPELWAARDEN (Makkelijk op één plek aan te passen)
# ==============================================================================

# De geheime 3-cijferige pincode. Elk cijfer (0 t/m 9) kies je met de draaiknop (potmeter).
SECRET_PIN = [4, 7, 2]           # De 3-cijferige kluiscode (in te voeren via potmeter 0-9)

# Stel deze in op True als je wilt testen ZONDER microfoon.
# Bij False (normaal gebruik) moet je na de pincode ook het wachtwoord inspreken (2FA).
BYPASS_VOICE_2FA = False         # True slaat de spraakstap over (zonder USB-microfoon)

# Het geheime woord dat je moet uitspreken bij stap 2 (Factor 2: Spraakherkenning).
VOICE_PASSPHRASE = "open"  # Geheime gesproken passphrase voor Factor 2

# Hoeveel seconden je krijgt om het wachtwoord in te spreken voordat de kluis
# weer terugspringt naar het pincode-scherm.
VOICE_TIMEOUT_S = 20.0           # Luistertijd voor Factor 2 voordat de kluis terugvalt naar PIN-invoer

# Als de kluis dicht is, hoort het binnenin donker te zijn.
# Komt er plots meer dan 50 lux licht binnen? Dan breekt er iemand in (Sabotage/Braak)!
LUX_SABOTAGE_THRESHOLD = 50.0  # Voorlopig hoog gezet voor testen in daglicht

# Als de temperatuur boven deze waarde komt, gaat het brandalarm af.
# (Staat op 30.0 °C zodat je het tijdens de demo makkelijk kunt testen met je vinger of adem).
TEMP_FIRE_THRESHOLD_C = 30.0     # Voorlopig laag gezet voor testen in kamerwarmte

# Om te voorkomen dat één toevallige meetfout meteen het brandalarm laat afgaan,
# moet de temperatuur 10 metingen achter elkaar (10x per seconde = 1 seconde lang) te hoog zijn.
FIRE_CONFIRM_READINGS = 10       # Opeenvolgende metingen (10 Hz) boven de drempel voor brandalarm

# De draaiknop (potmeter) geeft een getal van 0 tot 1023. Als de knop precies op de grens
# tussen bijv. cijfer 4 en 5 staat, kan het getal door kleine stroomschommelingen (ruis)
# telkens verspringen (4-5-4-5). Met een "drempel" (hysteresis) van 12 punten verandert
# het cijfer pas als je écht duidelijk voorbij de grens draait.
HYSTERESIS_10BIT = 12            # Dode band (op 0..1023) tegen flikkeren tussen twee cijfers

# Hoe vaak je een foute pincode mag invoeren voordat de kluis tijdelijk blokkeert.
MAX_PIN_ATTEMPTS = 3             # Pogingen voor de wachtperiode ingaat

# Hoe lang (in seconden) de rode LED knippert en "FOUTE CODE!" op het scherm staat.
WRONG_PIN_BLINK_S = 5.0          # Zwaailicht na een foute code

# Hoe lang (in seconden) de kluis geblokkeerd blijft na 3 foute pogingen (Lockout).
# (Staat op 10 seconden zodat je tijdens de presentatie niet 5 minuten hoeft te wachten!).
PIN_LOCKOUT_S = 10.0              # Wachtperiode (10 sec) na de laatste foute poging

# Staat iemand dichterbij dan 40 cm? Dan staat diegene vlak voor de kluis.
LOITER_DISTANCE_CM = 40.0        # Dichterbij dan dit = loitering

# Als iemand langer dan 15 seconden vlak voor de kluis blijft hangen ("loitering")
# ZONDER aan de knop te draaien of te drukken, vertrouwen we het niet -> Alarm!
LOITER_ALARM_S = 15.0            # Zo lang voor de kluis staan zonder iets te doen = alarm

# De Pico 2 W stuurt elke 0,5 seconde de afstand door via Wi-Fi (MQTT).
# Hebben we al 10 seconden niets gehoord? Dan is de Pico waarschijnlijk uitgeschakeld
# en negeren we de oude afstandsmeting.
PERIMETER_STALE_S = 10.0         # Afstandsmeting ouder dan dit wordt genegeerd (Pico offline)

# De gratis versie van ThingSpeak staat maximaal 1 bericht per 15 seconden toe.
TELEMETRY_INTERVAL_S = 15.0      # ThingSpeak-limiet: minstens 15 s tussen updates
ALARM_PUSH_INTERVAL_S = 120.0    # Minstens 2 minuten tussen alarmpushmeldingen

# De 5 mogelijke toestanden (states) waarin onze kluis kan zitten:
# 0 = PIN_INPUT (Op slot), 1 = VOICE_2FA (Spraak), 2 = UNLOCKED (Open), 3 = ALARM, 4 = LOCKOUT (Geblokkeerd)
MODE_CODES = {"PIN_INPUT": 0, "VOICE_2FA": 1, "UNLOCKED": 2, "ALARM": 3, "LOCKOUT": 4}


class VaultState:
    """
    Houdt alle actuele informatie van de kluis bij op één plek.

    Hoe werkt het?
    - De sensor-taak vult hier bijv. de gemeten temperatuur en lichtsterkte in.
    - De knop-taak vult hier de ingevoerde pincode en de nieuwe status (`mode`) in.
    - De motor/LED-taak kijkt naar `mode` en stuurt de stappenmotor, LED en sirene aan.
    """

    def __init__(self):
        """
        Zet alle variabelen klaar met hun veilige startwaarde (kluis op slot).
        """
        self.lock = threading.Lock()
        self.running = True
        self.mode = "PIN_INPUT"
        self.current_digit = 0
        self.entered_pin = []
        self.failed_attempts = 0
        self.lux = 0.0
        self.temp_c = 20.0
        self.perimeter_cm = 999.0
        self.loitering_alert = False
        self.perimeter_ts = 0.0         # monotonic tijdstip van de laatste afstandsmeting
        self.loiter_since = None        # monotonic tijdstip waarop iemand dichtbij kwam staan
        self.last_activity = 0.0        # laatste draai of knopdruk (monotonic)
        self.alarm_reason = ""
        self.unlock_executed = False    # Stappenmotor 1x draaien per ontgrendeling
        self.lock_executed = True       # Stappenmotor 1x terugdraaien per vergrendeling
        self.alarm_notified = False     # ntfy push 1x per alarm
        self.motor_busy = False         # True zolang de stappenmotor draait
        self.wrong_pin_until = 0.0      # monotonic tijdstip tot wanneer "foute code" getoond wordt
        self.lockout_until = 0.0        # monotonic tijdstip waarop de wachtperiode eindigt
        self.lockout_push_pending = False   # ntfy push 1x versturen bij start wachtperiode
        self.lockout_siren_pending = False  # korte sirene 1x afspelen bij start wachtperiode
