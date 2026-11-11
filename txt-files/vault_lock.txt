#!/usr/bin/env python3
import time
import board
import digitalio


class VaultLock:
    def __init__(self):
        # Active-low relais (True = uit, False = aan)
        self.relais = digitalio.DigitalInOut(board.D24)
        self.relais.switch_to_output(value=True)

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

        # Spoelen spanningsloos zetten tegen opwarming
        for coil in self.coils:
            coil.value = False

    def open(self):
        print("Kluis openen...")

        self.relais.value = False
        time.sleep(0.25)

        self._draai(
            stappen=3072,
            vooruit=False
        )

        self.relais.value = True

        print("Kluis geopend")

    def sluit(self):
        print("Kluis sluiten...")

        self.relais.value = False
        time.sleep(0.25)

        self._draai(
            stappen=3072,
            vooruit=True
        )

        self.relais.value = True

        print("Kluis gesloten")

    def stroomloos(self):
        self.relais.value = True

    def close(self):
        self.relais.value = True

        for coil in self.coils:
            coil.value = False
            coil.deinit()

        self.relais.deinit()

        print("Vault lock afgesloten")
