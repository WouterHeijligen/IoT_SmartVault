#!/usr/bin/env python3

class Sensors:
    def __init__(self):
        # Hier initialiseren we later:
        # - MCP3008
        # - Temperatuursensor
        # - Lichtsensor

        print("Sensors initialized")

    def lees_temperatuur(self):
        """
        Lees temperatuur uit.

        Returns:
            float: temperatuur in graden Celsius
        """

        # TODO: code van werkende temperatuursensor toevoegen
        temperatuur = 0.0

        return temperatuur

    def lees_licht(self):
        """
        Lees lichtsensor uit.

        Returns:
            float: lichtwaarde
        """

        # TODO: code van werkende lichtsensor toevoegen
        licht = 0.0

        return licht

    def lees_alles(self):
        return {
            "temperatuur": self.lees_temperatuur(),
            "licht": self.lees_licht()
        }

    def close(self):
        print("Sensors afgesloten")