#!/usr/bin/env python3
"""
================================================================================
BESTAND: voice.py
DOEL:    Tweestapsverificatie (Factor 2) met offline Spraakherkenning (Vosk).
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
Onze Smart Vault gebruikt **2FA (Two-Factor Authentication)**:
- Factor 1: De 3-cijferige pincode via de draaiknop (potmeter).
- Factor 2: Je moet het geheime wachtwoord ("open") uitspreken in de USB-microfoon.

💡 TWEE TOP-ARGUMENTEN VOOR JE PRESENTATIE:
1. "Waarom gebruiken jullie Vosk en geen Google/Cloud-spraakherkenning?"
   Vosk draait 100% OFFLINE op de Raspberry Pi zelf! Dat heeft twee grote voordelen:
   - Privacy: Je stem wordt nooit naar het internet gestuurd.
   - Betrouwbaarheid: Ook als de wifi uitvalt, kun je de kluis nog steeds openen!
2. "Waarom herkent hij het wachtwoord zo snel en nauwkeurig?"
   We geven aan Vosk een beperkte woordenlijst mee: `[doelzin, "[unk]"]`.
   Daardoor hoeft het taalmodel niet te kiezen uit 50.000 woorden, maar luistert
   het alleen of je het geheime wachtwoord zegt of iets anders/onbekends (`[unk]`)!
"""

