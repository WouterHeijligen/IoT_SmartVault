#!/usr/bin/env python3
"""
Uitgebreide Vosk Spraakherkenning Test met SPI OLED & USB-Microfoon
Thomas More Geel - IoT Essentials
Automatische sample rate detectie tegen ALSA PaErrorCode -9997
"""

import os
import sys
import json
import queue
import time
import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

print("[STAP 1/6] Script opgestart...")

# ==============================================================================
# 1. PADEN EN CONFIGURATIE CONTROLEREN
# ==============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MOGELIJKE_PADEN = [
    os.path.join(SCRIPT_DIR, "model"),
    os.path.join(SCRIPT_DIR, "..", "model"),
    os.path.expanduser("~/gpio/team_project/model")
]

MODEL_PATH = None
for pad in MOGELIJKE_PADEN:
    if os.path.exists(pad):
        MODEL_PATH = pad
        break

if not MODEL_PATH:
    print("\n[FOUT] Kan de Vosk 'model'-map nergens vinden!")
    sys.exit(1)

print(f"[STAP 2/6] Modelmap gevonden op: '{MODEL_PATH}'")

DEVICE_ID = 0  # Jouw USB PnP Sound Device

# Detecteer de hardware sample rate van de microfoon
try:
    dev_info = sd.query_devices(DEVICE_ID, 'input')
    SAMPLE_RATE = int(dev_info['default_samplerate'])
    print(f" -> Hardware sample rate van USB microfoon: {SAMPLE_RATE} Hz")
except Exception as e:
    print(f" -> [LET OP] Kon sample rate niet automatisch lezen ({e}), val terug op 44100 Hz")
    SAMPLE_RATE = 44100

audio_queue = queue.Queue()

# ==============================================================================
# 2. OLED DISPLAY INITIALISATIE (SPI)
# ==============================================================================
print("[STAP 3/6] Bezig met initialiseren van SPI OLED scherm...")
try:
    oled_reset = digitalio.DigitalInOut(board.D16)
    oled_cs = digitalio.DigitalInOut(board.D5)
    oled_dc = digitalio.DigitalInOut(board.D6)
    spi = board.SPI()

    WIDTH = 128
    HEIGHT = 64
    oled = adafruit_ssd1306.SSD1306_SPI(WIDTH, HEIGHT, spi, oled_dc, oled_reset, oled_cs)
    oled.fill(0)
    oled.show()
    print(" -> OLED succesvol geïnitialiseerd!")
except Exception as e:
    print(f" -> [LET OP] Kon OLED niet initialiseren: {e}")
    oled = None

font = ImageFont.load_default()

def teken_dashboard(status: str, tekst: str, audio_level: float = 0.0):
    """Tekent status, audiometer en herkende tekst op het OLED scherm."""
    if not oled:
        return

    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)

    def center_text(y, text):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = max(0, (oled.width - text_width) // 2)
        draw.text((x, y), text, font=font, fill=255)

    # Titel
    center_text(1, "SMART VAULT - VOSK")
    draw.line((0, 12, 127, 12), fill=255)

    # Status
    draw.text((2, 16), f"Status: {status[:14]}", font=font, fill=255)

    # Live Audiometer balk (reageert op audiovolume)
    balk_breedte = min(120, int(audio_level * 120))
    draw.rectangle((2, 28, 125, 32), outline=255, fill=0)
    if balk_breedte > 0:
        draw.rectangle((3, 29, 3 + balk_breedte, 31), fill=255)

    # Tekstvak
    weergave_tekst = f"> {tekst} <" if tekst else "[ Spreek nu ]"
    if len(weergave_tekst) > 18:
        weergave_tekst = ".." + weergave_tekst[-16:]

    bbox = draw.textbbox((0, 0), weergave_tekst, font=font)
    text_width = bbox[2] - bbox[0]
    box_width = text_width + 10
    box_left = max(2, (oled.width - box_width) // 2)
    box_right = min(125, box_left + box_width)

    draw.rectangle((box_left, 36, box_right, 52), outline=255, fill=0)
    center_text(40, weergave_tekst)

    # Onderbalk met live sample rate
    draw.line((0, 55, 127, 55), fill=255)
    draw.text((2, 56), "MIC: USB 0", font=font, fill=255)
    draw.text((70, 56), f"{int(SAMPLE_RATE/1000)}kHz", font=font, fill=255)

    oled.image(image)
    oled.show()

# ==============================================================================
# 3. VOSK AI MODEL LADEN
# ==============================================================================
print(f"[STAP 4/6] Vosk AI Model inladen op {SAMPLE_RATE} Hz...")
teken_dashboard("Laden...", "Model inladen")

t_start = time.time()
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLE_RATE)
print(f" -> Model succesvol geladen in {time.time() - t_start:.2f} seconden!")

# ==============================================================================
# 4. MICROFOON & AUDIO STREAM
# ==============================================================================
print(f"[STAP 5/6] USB-Microfoon initialiseren (Device ID: {DEVICE_ID}, Rate: {SAMPLE_RATE} Hz)...")

def audio_callback(indata, frames, time_info, status):
    """Callback die audioblokken aanlevert."""
    if status:
        print(f"\n[AUDIO STATUS WAARSCHUWING]: {status}", file=sys.stderr)
    audio_queue.put(bytes(indata))

print("[STAP 6/6] Spraakherkenning gestart!")
print("=================================================================")
print(" SPREEK NU IN DE MICROFOON (zeg bv: 'open sesam', 'test', 'hallo')")
print(" In de terminal zie je een live volume-meter (VU-meter).")
print(" Druk op CTRL+C om te stoppen.")
print("=================================================================\n")

teken_dashboard("Online", "")

last_terminal_print = 0
last_recognized_word = ""

try:
    # blocksize schaalt mee met de sample rate (~0.25 seconde audio per buffer)
    buffer_size = int(SAMPLE_RATE * 0.25)
    
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=buffer_size, device=DEVICE_ID,
                           dtype='int16', channels=1, callback=audio_callback):
        while True:
            data = audio_queue.get()

            # Bereken het actuele audiovolume (RMS) voor de live volumemeter
            audio_array = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_array.astype(float)**2))
            norm_level = min(1.0, rms / 3000.0)

            # Print elke 0.3s een live VU-meter in de console
            nu = time.time()
            if nu - last_terminal_print > 0.3:
                blokjes = int(norm_level * 25)
                meter = "█" * blokjes + "░" * (25 - blokjes)
                print(f"\r[MIC NIVEAU: {meter}] Laatst gehoord: '{last_recognized_word}'", end="", flush=True)
                last_terminal_print = nu

            # Vosk herkenning
            if recognizer.AcceptWaveform(data):
                res = json.loads(recognizer.Result())
                woord = res.get("text", "").strip()
                if woord:
                    last_recognized_word = woord
                    print(f"\n\n>> [DEFINITIEF HERKEND]: \"{woord}\"\n")
                    teken_dashboard("Herkend!", woord, audio_level=norm_level)
            else:
                partial_res = json.loads(recognizer.PartialResult())
                partial = partial_res.get("partial", "").strip()
                if partial:
                    teken_dashboard("Luistert...", partial, audio_level=norm_level)

except KeyboardInterrupt:
    print("\n\n[AFSLUITEN] Gestopt door gebruiker.")
except Exception as e:
    print(f"\n\n[ONVERWACHTE FOUT]: {e}")
finally:
    if oled:
        oled.fill(0)
        oled.show()
    print("Programma netjes afgesloten.")