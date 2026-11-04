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
SECRET_PIN = [4, 7, 2]

# Stel deze in op True als je wilt testen ZONDER microfoon.
# Bij False (normaal gebruik) moet je na de pincode ook het wachtwoord inspreken (2FA).
BYPASS_VOICE_2FA = False

# Het geheime woord dat je moet uitspreken bij stap 2 (Factor 2: Spraakherkenning).
VOICE_PASSPHRASE = "open"

# Hoeveel seconden je krijgt om het wachtwoord in te spreken voordat de kluis
# weer terugspringt naar het pincode-scherm.
VOICE_TIMEOUT_S = 20.0

# --- Alarm-drempelwaarden ---
# Als de kluis dicht is, hoort het binnenin donker te zijn.
# Komt er plots meer dan 50 lux licht binnen? Dan breekt er iemand in (Sabotage/Braak)!
# (Voor testen in een verlicht lokaal staat deze op 50.0 lux).
LUX_SABOTAGE_THRESHOLD = 50.0

# Als de temperatuur boven deze waarde komt, gaat het brandalarm af.
# (Staat op 30.0 °C zodat je het tijdens de demo makkelijk kunt testen met je vinger of adem).
TEMP_FIRE_THRESHOLD_C = 30.0

# Om te voorkomen dat één toevallige meetfout meteen het brandalarm laat afgaan,
# moet de temperatuur 10 metingen achter elkaar (10x per seconde = 1 seconde lang) te hoog zijn.
FIRE_CONFIRM_READINGS = 10

# --- Slimme instellingen voor bediening ---
# De draaiknop (potmeter) geeft een getal van 0 tot 1023. Als de knop precies op de grens
# tussen bijv. cijfer 4 en 5 staat, kan het getal door kleine stroomschommelingen (ruis)
# telkens verspringen (4-5-4-5). Met een "drempel" (hysteresis) van 12 punten verandert
# het cijfer pas als je écht duidelijk voorbij de grens draait.
HYSTERESIS_10BIT = 12

# Hoe vaak je een foute pincode mag invoeren voordat de kluis tijdelijk blokkeert.
MAX_PIN_ATTEMPTS = 3

# Hoe lang (in seconden) de rode LED knippert en "FOUTE CODE!" op het scherm staat.
WRONG_PIN_BLINK_S = 5.0

# Hoe lang (in seconden) de kluis geblokkeerd blijft na 3 foute pogingen (Lockout).
# (Staat op 10 seconden zodat je tijdens de presentatie niet 5 minuten hoeft te wachten!).
PIN_LOCKOUT_S = 10.0

# --- Afstandssensor (Pico 2 W met ultrasone sensor) ---
# Staat iemand dichterbij dan 40 cm? Dan staat diegene vlak voor de kluis.
LOITER_DISTANCE_CM = 40.0

# Als iemand langer dan 15 seconden vlak voor de kluis blijft hangen ("loitering")
# ZONDER aan de knop te draaien of te drukken, vertrouwen we het niet -> Alarm!
LOITER_ALARM_S = 15.0

# De Pico 2 W stuurt elke 0,5 seconde de afstand door via Wi-Fi (MQTT).
# Hebben we al 10 seconden niets gehoord? Dan is de Pico waarschijnlijk uitgeschakeld
# en negeren we de oude afstandsmeting.
PERIMETER_STALE_S = 10.0

# --- Cloud (ThingSpeak) ---
# De gratis versie van ThingSpeak staat maximaal 1 bericht per 15 seconden toe.
TELEMETRY_INTERVAL_S = 15.0

# De 5 mogelijke toestanden (states) waarin onze kluis kan zitten.
# Voor ThingSpeak-grafieken koppelen we aan elke tekst-status ook een vast getal (0 t/m 4).
MODE_CODES = {
    "PIN_INPUT": 0,  # Kluis op slot, wacht op pincode (Factor 1)
    "VOICE_2FA": 1,  # Pincode was goed, wacht nu op spraakwachtwoord (Factor 2)
    "UNLOCKED": 2,   # Kluis is geopend!
    "ALARM": 3,      # Alarm gaat af (brand, inbraak of verdacht lang rondhangen)
    "LOCKOUT": 4     # Tijdelijk geblokkeerd na 3x foute pincode
}


