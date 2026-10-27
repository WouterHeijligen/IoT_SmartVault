#!/usr/bin/env python3

import time
from gpiozero import OutputDevice


class VaultLock:
    def __init__(self):

        # Relais
        self.relais = OutputDevice(
            24,
            active_high=False,
            initial_value=False
        )

        # Stepper motor
        self.coils = [
            OutputDevice(17),
            OutputDevice(27),
            OutputDevice(22),
            OutputDevice(23)
        ]

        self.step_sequence = [
            [1, 1, 0, 0],
            [0, 1, 1, 0],
            [0, 0, 1, 1],
            [1, 0, 0, 1]
        ]

        self.step_delay = 0.010

    def _draai(self, stappen, vooruit=True):

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
                coil.value = waarde

            time.sleep(self.step_delay)

        # Motor stroomloos zetten
        for coil in self.coils:
            coil.off()

    def open(self):

        print("Kluis openen...")

        self.relais.on()
        time.sleep(0.25)

        self._draai(
            stappen=1024,
            vooruit=True
        )

        self.relais.off()

        print("Kluis geopend")

    def sluit(self):

        print("Kluis sluiten...")

        self.relais.on()
        time.sleep(0.25)

        self._draai(
            stappen=1024,
            vooruit=False
        )

        self.relais.off()

        print("Kluis gesloten")

    def stroomloos(self):
        """Zorg dat de motor geen stroom heeft (relais UIT)."""

        self.relais.off()

    def close(self):

        self.relais.off()

        for coil in self.coils:
            coil.off()
            coil.close()

        self.relais.close()

        print("Vault lock afgesloten")