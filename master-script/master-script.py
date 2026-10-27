#!/usr/bin/env python3
"""
SMART VAULT MASTER CONTROLLER (v1.3) - Raspberry Pi 5
Thomas More Geel - IoT Essentials Groepsproject
Architectuur: Multithreaded State Machine met SPI0 (MCP3008 + 7-pins SSD1306 OLED),
              I2C (BH1750), Active-Low Relais Motor-Interlock, 28BYJ-48 Full-Step Pusher, PWM RGB & MQTT.
"""

import time
import threading
import subprocess
import requests
import board
import busio
import digitalio
import pwmio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
from adafruit_mcp3xxx.mcp3008 import MCP3008
from adafruit_mcp3xxx.analog_in import AnalogIn
import paho.mqtt.client as mqtt

# ==============================================================================
# 1. CONFIGURATIE & DREMPELWAARDEN
# ==============================================================================
SECRET_PIN = [4, 7, 2]           # De 3-cijferige kluiscode (in te voeren via potmeter 0-9)
BYPASS_VOICE_2FA = True          # Zet op False zodra de USB-microfoon & Vosk (PP 8) gekoppeld zijn!
VOICE_PASSPHRASE = "open sesam"  # Geheime gesproken passphrase voor Factor 2

LUX_SABOTAGE_THRESHOLD = 5000.0  # Boven 50 lux bij gesloten kluis = direct SABOTAGE ALARM (voorlopig op 5000 lux gezet voor testen in daglicht)
TEMP_FIRE_THRESHOLD_C = 25.0     # Boven 45 °C = direct BRANDALARM (voorlopig op 25 °C gezet voor testen in kamerwarmte)
HYSTERESIS_10BIT = 12            # Dode band (op 0..1023) tegen flikkeren tussen twee cijfers
STEPPER_OPEN_STEPS = 2048        # 256 full-steps = 180 graden (duwt de 3D-geprinte pin naar buiten)
STEPPER_STEP_DELAY = 0.010       # 10 ms per stap voor maximaal koppel zonder stalling

# Lokale MQTT Broker op de Pi 5 (ontvangt afstand van de Pico WH)
MQTT_LOCAL_BROKER = "127.0.0.1"
MQTT_LOCAL_PORT = 1883
MQTT_TOPIC_PERIMETER = "vault/perimeter/distance"

# Cloud configuratie (voor PP 8: ntfy.sh push & ThingSpeak telemetry)
NTFY_TOPIC = "tm_smart_vault_bart_2026"  # Vervang door jullie eigen ntfy-topic (bv. tm_smart_vault_jan)
THINGSPEAK_WRITE_API_KEY = "U5EXRHBC2NGNG1PR"

# ==============================================================================
# 2. GEDEELDE SYSTEEMSTATUS (THREAD-SAFE MET LOCK)
# ==============================================================================
class VaultState:
    def __init__(self):
        self.lock = threading.Lock()
        self.spi_lock = threading.Lock()  # Voorkomt gelijktijdige SPI-toegang tussen ADC en OLED
        self.running = True
        # Modi: "PIN_INPUT", "VOICE_2FA", "UNLOCKED", "ALARM"
        self.mode = "PIN_INPUT"
        self.current_digit = 0          # Live cijfer (0-9) van de potmeter
        self.entered_pin = []           # Lijst met al bevestigde cijfers, bv. [4, 7]
        self.failed_attempts = 0        # Aantal foute pincode-pogingen
        self.lux = 0.0                  # BH1750 lichtwaarde (lux)
        self.temp_c = 20.0              # LM35 temperatuur (°C)
        self.perimeter_cm = 999.0       # HC-SR04 afstand vanaf Pico WH (cm)
        self.loitering_alert = False    # True als iemand > 5s binnen 40 cm staat
        self.alarm_reason = ""          # Reden van het alarm op OLED / ntfy
        self.unlock_executed = False    # Zorgt dat de stappenmotor 1x draait per ontgrendeling
        self.lock_executed = True       # Zorgt dat de stappenmotor 1x terugdraait per vergrendeling
        self.alarm_notified = False     # Zorgt dat ntfy push 1x verstuurd wordt per alarm

state = VaultState()

