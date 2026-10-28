#!/usr/bin/env python3
"""
Spraakherkenning (tweede factor) van de Smart Vault.

Rol van dit bestand:
    Bevat ``VoiceRecognition``, dat via een USB-microfoon luistert en met het
    offline Vosk-model (Kaldi) controleert of de geheime passphrase wordt
    uitgesproken.

Bibliotheken:
    * ``sounddevice`` (PortAudio) voor het opnemen van ruwe audio.
    * ``vosk`` (KaldiRecognizer, Model) voor offline herkenning: geen cloud,
      dus privacy en werking zonder internet.
    * ``python-dotenv`` voor VOSK_MODEL en MIC_DEVICE uit .env.
    * ``queue`` om audio van de callback-thread naar de luisterlus te brengen.

Threads en gedeelde toestand:
    Draait in de Voice-thread van main.py. Het bestand raakt ``VaultState``
    niet; main.py geeft een ``stop``-functie mee om vroegtijdig af te breken.
    Vosk en sounddevice worden pas in laad()/luister() geïmporteerd, zodat het
    programma ook zonder die bibliotheken start (bv. bij BYPASS_VOICE_2FA).
"""

import json
import os
import queue
import sys
import time

from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class VoiceRecognition:
    """
    Vosk spraakherkenning via een USB-microfoon (zelfde opzet als vosk_mic_test.py).

    Doel:
        Vaststellen of de gebruiker de geheime passphrase uitspreekt.

    Werking:
        laad() laadt het model eenmalig (lazy). luister() neemt audio op in
        blokken van 0,5 s en voedt die aan een KaldiRecognizer totdat de
        doelzin is gehoord, de timeout verloopt of ``stop`` True geeft.

    Ontwerpkeuzes:
        * Beperkte grammatica (restricted grammar): met een ``doelzin`` krijgt
          Vosk alleen [doelzin, "[unk]"] als mogelijke uitkomsten. Dat maakt
          herkenning veel nauwkeuriger en sneller en voorkomt dat andere
          woorden per ongeluk als passphrase gelden.
        * Sample rate wordt van de microfoon gelezen, want USB-mics draaien
          vaak op 44100 of 48000 Hz en niet op 16 kHz.
        * Model laden duurt seconden; dat gebeurt dus één keer en niet bij elke
          luisterronde.
    """

    def __init__(self):
        """
        Leest de configuratie; laadt het model nog niet.

        Werking:
            Zet ``model_pad`` (env VOSK_MODEL, anders map ``model-en`` naast
            dit bestand), ``device`` (env MIC_DEVICE, standaard 0),
            standaard ``sample_rate`` 44100 en lege model/sounddevice-verwijzingen.

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Geen; zware import en model-load worden uitgesteld naar laad().
        """
        self.model_pad = os.getenv("VOSK_MODEL", os.path.join(SCRIPT_DIR, "model-en"))
        self.device = int(os.getenv("MIC_DEVICE", "0"))
        self.sample_rate = 44100
        self.model = None
        self._sd = None

        print("Voice recognition initialized")

    def laad(self):
        """
        Laadt Vosk en detecteert de sample rate van de microfoon (eenmalig).

        Werking, stap voor stap:
            1. Al geladen (``model`` is niet None)? Dan meteen terug.
            2. Importeer sounddevice en vosk.Model (lazy).
            3. Vraag het invoerapparaat naar zijn standaard sample rate; bij
               een fout blijft 44100 Hz gebruikt en wordt dat gemeld.
            4. Controleer of de modelmap bestaat, anders FileNotFoundError.
            5. Laad het Vosk-model (traag, enkele seconden).

        Parameters:
            Geen.

        Returns:
            None. Vult ``model``, ``_sd`` en ``sample_rate``.

        Threads/locks:
            Draait in de Voice-thread; geen locks. Niet bedoeld om
            gelijktijdig vanuit meerdere threads te worden aangeroepen.

        Raises:
            FileNotFoundError: als de modelmap ontbreekt.
        """
        if self.model is not None:
            return

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
        """
        Luister naar spraak.

        Werking, stap voor stap:
            1. Importeer KaldiRecognizer en zorg dat het model geladen is.
            2. Maak een wachtrij en een audio-callback die elk ontvangen blok
               (als bytes) in de wachtrij zet en stream-statusfouten naar
               stderr schrijft. De callback draait in de PortAudio-thread en
               doet bewust minimaal werk.
            3. Maak de recognizer; met ``doelzin`` met beperkte grammatica
               [doelzin, "[unk]"], anders met vrije grammatica.
            4. Open een RawInputStream (int16, mono, blokken van 0,5 s,
               ``latency="high"`` tegen buffer-overruns op de Pi).
            5. Loop tot de deadline (``time.monotonic()``): stop bij
               ``stop()`` True; haal een blok uit de wachtrij (0,3 s
               timeout zodat stop/deadline regelmatig worden gecontroleerd).
            6. Geeft AcceptWaveform True, dan is dit een eindresultaat, anders
               een tussenresultaat (partial); lees de tekst uit de JSON.
            7. Negeer lege tekst, print nieuwe tekst en onthoud die als
               ``laatste``.
            8. Bevat de tekst de doelzin, geef dan direct terug (ook een
               gedeeltelijke match werkt; snellere reactie).

        Args:
            timeout_s: maximale luistertijd in seconden
            stop: optionele functie; luisteren stopt zodra die True geeft
            doelzin: stopt zodra deze zin (ook gedeeltelijk) wordt gehoord

        Returns:
            str: laatst herkende tekst (leeg bij niets gehoord)

        Threads/locks:
            Blokkeert de Voice-thread; de audio-callback draait in een
            PortAudio-thread en communiceert alleen via ``queue.Queue``
            (thread-safe). Raakt ``VaultState`` niet.

        Hardware/bibliotheken:
            USB-microfoon via sounddevice; Vosk/Kaldi voor herkenning.
        """
        from vosk import KaldiRecognizer

        self.laad()

        audio = queue.Queue()

        def callback(indata, frames, time_info, status):
            """
            Audio-callback van sounddevice (draait in de PortAudio-thread).

            Parameters:
                indata: ruwe audiobuffer (int16) van het huidige blok.
                frames: aantal frames in het blok (ongebruikt).
                time_info: tijdsinformatie van PortAudio (ongebruikt).
                status: stream-statusvlaggen (bv. overflow); wordt gemeld.

            Returns:
                None. Zet een bytes-kopie van het blok in de wachtrij
                ``audio`` (thread-safe) voor de luisterlus; niets anders
                gebeurt hier zodat de callback snel blijft.
            """
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
        """
        Geef het Vosk-model vrij bij afsluiten.

        Werking:
            Zet ``model`` op None zodat het geheugen vrijkomt (en laad() het
            zo nodig opnieuw kan laden).

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Aanroepen nadat de Voice-thread is gestopt; geen locks.
        """
        self.model = None
        print("Voice recognition afgesloten")
