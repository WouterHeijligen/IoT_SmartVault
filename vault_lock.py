#!/usr/bin/env python3
"""
Mechanisch slot van de Smart Vault: relais + stappenmotor.

Rol van dit bestand:
    Bevat ``VaultLock``, dat de kluisdeur fysiek opent en sluit. Een relais
    schakelt de voeding van de stappenmotor, de motor zelf wordt via vier
    GPIO-pinnen (spoelen) aangestuurd.

Hardware en bibliotheken:
    * ``digitalio.DigitalInOut`` voor relais op GPIO 24 en
      spoelen op GPIO 17, 27, 22 en 23.
    * Relais is active-low: GPIO laag = relais aan.

Threads en gedeelde toestand:
    Geen eigen threads of locks. open()/sluit() blokkeren ~10 s; ze worden
    aangeroepen vanuit de actuator-thread van main.py, die ``motor_busy`` in
    ``VaultState`` bijhoudt. stroomloos() mag ook uit andere threads (bv. bij
    alarm of afsluiten) worden aangeroepen.
"""

import time
import board
import digitalio


class VaultLock:
    """
    Bestuurt de deurvergrendeling van de kluis (relais + stappenmotor).

    Doel:
        De deur 1x openen of sluiten per statuswisseling, en de motor daarna
        weer volledig stroomloos maken zodat hij niet warm wordt.

    Werking:
        Eerst wordt het relais ingeschakeld (voeding motor aan), dan draait de
        motor een vast aantal stappen via een vierfasen-sequentie, en daarna
        gaat het relais weer uit.

    Ontwerpkeuzes:
        * Relais is active-low: een laag signaal schakelt het in.
          De uitgang begint hoog zodat de motor bij opstarten stroomloos is.
        * Full-step sequentie met twee spoelen tegelijk aan: meer koppel dan
          wave drive, eenvoudig en robuust voor een 28BYJ-48-achtige motor.
        * Motor wordt na elke beweging stroomloos gezet en het relais
          schakelt de voeding af: geen houdkoppel, geen opwarming, veiliger.
    """

    def __init__(self):
        """
        Initialiseert het relais, de vier motorspoelen en de stapsequentie.

        Werking:
            1. Maak het relais (GPIO 24, active-low, uit).
            2. Maak vier spoelen (GPIO 17, 27, 22, 23).
            3. Definieer de full-step sequentie (4 patronen, steeds twee
               aangrenzende spoelen aan).
            4. Stel ``step_delay`` in op 10 ms per stap (snel genoeg, maar
               de motor kan het nog volgen zonder stappen te missen).

        Parameters:
            Geen.

        Returns:
            None. Zet relais, coils, step_sequence en step_delay.

        Threads/locks:
            Eenmalig bij opstarten; geen locks.

        Hardware/bibliotheken:
            digitalio.DigitalInOut voor relais en spoelen.
        """

        # Relais
        self.relais = digitalio.DigitalInOut(board.D24)
        self.relais.switch_to_output(value=True)

        # Stepper motor
        self.coils = []
        for pin in (board.D17, board.D27, board.D22, board.D23):
            coil = digitalio.DigitalInOut(pin)
            coil.switch_to_output(value=False)
            self.coils.append(coil)

        self.step_sequence = [
            [1, 1, 0, 0],
            [0, 1, 1, 0],
            [0, 0, 1, 1],
            [1, 0, 0, 1]
        ]

        self.step_delay = 0.010

    def _draai(self, stappen, vooruit=True):
        """
        Draai de stappenmotor een aantal stappen en zet hem daarna stroomloos.

        Werking, stap voor stap:
            1. Kies de sequentie: normaal voor vooruit, omgekeerde volgorde
               voor achteruit.
            2. Per stap: kies patroon ``stap % 4`` en zet elke spoel op de
               bijbehorende waarde (1 = aan, 0 = uit).
            3. Wacht ``step_delay`` (10 ms) zodat de motor de stap kan maken.
            4. Zet na afloop alle spoelen uit zodat er geen stroom meer loopt.

        Parameters:
            stappen (int): aantal te zetten stappen.
            vooruit (bool): True = openrichting, False = sluitrichting.

        Returns:
            None

        Threads/locks:
            Blokkeert de aanroepende thread (stappen x 10 ms). Raakt geen
            gedeelde state; de aanroeper zet ``motor_busy``.

        Hardware/bibliotheken:
            Vier digitalio.DigitalInOut-spoelen.

        Ontwerpkeuzes:
            Full-step sequentie; reversed() voor de tegengestelde richting
            vermijdt een tweede tabel.
        """

        sequence = (
            self.step_sequence
            if vooruit
            else list(reversed(self.step_sequence))
        )

        for stap in range(stappen):

            patroon = sequence[
                stap % len(sequence)
            ]

            for coil, waarde in zip(
                self.coils,
                patroon
            ):
                coil.value = bool(waarde)

            time.sleep(self.step_delay)

        # Motor stroomloos zetten
        for coil in self.coils:
            coil.value = False

    def open(self):
        """
        Open de kluis: relais aan, motor 3072 stappen vooruit, relais uit.

        Werking, stap voor stap:
            1. Schakel het relais in (voeding motor).
            2. Wacht 0.25 s zodat de voeding stabiel is.
            3. Draai 1024 stappen vooruit via _draai().
            4. Schakel het relais uit (motor weer stroomloos).

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Blokkeert ~10 s. Wordt vanuit de actuator-thread aangeroepen
            terwijl ``VaultState.motor_busy`` True is.

        Hardware/bibliotheken:
            Relais (GPIO 24) en stappenmotor via digitalio.

        Ontwerpkeuzes:
            Relais pas aan vlak voor het draaien, zodat de motor in rust geen
            stroom of warmte verbruikt.
        """

        print("Kluis openen...")

        self.relais.value = False
        time.sleep(0.25)

        self._draai(
            stappen=3072,
            vooruit=True
        )

        self.relais.value = True

        print("Kluis geopend")

    def sluit(self):
        """
        Sluit de kluis: relais aan, motor 1024 stappen achteruit, relais uit.

        Werking:
            Spiegelbeeld van open(): relais aan, 0.25 s wachten, 1024 stappen
            in omgekeerde sequentie, relais uit. Hetzelfde aantal stappen
            brengt de deur precies terug in de uitgangspositie.

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Blokkeert ~10 s; aanroeper (actuator-thread) beheert
            ``motor_busy``.

        Hardware/bibliotheken:
            Relais (GPIO 24) en stappenmotor via digitalio.
        """

        print("Kluis sluiten...")

        self.relais.value = False
        time.sleep(0.25)

        self._draai(
            stappen=3072,
            vooruit=False
        )

        self.relais.value = True

        print("Kluis gesloten")

    def stroomloos(self):
        """
        Zorg dat de motor geen stroom heeft (relais UIT).

        Werking:
            Zet alleen het relais uit; omdat het relais active-low is, betekent
            dat dat de motorvoeding wordt onderbroken. Veilig om vaak aan te
            roepen (idempotent).

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Neemt geen locks; mag uit elke thread, bv. in de alarm- of
            afsluitpad, om zeker te zijn dat de motor niet onder spanning
            blijft staan.

        Hardware/bibliotheken:
            Relais op GPIO 24 via digitalio.
        """

        self.relais.value = True

    def close(self):
        """
        Geef alle GPIO-resources vrij bij afsluiten.

        Werking, stap voor stap:
            1. Relais uit (motor stroomloos).
            2. Per spoel: uit en ``deinit()`` om de pin vrij te geven.
            3. Sluit het relais-object.

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Aanroepen nadat de actuator-thread is gestopt; geen locks.

        Hardware/bibliotheken:
            digitalio: deinit() geeft de pinnen terug aan het systeem.
        """

        self.relais.value = True

        for coil in self.coils:
            coil.value = False
            coil.deinit()

        self.relais.deinit()

        print("Vault lock afgesloten")