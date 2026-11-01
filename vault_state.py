#!/usr/bin/env python3
"""
Configuratie, drempelwaarden en gedeelde systeemstatus van de Smart Vault.

Rol van dit bestand:
    Enige plek voor alle instelbare constanten (PIN, tijden, drempels) en
    voor ``VaultState``, het gedeelde geheugen waarmee de threads van main.py
    (Button, Sensors-OLED, Actuators, Cloud, Voice) met elkaar communiceren.

Threads en locks:
    ``VaultState.lock`` beschermt alle velden: lees of schrijf ze alleen
    binnen ``with state.lock``. ``VaultState.spi_lock`` is een aparte lock
    voor de gedeelde SPI-bus (MCP3008 en OLED). Tijdstippen zijn
    ``time.monotonic()``-waarden, zodat klokcorrecties (NTP) niets verstoren.
"""

import threading

# ==============================================================================
# Configuratie & drempelwaarden
# ==============================================================================
# Cijfers 0-9 via de potmeter; drie cijfers is een bruikbare balans tussen
# veiligheid en snelheid van invoeren.
SECRET_PIN = [4, 7, 2]           # De 3-cijferige kluiscode (in te voeren via potmeter 0-9)
# Handig tijdens ontwikkeling of als de USB-microfoon ontbreekt; moet False
# blijven in productie, anders vervalt de tweede factor.
BYPASS_VOICE_2FA = False         # True slaat de spraakstap over (zonder USB-microfoon)
# Dezelfde zin wordt als enige toegestane grammatica in Vosk geladen.
VOICE_PASSPHRASE = "open sesam"  # Geheime gesproken passphrase voor Factor 2
# 20 s geeft genoeg tijd om te spreken zonder dat de kluis lang half-open blijft.
VOICE_TIMEOUT_S = 20.0           # Luistertijd voor Factor 2 voordat de kluis terugvalt naar PIN-invoer

# Daglicht is ver onder 5000 lux binnen; test-waarde zodat sabotage niet bij
# gewoon daglicht afgaat. Productiewaarde moet lager (bv. ~100-500 lux).
LUX_SABOTAGE_THRESHOLD = 5000.0  # Voorlopig hoog gezet voor testen in daglicht
# Kamertemperatuur ~20-22 °C; 30 °C laat het alarm testen met een hand/föhn.
# Productiewaarde ligt veel hoger (bv. 50-60 °C).
TEMP_FIRE_THRESHOLD_C = 30.0     # Voorlopig laag gezet voor testen in kamerwarmte
# 10 metingen bij 10 Hz = 1 s aaneengesloten: voorkomt vals alarm door ruis.
FIRE_CONFIRM_READINGS = 10       # Opeenvolgende metingen (10 Hz) boven de drempel voor brandalarm
# 12 van 1024 (~1,2%) is kleiner dan een cijferbreedte (~102) maar groter dan
# de ADC-ruis, zodat de potmeter op een grens niet tussen twee cijfers flikkert.
HYSTERESIS_10BIT = 12            # Dode band (op 0..1023) tegen flikkeren tussen twee cijfers
# Drie is gebruikelijk (zoals een pinautomaat): tolerant maar niet te raden.
MAX_PIN_ATTEMPTS = 3             # Pogingen voor de wachtperiode ingaat
# Lang genoeg om op te vallen, kort genoeg om niet te storen.
WRONG_PIN_BLINK_S = 3.0          # Zwaailicht na een foute code
# 300 s maakt brute force onpraktisch zonder een gebruiker permanent buiten te sluiten.
PIN_LOCKOUT_S = 300              # Wachtperiode (5 min) na de laatste foute poging
# 40 cm = armlengte: iemand die zo dicht staat is bezig met de kluis.
LOITER_DISTANCE_CM = 40.0        # Dichterbij dan dit = loitering
# Een minuut geeft eigenaren tijd om de code in te voeren, maar wie blijft
# treuzelen zonder iets te doen valt op.
LOITER_ALARM_S = 60.0            # Zo lang voor de kluis staan zonder iets te doen = alarm
# De Pico meldt elke 0,5 s; 10 s = ca. 20 gemiste metingen, dus waarschijnlijk offline.
PERIMETER_STALE_S = 10.0         # Afstandsmeting ouder dan dit wordt genegeerd (Pico offline)