# ==============================================================================
# 2. DE KLASSE VAULTSTATE (Het centrale geheugen van de kluis)
# ==============================================================================
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
        # --- Slotjes (Locks) voor veilig samenwerken tussen threads ---
        # `lock`: gebruik `with state.lock:` als je onderstaande variabelen leest of aanpast.
        self.lock = threading.Lock()
        # `spi_lock`: de MCP3008-chip (sensoren) en het OLED-scherm zitten op dezelfde
        # SPI-datakabel. Dit slotje zorgt dat ze nooit tegelijk door elkaar praten.
        self.spi_lock = threading.Lock()

        # Zolang `running` op True staat, blijven alle achtergrondtaken draaien.
        # Bij afsluiten (Ctrl+C) zetten we deze op False zodat alles netjes stopt.
        self.running = True

        # --- Huidige status en Pincode ---
        self.mode = "PIN_INPUT"         # We starten altijd vergrendeld in het pincode-scherm
        self.current_digit = 0          # Het cijfer (0-9) waar de draaiknop nu op staat
        self.entered_pin = []           # Lijstje met de al bevestigde cijfers, bijv. [4, 7]
        self.failed_attempts = 0        # Aantal keer dat er een foute pincode is ingevoerd

        # --- Laatst gemeten sensorwaarden ---
        self.lux = 0.0                  # Lichtsterkte in de kluis (in lux)
        self.temp_c = 20.0              # Temperatuur in de kluis (in °C, start op kamertemperatuur)
        self.perimeter_cm = 999.0       # Afstand tot een persoon voor de kluis (999 = niemand te zien)
        self.loitering_alert = False    # True als er iemand dichterbij dan 40 cm staat

        # --- Tijdstippen (voor timers en controles) ---
        # We gebruiken in main.py `time.monotonic()`: een interne stopwatch die altijd
        # vooruit telt, zelfs als de Raspberry Pi zijn winter-/zomertijd aanpast.
        self.perimeter_ts = 0.0         # Tijdstip waarop de laatste afstandsmeting binnenkwam
        self.loiter_since = None        # Tijdstip vanaf wanneer iemand voor de kluis staat te wachten
        self.last_activity = 0.0        # Tijdstip waarop voor het laatst gedraaid of gedrukt is
        self.wrong_pin_until = 0.0      # Tot dit tijdstip blijft "FOUTE CODE!" op het scherm staan
        self.lockout_until = 0.0        # Tot dit tijdstip blijft de kluis geblokkeerd na 3 fouten

        # --- Alarm en Eenmalige Actie-vlaggetjes (Flags) ---
        # Waarom deze True/False vlaggetjes?
        # De taken controleren 10 tot 30 keer per seconde de status. Als de status "UNLOCKED"
        # wordt, willen we dat de stappenmotor maar ÉÉN keer opendraait (en niet 30x per seconde!).
        self.alarm_reason = ""          # Reden van het alarm voor op het scherm (bijv. "BRAND! T=32.5C")
        self.unlock_executed = False    # Wordt True zodra de motor de kluis heeft opengedraaid
        self.lock_executed = True       # Begint op True omdat de kluis bij de start al op slot zit
        self.alarm_notified = False     # Zorgt dat we maar 1x een smartphone-melding sturen per alarm
        self.motor_busy = False         # True terwijl de motor draait (dan negeren we stroompieken op de temperatuursensor)
        self.lockout_push_pending = False   # Moet er nog 1x een pushbericht uit voor de blokkering?
        self.lockout_siren_pending = False  # Moet de sirene nog 1x kort loeien bij blokkering?
