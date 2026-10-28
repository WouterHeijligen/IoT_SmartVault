#!/usr/bin/env python3

import os
import subprocess
import threading
import time

import requests
from dotenv import load_dotenv

load_dotenv()


class Notificaties:
    """Push-notificaties (ntfy.sh) en sirene via de Bluetooth speaker."""

    def __init__(self):
        self.topic = os.getenv("NTFY_TOPIC", "tm_smart_vault_bart_2026")
        self.speaker_mac = os.getenv("BT_SPEAKER_MAC", "33:A8:8C:0F:CC:A0")
        self.sirene_bestand = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "sirene.wav"
        )
        self._sirene_proces = None
        self._sirene_lock = threading.Lock()

    def start_speaker_verbinding(self):
        """Houdt de Bluetooth speaker verbonden (verbindt opnieuw na uitval)."""

        threading.Thread(target=self._speaker_loop, daemon=True).start()

    def _speaker_loop(self):
        while True:
            try:
                info = subprocess.run(
                    ["bluetoothctl", "info", self.speaker_mac],
                    capture_output=True, text=True, timeout=10,
                ).stdout
                if "Connected: yes" not in info:
                    print(f"[AUDIO] Speaker {self.speaker_mac} niet verbonden, opnieuw verbinden...")
                    subprocess.run(
                        ["bluetoothctl", "connect", self.speaker_mac],
                        capture_output=True, text=True, timeout=20,
                    )
            except Exception as e:
                print(f"[AUDIO] Bluetooth-controle mislukt: {e}")
            time.sleep(30)

    def stop_sirene(self):
        """Stopt de sirene meteen (na reset van het alarm)."""

        with self._sirene_lock:
            if self._sirene_proces and self._sirene_proces.poll() is None:
                self._sirene_proces.terminate()

    def sirene(self):
        """Speelt sirene.wav af via de standaard audio-uitvoer (non-blocking, geen overlap)."""

        with self._sirene_lock:
            if self._sirene_proces and self._sirene_proces.poll() is None:
                return
            try:
                self._sirene_proces = subprocess.Popen(
                    ["pw-play", self.sirene_bestand],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                threading.Thread(
                    target=self._meld_sirene_fout, args=(self._sirene_proces,), daemon=True
                ).start()
            except Exception as e:
                print(f"[AUDIO] Kon sirene niet afspelen: {e}")

    def _meld_sirene_fout(self, proces):
        fout = proces.communicate()[1]
        if proces.returncode not in (0, -15):
            print(f"[AUDIO] pw-play faalde ({proces.returncode}): {fout.strip()}")

    def stuur_push(self, bericht):
        """Stuurt een push-notificatie naar je smartphone via ntfy.sh."""

        print(f"[NTFY PUSH] Versturen naar '{self.topic}': {bericht}")

        try:
            resp = requests.post(
                f"https://ntfy.sh/{self.topic}",
                data=bericht.encode("utf-8"),
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
