#!/usr/bin/env python3
"""
================================================================================
BESTAND: mqtt_client.py
DOEL:    Alle MQTT-communicatie (Cloud-dashboard ThingSpeak + Lokale Pico 2 W).
================================================================================

UITLEG VOOR JE VERDEDIGING (IoT Essentials):
--------------------------------------------
Wat is MQTT?
MQTT is een superlicht communicatieprotocol dat speciaal gemaakt is voor IoT.
Het werkt met een **Broker** (een soort postkantoor) en **Topics** (postvakjes):
- Een **Publisher** (zender) stuurt een berichtje naar een topic, bijv. `vault/perimeter/distance`.
- Een **Subscriber** (ontvanger) abonneert zich op dat topic en krijgt elk nieuw
  bericht automatisch doorgestuurd.

In ons project gebruiken we MQTT op TWEE manieren (daarom staan er 2 klassen in dit bestand):
1. `MQTTClient` (PUBLISHER naar de Cloud):
   Stuurt elke 15 seconden onze meetwaarden (licht, temperatuur, afstand, status en
   gekozen cijfer) naar het online **ThingSpeak** dashboard (`mqtt3.thingspeak.com`).
2. `PerimeterListener` (SUBSCRIBER op de Raspberry Pi zelf):
   Luistert naar de lokale MQTT-broker op de Pi (`127.0.0.1`) waar de **Pico 2 W**
   elke halve seconde de gemeten afstand van de ultrasone sensor naartoe stuurt!

💡 TIP VOOR JE PRESENTATIE (Waarom een `.env` bestand?):
Onze ThingSpeak-wachtwoorden staan NIET in de Python-code, maar in een apart
`.env`-bestand dat we inladen met `load_dotenv()`. Zo komen je geheime sleutels
nooit per ongeluk op GitHub te staan!
"""

import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Laad de geheime ThingSpeak-inloggegevens uit het `.env`-bestand
load_dotenv()


class MQTTClient:
    """
    DEEL 1: Stuurt elke 15 seconden de kluisgegevens door naar ThingSpeak in de cloud.
    """

    # Het adres en poortnummer van de ThingSpeak MQTT-broker
    MQTT_HOST = "mqtt3.thingspeak.com"
    MQTT_PORT = 1883
    MQTT_KEEPALIVE = 60

    CHANNEL_ID = "3529335"

    def __init__(self):
        """
        Haalt de ThingSpeak-inloggegevens uit het `.env`-bestand en zet de MQTT-client klaar.
        """
        self.client_id = os.getenv(
            "THINGSPEAK_MQTT_CLIENT_ID"
        )

        self.username = os.getenv(
            "THINGSPEAK_MQTT_USERNAME"
        )

        self.password = os.getenv(
            "THINGSPEAK_MQTT_PASSWORD"
        )

        self.channel_id = os.getenv(
            "THINGSPEAK_CHANNEL_ID"
        )

        # Controleer of alle inloggegevens wel ingevuld zijn in `.env`
        if not all([
            self.client_id,
            self.username,
            self.password
        ]):
            raise RuntimeError(
                "ThingSpeak MQTT credentials ontbreken. "
                "Controleer de environment variables."
            )

        # Het vaste topic-formaat dat ThingSpeak verwacht om data op te ontvangen
        self.topic = f"channels/{self.channel_id}/publish"

        self.connected = False

        # Maak de Paho MQTT-client aan en stel gebruikersnaam en wachtwoord in
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            self.client_id
        )

        self.client.username_pw_set(
            self.username,
            self.password
        )

        # Koppel twee hulpfuncties (callbacks) die automatisch worden aangeroepen
        # zodra de verbinding gelukt is (`on_connect`) of verbroken wordt (`on_disconnect`).
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    # ---------------------------------------------------------
    # Automatische meldfuncties (MQTT callbacks)
    # ---------------------------------------------------------

    def _on_connect(
        self,
        client,
        userdata,
        flags,
        reason_code,
        properties
    ):
        """
        Wordt automatisch aangeroepen zodra ThingSpeak reageert op onze verbindingspoging.
        `reason_code == 0` betekent: Alles is gelukt, we zijn verbonden!
        """
        if reason_code == 0:
            self.connected = True
            print("MQTT connected OK")
        else:
            self.connected = False
            print(
                f"MQTT connection failed: {reason_code}"
            )

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties
    ):
        """
        Wordt automatisch aangeroepen als de verbinding met ThingSpeak wegvalt.
        """
        self.connected = False

        print(
            f"MQTT disconnected: {reason_code}"
        )

    # ---------------------------------------------------------
    # Verbinden met ThingSpeak
    # ---------------------------------------------------------

    def connect(self):
        """
        Maakt verbinding met de ThingSpeak-server en start `loop_start()`.

        💡 WAT DOET `loop_start()`?
        Hiermee handelt de Paho-bibliotheek al het internetverkeer zelf op de
        achtergrond af (en herverbindt hij automatisch als wifi even hapert),
        zodat ons hoofdprogramma nooit hoeft te wachten!
        """
        print(
            f"Connecting to MQTT broker: {self.MQTT_HOST}"
        )

        self.client.connect(
            self.MQTT_HOST,
            self.MQTT_PORT,
            self.MQTT_KEEPALIVE
        )

        # Start de netwerk-achtergrondtaak van Paho MQTT
        self.client.loop_start()

    # ---------------------------------------------------------
    # Eenvoudige testfunctie (alleen licht en temperatuur)
    # ---------------------------------------------------------

    def stuur_sensorwaarden(
        self,
        temperatuur,
        licht
    ):
        """
        Stuurt alleen licht (field1) en temperatuur (field2) naar ThingSpeak.
        Wordt gebruikt als je dit bestand los test (`python3 mqtt_client.py`).
        """
        payload = (
            f"field1={licht:.1f}"
            f"&field2={temperatuur:.2f}"
            f"&status=SmartVaultSensorMeasurement"
        )

        print(f"MQTT payload: {payload}")

        message = self.client.publish(
            topic=self.topic,
            payload=payload,
            qos=0,
            retain=False
        )

        if message.rc == mqtt.MQTT_ERR_SUCCESS:
            print("MQTT publish OK")
            return True

        print(
            f"MQTT publish failed: {message.rc}"
        )

        return False

    # ---------------------------------------------------------
    # Volledige kluis-telemetrie versturen (gebruikt door main.py)
    # ---------------------------------------------------------

    def stuur_telemetrie(self, lux, temperatuur, afstand_cm, status_code, status, cijfer):
        """
        Stuurt alle 5 de meetwaarden van de Smart Vault in één keer naar ThingSpeak:
        - `field1`: Lichtsterkte in de kluis (lux)
        - `field2`: Temperatuur in de kluis (°C)
        - `field3`: Afstand van de persoon voor de kluis (cm)
        - `field4`: Huidige modus als getal (0=PIN, 1=Spraak, 2=Open, 3=Alarm, 4=Geblokkeerd)
        - `field5`: Het gekozen cijfer op de draaiknop (0 t/m 9)
        - `status`: De naam van de modus als tekst (bijv. "PIN_INPUT")
        """
        payload = (
            f"field1={lux:.1f}"
            f"&field2={temperatuur:.2f}"
            f"&field3={afstand_cm:.1f}"
            f"&field4={status_code:d}"
            f"&field5={cijfer:d}"
            f"&status={status}"
        )

        # Publiceer het bericht op het ThingSpeak-kanaal
        message = self.client.publish(
            topic=self.topic,
            payload=payload,
            qos=0,
            retain=False
        )

        if message.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[THINGSPEAK] Publish OK -> {payload}")
            return True

        print(f"[THINGSPEAK FOUT] Publish mislukt: {message.rc}")

        return False

    # ---------------------------------------------------------
    # Netjes afsluiten
    # ---------------------------------------------------------

    def close(self):
        """
        Stopt de achtergrondtaak en verbreekt netjes de verbinding met ThingSpeak.
        """
        print("Closing MQTT connection...")

        self.client.loop_stop()
        self.client.disconnect()

        print("MQTT connection closed.")