# ==============================================================================
# 3. HARDWARE INITIALISATIE (CONFORM DEFINITIEVE GPIO PIN-MAP)
# ==============================================================================
# A. I2C Bus (GPIO 2 = SDA, GPIO 3 = SCL) -> BH1750 (0x23 Sabotage)
i2c = busio.I2C(board.SCL, board.SDA)
BH1750_ADDR = 0x23
BH1750_CMD_HRES = bytearray([0x10])

# B. SPI0 Bus (GPIO 11=SCLK, GPIO 10=MOSI, GPIO 9=MISO) -> MCP3008 ADC & 7-pins SSD1306 SPI OLED
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# MCP3008 ADC (CS op GPIO 16 / Fysieke Pin 36 om Pi 5 'GPIO busy' op CE0 te vermijden)
adc_cs = digitalio.DigitalInOut(board.D16)
mcp = MCP3008(spi, adc_cs)
adc_pot = AnalogIn(mcp, 0)    # CH0 (kanaal 0): 10k Potmeter voor cijferslot (0-9)
adc_lm35 = AnalogIn(mcp, 1)   # CH1 (kanaal 1): LM35 temperatuursensor

# 0.96" 7-pins SSD1306 SPI OLED (RES=GPIO 5/Pin 29, DC=GPIO 25/Pin 22, CS=GND -> None)
try:
    oled_res = digitalio.DigitalInOut(board.D5)   # Pin 29 (GPIO 5)
    oled_dc = digitalio.DigitalInOut(board.D25)   # Pin 22 (GPIO 25)
    oled_cs = None                                # CS hangt fysiek aan GND!
    oled = adafruit_ssd1306.SSD1306_SPI(128, 64, spi, oled_dc, oled_res, oled_cs)
    oled.fill(0)
    oled.show()
    OLED_AVAILABLE = True
except Exception as e:
    print(f"[WAARSCHUWING] SPI OLED niet gevonden: {e}")
    OLED_AVAILABLE = False

# C. Bevestigingsknop Cijferslot op GPIO 4 (Interne Pull-Up -> Active-Low: False = Ingedrukt)
btn_confirm = digitalio.DigitalInOut(board.D4)
btn_confirm.direction = digitalio.Direction.INPUT
btn_confirm.pull = digitalio.Pull.UP

# D. 5V Relais Motor Safety Interlock op GPIO 24 (Active-Low: True = UIT/Stroomloos, False = AAN)
relay_interlock = digitalio.DigitalInOut(board.D24)
relay_interlock.direction = digitalio.Direction.OUTPUT
relay_interlock.value = True  # Veilige startpositie: NO-contact staat open (motor heeft 0V)

# E. 28BYJ-48 Stappenmotor via ULN2003 op GPIO 17, 27, 22, 23
STEPPER_PINS = [board.D17, board.D27, board.D22, board.D23]
stepper_coils = []
for pin in STEPPER_PINS:
    coil = digitalio.DigitalInOut(pin)
    coil.direction = digitalio.Direction.OUTPUT
    coil.value = False
    stepper_coils.append(coil)

# Full-Step sequentie (2 spoelen tegelijk bekrachtigd voor maximaal duw-koppel)
FULL_STEP_SEQ = [
    [True,  True,  False, False],
    [False, True,  True,  False],
    [False, False, True,  True],
    [True,  False, False, True],
]

# F. RGB LED via PWM op GPIO 12 (Rood), GPIO 13 (Groen), GPIO 19 (Blauw)
pwm_r = pwmio.PWMOut(board.D12, frequency=1000, duty_cycle=0)
pwm_g = pwmio.PWMOut(board.D13, frequency=1000, duty_cycle=0)
pwm_b = pwmio.PWMOut(board.D19, frequency=1000, duty_cycle=0)

def set_rgb_percent(r_pct: int, g_pct: int, b_pct: int):
    """Zet RGB LED kleur van 0..100% om naar 16-bit PWM duty cycle (0..65535)."""
    pwm_r.duty_cycle = int((r_pct / 100.0) * 65535)
    pwm_g.duty_cycle = int((g_pct / 100.0) * 65535)
    pwm_b.duty_cycle = int((b_pct / 100.0) * 65535)


