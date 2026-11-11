#!/usr/bin/env python3
import time

import board
import busio
import digitalio
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn


class Sensors:
    BH1750_ADDRESS = 0x23
    BH1750_COMMAND_HIGH_RES = bytearray([0x10])  # Continuous High-Res mode (1 lux)

    def __init__(self):
        self.i2c = busio.I2C(board.D3, board.D2)
        self.laatste_lux = 0.0

        while not self.i2c.try_lock():
            time.sleep(0.01)
        try:
            self.i2c.writeto(self.BH1750_ADDRESS, self.BH1750_COMMAND_HIGH_RES)
        finally:
            self.i2c.unlock()

        # Eerste BH1750-meting duurt ~120 ms
        time.sleep(0.2)

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
        # LM35: 10 mV/°C
        voltage_mv = self.lm35_channel.voltage * 1000.0

        return voltage_mv / 10.0

    def lees_licht(self):
        result = bytearray(2)

        if not self.i2c.try_lock():
            return self.laatste_lux

        try:
            self.i2c.readfrom_into(self.BH1750_ADDRESS, result)
        finally:
            self.i2c.unlock()

        # Datasheet-schaalfactor 1.2 voor lux
        self.laatste_lux = ((result[0] << 8) | result[1]) / 1.2
        return self.laatste_lux

    def lees_potmeter_raw(self):
        # 16-bit waarde terugschalen naar 10-bit (0..1023)
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
