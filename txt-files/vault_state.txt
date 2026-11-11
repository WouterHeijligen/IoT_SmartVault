#!/usr/bin/env python3
import threading

SECRET_PIN = [4, 7, 2]
BYPASS_VOICE_2FA = False
VOICE_PASSPHRASE = "open"
VOICE_TIMEOUT_S = 20.0
LUX_SABOTAGE_THRESHOLD = 50.0
TEMP_FIRE_THRESHOLD_C = 30.0
FIRE_CONFIRM_READINGS = 10
HYSTERESIS_10BIT = 12
MAX_PIN_ATTEMPTS = 3
WRONG_PIN_BLINK_S = 5.0
PIN_LOCKOUT_S = 10.0
LOITER_DISTANCE_CM = 40.0
LOITER_ALARM_S = 15.0
PERIMETER_STALE_S = 10.0
TELEMETRY_INTERVAL_S = 15.0  # ThingSpeak rate limit
ALARM_PUSH_INTERVAL_S = 120.0
MODE_CODES = {"PIN_INPUT": 0, "VOICE_2FA": 1, "UNLOCKED": 2, "ALARM": 3, "LOCKOUT": 4}


class VaultState:
    def __init__(self):
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
        self.perimeter_ts = 0.0  # monotonic
        self.loiter_since = None  # monotonic
        self.last_activity = 0.0  # monotonic
        self.alarm_reason = ""
        self.unlock_executed = False
        self.lock_executed = True  # Start vergrendeld: één motorbeweging per overgang
        self.alarm_notified = False
        self.motor_busy = False
        self.wrong_pin_until = 0.0  # monotonic
        self.lockout_until = 0.0  # monotonic
        self.lockout_push_pending = False
        self.lockout_siren_pending = False
