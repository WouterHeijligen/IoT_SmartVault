import time
import board
import busio
import paho.mqtt.client as mqtt

# ==============================================================================
# 1. HARDWARE & BH1750 I2C SENSOR CONFIGURATIE
# ==============================================================================

# Wijs de hardware I2C-pinnen van de Pi toe (GPIO 2 & GPIO 3)
scl_pin = board.SCL   # Fysieke pin 5
sda_pin = board.SDA   # Fysieke pin 3

# Initialiseer de I2C-controller
i2c = busio.I2C(scl_pin, sda_pin)

# BH1750 hardware-constanten
BH1750_ADDRESS = 0x23              # I2C adres (ADDR aan GND of los)
COMMAND_HIGH_RES = bytearray([0x10]) # Opcode voor continue H-Resolution meting (1 lux)

def read_bh1750_lux(i2c_bus, addr):
    """
    Leest 2 bytes uit over I2C, voegt MSB en LSB samen via bitshift,
    en deelt door de 1.2 optische factor conform de datasheet.
    """
    result = bytearray(2)
    i2c_bus.writeto_then_readfrom(addr, COMMAND_HIGH_RES, result)
    lux = ((result[0] << 8) | result[1]) / 1.2
    return lux

# ==============================================================================
# 2. THINGSPEAK & MQTT CONFIGURATIE
# ==============================================================================

INTERVAL = 15  # ThingSpeak vereist minstens 15s tussen updates op de gratis tier

MQTT_HOST = "mqtt3.thingspeak.com"
MQTT_PORT = 1883
MQTT_KEEPALIVE_INTERVAL = 60

# ⚠️ VUL HIER JOUW GEGEVENS IN VAN THINGSPEAK (Devices -> MQTT):
CHANNEL_ID = "3529778"      # Vul je numerieke Channel ID in
MQTT_TOPIC = f"channels/{CHANNEL_ID}/publish"

MQTT_CLIENT_ID = "Oh01HRU1BQwMJwwyEgMcPTI"
MQTT_USER = "Oh01HRU1BQwMJwwyEgMcPTI"
MQTT_PWD = "RrEVlgbRTuHLGtJ0HzYnEb07"

# ==============================================================================
# 3. MQTT CALLBACK HANDLERS (Paho API v2)
# ==============================================================================

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print(f"[MQTT] Verbonden met ThingSpeak broker ({MQTT_HOST})!")
    else:
        print(f"[MQTT] Fout bij verbinden, return code: {rc}")

def on_disconnect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Verbinding verbroken (code: {rc})")

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    print(f"[MQTT IN] {msg.topic}: {payload}")

# ==============================================================================
# 4. INITIALISATIE MQTT CLIENT
# ==============================================================================

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
client.username_pw_set(MQTT_USER, MQTT_PWD)

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

print("Verbinding maken met ThingSpeak MQTT broker...")
client.connect(MQTT_HOST, MQTT_PORT, keepalive=MQTT_KEEPALIVE_INTERVAL)
client.loop_start()  # Start achtergrondthread voor MQTT communicatie

# ==============================================================================
# 5. HOOFDPROGRAMMA (Meetlus)
# ==============================================================================

print("Starting BH1750 Cloud Uplink to ThingSpeak...")

try:
    while True:
        lux_val = None

        # 1. Lees de sensor veilig uit via I2C bus lock
        if i2c.try_lock():
            try:
                lux_val = read_bh1750_lux(i2c, BH1750_ADDRESS)
            finally:
                i2c.unlock()

        # 2. Als de meting geslaagd is, stuur door naar de cloud
        if lux_val is not None:
            print(f"[METING] Lichtsterkte: {lux_val:.2f} Lux")

            # ThingSpeak payload formaat voor Field 1
            mqtt_payload = f"field1={lux_val:.2f}&status=MQTTPUBLISH"
            
            try:
                print(f"[MQTT OUT] Publiceren -> {mqtt_payload}")
                client.publish(topic=MQTT_TOPIC, payload=mqtt_payload, qos=0, retain=False)
            except OSError as e:
                print(f"[FOUT] Netwerkfout: {e}. Reconnecten...")
                client.reconnect()

        # 3. Wacht 15 seconden conform de ThingSpeak rate limit
        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("\nAfsluiten...")
    client.loop_stop()
    client.disconnect()
    print("MQTT netwerklus gestopt. Klaar.")