# ==============================================================================
# 4. THREAD 1: DRUKKNOP AFHANDELING (50 Hz - Puur GPIO, geen SPI-storing!)
# ==============================================================================
def thread_potmeter_and_button():
    """
    Controleert op 50 Hz de bevestigingsknop (GPIO 4) met flankdetectie en debounce.
    """
    last_btn_state = True  # True = niet ingedrukt (Pull-Up)

    while state.running:
        try:
            current_btn = btn_confirm.value
            if not current_btn and last_btn_state:  # Knop net ingedrukt (falling edge)
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
                                print(f"[AUTH] Foute pincode! Poging {state.failed_attempts}/3")
                                state.entered_pin = []
                                if state.failed_attempts >= 3:
                                    state.mode = "ALARM"
                                    state.alarm_reason = "3x FOUTE PINCODE"

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

                time.sleep(0.25)  # Debounce tijd na indrukken

            last_btn_state = current_btn

        except Exception as e:
            print(f"[FOUT in Knop Thread]: {e}")

        time.sleep(0.02)  # 50 Hz polling


# ==============================================================================
# 5. THREAD 2: I2C SABOTAGE (BH1750) & SPI OLED UI (SSD1306) (6 Hz)
# ==============================================================================
def read_bh1750_lux() -> float:
    """Leest de BH1750 lichtsensor (0x23) low-level uit op de I2C-bus."""
    buf = bytearray(2)
    if i2c.try_lock():
        try:
            i2c.writeto_then_readfrom(BH1750_ADDR, BH1750_CMD_HRES, buf)
        finally:
            i2c.unlock()
    return ((buf[0] << 8) | buf[1]) / 1.2

def thread_i2c_sensors_and_oled():
    """
    Leest op 10 Hz de sensoren uit en ververst het OLED-scherm.
    Door oled.show() onmiddellijk (< 0.1 ms) na het lezen van de MCP3008 uit te voeren,
    zijn de 3 SPI-bytes van de MCP3008 onzichtbaar op een 6-pins OLED (zonder CS-pin).
    """
    font = ImageFont.load_default()
    last_digit = 0

    while state.running:
        try:
            # 1. Lees MCP3008 (CH0 potmeter & CH1 LM35) en herstel DIRECT (<0.1ms) het OLED-scherm
            with state.spi_lock:
                raw_10bit = adc_pot.value >> 6
                temp_c = (adc_lm35.voltage * 1000.0) / 10.0
                if OLED_AVAILABLE:
                    oled.show()  # Wist binnen 0.1 ms de 3 ADC-bytes in de linkerbovenhoek!

            candidate_digit = (raw_10bit * 10) // 1024
            if candidate_digit > 9:
                candidate_digit = 9

            if candidate_digit != last_digit:
                border_raw = (max(candidate_digit, last_digit) * 1024) // 10
                if abs(raw_10bit - border_raw) >= HYSTERESIS_10BIT:
                    last_digit = candidate_digit

            # 2. Lees BH1750 lichtwaarde via I2C
            lux = read_bh1750_lux()

            with state.lock:
                state.current_digit = last_digit
                state.temp_c = temp_c
                state.lux = lux

                # Brandcheck (LM35)
                if temp_c > TEMP_FIRE_THRESHOLD_C and state.mode != "ALARM":
                    state.mode = "ALARM"
                    state.alarm_reason = f"BRAND! T={temp_c:.1f}C"

                # Sabotagecheck (BH1750)
                if lux > LUX_SABOTAGE_THRESHOLD and state.mode not in ("UNLOCKED", "ALARM"):
                    print(f"[SABOTAGE] Licht gedetecteerd in gesloten kluis ({lux:.1f} lux)!")
                    state.mode = "ALARM"
                    state.alarm_reason = f"BRAAK! ({int(lux)} lx)"

                mode = state.mode
                digit = state.current_digit
                pin_so_far = list(state.entered_pin)
                loitering = state.loitering_alert
                reason = state.alarm_reason

            # 3. Teken het nieuwe frame en stuur naar het OLED-scherm
            if OLED_AVAILABLE:
                image = Image.new("1", (oled.width, oled.height))
                draw = ImageDraw.Draw(image)

                top_bar = f"L:{int(lux)}lx T:{temp_c:.1f}C"
                if loitering:
                    top_bar += " [LOITER!]"
                draw.text((2, 0), top_bar, font=font, fill=255)
                draw.line((0, 12, 127, 12), fill=255)

                if mode == "PIN_INPUT":
                    draw.text((2, 16), "STATUS: VERGRENDELD", font=font, fill=255)
                    slots = [str(pin_so_far[i]) if i < len(pin_so_far) else "_" for i in range(3)]
                    draw.text((2, 30), f"PIN: {'  '.join(slots)}", font=font, fill=255)
                    draw.text((2, 46), f"Draai: [ {digit} ] (Druk=OK)", font=font, fill=255)

                elif mode == "VOICE_2FA":
                    draw.text((2, 18), "FACTOR 1 (PIN): OK!", font=font, fill=255)
                    draw.text((2, 34), "SPREEK WACHTWOORD IN:", font=font, fill=255)
                    draw.text((2, 48), f'"{VOICE_PASSPHRASE.upper()}"', font=font, fill=255)

                elif mode == "UNLOCKED":
                    draw.text((10, 22), "** KLUIS GEOPEND **", font=font, fill=255)
                    draw.text((4, 42), "Druk knop om te sluiten", font=font, fill=255)

                elif mode == "ALARM":
                    draw.rectangle((0, 14, 127, 63), outline=255, fill=0)
                    draw.text((14, 16), "!!! ALARM ACTIEF !!!", font=font, fill=255)
                    draw.text((6, 30), reason[:20], font=font, fill=255)
                    if temp_c <= TEMP_FIRE_THRESHOLD_C and lux <= LUX_SABOTAGE_THRESHOLD:
                        draw.text((6, 46), "Veilig -> Druk=Reset", font=font, fill=255)
                    else:
                        draw.text((6, 46), "Druk knop voor Reset", font=font, fill=255)

                with state.spi_lock:
                    oled.image(image)
                    oled.show()

        except Exception as e:
            print(f"[FOUT in Sensor/OLED Thread]: {e}")

        time.sleep(0.10)  # 10 Hz verversing


