#!/usr/bin/env python3
"""
================================================================================
BESTAND: notificaties.py
DOEL:    Alarmering op afstand (Pushbericht naar smartphone) & Sirene (Bluetooth).
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
Als er wordt ingebroken, er brand uitbreekt, of iemand 3x een foute pincode
intoetst, doet deze klasse twee dingen:
1. LOKAAL AFSCHRIKKEN (`sirene`):
   Speelt het geluidsbestand `sirene.wav` af via de gekoppelde Bluetooth-speaker.
2. OP AFSTAND WAARSCHUWEN (`stuur_push`):
   Stuurt via internet (HTTPS POST met de `requests` bibliotheek) een melding
   naar de gratis app `ntfy.sh` op je smartphone!

💡 TWEE SLIMME DINGEN OM TE NOEMEN TIJDENS JE PRESENTATIE:
- "Waarom crasht de kluis niet als het internet of de speaker uitvalt?"
  Alle netwerk- en Bluetooth-acties zitten in een `try ... except`-blok. Als
  wifi even hapert, print het programma netjes een melding, maar blijven het
  slot en het scherm gewoon doorwerken!
- "Hoe werkt de sirene zonder dat het programma bevriest?"
  We starten het afspelen van `sirene.wav` met `subprocess.Popen` op de
  achtergrond. Zo kan de kluis tegelijkertijd het rode zwaailicht laten
  knipperen én reageren op de reset-knop (`stop_sirene`).
"""

import os
import subprocess
import threading
import time

import requests
from dotenv import load_dotenv

# Laad de geheime instellingen (zoals NTFY_TOPIC en BT_SPEAKER_MAC) uit het `.env` bestand
load_dotenv()


class Notificaties:
    """
    Regelt zowel de push-meldingen naar de smartphone als het sirenegeluid via de Bluetooth-speaker.
    """

    def __init__(self):
        """
        Haalt het ntfy-onderwerp (topic) en het MAC-adres van de Bluetooth-speaker
        uit het `.env` bestand en zoekt het pad naar `sirene.wav` op.
        """
        self.topic = os.getenv("NTFY_TOPIC")
        self.speaker_mac = os.getenv("BT_SPEAKER_MAC")
        # Zoek `sirene.wav` in dezelfde map als waar dit Python-bestand staat
        self.sirene_bestand = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "sirene.wav"
        )
        # Houdt bij of het geluidsprogramma (`pw-play`) op dit moment al aan het spelen is
        self._sirene_proces = None
        # Slotje zodat twee threads nooit tegelijk de sirene starten of stoppen
        self._sirene_lock = threading.Lock()

    def start_speaker_verbinding(self):
        """
        Start op de achtergrond een hulpfunctie (`_speaker_loop`) die controleert
        of de Bluetooth-speaker nog verbonden is, en zo nodig opnieuw verbindt.
        """
        threading.Thread(target=self._speaker_loop, daemon=True).start()

    def _speaker_loop(self):
        """
        Controleert elke 30 seconden via het Linux-commando `bluetoothctl` of de
        Bluetooth-speaker nog verbonden is ("Connected: yes").
        Zo niet, dan verbindt de Raspberry Pi automatisch opnieuw!
        """
        while True:
            try:
                # Vraag de status van de Bluetooth-speaker op bij Linux
                info = subprocess.run(
                    ["bluetoothctl", "info", self.speaker_mac],
                    capture_output=True, text=True, timeout=10,
                ).stdout
                # Staat er geen "Connected: yes" in de tekst? Verbind dan opnieuw!
                if "Connected: yes" not in info:
                    print(f"[AUDIO] Speaker {self.speaker_mac} niet verbonden, opnieuw verbinden...")
                    subprocess.run(
                        ["bluetoothctl", "connect", self.speaker_mac],
                        capture_output=True, text=True, timeout=20,
                    )
            except Exception as e:
                print(f"[AUDIO] Bluetooth-controle mislukt: {e}")
            # Wacht 30 seconden voor de volgende controle
            time.sleep(30)

    def stop_sirene(self):
        """
        Stopt het sirenegeluid onmiddellijk (bijvoorbeeld zodra je het alarm reset met de drukknop).
        """
        with self._sirene_lock:
            # `poll() is None` betekent: het afspeelprogramma draait nog steeds
            if self._sirene_proces and self._sirene_proces.poll() is None:
                self._sirene_proces.terminate()

    def sirene(self):
        """
        Start het afspelen van `sirene.wav` op de achtergrond.
        Als de sirene al aan het loeien is, doet deze functie niets (zodat het geluid
        niet dubbel door elkaar heen gaat spelen).
        """
        with self._sirene_lock:
            # Speelt de sirene al? Dan hoeven we niets te doen.
            if self._sirene_proces and self._sirene_proces.poll() is None:
                return
            try:
                # Start het Linux audio-programma (`pw-play`) op de achtergrond met `Popen`
                self._sirene_proces = subprocess.Popen(
                    self._sirene_commando(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                # Controleer in een apart achtergrondtaakje of het afspelen zonder fouten lukt
                threading.Thread(
                    target=self._meld_sirene_fout, args=(self._sirene_proces,), daemon=True
                ).start()
            except Exception as e:
                print(f"[AUDIO] Kon sirene niet afspelen: {e}")

    def _sirene_commando(self):
        """
        Geeft het juiste Linux-commando terug om `sirene.wav` af te spelen met `pw-play`.
        (Als je het script met `sudo` start, zorgt dit stukje ervoor dat het geluid
        toch via de gewone aangemelde gebruiker naar de Bluetooth-speaker wordt gestuurd).
        """
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
        """
        Wacht op de achtergrond tot het geluidsbestand klaar is en print alleen een
        foutmelding als er echt iets misging (code 0 = normaal klaar, code -15 = gestopt met knop).
        """
        fout = proces.communicate()[1]
        if proces.returncode not in (0, -15):
            print(f"[AUDIO] pw-play faalde ({proces.returncode}): {fout.strip()}")

    def stuur_push(self, bericht):
        """
        Stuurt een push-notificatie naar je smartphone via de dienst `ntfy.sh`.

        Hoe werkt dit?
        We sturen een HTTP POST-verzoek (net zoals een webpagina een formulier verstuurt)
        naar `https://ntfy.sh/<jouw_geheime_topic>`.
        Iedereen die in de ntfy-app op zijn telefoon geabonneerd is op dat topic,
        krijgt binnen een seconde een melding met hoge prioriteit en een zwaailicht-icoontje!
        """
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
                timeout=5,  # Wacht maximaal 5 seconden op internet
            )

            # HTTP-code 200 betekent: "OK, goed ontvangen door de server!"
            if resp.status_code == 200:
                print("[NTFY PUSH] Succesvol afgeleverd op smartphone!")
            else:
                print(f"[NTFY FOUT] HTTP status {resp.status_code}")

        except Exception as e:
            print(f"[NTFY FOUT] Kon push alert niet versturen: {e}")
