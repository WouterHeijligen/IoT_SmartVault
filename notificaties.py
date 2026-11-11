#!/usr/bin/env python3
import os
import subprocess
import threading
import time

import requests
from dotenv import load_dotenv

load_dotenv()


class Notificaties:
    def __init__(self):
        self.topic = os.getenv("NTFY_TOPIC")
        self.speaker_mac = os.getenv("BT_SPEAKER_MAC")
        self.sirene_bestand = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "sirene.wav"
        )
        self._sirene_proces = None
        self._sirene_lock = threading.Lock()

    def start_speaker_verbinding(self):
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
        with self._sirene_lock:
            if self._sirene_proces and self._sirene_proces.poll() is None:
                self._sirene_proces.terminate()

    def sirene(self):
        with self._sirene_lock:
            if self._sirene_proces and self._sirene_proces.poll() is None:
                return
            try:
                self._sirene_proces = subprocess.Popen(
                    self._sirene_commando(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                threading.Thread(
                    target=self._meld_sirene_fout, args=(self._sirene_proces,), daemon=True
                ).start()
            except Exception as e:
                print(f"[AUDIO] Kon sirene niet afspelen: {e}")

    def _sirene_commando(self):
        # PipeWire vereist onder sudo de runtime-dir van de ingelogde gebruiker
        sudo_user = os.getenv("SUDO_USER")
        if os.geteuid() == 0 and sudo_user:
            uid = os.getenv("SUDO_UID", "1000")
            return [
                "sudo", "-u", sudo_user,
                f"XDG_RUNTIME_DIR=/run/user/{uid}",
                "pw-play", self.sirene_bestand,
            ]
        return ["pw-play", self.sirene_bestand]

    def _meld_sirene_fout(self, proces):
        fout = proces.communicate()[1]
        # -15 = SIGTERM via stop_sirene()
        if proces.returncode not in (0, -15):
            print(f"[AUDIO] pw-play faalde ({proces.returncode}): {fout.strip()}")

    def stuur_push(self, bericht):
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
