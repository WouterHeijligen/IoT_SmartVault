#!/usr/bin/env python3

import os
import subprocess

import requests
from dotenv import load_dotenv

load_dotenv()


class Notificaties:
    """Push-notificaties (ntfy.sh) en sirene via de Bluetooth speaker."""

    def __init__(self):
        self.topic = os.getenv("NTFY_TOPIC", "tm_smart_vault_bart_2026")

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

    def sirene(self):
        """Speelt een waarschuwingsgeluid af (non-blocking)."""

        try:
            subprocess.Popen(
                ["speaker-test", "-t", "sine", "-f", "880", "-l", "1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"[AUDIO] Kon Bluetooth sirene niet afspelen: {e}")