class PerimeterListener:
    """
    DEEL 2: Luistert op de Raspberry Pi naar de afstandsmetingen van de Pico 2 W.

    Hoe werkt dit?
    Op de Raspberry Pi draait een lokale MQTT-broker (Mosquitto) op adres `127.0.0.1`
    (dat betekent: "deze computer zelf"). De Pico 2 W stuurt via Wi-Fi elke 0,5 seconde
    de gemeten afstand in centimeters naar het topic `vault/perimeter/distance`.
    Deze klasse vangt dat getal op en geeft het direct door aan `main.py`!
    """

    BROKER = "127.0.0.1"
    PORT = 1883
    TOPIC = "vault/perimeter/distance"

    def __init__(self, on_afstand):
        """
        Zet de lokale MQTT-ontvanger klaar.
        `on_afstand` is de functie uit `main.py` die we aanroepen zodra er een
        nieuwe afstand binnenkomt.
        """
        self.on_afstand = on_afstand

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="Pi5_SmartVault_Master"
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """
        Zodra we verbonden zijn met onze lokale broker, abonneren (`subscribe`) we ons
        meteen op het topic `vault/perimeter/distance`.
        """
        if reason_code == 0:
            print(f"[MQTT] Verbonden met lokale broker ({self.BROKER}). Subscribed op {self.TOPIC}")
            client.subscribe(self.TOPIC, qos=0)
        else:
            print(f"[MQTT] Verbinding mislukt met code: {reason_code}")

    def _on_message(self, client, userdata, msg):
        """
        Wordt automatisch aangeroepen telkens als de Pico 2 W een nieuwe afstand stuurt.
        We zetten de ontvangen tekst (bijv. `"42.5"`) om naar een kommagetal (`float`)
        en geven dat door aan `self.on_afstand(afstand)`.
        """
        try:
            afstand = float(msg.payload.decode("utf-8").strip())
        except ValueError:
            # Als er per ongeluk iets binnenkomt dat geen geldig getal is, negeren we het veilig
            return

        self.on_afstand(afstand)

    def connect(self):
        """
        Verbindt met de lokale MQTT-broker op de Raspberry Pi en start het luisteren
        op de achtergrond (`loop_start`).
        """
        try:
            self.client.connect(self.BROKER, self.PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"[MQTT WAARSCHUWING] Lokale broker nog niet bereikbaar: {e}")

    def close(self):
        """
        Stopt het luisteren en verbreekt de lokale MQTT-verbinding bij het afsluiten.
        """
        self.client.loop_stop()
        self.client.disconnect()


# ==============================================================================
# LOSSE TEST: Wordt alleen uitgevoerd als je `python3 mqtt_client.py` typt
# ==============================================================================
if __name__ == "__main__":

    mqtt_client = MQTTClient()

    try:
        mqtt_client.connect()

        # Stuur één keer twee testwaarden naar ThingSpeak
        mqtt_client.stuur_sensorwaarden(
            temperatuur=22.5,
            licht=250.0
        )

    finally:
        mqtt_client.close()