# ==============================================================================
# 6. THREAD 3: ACTUATOREN (RELAIS INTERLOCK, STAPPENMOTOR, RGB PWM & BT AUDIO)
# ==============================================================================
def rotate_stepper_full_step(steps: int, forward: bool = True):
    """Draait de 28BYJ-48 stappenmotor in Full-Step modus (dubbel koppel)."""
    seq = FULL_STEP_SEQ if forward else list(reversed(FULL_STEP_SEQ))
    for step_idx in range(steps):
        pattern = seq[step_idx % 4]
        for coil, val in zip(stepper_coils, pattern):
            coil.value = val
        time.sleep(STEPPER_STEP_DELAY)
    # Zet alle spoelen weer uit na beweging
    for coil in stepper_coils:
        coil.value = False


def trigger_bluetooth_siren():
    """Speelt een waarschuwingsgeluid af over de gekoppelde Bluetooth speaker (non-blocking)."""
    try:
        subprocess.Popen(
            ["speaker-test", "-t", "sine", "-f", "880", "-l", "1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"[AUDIO] Kon Bluetooth sirene niet afspelen: {e}")


def thread_actuators_and_audio():
    """
    Stuurt de RGB LED (PWM), het 5V Relais (Motor Safety Interlock) en de
    28BYJ-48 stappenmotor met 3D-geprinte duw-pin aan.
    """
    blink_toggle = False
    last_siren_time = 0.0

    while state.running:
        with state.lock:
            mode = state.mode
            need_unlock_motion = (mode == "UNLOCKED" and not state.unlock_executed)
            if need_unlock_motion:
                state.unlock_executed = True

            need_lock_motion = (mode == "PIN_INPUT" and not state.lock_executed)
            if need_lock_motion:
                state.lock_executed = True

        # 1A. Kluis OPENEN (enkel vooruit draaien!)
        if need_unlock_motion:
            set_rgb_percent(0, 100, 0)  # Groen
            print("[INTERLOCK] 5V Relais AAN -> Kluis openen...")
            relay_interlock.value = False  # Relais AAN
            time.sleep(0.25)

            print(f"[STAPPENMOTOR] Opent kluis ({STEPPER_OPEN_STEPS} full-steps vooruit)...")
            rotate_stepper_full_step(STEPPER_OPEN_STEPS, forward=True)

            relay_interlock.value = True   # Relais weer UIT (motor stroomloos terwijl kluis open staat)
            print("[INTERLOCK] Kluis staat open (motor stroomloos).")

        # 1B. Kluis SLUITEN (pas als op de knop is gedrukt!)
        if need_lock_motion:
            set_rgb_percent(0, 0, 80)   # Blauw
            print("[INTERLOCK] 5V Relais AAN -> Kluis sluiten...")
            relay_interlock.value = False  # Relais AAN
            time.sleep(0.25)

            print(f"[STAPPENMOTOR] Sluit kluis ({STEPPER_OPEN_STEPS} full-steps achteruit)...")
            rotate_stepper_full_step(STEPPER_OPEN_STEPS, forward=False)

            relay_interlock.value = True   # Relais weer UIT
            print("[INTERLOCK] Kluis is weer vergrendeld.")

        # 2. Visuele status (RGB PWM) & Bluetooth Sirene
        if mode == "PIN_INPUT":
            relay_interlock.value = True   # Zekerstellen dat motor stroomloos is
            set_rgb_percent(0, 0, 80)      # Blauw tijdens code-invoer

        elif mode == "VOICE_2FA":
            set_rgb_percent(80, 30, 0)     # Oranje/Geel tijdens wachten op stem

        elif mode == "UNLOCKED":
            set_rgb_percent(0, 100, 0)     # Groen

        elif mode == "ALARM":
            relay_interlock.value = True   # Motor blijft gegarandeerd stroomloos tijdens alarm!
            blink_toggle = not blink_toggle
            if blink_toggle:
                set_rgb_percent(100, 0, 0) # Fel Rood knipperend
            else:
                set_rgb_percent(0, 0, 0)

            # Speel elke 4 seconden een sirene-puls over de Bluetooth speaker
            if time.time() - last_siren_time > 4.0:
                trigger_bluetooth_siren()
                last_siren_time = time.time()

        time.sleep(0.15)


# ==============================================================================
# 7. THREAD 4: CLOUD INTEGRATIES (THINGSPEAK & NTFY.SH)
# ==============================================================================
def send_ntfy_alert(message: str):
    """
    Stuurt direct een push-notificatie naar je smartphone via ntfy.sh.
    Open op je gsm de ntfy app (of https://ntfy.sh) en abonneer op NTFY_TOPIC.
    """
    print(f"[NTFY PUSH] Versturen naar '{NTFY_TOPIC}': {message}")
    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": "Smart Vault Alarm!",
                "Priority": "high",
                "Tags": "rotating_light,lock"
            },
            timeout=5,
        )
        if resp.status_code == 200:
            print("[NTFY PUSH] Succesvol afgeleverd op smartphone!")
        else:
            print(f"[NTFY FOUT] HTTP status {resp.status_code}")
    except Exception as e:
        print(f"[NTFY FOUT] Kon push alert niet versturen: {e}")


