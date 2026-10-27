#!/usr/bin/env python3

import time
import board
import busio
import digitalio
import paho.mqtt.client as mqtt

import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn


# ============================================================
# BH1750 LIGHT SENSOR - I2C
# ============================================================

scl_pin = board.D3
sda_pin = board.D2

i2c = busio.I2C(scl_pin, sda_pin)

BH1750_ADDRESS = 0x23
BH1750_COMMAND_HIGH_RES = bytearray([0x10])


def get_light_level():
    result = bytearray(2)

    while not i2c.try_lock():
        time.sleep(0.01)

    try:
        i2c.writeto_then_readfrom(
            BH1750_ADDRESS,
            BH1750_COMMAND_HIGH_RES,
            result
        )
    finally:
        i2c.unlock()

    lux = ((result[0] << 8) | result[1]) / 1.2

    return lux


# ============================================================
# LM35 TEMPERATURE SENSOR - MCP3008 SPI
# ============================================================

spi = busio.SPI(
    clock=board.SCK,
    MISO=board.MISO,
    MOSI=board.MOSI
)

# MCP3008 CS connected to GPIO24
cs = digitalio.DigitalInOut(board.D24)

mcp = MCP.MCP3008(spi, cs)

# LM35 connected to channel 1
lm35_channel = AnalogIn(mcp, MCP.P1)


def get_temperature():
    voltage_mv = lm35_channel.voltage * 1000.0

    # LM35 = 10 mV per degree Celsius
    temperature_c = voltage_mv / 10.0

    return temperature_c, voltage_mv


# ============================================================
# MQTT / THINGSPEAK
# ============================================================

MQTT_HOST = "mqtt3.thingspeak.com"
MQTT_PORT = 1883
MQTT_KEEPALIVE_INTERVAL = 60

MQTT_TOPIC = "channels/3529335/publish"

# Vul hier dezelfde gegevens in als in je werkende mqqt_test.py
MQTT_CLIENT_ID = "KR40OTsKJAM9KBgCGwE1IBQ"
MQTT_USER = "KR40OTsKJAM9KBgCGwE1IBQ"
MQTT_PWD = "jieGpRIkJ13nBPhXa2yAFR5g"

# ThingSpeak niet te vaak updaten
PUBLISH_INTERVAL = 20


# ============================================================
# MQTT CALLBACKS
# ============================================================

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print("Connected OK")
    else:
        print("Bad connection with result code " + str(rc))


def on_disconnect(
    client,
    userdata,
    disconnect_flags,
    reason_code,
    properties
):
    print("Disconnected result code " + str(reason_code))


def on_message(client, userdata, msg):
    payload = msg.payload.decode(
        "utf-8",
        errors="replace"
    )

    print(
        "Received message on topic: "
        + msg.topic
        + "; message: "
        + payload
    )


# ============================================================
# MQTT CLIENT SETUP
# ============================================================

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    MQTT_CLIENT_ID
)

client.username_pw_set(
    MQTT_USER,
    MQTT_PWD
)

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message


print("----------------------------------------")
print(" Smart Vault Sensor Monitoring")
print("----------------------------------------")
print(" BH1750 : Light")
print(" LM35   : Temperature")
print("----------------------------------------")
print("Attempting to connect to", MQTT_HOST)

client.connect(
    MQTT_HOST,
    MQTT_PORT,
    MQTT_KEEPALIVE_INTERVAL
)

client.loop_start()


# ============================================================
# MAIN LOOP
# ============================================================

try:

    while True:

        try:

            # ---------------------------------------------
            # Read light sensor
            # ---------------------------------------------

            lux = get_light_level()

            # ---------------------------------------------
            # Read temperature sensor
            # ---------------------------------------------

            temperature_c, voltage_mv = get_temperature()

            # ---------------------------------------------
            # Print measurements
            # ---------------------------------------------

            print("----------------------------------------")

            print(
                f"Light       : {lux:.1f} lux"
            )

            print(
                f"Temperature : {temperature_c:.2f} °C"
            )

            print(
                f"LM35 voltage: {voltage_mv:.1f} mV"
            )

            # ---------------------------------------------
            # ThingSpeak MQTT payload
            #
            # field1 = Light
            # field2 = Temperature
            # ---------------------------------------------

            payload = (
                f"field1={lux:.1f}"
                f"&field2={temperature_c:.2f}"
                f"&status=SmartVaultSensorMeasurement"
            )

            print("MQTT payload:", payload)

            # ---------------------------------------------
            # Publish MQTT message
            # ---------------------------------------------

            message = client.publish(
                topic=MQTT_TOPIC,
                payload=payload,
                qos=0,
                retain=False
            )

            if message.rc == mqtt.MQTT_ERR_SUCCESS:
                print("MQTT publish OK")
            else:
                print(
                    f"MQTT publish failed: {message.rc}"
                )

        except OSError as error:

            print(
                f"Sensor/I2C/SPI error: {error}"
            )

        except Exception as error:

            print(
                f"Unexpected error: {error}"
            )

        time.sleep(PUBLISH_INTERVAL)


except KeyboardInterrupt:

    print()
    print("Stopping Smart Vault sensor...")


finally:

    client.loop_stop()
    client.disconnect()

    print("MQTT disconnected.")