import json
import os
import queue
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# De map waarin dit Python-bestand zelf staat
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class VoiceRecognition:
    """
    Zorgt voor het opnemen van geluid via de USB-microfoon en het herkennen
    van het gesproken wachtwoord met behulp van Vosk.
    """

    def __init__(self):
        """
        Zet de basisinstellingen klaar (waar staat het taalmodel en welke microfoon gebruiken we?).
        Het grote taalmodel zelf laden we pas later in `laad()`, zodat het opstarten snel gaat.
        """
        # Zoek de map met het Engelse taalmodel (`model-en`)
        self.model_pad = os.getenv("VOSK_MODEL", os.path.join(SCRIPT_DIR, "model-en"))
        # Welk microfoon-nummer gebruiken we? (standaard apparaat 0)
        self.device = int(os.getenv("MIC_DEVICE", "0"))
        # Standaard opnamekwaliteit (44100 Hz = 44.100 geluidsmetingen per seconde)
        self.sample_rate = 44100
        self.model = None
        self._sd = None

        print("Voice recognition initialized")

    def laad(self):
        """
        Laadt het Vosk-taalmodel in het geheugen van de Raspberry Pi (gebeurt maar 1 keer)
        en vraagt aan de USB-microfoon op welke snelheid (sample rate) hij werkt.
        """
        # Als het model al geladen is, zijn we meteen klaar!
        if self.model is not None:
            return

        # We importeren `sounddevice` en `vosk` pas hier. Voordeel: als je test zonder
        # microfoon (`BYPASS_VOICE_2FA = True`), crasht het programma niet als Vosk niet geïnstalleerd is.
        import sounddevice as sd
        from vosk import Model

        self._sd = sd
        try:
            # Vraag aan de aangesloten USB-microfoon wat zijn standaard sample rate is (bijv. 44100 of 48000 Hz)
            info = sd.query_devices(self.device, "input")
            self.sample_rate = int(info["default_samplerate"])
        except Exception as e:
            print(f"[VOICE] Sample rate niet leesbaar ({e}), gebruik {self.sample_rate} Hz")

        # Controleer of het mapje met het taalmodel wel echt op de Pi staat
        if not os.path.isdir(self.model_pad):
            raise FileNotFoundError(f"Vosk-modelmap niet gevonden: {self.model_pad}")

        print(f"[VOICE] Model laden uit '{self.model_pad}' ({self.sample_rate} Hz, device {self.device})...")
        self.model = Model(self.model_pad)

    def luister(self, timeout_s=10.0, stop=None, doelzin=None):
        """
        Zet de microfoon aan en luistert maximaal `timeout_s` seconden of de `doelzin` gezegd wordt.

        Hoe werkt dit stap voor stap?
        1. De microfoon neemt continu stukjes geluid van 0,5 seconde op en stopt die
           in een wachtrij (`audio = queue.Queue()`).
        2. Onze `while`-lus haalt telkens een stukje geluid uit die wachtrij en geeft
           het aan de Vosk-herkenner (`recognizer`).
        3. Vosk geeft het herkende woord terug in JSON-formaat (bijv. `{"text": "open"}`).
        4. Zit het geheime wachtwoord (`doelzin`) in de tekst? Dan stopt hij meteen en
           geeft hij de tekst terug aan `main.py`, die de kluis opent!
        """
        from vosk import KaldiRecognizer

        # Zorg dat het taalmodel geladen is
        self.laad()

        # Een wachtrij (Queue) waarin de microfoon zijn opgenomen stukjes geluid legt
        audio = queue.Queue()

        def callback(indata, frames, time_info, status):
            """
            Deze kleine hulpfunctie wordt op de achtergrond automatisch aangeroepen
            door de microfoon telkens als er een halve seconde geluid is opgenomen.
            Hij stopt het ruwe geluid (`bytes(indata)`) meteen in de `audio`-wachtrij.
            """
            if status:
                print(f"[VOICE AUDIO] {status}", file=sys.stderr)
            audio.put(bytes(indata))

        # Maak de spraakherkenner aan. Als we een `doelzin` (zoals "open") meegeven,
        # vertellen we Vosk dat hij alleen op dat woord hoeft te letten (en "[unk]" voor al het andere).
        recognizer = (
            KaldiRecognizer(self.model, self.sample_rate, json.dumps([doelzin.lower(), "[unk]"]))
            if doelzin
            else KaldiRecognizer(self.model, self.sample_rate)
        )
        laatste = ""
        # Bereken het eindtijdstip waarop de luistertijd (bijv. 20 seconden) voorbij is
        einde = time.monotonic() + timeout_s

        # Open de microfoon-verbinding (`RawInputStream`). Zodra het `with`-blok klaar is,
        # wordt de microfoon ook automatisch weer netjes uitgeschakeld.
        with self._sd.RawInputStream(
            samplerate=self.sample_rate,
            # Neem op in blokjes van 0,5 seconde in mono (channels=1)
            blocksize=int(self.sample_rate * 0.5),
            device=self.device,
            dtype="int16",
            channels=1,
            latency="high",
            callback=callback,
        ):
            # Blijf luisteren zolang de tijd nog niet om is
            while time.monotonic() < einde:
                # Moeten we eerder stoppen (bijv. omdat er intussen een alarm afging)?
                if stop is not None and stop():
                    break

                # Haal het volgende stukje geluid uit de wachtrij (wacht max 0,3 s)
                try:
                    data = audio.get(timeout=0.3)
                except queue.Empty:
                    continue

                # Geef het geluidsfragment aan Vosk en haal het herkende woord uit de JSON-tekst
                if recognizer.AcceptWaveform(data):
                    tekst = json.loads(recognizer.Result()).get("text", "").strip()
                else:
                    tekst = json.loads(recognizer.PartialResult()).get("partial", "").strip()

                # Als het stil was (lege tekst), ga door naar het volgende geluidsfragment
                if not tekst:
                    continue

                # Print wat er gehoord is (als het nieuw is)
                if tekst != laatste:
                    laatste = tekst
                    print(f"[VOICE] Gehoord: '{tekst}'")

                # Hebben we het geheime wachtwoord gehoord? Geef het direct terug!
                if doelzin and doelzin in tekst.lower():
                    return tekst

        return laatste

    def close(self):
        """
        Maakt het taalmodel leeg bij het afsluiten van het programma.
        """
        self.model = None
        print("Voice recognition afgesloten")