def publish_thingspeak_telemetry(lux: float, temp_c: float, distance_cm: float, mode: str):
    """
    Stuurt elke 15 seconden alle telemetrie (Pi 5 + Pico WH) naar ThingSpeak:
    - field1 = Lichtsterkte (Lux - BH1750)
    - field2 = Temperatuur (°C - LM35)
    - field3 = Perimeter Afstand (cm - HC-SR04 vanaf Pico WH via MQTT)
    - field4 = Kluis Status Code (0=VERGRENDELD, 1=2FA, 2=GEOPEND, 3=ALARM)
    """
    if THINGSPEAK_WRITE_API_KEY == "JOUW_WRITE_API_KEY_HIER" or not THINGSPEAK_WRITE_API_KEY:
        print(
            f"[THINGSPEAK - Geen API Key] Lux={lux:.1f}, Temp={temp_c:.1f}C, "
            f"Afstand={distance_cm:.1f}cm, Mode={mode}"
        )
        return

    mode_map = {"PIN_INPUT": 0, "VOICE_2FA": 1, "UNLOCKED": 2, "ALARM": 3}
    mode_code = mode_map.get(mode, 0)

    try:
        resp = requests.post(
            "https://api.thingspeak.com/update.json",
            json={
                "api_key": THINGSPEAK_WRITE_API_KEY,
                "field1": round(lux, 1),
                "field2": round(temp_c, 1),
                "field3": round(distance_cm, 1),
                "field4": mode_code,
                "status": mode,
            },
            timeout=5,
        )
        if resp.status_code == 200 and resp.text != "0":
            print(f"[THINGSPEAK] Update #{resp.text} OK -> Lux={lux:.1f}, Temp={temp_c:.1f}C, Dist={distance_cm:.1f}cm, Mode={mode}")
        else:
            print(f"[THINGSPEAK WAARSCHUWING] Geweigerd (15s rate-limit of foute key): {resp.text}")
    except Exception as e:
        print(f"[THINGSPEAK FOUT] Kon data niet versturen: {e}")


