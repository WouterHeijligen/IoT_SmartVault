#!/usr/bin/env python3
"""
LM35 Temperatuursensor uitlezen via MCP3008 ADC (SPI) op Raspberry Pi 5
Thomas More Geel - IoT Essentials
"""

import time
import board
import busio
import digitalio
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn

# --- SPI & ADC Initialisatie ---
# Initialiseer de SPI-bus (SCLK, MOSI, MISO)
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# Initialiseer Chip Select (CS) op GPIO 24 (of CE0 / GPIO 8 afhankelijk van je wiring)
cs = digitalio.DigitalInOut(board.D24)

# MCP3008 initialiseren
mcp = MCP.MCP3008(spi, cs)

# LM35 aangesloten op CH1 van de MCP3008
lm35_channel = AnalogIn(mcp, MCP.P1)

print("----------------------------------------")
print(" LM35 Temperatuursensor uitlezen gestart")
print(" Druk op CTRL+C om te stoppen.")
print("----------------------------------------")

try:
    while True:
        # 1. Lees de spanning in millivolt uit via de MCP3008
        # De .voltage property geeft direct de gemeten spanning in Volt (0V tot 3.3V)
        voltage_mv = lm35_channel.voltage * 1000.0

        # 2. Omrekening naar graden Celsius voor de LM35:
        # De LM35 geeft een linear signaal af van 10 mV per °C (dus 10 mV/°C)
        temperature_c = voltage_mv / 10.0

        # 3. Print de meetresultaten naar de console
        print(f"Gemeten Spanning: {voltage_mv:.1f} mV  -->  Temperatuur: {temperature_c:.2f} °C")

        # Wacht 1 seconde voor de volgende meting
        time.sleep(1.0)

except KeyboardInterrupt:
    print("\nProgramma gestopt door gebruiker.")