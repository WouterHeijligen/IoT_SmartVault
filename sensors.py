#!/usr/bin/env python3
"""
Sensorlaag van de Smart Vault (Raspberry Pi 5).

Rol van dit bestand:
    Bundelt alle analoge en digitale sensoren in één klasse, ``Sensors``,
    zodat de rest van de applicatie (main.py) alleen nog Python-waarden
    krijgt: temperatuur in °C, licht in lux en een ruwe potmeterwaarde.

Hardware en bibliotheken:
    * BH1750 lichtsensor via I2C (``busio.I2C``) op GPIO 2 (SDA) / GPIO 3 (SCL).
    * MCP3008 10-bit ADC via SPI0 (``busio.SPI`` + ``adafruit_mcp3xxx``),
      omdat de Raspberry Pi zelf geen analoge ingangen heeft. Kanaal 0 is de
      potmeter (cijferslot), kanaal 1 de LM35 temperatuursensor.
    * ``digitalio`` voor de chip-select (CS) van de MCP3008 op GPIO 25.

Threads en gedeelde toestand:
    Deze module kent zelf geen threads of locks. De SPI-bus wordt ook door het
    OLED-display gebruikt; de aanroeper (main.py) moet daarom ``spi_lock`` uit
    ``VaultState`` nemen rond lees_temperatuur() en lees_potmeter_raw().
    De I2C-bus wordt intern beschermd met ``try_lock()``/``unlock()``.
"""

import time

import board
import busio
import digitalio
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn


