import os
import time

import board
import socketpool
import wifi
import adafruit_hcsr04
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# RCWL-9610A in trigger/echo-modus: TRIG op GP27 (pin 32), ECHO op GP28 (pin 34)
sonar = adafruit_hcsr04.HCSR04(trigger_pin=board.GP27, echo_pin=board.GP28)

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "vault/perimeter/distance")
PUBLISH_INTERVAL_S = 0.5


def connect_wifi():
    while not wifi.radio.connected:
        try:
            print("Wi-Fi verbinden...")
            wifi.radio.connect(
                os.getenv("CIRCUITPY_WIFI_SSID"),
                os.getenv("CIRCUITPY_WIFI_PASSWORD"),
            )
        except Exception as e:
            print(f"Wi-Fi mislukt: {e}")
            time.sleep(2)
    print(f"Wi-Fi OK, IP: {wifi.radio.ipv4_address}")


def connect_mqtt():
    client = MQTT.MQTT(
        broker=MQTT_BROKER,
        port=1883,
        socket_pool=socketpool.SocketPool(wifi.radio),
        client_id="pico_perimeter",
    )
    client.connect()
    print(f"MQTT verbonden met {MQTT_BROKER}")
    return client


connect_wifi()
mqtt = connect_mqtt()

while True:
    try:
        if not wifi.radio.connected:
            connect_wifi()
            mqtt = connect_mqtt()

        afstand = sonar.distance
        mqtt.publish(MQTT_TOPIC, f"{afstand:.1f}")
        print(f"Afstand: {afstand:.1f} cm")

    except RuntimeError:
        print("Geen echo ontvangen (te dichtbij, te ver of bedrading controleren)")

    except Exception as e:
        print(f"Verbinding verbroken ({e}), opnieuw verbinden...")
        time.sleep(2)
        try:
            connect_wifi()
            mqtt = connect_mqtt()
        except Exception as e2:
            print(f"Opnieuw verbinden mislukt: {e2}")

    time.sleep(PUBLISH_INTERVAL_S)
