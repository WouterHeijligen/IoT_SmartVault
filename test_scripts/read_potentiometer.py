#!/usr/bin/env python3
"""
Potentiometer uitlezen (0-9) en weergeven op SSD1306 OLED Display
Thomas More Geel - IoT Essentials
MCP3008 via SPI0 (CH0) & SSD1306 OLED via I2C (0x3C)
"""

import time
import board
import busio
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn

# ==============================================================================
# 1. INITIALISATIE SSD1306 OLED
# ==============================================================================
# Define the Reset Pin
oled_reset = digitalio.DigitalInOut(board.D16)

# Change these
# to the right size for your display!
WIDTH = 128
HEIGHT = 64 # Change to 64 if needed
BORDER = 5

# Use for SPI
spi = board.SPI()
oled_dc = digitalio.DigitalInOut(board.D6)
oled = adafruit_ssd1306.SSD1306_SPI(WIDTH, HEIGHT, spi, oled_dc, oled_reset, None)

# Clear display.
oled.fill(0)
oled.show()

# ==============================================================================
# 2. INITIALISATIE SPI & MCP3008 ADC
# ==============================================================================
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# Chip Select op GPIO 8 (CE0)
cs = digitalio.DigitalInOut(board.D24)
mcp = MCP.MCP3008(spi, cs)

# Potentiometer aangesloten op Kanaal 0 (CH0)
pot_channel = AnalogIn(mcp, MCP.P0)

# ==============================================================================
# 3. HELPER FUNCTIES
# ==============================================================================
def raw_to_digit(raw_10bit: int) -> int:
    """
    Zet de 10-bit ADC-waarde (0..1023) om naar een cijfer van 0 t/m 9.
    Door gehele deling door 102.4 krijgen we exact 10 gelijke intervallen.
    """
    digit = (raw_10bit * 10) // 1024
    return min(9, max(0, digit))

def teken_dashboard(digit: int, raw_val: int, voltage: float):
    """Tekent het cijferslot en de voortgangsbalk op het OLED-scherm."""
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    # Helper om tekst horizontaal te centreren
    def center_text(y, text):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (oled.width - text_width) // 2
        draw.text((x, y), text, font=font, fill=255)

    # -------------------------
    # Titel
    # -------------------------
    center_text(1, "SMART VAULT")
    draw.line((0, 12, 127, 12), fill=255)

    # -------------------------
    # Geselecteerde code
    # -------------------------
    code_text = f"CODE: [{digit}]"

    bbox = draw.textbbox((0, 0), code_text, font=font)
    text_width = bbox[2] - bbox[0]

    # Vak automatisch aanpassen aan tekstbreedte
    padding = 6
    box_width = text_width + (padding * 2)

    box_left = (oled.width - box_width) // 2
    box_right = box_left + box_width

    draw.rectangle(
        (box_left, 17, box_right, 39),
        outline=255,
        fill=0
    )

    center_text(24, code_text)

    # -------------------------
    # Voortgangsbalk 0 t/m 9
    # -------------------------
    draw.rectangle((10, 43, 118, 50), outline=255, fill=0)

    vul_breedte = int((digit / 9.0) * 106)

    if vul_breedte > 0:
        draw.rectangle(
            (11, 44, 11 + vul_breedte, 49),
            fill=255
        )

    # -------------------------
    # Voltage + ADC
    # -------------------------
    draw.text(
        (2, 54),
        f"U:{voltage:.2f}V",
        font=font,
        fill=255
    )

    adc_text = f"ADC:{raw_val}"
    bbox = draw.textbbox((0, 0), adc_text, font=font)
    adc_width = bbox[2] - bbox[0]

    draw.text(
        (126 - adc_width, 54),
        adc_text,
        font=font,
        fill=255
    )

    oled.image(image)
    oled.show()


# ==============================================================================
# 4. HOOFDPROGRAMMA
# ==============================================================================
def main():
    print("==================================================")
    print(" Potentiometer Cijferslot (0-9) op OLED gestart")
    print(" Draai aan de potmeter om de waarde te veranderen.")
    print(" Druk op CTRL+C om te stoppen.")
    print("==================================================")

    last_digit = -1

    try:
        while True:
            # CircuitPython AnalogIn schaalt naar 16-bit (0..65535).
            # Met >> 6 krijgen we weer de pure 10-bit ADC resolutie (0..1023).
            raw_10bit = pot_channel.value >> 6
            voltage = pot_channel.voltage
            oled.show()
            huidig_cijfer = raw_to_digit(raw_10bit)

            # Update scherm en terminal als het getal verandert (of bij minimale variatie)
            if huidig_cijfer != last_digit:
                print(f">> Gekozen Cijfer: {huidig_cijfer} (ADC: {raw_10bit}, Spanning: {voltage:.2f}V)")
                last_digit = huidig_cijfer

            # Teken de actuele status op het display
            teken_dashboard(huidig_cijfer, raw_10bit, voltage)

            time.sleep(0.05)  # 20 Hz update-snelheid voor soepele respons

    except KeyboardInterrupt:
        print("\nProgramma gestopt door gebruiker.")
    finally:
        # Wis het scherm netjes bij afsluiten
        oled.fill(0)
        oled.show()
        print("Display gewist en afgesloten.")

if __name__ == "__main__":
    main()