# ThingSpeak accepteert op de gratis laag maximaal één update per 15 s.
TELEMETRY_INTERVAL_S = 15.0      # ThingSpeak-limiet: minstens 15 s tussen updates

# Modi: "PIN_INPUT", "VOICE_2FA", "UNLOCKED", "ALARM", "LOCKOUT"
# De numerieke codes worden als veld naar ThingSpeak gestuurd (grafiek/dashboard).
MODE_CODES = {"PIN_INPUT": 0, "VOICE_2FA": 1, "UNLOCKED": 2, "ALARM": 3, "LOCKOUT": 4}


class VaultState:
    """
    Gedeelde systeemstatus van de kluis (één instantie, gedeeld door alle threads).

    Doel:
        Eén centrale plek voor modus, sensorwaarden, timers en
        eenmalig-actie-vlaggen, zodat threads niet rechtstreeks van elkaar
        afhangen.

    Werking:
        Threads schrijven hun meetwaarden of gebeurtenissen in dit object; de
        actuator-thread leest die en bepaalt de modus en acties.

    Threads/locks:
        Alle velden alleen aanraken binnen ``with state.lock``. ``spi_lock``
        staat los daarvan en dient uitsluitend om de SPI-bus tussen ADC en OLED
        te scheiden. Houd beide locks bij voorkeur niet tegelijk vast om
        deadlocks te vermijden.

    Ontwerpkeuzes:
        Eenmalig-actie-vlaggen (``unlock_executed``, ``alarm_notified`` e.d.)
        zorgen dat een motor, push of sirene niet bij elke lus-iteratie opnieuw
        wordt gestart.
    """

    def __init__(self):
        """
        Zet alle velden op hun beginwaarde (kluis dicht, wachtend op PIN).

        Parameters:
            Geen.

        Returns:
            None

        Velden:
            lock: algemene threadslot voor alle onderstaande velden.
            spi_lock: voorkomt gelijktijdige SPI-toegang tussen ADC en OLED.
            running: False = alle threads moeten stoppen.
            mode: huidige modus, een sleutel uit MODE_CODES.
            current_digit: cijfer (0-9) waar de potmeter nu op staat.
            entered_pin: reeds bevestigde cijfers van de PIN-invoer.
            failed_attempts: aantal foute PIN-pogingen sinds de laatste reset.
            lux: laatste lichtmeting in lux.
            temp_c: laatste (mediaan-)temperatuur in °C; 20.0 is een
                neutrale beginwaarde onder de brandgrens.
            perimeter_cm: laatste afstand van de Pico; 999.0 = niemand/geen data.
            loitering_alert: True zolang iemand te lang dichtbij staat.
            perimeter_ts: monotonic-tijd van de laatste afstandsmeting.
            loiter_since: monotonic-tijd van het begin van loitering, of None.
            last_activity: monotonic-tijd van de laatste draai of knopdruk.
            alarm_reason: tekst waarom het alarm afging (leeg = geen alarm).
            unlock_executed: motor één keer draaien per ontgrendeling.
            lock_executed: motor één keer terugdraaien per vergrendeling;
                begint True omdat de kluis dicht is.
            alarm_notified: ntfy-push één keer per alarm.
            motor_busy: True zolang de stappenmotor draait.
            wrong_pin_until: tot dit monotonic-tijdstip wordt "foute code" getoond.
            lockout_until: monotonic-tijdstip waarop de wachtperiode eindigt.
            lockout_push_pending: push één keer versturen bij start wachtperiode.
            lockout_siren_pending: korte sirene één keer afspelen bij start wachtperiode.
        """
        self.lock = threading.Lock()
        self.spi_lock = threading.Lock()  # Voorkomt gelijktijdige SPI-toegang tussen ADC en OLED
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
