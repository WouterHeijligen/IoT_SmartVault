#!/usr/bin/env python3
"""
Meldingen van de Smart Vault: ntfy-pushberichten en sirene via Bluetooth.

Rol van dit bestand:
    Bevat ``Notificaties``, dat (1) push-meldingen naar de smartphone stuurt
    via ntfy.sh, (2) een sirene (sirene.wav) afspeelt en (3) de Bluetooth
    speaker verbonden houdt.

Bibliotheken en hardware:
    * ``requests`` voor de HTTP-POST naar ntfy.sh.
    * ``subprocess`` voor ``bluetoothctl`` (speaker verbinden) en ``pw-play``
      (PipeWire-afspeler voor het .wav-bestand).
    * ``python-dotenv`` voor NTFY_TOPIC en BT_SPEAKER_MAC uit .env.
    * Bluetooth speaker als sirene-uitvoer.

Threads en gedeelde toestand:
    Methoden worden vanuit verschillende threads aangeroepen (Actuators,
    Cloud). ``_sirene_lock`` beschermt het sirene-subproces. De speaker-lus
    en de foutmelder draaien als daemon-threads. ``VaultState`` wordt niet
    aangeraakt.
"""

import os
import subprocess
import threading
import time

import requests
from dotenv import load_dotenv

load_dotenv()


