"""
================================================================================
BESTAND: pico_2w/code.py
DOEL:    Draadloze afstandssensor op de Raspberry Pi Pico 2 W (CircuitPython).
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
Waarom gebruiken we naast onze Raspberry Pi 5 óók nog een Raspberry Pi Pico 2 W?
In een echt IoT-systeem hangt een bewegingssensor of afstandssensor vaak op een
andere plek (bijvoorbeeld boven de deur of aan de muur voor de kluis).
De Pico 2 W is een kleine, zuinige microcontroller met ingebouwde Wi-Fi:
1. Hij meet elke halve seconde (0,5 s) met een ultrasone sensor (type RCWL-9610A / HC-SR04)
   hoe ver iemand van de kluis vandaan staat (in centimeters).
2. Hij stuurt dat getal draadloos via **MQTT** over Wi-Fi naar de Raspberry Pi 5
   op het topic `vault/perimeter/distance`.
3. De Raspberry Pi 5 ontvangt dit getal. Blijft iemand langer dan 15 seconden
   dichterbij dan 40 cm staan zonder de kluis te bedienen ("loitering")?
   Dan gaat op de Pi 5 het alarm af!

💡 HOE WERKT EEN ULTRASONE SENSOR? (Makkelijke uitleg voor je presentatie)
Net als een vleermuis! De sensor stuurt via de `TRIG`-pin (GP27) een kort,
onhoorbaar hoog geluidspulsje uit. Dat geluid kaatst terug tegen een persoon
en wordt opgevangen door de `ECHO`-pin (GP28). Uit de tijd die het geluid
onderweg was, berekent de bibliotheek `adafruit_hcsr04` automatisch de afstand
in centimeters!
"""

import os
import time

import board
import socketpool
import wifi
import adafruit_hcsr04
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# 1. Ultrasone afstandssensor klaarmaken:
# TRIG (geluid zenden) zit op pin GP27, ECHO (geluid terug ontvangen) zit op pin GP28.
sonar = adafruit_hcsr04.HCSR04(trigger_pin=board.GP27, echo_pin=board.GP28)

# 2. Haal de netwerkinstellingen uit het bestand `settings.toml` op de Pico 2 W.
# Zo staan er geen wifi-wachtwoorden of IP-adressen vast in de broncode!
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "vault/perimeter/distance")
PUBLISH_INTERVAL_S = 0.5  # Elke halve seconde een meting versturen


def connect_wifi():
    """
    Maakt verbinding met het Wi-Fi netwerk (gegevens komen uit `settings.toml`).
    Blijft het elke 2 seconden opnieuw proberen tot er verbinding is.
    """
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
    """
    Maakt verbinding met de lokale MQTT-broker (Mosquitto) die op de Raspberry Pi 5 draait.
    Geeft het verbonden MQTT-object terug zodat we daarmee berichten kunnen sturen (`publish`).
    """
    client = MQTT.MQTT(
        broker=MQTT_BROKER,
        port=1883,
        socket_pool=socketpool.SocketPool(wifi.radio),
        client_id="pico_perimeter",
    )
    client.connect()
    print(f"MQTT verbonden met {MQTT_BROKER}")
    return client


# Verbind bij het opstarten eerst met Wi-Fi en daarna met de MQTT-broker
connect_wifi()
mqtt = connect_mqtt()

# ==============================================================================
# HOOFDLUS: Meet elke 0,5 seconde de afstand en stuur die via MQTT naar de Pi 5
# ==============================================================================
while True:
    try:
        # Als de Wi-Fi tussendoor is weggevallen, verbind dan eerst opnieuw
        if not wifi.radio.connected:
            connect_wifi()
            mqtt = connect_mqtt()

        # Meet de afstand in centimeters met de ultrasone sensor
        afstand = sonar.distance

        # Stuur de afstand met 1 cijfer achter de komma (bijv. "38.4") naar de Raspberry Pi 5
        mqtt.publish(MQTT_TOPIC, f"{afstand:.1f}")
        print(f"Afstand: {afstand:.1f} cm")

    except RuntimeError:
        # Als niemand voor de sensor staat (of te ver weg), komt er geen echo terug.
        # De sensor geeft dan een `RuntimeError`. Dat is heel normaal, dus we vangen
        # die netjes op en meten een halve seconde later gewoon opnieuw!
        print("Geen echo ontvangen (te dichtbij, te ver of bedrading controleren)")

    except Exception as e:
        # Ging er iets mis met de netwerkverbinding? Wacht 2 seconden en verbind opnieuw.
        print(f"Verbinding verbroken ({e}), opnieuw verbinden...")
        time.sleep(2)
        try:
            connect_wifi()
            mqtt = connect_mqtt()
        except Exception as e2:
            print(f"Opnieuw verbinden mislukt: {e2}")

    # Wacht een halve seconde tot de volgende meting
    time.sleep(PUBLISH_INTERVAL_S)