def thread_cloud_and_alerts():
    """
    Draait op de achtergrond voor periodieke ThingSpeak updates (elke 15s)
    en directe ntfy.sh push-meldingen bij alarm.
    """
    last_thingspeak_push = 0.0

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

        # 1. Directe push-notificatie bij nieuw alarm
        if should_alert:
            send_ntfy_alert(f"SMART VAULT ALARM: {reason} (Lux={lux:.1f}, Temp={temp_c:.1f}C)")

        # 2. Elke 15 seconden telemetrie naar ThingSpeak
        if time.time() - last_thingspeak_push >= 15.0:
            publish_thingspeak_telemetry(lux, temp_c, dist, mode)
            last_thingspeak_push = time.time()

        time.sleep(0.5)


# ==============================================================================
# 8. LOKALE MQTT SUBSCRIBER (VOOR PICO WH PERIMETER SENSOR)
# ==============================================================================
def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[MQTT] Verbonden met lokale broker ({MQTT_LOCAL_BROKER}). Subscribed op {MQTT_TOPIC_PERIMETER}")
        client.subscribe(MQTT_TOPIC_PERIMETER, qos=0)
    else:
        print(f"[MQTT] Verbinding mislukt met code: {reason_code}")


def on_mqtt_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8").strip()
        dist_cm = float(payload_str)
        with state.lock:
            state.perimeter_cm = dist_cm
            state.loitering_alert = (dist_cm < 40.0)
    except ValueError:
        pass


# ==============================================================================
# 9. MAIN STARTUP & GRACEFUL SHUTDOWN
# ==============================================================================
def main():
    print("=====================================================")
    print(" 🔐 SMART VAULT CONTROLLER v1.3 OPSTARTEN...")
    print(f"    Geheime Pincode : {SECRET_PIN}")
    print(f"    Voice 2FA Bypass: {BYPASS_VOICE_2FA}")
    print("=====================================================")

    # Start lokale MQTT client op de achtergrond
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Pi5_SmartVault_Master")
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    try:
        mqtt_client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, keepalive=60)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"[MQTT WAARSCHUWING] Lokale broker nog niet bereikbaar: {e}")

    # Start de 4 worker threads
    threads = [
        threading.Thread(target=thread_potmeter_and_button, name="SPI-Pot-Button", daemon=True),
        threading.Thread(target=thread_i2c_sensors_and_oled, name="I2C-BH1750-OLED", daemon=True),
        threading.Thread(target=thread_actuators_and_audio, name="Actuators-PWM", daemon=True),
        threading.Thread(target=thread_cloud_and_alerts, name="Cloud-Placeholders", daemon=True),
    ]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Bezig met veilig afsluiten en vrijgeven van GPIO-pinnen...")
        state.running = False
        time.sleep(0.3)
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        relay_interlock.value = True  # Zorg dat de motor stroomloos achterblijft
        relay_interlock.deinit()
        btn_confirm.deinit()
        for coil in stepper_coils:
            coil.value = False
            coil.deinit()
        pwm_r.deinit()
        pwm_g.deinit()
        pwm_b.deinit()
        if OLED_AVAILABLE:
            oled.fill(0)
            oled.show()
        print("[SHUTDOWN] Voltooid.")


if __name__ == "__main__":
    main()