class Notificaties:
    """
    Push-notificaties (ntfy.sh) en sirene via de Bluetooth speaker.

    Doel:
        Eigenaar waarschuwen (push) en omstanders afschrikken (sirene).

    Ontwerpkeuzes:
        * Sirene is non-blocking en voorkomt overlap: een lopend proces wordt
          niet opnieuw gestart.
        * Sudo-aware pw-play: zie _sirene_commando().
        * Instellingen komen uit omgevingsvariabelen met een standaardwaarde.
        * Netwerkfouten en Bluetooth-fouten worden afgevangen en gelogd, zodat
          een mislukte melding de kluis nooit laat crashen.
    """

    def __init__(self):
        """
        Leest configuratie en maakt de sirene-administratie.

        Werking:
            Zet ``topic`` (env NTFY_TOPIC), ``speaker_mac`` (env
            BT_SPEAKER_MAC), het pad naar sirene.wav naast dit bestand, een
            lege procesverwijzing en ``_sirene_lock``.

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Maakt ``_sirene_lock`` aan, die ``_sirene_proces`` beschermt
            tegen gelijktijdige toegang.
        """
        self.topic = os.getenv("NTFY_TOPIC", "tm_smart_vault_bart_2026")
        self.speaker_mac = os.getenv("BT_SPEAKER_MAC", "33:A8:8C:0F:CC:A0")
        self.sirene_bestand = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "sirene.wav"
        )
        self._sirene_proces = None
        self._sirene_lock = threading.Lock()

    def start_speaker_verbinding(self):
        """
        Houdt de Bluetooth speaker verbonden (verbindt opnieuw na uitval).

        Werking:
            Start één daemon-thread die _speaker_loop() draait en dus
            automatisch stopt als het programma eindigt. Niet blokkerend.

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Maakt een nieuwe daemon-thread; roep dit maar één keer aan,
            anders ontstaan meerdere controle-lussen.
        """

        threading.Thread(target=self._speaker_loop, daemon=True).start()

    def _speaker_loop(self):
        """
        Oneindige lus die elke 30 s de Bluetooth-verbinding controleert.

        Werking, stap voor stap:
            1. Vraag ``bluetoothctl info <mac>`` op (timeout 10 s).
            2. Staat "Connected: yes" er niet in, meld dat en voer
               ``bluetoothctl connect <mac>`` uit (timeout 20 s).
            3. Elke fout (bv. bluetoothctl ontbreekt, timeout) wordt gelogd en
               de lus gaat door.
            4. Slaap 30 s.

        Parameters:
            Geen.

        Returns:
            None (eindeloos).

        Threads/locks:
            Draait in een eigen daemon-thread; raakt geen gedeelde state.

        Hardware/bibliotheken:
            bluetoothctl (BlueZ) via subprocess. 30 s is een balans tussen
            snel herstel en weinig Bluetooth-verkeer.
        """
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
        """
        Stopt de sirene meteen (na reset van het alarm).

        Werking:
            Neemt ``_sirene_lock``; loopt het afspeelproces nog
            (``poll() is None``), dan wordt het met ``terminate()`` (SIGTERM)
            beëindigd. Is er niets actief, dan gebeurt er niets.

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Gebruikt ``_sirene_lock``; veilig vanuit elke thread.
            De foutmelder negeert returncode -15 (SIGTERM), dus deze stop
            geeft geen foutmelding.
        """

        with self._sirene_lock:
            if self._sirene_proces and self._sirene_proces.poll() is None:
                self._sirene_proces.terminate()

    def sirene(self):
        """
        Speelt sirene.wav af via de standaard audio-uitvoer (non-blocking, geen overlap).

        Werking, stap voor stap:
            1. Neem ``_sirene_lock``.
            2. Draait er al een sirene, dan terug (geen overlap/stapeling).
            3. Start het afspeelcommando uit _sirene_commando() met
               ``Popen`` (stdout weggegooid, stderr opgevangen).
            4. Start een daemon-thread die de uitvoer afwacht en fouten meldt.
            5. Faalt het starten, dan wordt dat gelogd.

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Gebruikt ``_sirene_lock`` rond ``_sirene_proces``; start een
            daemon-thread (_meld_sirene_fout). Blokkeert niet op het afspelen.

        Hardware/bibliotheken:
            pw-play (PipeWire) naar de Bluetooth speaker; subprocess.
        """

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
        """
        Onder sudo zit root niet in de audiosessie: speel af als de oorspronkelijke gebruiker.

        Werking:
            1. Lees ``SUDO_USER``.
            2. Draait het programma als root (euid 0) via sudo, dan wordt
               ``sudo -u <gebruiker> XDG_RUNTIME_DIR=/run/user/<uid> pw-play
               <bestand>`` teruggegeven. XDG_RUNTIME_DIR wijst naar de
               PipeWire-socket van die gebruiker (uid uit SUDO_UID, standaard
               1000), anders vindt pw-play de audioserver niet.
            3. Anders gewoon ``pw-play <bestand>``.

        Parameters:
            Geen.

        Returns:
            list[str]: het commando voor subprocess.Popen.

        Threads/locks:
            Leest alleen omgevingsvariabelen; geen locks.

        Ontwerpkeuzes:
            GPIO vereist vaak sudo, terwijl PipeWire per gebruiker draait;
            dit verbindt beide werelden.
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
        Wacht op het sirene-proces en meldt onverwachte fouten.

        Werking:
            ``communicate()`` wacht tot pw-play klaar is en geeft stderr terug.
            Een returncode anders dan 0 (normaal) of -15 (door
            stop_sirene() beëindigd) wordt met de foutuitvoer gelogd.

        Parameters:
            proces (subprocess.Popen): het te bewaken afspeelproces.

        Returns:
            None

        Threads/locks:
            Draait in een eigen daemon-thread; neemt geen lock. Het uitlezen
            van stderr voorkomt ook dat de pipe vol loopt.
        """
        fout = proces.communicate()[1]
        if proces.returncode not in (0, -15):
            print(f"[AUDIO] pw-play faalde ({proces.returncode}): {fout.strip()}")

    def stuur_push(self, bericht):
        """
        Stuurt een push-notificatie naar je smartphone via ntfy.sh.

        Werking, stap voor stap:
            1. Log het bericht.
            2. POST de UTF-8 tekst naar ``https://ntfy.sh/<topic>`` met
               headers Title, Priority=high en Tags (rotating_light,lock)
               zodat de telefoon luid en met icoon meldt.
            3. Timeout 5 s zodat een trage verbinding de aanroeper niet lang
               blokkeert.
            4. HTTP 200 = afgeleverd; andere status of uitzondering wordt
               gelogd (niet opnieuw geworpen).

        Parameters:
            bericht (str): de berichttekst.

        Returns:
            None

        Threads/locks:
            Blokkeert de aanroepende thread tot 5 s; geen locks, geen
            VaultState. De aanroeper gebruikt vlaggen als
            ``alarm_notified`` om dubbele pushes te voorkomen.

        Hardware/bibliotheken:
            ``requests`` (HTTPS) naar de publieke ntfy.sh-service.
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
                timeout=5,
            )

            if resp.status_code == 200:
                print("[NTFY PUSH] Succesvol afgeleverd op smartphone!")
            else:
                print(f"[NTFY FOUT] HTTP status {resp.status_code}")

        except Exception as e:
            print(f"[NTFY FOUT] Kon push alert niet versturen: {e}")
