"""
Perimeter-sensor van de Smart Vault (Raspberry Pi Pico 2 W, CircuitPython).

Rol van dit bestand:
    Draait als ``code.py`` op de Pico 2 W en meet continu de afstand tot
    personen voor de kluis. Elke 0,5 s wordt de afstand in cm via MQTT naar de
    Raspberry Pi gestuurd, waar main.py loitering (te lang dichtbij staan)
    mee detecteert.

Werking, stap voor stap:
    1. Initialiseer de ultrasone sensor.
    2. Verbind met Wi-Fi en daarna met de MQTT-broker.
    3. Eindeloze lus: controleer Wi-Fi, meet afstand, publiceer, wacht.
    4. Bij fouten wordt opnieuw verbonden in plaats van te crashen.

Hardware en bibliotheken:
    * RCWL-9610A in trigger/echo-modus via ``adafruit_hcsr04`` (HC-SR04
      compatibel): TRIG op GP27, ECHO op GP28.
    * ``wifi``/``socketpool`` (CircuitPython) en ``adafruit_minimqtt`` voor
      MQTT; MQTT is licht en geschikt voor een microcontroller.
    * Instellingen (MQTT_BROKER, MQTT_TOPIC, Wi-Fi) uit settings.toml via
      ``os.getenv``, zodat geen geheimen in de code staan.

Threads en gedeelde toestand:
    Eén enkele lus zonder threads of locks; geen gedeelde state. De Pi leest
    de waarde en gebruikt ``PERIMETER_STALE_S`` om te detecteren dat de Pico
    offline is. Het bericht is bewust alleen een getal in tekst (bv. "123.4").
"""

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
    """
    Verbind met Wi-Fi en blokkeer tot dat gelukt is.

    Werking:
        Zolang ``wifi.radio.connected`` False is: probeer te verbinden met
        SSID/wachtwoord uit settings.toml; bij een fout wordt de melding
        getoond en wacht de functie 2 s voor een nieuwe poging. Print daarna
        het IP-adres.

    Parameters:
        Geen.

    Returns:
        None

    Threads/locks:
        Geen threads; blokkeert de hoofdlus tot er verbinding is, wat hier
        bewust is: zonder netwerk valt niets te publiceren.

    Hardware/bibliotheken:
        Ingebouwde Wi-Fi van de Pico 2 W via CircuitPython ``wifi``.
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
    Maak een MQTT-client en verbind met de broker.

    Werking:
        Maakt een ``MQTT.MQTT``-client met broker uit ``MQTT_BROKER``, poort
        1883 (onversleuteld, lokaal netwerk), een socketpool op de Wi-Fi-radio
        en vaste client_id "pico_perimeter" (zodat een herverbinding de oude
        sessie vervangt in plaats van dubbele clients te maken). Verbindt en
        print de broker.

    Parameters:
        Geen.

    Returns:
        MQTT.MQTT: de verbonden client; de aanroeper bewaart deze in ``mqtt``.

    Threads/locks:
        Geen; kan een uitzondering gooien als de broker onbereikbaar is, die
        de hoofdlus afvangt.

    Hardware/bibliotheken:
        adafruit_minimqtt en socketpool over de Wi-Fi-radio.
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


connect_wifi()
mqtt = connect_mqtt()

# Hoofdlus: meet en publiceer elke PUBLISH_INTERVAL_S. RuntimeError van de
# sensor (geen echo) is normaal en wordt overgeslagen; elke andere fout
# betekent verbindingsverlies en triggert herverbinden.
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
