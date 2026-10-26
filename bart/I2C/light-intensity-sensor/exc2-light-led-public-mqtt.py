import time       # Voor tijdsvertragingen (pauzes tussen opeenvolgende metingen)
import board      # Bevat de hardware-definities van de GPIO-pinnen op de Pi
import busio      # Handelt hardware-communicatiebussen af (I2C, SPI, UART)
import digitalio  # Voor digitale input/output (GPIO) aansturing
import paho.mqtt.client as mqtt  # Officiële MQTT-bibliotheek voor Python (Paho)

# ==============================================================================
# 1. HARDWARE & GPIO / I2C INITIALISATIE
# ==============================================================================

# Wijs de fysieke pinnen toe voor de I2C-hardwarebus van de Raspberry Pi:
# - SCL (Serial Clock): GPIO 3 (fysieke pin 5) -> synchroniseert de bits
# - SDA (Serial Data):  GPIO 2 (fysieke pin 3) -> transporteert de data-bits
scl_pin = board.SCL
sda_pin = board.SDA

# Initialiseer de status-LED's op de GPIO-header
led1 = digitalio.DigitalInOut(board.D17)  # GPIO 17 (Pin 11): Indicator voor 'Donker'
led2 = digitalio.DigitalInOut(board.D27)  # GPIO 27 (Pin 13): Indicator voor 'Licht'
led1.direction = digitalio.Direction.OUTPUT
led2.direction = digitalio.Direction.OUTPUT

# Start de I2C-bus controller van de Raspberry Pi
i2c = busio.I2C(scl_pin, sda_pin)

# ==============================================================================
# 2. SENSOR CONSTANTEN (Conform Rohm BH1750 Datasheet)
# ==============================================================================

# Standaard 7-bits I2C-adres wanneer de ADDR-pin aan GND ligt of zweeft
ADDRESS = 0x23  

# Meetcommando: Continue meting in Hoge Resolutie (1 Lux resolutie, typisch 120ms integratietijd).
# Wordt verzonden als bytearray ([0x10] = decimaal 16) conform de instructietabel.
COMMAND_HIGH_RES = bytearray([0x10])

# ==============================================================================
# 3. LOKALE MQTT BROKER CONFIGURATIE & VERBINDING
# ==============================================================================

# Lokale netwerkinstellingen (communicatie binnen dezelfde Raspberry Pi via loopback)
MQTT_BROKER = "test.mosquitto.org"        # IP-adres van het lokale postkantoor (localhost)
MQTT_PORT = 1883                 # Standaard onversleutelde MQTT TCP-poort
MQTT_TOPIC = "lichtsterkte"      # Het specifieke onderwerp/postbus waarin we publiceren
MQTT_KEEPALIVE_INTERVAL = 60     # Heartbeat interval in seconden

# Maak de MQTT-client aan met de moderne Paho v2 API-standaard
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Maak de daadwerkelijke TCP-verbinding met de lokale Mosquitto broker
client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE_INTERVAL)

# Start een asynchrone achtergrondthread. Deze verzorgt automatisch de netwerk-I/O,
# TCP ACK handshakes en keepalives zonder dat onze sensorlus in while True blokkeert.
client.loop_start()

# ==============================================================================
# 4. SENSOR MEETFUNCTIE (I2C Uitlezing & 16-bit Reconstructie)
# ==============================================================================

def get_value(i2c_bus, addr):
    """
    Communiceert met de BH1750 via I2C, leest 2 bytes uit en
    rekent deze via de datasheetformule om naar een reële waarde in Lux.
    """
    # Buffer van exact 2 bytes klaargezet in RAM: [0x00, 0x00]
    result = bytearray(2)

    # Voer een gecombineerde schrijf- en leesactie uit:
    # 1. writeto: Stuur opcode 0x10 naar adres 0x23 (start meting)
    # 2. readfrom: Lees direct de 2 teruggestuurde databytes in 'result'
    i2c_bus.writeto_then_readfrom(addr, COMMAND_HIGH_RES, result)

    # 16-bit reconstructie:
    # result[0] = Hoge byte (Most Significant Byte - MSB)
    # result[1] = Lage byte (Least Significant Byte - LSB)
    # 1. result[0] << 8: Schuif de bits 8 posities naar links (wordt bits 15..8)
    # 2. | result[1]:    Voeg de lage byte in op de opengevallen bits 7..0 via bitwise OR
    # 3. / 1.2:          Optische kalibratiedeling volgens Rohm specificatie
    lux = ((result[0] << 8) | result[1]) / 1.2
    
    return lux

# ==============================================================================
# 5. HOOFDPROGRAMMA (Meetlus & Publicatie)
# ==============================================================================

print("Starting BH1750 Light Sensor & Local MQTT Publisher...")
print(f"Verbonden met broker op {MQTT_BROKER}:{MQTT_PORT} (Topic: '{MQTT_TOPIC}')")

try:
    while True:
        # Vraag exclusieve hardware-toegang tot de I2C-bus (bus locken tegen race conditions)
        if i2c.try_lock():
            try:
                # 1. Meet de actuele lichtwaarde
                lux_val = get_value(i2c, ADDRESS)
                
                # 2. Publiceer de waarde naar de lokale broker (geconverteerd naar tekst-string)
                client.publish(MQTT_TOPIC, str(lux_val))
                
                # 3. Lokale feedback in de console en sturing van de drempelwaarde-LED's
                if lux_val < 20:
                    print(f"[METING] {lux_val:.2f} Lux -> Status: DONKER (LED1 AAN)")
                    led1.value = True
                    led2.value = False
                else:
                    print(f"[METING] {lux_val:.2f} Lux -> Status: LICHT (LED2 AAN)")
                    led1.value = False
                    led2.value = True

            except Exception as e:
                print(f"[FOUT] Fout bij uitlezen sensor: {e}")
            finally:
                # Zorg dat de I2C-bus ALTIJD wordt vrijgegeven voor andere processen
                i2c.unlock()

        # Pauzeer 1 seconde tussen metingen
        time.sleep(1)

except KeyboardInterrupt:
    # Nette en veilige shutdown bij Ctrl+C
    print("\nAfsluiten door gebruiker...")
    
    # Stop de MQTT achtergrondthread en sluit de TCP-socket netjes af
    client.loop_stop()
    client.disconnect()
    
    # Schakel beide LED's uit ter bescherming van de pinnen
    led1.value = False
    led2.value = False
    print("MQTT netwerkverbinding gesloten en hardware veilig uitgeschakeld.")
