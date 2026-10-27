#!/usr/bin/env python3

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
    """

    BH1750_ADDRESS = 0x23
    BH1750_COMMAND_HIGH_RES = bytearray([0x10])

    def __init__(self):
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

        Returns:
            float: temperatuur in graden Celsius
        """

        voltage_mv = self.lm35_channel.voltage * 1000.0

        return voltage_mv / 10.0

    def lees_licht(self):
        """
        Lees de BH1750 lichtsensor uit.

        Returns:
            float: lichtwaarde in lux
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

        Returns:
            int: ruwe waarde van 0 t/m 1023 (10-bit)
        """

        return self.potmeter_channel.value >> 6

    def lees_alles(self):
        return {
            "temperatuur": self.lees_temperatuur(),
            "licht": self.lees_licht(),
            "potmeter": self.lees_potmeter_raw()
        }

    def close(self):
        self.cs.deinit()
        print("Sensors afgesloten")
