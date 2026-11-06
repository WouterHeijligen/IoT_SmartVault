#!/usr/bin/env python3
"""
================================================================================
BESTAND: sensors.py
DOEL:    Uitlezen van alle sensoren op de kluis (Licht, Temperatuur, Draaiknop).
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
In dit bestand lezen we drie verschillende sensoren uit:
1. BH1750 Lichtsensor (Digitaal, via de I2C-bus op GPIO 2 en 3):
   Meet hoeveel licht (in lux) er in de kluis valt. Als de kluis op slot zit
   en er valt plots licht naar binnen, weten we dat de kluis wordt opengebroken!
2. Potmeter / Draaiknop (Analoog, op kanaal 0 van de MCP3008-chip):
   Hiermee draait de gebruiker naar het juiste cijfer (0 t/m 9) van de pincode.
3. LM35 Temperatuursensor (Analoog, op kanaal 1 van de MCP3008-chip):
   Meet de temperatuur in graden Celsius om brand te detecteren.

💡 BELANGRIJKE VRAAG OP JE VERDEDIGING (Waarom een MCP3008 chip?):
Een Raspberry Pi heeft alleen DIGITALE pinnen (die kennen alleen 0 of 1, aan of uit).
Maar een draaiknop (potmeter) en een LM35 temperatuursensor geven een ANALOGE
spanning af (bijv. 0,22 Volt of 1,65 Volt). Daarom gebruiken we de MCP3008:
dat is een ADC (Analoog-naar-Digitaal Converter). Die chip meet de analoge
spanning en stuurt die via de SPI-bus als een digitaal getal naar de Raspberry Pi!
"""

import time

import board
import busio
import digitalio
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn


class Sensors:
    """
    Bundelt alle sensoren in één handige klasse, zodat `main.py` gewoon
    `lees_temperatuur()`, `lees_licht()` en `lees_potmeter_raw()` kan aanroepen.
    """

    # Het vaste adres van de BH1750 lichtsensor op de I2C-kabel is 0x23 (hexadecimaal).
    BH1750_ADDRESS = 0x23
    # Commando 0x10 vertelt de BH1750: "Blijf continu meten met hoge nauwkeurigheid (1 lux)".
    BH1750_COMMAND_HIGH_RES = bytearray([0x10])

    def __init__(self):
        """
        Zet de communicatiekabels (I2C en SPI) open en bereidt de sensoren voor.
        """
        # --- 1. I2C-bus klaarmaken voor de BH1750 Lichtsensor ---
        # I2C gebruikt maar 2 draadjes: een kloklijn (SCL op GPIO 3) en een datalijn (SDA op GPIO 2).
        self.i2c = busio.I2C(board.D3, board.D2)
        # Bewaart de laatst gemeten lichtwaarde
        self.laatste_lux = 0.0

        # We reserveren heel even de I2C-lijn (`try_lock`), sturen het startcommando
        # naar de BH1750, en geven de lijn in `finally` altijd weer netjes vrij (`unlock`).
        while not self.i2c.try_lock():
            time.sleep(0.01)
        try:
            self.i2c.writeto(self.BH1750_ADDRESS, self.BH1750_COMMAND_HIGH_RES)
        finally:
            self.i2c.unlock()

        # Geef de lichtsensor 0,2 seconde de tijd om zijn allereerste meting af te ronden.
        time.sleep(0.2)

        # --- 2. SPI-bus klaarmaken voor de MCP3008 (ADC-chip) ---
        # Let op: ook het OLED-scherm gebruikt deze SPI-bus! Daarom geeft `main.py`
        # deze `self.spi` straks ook door aan het Display-object.
        self.spi = busio.SPI(
            clock=board.SCK,
            MISO=board.MISO,
            MOSI=board.MOSI
        )

        # CS = Chip Select (op GPIO 25). Hiermee zegt de Raspberry Pi tegen de MCP3008:
        # "Ik praat nu tegen jou!"
        self.cs = digitalio.DigitalInOut(board.D25)
        self.mcp = MCP.MCP3008(self.spi, self.cs)

        # Sluit de analoge kanalen aan:
        # Kanaal P0 = Potmeter (draaiknop voor pincode)
        # Kanaal P1 = LM35 (temperatuursensor)
        self.potmeter_channel = AnalogIn(self.mcp, MCP.P0)
        self.lm35_channel = AnalogIn(self.mcp, MCP.P1)

        print("Sensors initialized")

    def lees_temperatuur(self):
        """
        Leest de LM35 temperatuursensor uit en geeft de temperatuur in °C terug.

        💡 HOE WERKT DE FORMULE? (Goed om te weten voor je presentatie!)
        De LM35 is heel makkelijk: per graad Celsius geeft hij precies 10 millivolt (mV) af.
        Dus:
        - 20 °C = 200 mV (0,20 Volt)
        - 25 °C = 250 mV (0,25 Volt)
        We vermenigvuldigen het aantal Volt met 1000 (om van Volt naar millivolt te gaan)
        en delen daarna door 10 om het aantal graden Celsius te krijgen!
        """
        voltage_mv = self.lm35_channel.voltage * 1000.0

        return voltage_mv / 10.0

    def lees_licht(self):
        """
        Leest de lichtsterkte (in lux) uit de BH1750 sensor via I2C.

        Hoe werkt het?
        De sensor stuurt 2 losse bytes terug (samen een 16-bit getal).
        Met `(result[0] << 8) | result[1]` plakken we die twee bytes aan elkaar tot één getal,
        en volgens de handleiding (datasheet) van de BH1750 moet je dat getal delen door 1.2
        om de echte waarde in lux te krijgen.
        """
        result = bytearray(2)

        # Is de I2C-lijn heel even bezet? Geen probleem, geef gewoon de vorige waarde terug
        # zodat het programma nooit hoeft te wachten.
        if not self.i2c.try_lock():
            return self.laatste_lux

        try:
            # Lees de 2 bytes met de nieuwste lichtmeting uit de sensor
            self.i2c.readfrom_into(self.BH1750_ADDRESS, result)
        finally:
            self.i2c.unlock()

        # Plak de twee bytes aan elkaar en deel door 1.2 (formule uit de datasheet)
        self.laatste_lux = ((result[0] << 8) | result[1]) / 1.2
        return self.laatste_lux

    def lees_potmeter_raw(self):
        """
        Leest de stand van de draaiknop (potmeter) uit als een getal van 0 t/m 1023.

        💡 WAAROM STAAT ER `>> 6`?
        De MCP3008 is een 10-bit chip (geeft getallen van 0 t/m 1023).
        Maar de Adafruit-bibliotheek trekt dat getal standaard omhoog naar 16-bit (0 t/m 65535).
        Door 6 bits naar rechts te schuiven (`>> 6`, oftewel delen door 64) krijgen we
        weer netjes het originele 10-bit getal van 0 t/m 1023 terug!
        """
        return self.potmeter_channel.value >> 6

    def lees_alles(self):
        """
        Hulpfunctie om in één keer alle drie de sensoren uit te lezen en als
        woordenboekje (dictionary) terug te geven.
        """
        return {
            "temperatuur": self.lees_temperatuur(),
            "licht": self.lees_licht(),
            "potmeter": self.lees_potmeter_raw()
        }

    def close(self):
        """
        Geeft de Chip-Select pin (GPIO 25) weer netjes vrij bij het afsluiten.
        """
        self.cs.deinit()
        print("Sensors afgesloten")
