#!/usr/bin/env python3
import json
import os
import queue
import sys
import time

from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class VoiceRecognition:
    def __init__(self):
        self.model_pad = os.getenv("VOSK_MODEL", os.path.join(SCRIPT_DIR, "model-en"))
        self.device = int(os.getenv("MIC_DEVICE", "0"))
        self.sample_rate = 44100
        self.model = None
        self._sd = None

        print("Voice recognition initialized")

    def laad(self):
        if self.model is not None:
            return

        # Lazy import zodat BYPASS_VOICE_2FA zonder Vosk/sounddevice werkt
        import sounddevice as sd
        from vosk import Model

        self._sd = sd
        try:
            info = sd.query_devices(self.device, "input")
            self.sample_rate = int(info["default_samplerate"])
        except Exception as e:
            print(f"[VOICE] Sample rate niet leesbaar ({e}), gebruik {self.sample_rate} Hz")

        if not os.path.isdir(self.model_pad):
            raise FileNotFoundError(f"Vosk-modelmap niet gevonden: {self.model_pad}")

        print(f"[VOICE] Model laden uit '{self.model_pad}' ({self.sample_rate} Hz, device {self.device})...")
        self.model = Model(self.model_pad)

    def luister(self, timeout_s=10.0, stop=None, doelzin=None):
        from vosk import KaldiRecognizer

        self.laad()

        audio = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[VOICE AUDIO] {status}", file=sys.stderr)
            audio.put(bytes(indata))

        recognizer = (
            KaldiRecognizer(self.model, self.sample_rate, json.dumps([doelzin.lower(), "[unk]"]))
            if doelzin
            else KaldiRecognizer(self.model, self.sample_rate)
        )
        laatste = ""
        einde = time.monotonic() + timeout_s

        with self._sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=int(self.sample_rate * 0.5),
            device=self.device,
            dtype="int16",
            channels=1,
            latency="high",
            callback=callback,
        ):
            while time.monotonic() < einde:
                if stop is not None and stop():
                    break

                try:
                    data = audio.get(timeout=0.3)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    tekst = json.loads(recognizer.Result()).get("text", "").strip()
                else:
                    tekst = json.loads(recognizer.PartialResult()).get("partial", "").strip()

                if not tekst:
                    continue

                if tekst != laatste:
                    laatste = tekst
                    print(f"[VOICE] Gehoord: '{tekst}'")

                if doelzin and doelzin in tekst.lower():
                    return tekst

        return laatste

    def close(self):
        self.model = None
        print("Voice recognition afgesloten")
