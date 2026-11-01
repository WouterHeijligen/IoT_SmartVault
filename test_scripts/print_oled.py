import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
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

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
image = Image.new("1", (oled.width, oled.height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a white background
draw.rectangle((0, 0, oled.width, oled.height), outline=255, fill=255)
# Draw a smaller inner rectangle
draw.rectangle(
  (BORDER, BORDER, oled.width - BORDER - 1, oled.height - BORDER - 1),
  outline=0,
  fill=0,
)

# Load default font.
font = ImageFont.load_default()

# Draw Some Text
text = "Hello Wouter!"
bbox = font.getbbox(text)
(font_width, font_height) = bbox[2] - bbox[0], bbox[3] - bbox[1]
draw.text(
  (oled.width // 2 - font_width // 2, oled.height // 2 - font_height // 2),
  text,
  font=font,
  fill=255,
)

# Display image
oled.image(image)
oled.show()