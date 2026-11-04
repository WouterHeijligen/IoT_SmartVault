#!/usr/bin/env python3
"""
================================================================================
BESTAND: vault_lock.py
DOEL:    Het fysieke slot van de kluis (Relais + 28BYJ-48 Stappenmotor).
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
Om het slot van de kluis fysiek open en dicht te schuiven, gebruiken we een
stappenmotor (type 28BYJ-48 met driverboard). Een stappenmotor draait niet
zomaar rond zoals een ventilator, maar zet hele kleine, precieze stapjes.
Zo weten we exact hoe ver het slot open of dicht schuift!

💡 TWEE GOUDEN VRAGEN OP JE VERDEDIGING:
1. "Waarom zit er een relais tussen?"
   Een stappenmotor trekt redelijk wat stroom en kan warm worden als er spanning
   op het driverboard blijft staan. Het relais (op GPIO 24) werkt als een
   veiligheidsschakelaar (interlock): we zetten de stroom naar de motor ALLEEN aan
   op het moment dat de kluis open of dicht moet. Daarna schakelt het relais de
   stroom meteen weer helemaal uit!
2. "Waarom zetten jullie het relais op False om hem AAN te zetten?"
   Ons relais-bordje is 'Active-Low'. Dat betekent dat de schakelaar dichtklapt
   zodra de GPIO-pin naar 0 Volt (LOW / `False`) wordt getrokken, en uitgaat
   bij 3.3 Volt (HIGH / `True`).
"""

import time
import board
import digitalio


class VaultLock:
    """
    Stuurt het relais en de stappenmotor aan om de kluisdeur te openen en te sluiten.
    """

    def __init__(self):
        """
        Zet de GPIO-pinnen voor het relais en de vier spoelen van de stappenmotor klaar.
        """
        # 1. Relais klaarmaken op GPIO 24.
        # Let op: Active-Low! `value=True` betekent dus dat het relais veilig UIT start.
        self.relais = digitalio.DigitalInOut(board.D24)
        self.relais.switch_to_output(value=True)

        # 2. De stappenmotor heeft 4 elektromagnetische spoelen (coils) op GPIO 17, 27, 22 en 23.
        # We zetten ze allemaal klaar als uitgang (output) en zetten ze standaard UIT (`False`).
        self.coils = []
        for pin in (board.D17, board.D27, board.D22, board.D23):
            coil = digitalio.DigitalInOut(pin)
            coil.switch_to_output(value=False)
            self.coils.append(coil)

        # 3. Het stappatroon (Full-Step mode):
        # Door steeds 2 aangrenzende spoelen tegelijk aan te zetten (1 = aan, 0 = uit)
        # en dat rondje steeds door te schuiven, wordt het magneetveld rondgetrokken
        # en draait het motortje met maximale kracht (koppel) stap voor stap rond.
        self.step_sequence = [
            [1, 1, 0, 0],  # Stap 1: spoel 1 en 2 aan
            [0, 1, 1, 0],  # Stap 2: spoel 2 en 3 aan
            [0, 0, 1, 1],  # Stap 3: spoel 3 en 4 aan
            [1, 0, 0, 1]   # Stap 4: spoel 4 en 1 aan
        ]

        # Wachttijd tussen twee stapjes (10 milliseconden = 100 stapjes per seconde).
        # Als je dit te kort maakt, kan de motor het mechanisch niet bijhouden.
        self.step_delay = 0.010

    def _draai(self, stappen, vooruit=True):
        """
        Hulpfunctie die de motor een exact aantal stappen laat draaien.
        - `vooruit=True`:  draait de lijst in normale volgorde af (sluiten).
        - `vooruit=False`: draait de lijst achterstevoren af met `reversed()` (openen).
        """
        # Kies de juiste volgorde van het stappatroon (vooruit of achteruit)
        sequence = (
            self.step_sequence
            if vooruit
            else list(reversed(self.step_sequence))
        )

        # Loop het gevraagde aantal stappen af
        for stap in range(stappen):
            # Met `% 4` (modulo) herhalen we steeds patroon 0, 1, 2, 3, 0, 1, 2, 3...
            patroon = sequence[
                stap % len(sequence)
            ]

            # Zet elk van de 4 spoelen aan (True) of uit (False) volgens het gekozen patroon
            for coil, waarde in zip(
                self.coils,
                patroon
            ):
                coil.value = bool(waarde)

            # Geef het motortje 10 ms de tijd om fysiek naar dit magneetveld toe te draaien
            time.sleep(self.step_delay)

        # Klaar met draaien! Zet alle 4 de spoelen weer uit zodat de motor niet heet wordt.
        for coil in self.coils:
            coil.value = False

    def open(self):
        """
        Open het kluisslot:
        1. Zet het relais AAN (`False`, want active-low) zodat de motor stroom krijgt.
        2. Wacht 0,25 seconde zodat het relais fysiek is omgeklikt en de spanning stabiel is.
        3. Draai 3072 stappen achteruit (dit is precies anderhalve omwenteling van de as).
        4. Zet het relais weer UIT (`True`).
        """
        print("Kluis openen...")

        self.relais.value = False  # Stroom AAN
        time.sleep(0.25)

        self._draai(
            stappen=3072,
            vooruit=False
        )

        self.relais.value = True   # Stroom UIT

        print("Kluis geopend")

    def sluit(self):
        """
        Sluit het kluisslot:
        Precies het omgekeerde van `open()`: relais AAN, 3072 stappen vooruit draaien
        zodat de schuif weer op zijn exacte beginplek zit, en relais weer UIT.
        """
        print("Kluis sluiten...")

        self.relais.value = False  # Stroom AAN
        time.sleep(0.25)

        self._draai(
            stappen=3072,
            vooruit=True
        )

        self.relais.value = True   # Stroom UIT

        print("Kluis gesloten")

    def stroomloos(self):
        """
        Veiligheidsfunctie: zorgt dat het relais gegarandeerd UIT staat (`True`).
        Wordt o.a. aangeroepen bij een alarm of bij het afsluiten van het programma.
        """
        self.relais.value = True

    def close(self):
        """
        Ruimt alles netjes op bij het afsluiten van het programma:
        zet het relais en alle spoelen uit en geeft de GPIO-pinnen vrij (`deinit`).
        """
        self.relais.value = True

        for coil in self.coils:
            coil.value = False
            coil.deinit()

        self.relais.deinit()

        print("Vault lock afgesloten")
