#read out the BH1750 light sensor
import time
import board
import busio

# Create sensor object, communicating over the board's I2C bus
scl_pin = board.D3 # Replace with your actual SCL pin, D3 for I2c1 (D1 for I2c0)
sda_pin = board.D2 # Replace with your actual SDA pin, D2 for I2c1 (D0 for I2c0)

# Initialize the bus
i2c = busio.I2C(scl_pin, sda_pin)
ADDRESS = 0x23
COMMAND_HIGH_RES = bytearray([0x10]) # 1lx resolution

def get_value(i2c_bus, addr):
  # Buffer to hold the 2 bytes of data
  result = bytearray(2)
  
  # Combined write/read operation (replaces i2c_rdwr)
  # Sends 0x10, then reads 2 bytes back
  i2c_bus.writeto_then_readfrom(addr, COMMAND_HIGH_RES, result)
  
  # Conversion logic from BH1750 datasheet
  # MSB is result[0], LSB is result[1]
  lux = ((result[0] << 8) | result[1]) / 1.2
  return lux
print("Starting BH1750 Light Sensor...")

try:
  while True:
    # Ensure the bus is locked before communication
    if i2c.try_lock():
      try:
        lux_val = get_value(i2c, ADDRESS)
        print(f"{lux_val:.2f} Lux")
      finally:
        i2c.unlock()
    
    time.sleep(1)
except KeyboardInterrupt:
  print("\nStopped by user.")