#!/usr/bin/env python3
"""Configuratie, drempelwaarden en gedeelde systeemstatus van de Smart Vault."""

import threading

# ==============================================================================
# Configuratie & drempelwaarden
# ==============================================================================
SECRET_PIN = [4, 7, 2]           # De 3-cijferige kluiscode (in te voeren via potmeter 0-9)
BYPASS_VOICE_2FA = False         # True slaat de spraakstap over (zonder USB-microfoon)
VOICE_PASSPHRASE = "open sesam"  # Geheime gesproken passphrase voor Factor 2
VOICE_TIMEOUT_S = 20.0           # Luistertijd voor Factor 2 voordat de kluis terugvalt naar PIN-invoer

LUX_SABOTAGE_THRESHOLD = 5000.0  # Voorlopig hoog gezet voor testen in daglicht
TEMP_FIRE_THRESHOLD_C = 25.0     # Voorlopig laag gezet voor testen in kamerwarmte
HYSTERESIS_10BIT = 12            # Dode band (op 0..1023) tegen flikkeren tussen twee cijfers
MAX_PIN_ATTEMPTS = 3             # Pogingen voor de wachtperiode ingaat
WRONG_PIN_BLINK_S = 3.0          # Zwaailicht na een foute code
PIN_LOCKOUT_S = 300              # Wachtperiode (5 min) na de laatste foute poging
LOITER_DISTANCE_CM = 40.0        # Dichterbij dan dit = loitering

TELEMETRY_INTERVAL_S = 15.0      # ThingSpeak-limiet: minstens 15 s tussen updates

# Modi: "PIN_INPUT", "VOICE_2FA", "UNLOCKED", "ALARM", "LOCKOUT"
MODE_CODES = {"PIN_INPUT": 0, "VOICE_2FA": 1, "UNLOCKED": 2, "ALARM": 3, "LOCKOUT": 4}


class VaultState:
    def __init__(self):
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
        self.alarm_reason = ""
        self.unlock_executed = False    # Stappenmotor 1x draaien per ontgrendeling
        self.lock_executed = True       # Stappenmotor 1x terugdraaien per vergrendeling
        self.alarm_notified = False     # ntfy push 1x per alarm
        self.wrong_pin_until = 0.0      # monotonic tijdstip tot wanneer "foute code" getoond wordt
        self.lockout_until = 0.0        # monotonic tijdstip waarop de wachtperiode eindigt
        self.lockout_push_pending = False   # ntfy push 1x versturen bij start wachtperiode
        self.lockout_siren_pending = False  # korte sirene 1x afspelen bij start wachtperiode