class Sensors:
    """
    Sensoren van de Smart Vault.

    Aansluitingen:
        BH1750 (I2C 0x23)  -> GPIO 2 (SDA), GPIO 3 (SCL)
        MCP3008 (SPI0)     -> CS op GPIO 25
            CH0: potmeter (cijferslot)
            CH1: LM35 temperatuursensor

    Doel:
        Eén toegangspunt tot alle sensoren, zodat de rest van het systeem niet
        hoeft te weten welke bus of welk ADC-kanaal bij welke meting hoort.

    Werking:
        De constructor opent de I2C- en SPI-bus, zet de BH1750 in continue
        meetmodus en maakt twee ADC-kanalen aan. De lees_*-methoden geven
        daarna direct een actuele meetwaarde terug.

    Threads/locks:
        De klasse is zelf niet thread-safe voor SPI: de aanroeper houdt
        ``VaultState.spi_lock`` vast omdat het OLED dezelfde SPI-bus deelt.
        Voor I2C gebruikt de klasse ``try_lock()``.

    Ontwerpkeuzes:
        * BH1750 draait in continue modus: de sensor meet zelf door (~120 ms
          per meting), dus uitlezen is een snelle read zonder wachttijd of
          opnieuw triggeren per meting.
        * Bij een bezette I2C-bus wordt de laatste lux-waarde teruggegeven in
          plaats van te blokkeren, zodat de meetlus (10 Hz) niet vertraagt.
    """

    BH1750_ADDRESS = 0x23
    BH1750_COMMAND_HIGH_RES = bytearray([0x10])

    def __init__(self):
        """
        Initialiseert alle sensoren en start de continue BH1750-meting.

        Werking, stap voor stap:
            1. Open de I2C-bus (SCL=GPIO 3, SDA=GPIO 2) en zet de laatste
               luxwaarde op 0.0 (fallback als de bus bezet is).
            2. Pak de I2C-lock (wacht in stappen van 10 ms), stuur commando
               0x10 (continuous high-resolution mode) naar adres 0x23 en
               geef de lock altijd vrij (try/finally).
            3. Wacht 0.2 s zodat de eerste meting (~120 ms) klaar is.
            4. Open SPI0 (SCK/MISO/MOSI) en maak de chip-select op GPIO 25.
            5. Maak de MCP3008 en twee ``AnalogIn``-kanalen: P0 (potmeter)
               en P1 (LM35).

        Parameters:
            Geen.

        Returns:
            None. Zet de attributen i2c, laatste_lux, spi, cs, mcp,
            potmeter_channel en lm35_channel.

        Threads/locks:
            Wordt eenmalig bij het opstarten aangeroepen, vóór de threads
            starten; de I2C-lock wordt kort en tijdelijk genomen.

        Hardware/bibliotheken:
            busio (I2C/SPI), digitalio (CS-pin) en adafruit_mcp3xxx voor de
            ADC, omdat de Pi geen analoge ingang heeft.

        Ontwerpkeuzes:
            High-res continue modus geeft 1 lx resolutie zonder per meting een
            commando te hoeven sturen.
        """
        # I2C bus voor de BH1750 lichtsensor
        self.i2c = busio.I2C(board.D3, board.D2)
        self.laatste_lux = 0.0

        # Start continue meting (high-res, ~120 ms per meting)
        while not self.i2c.try_lock():
            time.sleep(0.01)
        try:
            self.i2c.writeto(self.BH1750_ADDRESS, self.BH1750_COMMAND_HIGH_RES)
        finally:
            self.i2c.unlock()
        time.sleep(0.2)

        # SPI0 bus, wordt ook door het OLED-display gebruikt
        self.spi = busio.SPI(
            clock=board.SCK,
            MISO=board.MISO,
            MOSI=board.MOSI
        )

        self.cs = digitalio.DigitalInOut(board.D25)
        self.mcp = MCP.MCP3008(self.spi, self.cs)

        self.potmeter_channel = AnalogIn(self.mcp, MCP.P0)
        self.lm35_channel = AnalogIn(self.mcp, MCP.P1)

        print("Sensors initialized")

    def lees_temperatuur(self):
        """
        Lees de LM35 uit (10 mV per graad Celsius).

        Doel:
            Geeft de omgevingstemperatuur voor de brandalarm-detectie.

        Werking, stap voor stap:
            1. Lees de spanning van ADC-kanaal 1 (in volt, door de
               bibliotheek omgerekend uit de 10-bit ADC-waarde).
            2. Reken om naar millivolt (x 1000).
            3. Deel door 10: de LM35 levert 10 mV per graad Celsius.

        Parameters:
            Geen.

        Returns:
            float: temperatuur in graden Celsius

        Threads/locks:
            Leest de gedeelde SPI-bus; de aanroeper moet ``spi_lock`` nemen
            omdat het OLED dezelfde bus gebruikt. Raakt zelf geen state.

        Hardware/bibliotheken:
            LM35 via MCP3008 kanaal 1 (``AnalogIn``); de LM35 is analoog en
            de Pi heeft geen ADC.

        Opmerking:
            Deze methode doet één enkele lezing. Het uitmiddelen (mediaan van
            5 lezingen om ruis en uitschieters te onderdrukken) gebeurt bij de
            aanroeper in main.py, niet hier.
        """

        voltage_mv = self.lm35_channel.voltage * 1000.0

        return voltage_mv / 10.0

    def lees_licht(self):
        """
        Lees de BH1750 lichtsensor uit.

        Doel:
            Geeft de lichtsterkte voor de sabotagedetectie (plotseling veel
            licht = kluis geopend/belicht).

        Werking, stap voor stap:
            1. Maak een buffer van 2 bytes.
            2. Probeer de I2C-lock te pakken. Lukt dat niet, dan wordt direct
               de laatst bekende waarde teruggegeven (geen blokkade).
            3. Lees 2 bytes van adres 0x23; de sensor meet continu zelf.
            4. Geef de lock vrij (try/finally).
            5. Combineer de bytes tot een 16-bit getal (hoog << 8 | laag) en
               deel door 1.2 (datasheet-omrekenfactor naar lux).
            6. Bewaar het resultaat in ``laatste_lux`` en geef het terug.

        Parameters:
            Geen.

        Returns:
            float: lichtwaarde in lux

        Threads/locks:
            Gebruikt de I2C ``try_lock()``; schrijft ``self.laatste_lux``.
            Niet afhankelijk van ``spi_lock``.

        Hardware/bibliotheken:
            BH1750 via busio.I2C.

        Ontwerpkeuzes:
            Continue modus: geen trigger of wachttijd per meting nodig.
            ``try_lock`` met fallback voorkomt dat de 10 Hz-lus blokkeert.
        """

        result = bytearray(2)

        if not self.i2c.try_lock():
            return self.laatste_lux

        try:
            # Continuous mode: de sensor meet zelf door, dus alleen uitlezen
            self.i2c.readfrom_into(self.BH1750_ADDRESS, result)
        finally:
            self.i2c.unlock()

        self.laatste_lux = ((result[0] << 8) | result[1]) / 1.2
        return self.laatste_lux

    def lees_potmeter_raw(self):
        """
        Lees de potmeter uit.

        Doel:
            Levert de draaistand van het cijferslot als ruwe waarde.

        Werking, stap voor stap:
            1. Lees de 16-bit schaalwaarde van ADC-kanaal 0 (de bibliotheek
               schaalt de 10-bit MCP3008-waarde op naar 0..65535).
            2. Schuif 6 bits naar rechts (``>> 6``) om terug te gaan naar de
               oorspronkelijke 10-bit resolutie 0..1023.

        Parameters:
            Geen.

        Returns:
            int: ruwe waarde van 0 t/m 1023 (10-bit)

        Threads/locks:
            Leest de gedeelde SPI-bus; de aanroeper neemt ``spi_lock``.

        Hardware/bibliotheken:
            Potmeter via MCP3008 kanaal 0.

        Ontwerpkeuzes:
            De mapping naar een cijfer 0-9 en de hysterese
            (``HYSTERESIS_10BIT``) gebeuren bij de aanroeper; hier blijft de
            waarde ruw zodat die logica op één plek staat.
        """

        return self.potmeter_channel.value >> 6

    def lees_alles(self):
        """
        Lees alle sensoren in één keer uit.

        Werking:
            Roept lees_temperatuur(), lees_licht() en lees_potmeter_raw()
            achter elkaar aan en bundelt de uitkomsten.

        Parameters:
            Geen.

        Returns:
            dict: {"temperatuur": float (°C), "licht": float (lux),
            "potmeter": int (0..1023)}

        Threads/locks:
            Raakt de SPI- en I2C-bus; de aanroeper moet ``spi_lock`` nemen.

        Hardware/bibliotheken:
            LM35 + potmeter (MCP3008/SPI) en BH1750 (I2C).
        """
        return {
            "temperatuur": self.lees_temperatuur(),
            "licht": self.lees_licht(),
            "potmeter": self.lees_potmeter_raw()
        }

    def close(self):
        """
        Geef de chip-select-pin van de MCP3008 vrij bij afsluiten.

        Werking:
            Roept ``deinit()`` aan op de digitalio-pin (GPIO 25) zodat de pin
            niet vergrendeld blijft voor een volgende start.

        Parameters:
            Geen.

        Returns:
            None

        Threads/locks:
            Aanroepen nadat de threads zijn gestopt; neemt geen locks.

        Hardware/bibliotheken:
            digitalio (CS op GPIO 25). De I2C/SPI-bussen blijven open tot het
            proces eindigt.
        """
        self.cs.deinit()
        print("Sensors afgesloten")
