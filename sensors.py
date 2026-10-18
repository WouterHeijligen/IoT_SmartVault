#!/usr/bin/env python3

import time
import board
import busio
import digitalio
import paho.mqtt.client as mqtt
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn

class Sensors:
    def __init__(self):
        # ============================================================
        # LM35 TEMPERATURE SENSOR - MCP3008 SPI
        # ============================================================

        self.spi = busio.SPI(
            clock=board.SCK,
            MISO=board.MISO,
            MOSI=board.MOSI
        )

        # MCP3008 CS connected to GPIO25
        self.cs = digitalio.DigitalInOut(board.D25)

        self.mcp = MCP.MCP3008(self.spi, self.cs)

        # LM35 connected to channel 1
        self.lm35_channel = AnalogIn(self.mcp, MCP.P1)

        # 10-k potentiometer connecter to channel 0
        self.pot_channel = AnalogIn(self.mcp, MCP.P0)

        # ============================================================
        # BH1750 LIGHT SENSOR - I2C
        # ============================================================

        self.i2c = busio.I2C(
            board.D3,
            board.D2
        )

        self.BH1750_ADDRESS = 0x23
        self.BH1750_COMMAND_HIGH_RES = bytearray([0x10])

        print("Sensors initialized")

    def raw_to_digit(self, raw_10bit: int) -> int:
        """
        Zet de 10-bit ADC-waarde (0..1023) om naar een cijfer van 0 t/m 9.
        Door gehele deling door 102.4 krijgen we exact 10 gelijke intervallen.
        """
        digit = (raw_10bit * 10) // 1024
        return min(9, max(0, digit))

    def lees_temperatuur(self):
        """
        Lees temperatuur uit.

        Returns:
            float: temperatuur in graden Celsius
        """

        voltage_mv = self.lm35_channel.voltage * 1000.0
        
        # LM35 = 10 mV per degree Celsius
        temperatuur = voltage_mv / 10.0

        return temperatuur

    def lees_licht(self):
        """
        Lees lichtsensor uit.

        Returns:
            float: lichtwaarde
        """

        result = bytearray(2)
        
        while not self.i2c.try_lock():
            time.sleep(0.01)
    
        try:
            self.i2c.writeto_then_readfrom(
                self.BH1750_ADDRESS,
                self.BH1750_COMMAND_HIGH_RES,
                result
            )
        finally:
            self.i2c.unlock()
    
        licht = ((result[0] << 8) | result[1]) / 1.2

        return licht

    def lees_potentiometer(self):
        """
        Lees de waarde van de 10-k potentiometer uit.

        Returns:
            float: potentiometerwaarde (0..1023)
        """

        raw_value = self.pot_channel.value
        return raw_value

    def lees_alles(self):
        return {
            "temperatuur": self.lees_temperatuur(),
            "licht": self.lees_licht(),
            "potentiometer": self.lees_potentiometer()
        }

    def close(self):
        self.spi.deinit()
        self.cs.deinit()
        self.i2c.deinit()
        print("Sensors afgesloten")