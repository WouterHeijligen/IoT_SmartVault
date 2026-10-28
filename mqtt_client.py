#!/usr/bin/env python3
"""MQTT-communicatie van de Smart Vault: ThingSpeak-telemetrie en perimeter-ontvanger.

Rol in de architectuur:
    Dit bestand bevat twee onafhankelijke MQTT-clients (paho-mqtt):

    - ``MQTTClient``: PUBLISHER naar de cloud (ThingSpeak, mqtt3.thingspeak.com).
      Wordt door de cloud-thread in main.py elke TELEMETRY_INTERVAL_S (15 s,
      ThingSpeak-limiet) aangeroepen met lux, temperatuur, afstand en modus.
    - ``PerimeterListener``: SUBSCRIBER op de lokale broker (127.0.0.1) die de
      afstandsmetingen van de Pico WH (ultrasone perimetersensor) ontvangt en
      doorgeeft aan de callback ``on_perimeter_afstand`` in main.py.

Threads en gedeelde state:
    Beide klassen gebruiken ``loop_start()`` van paho: het netwerkverkeer en de
    callbacks draaien in een eigen achtergrondthread van paho. Dit bestand
    raakt ``VaultState`` niet rechtstreeks en gebruikt ``state.lock`` niet; de
    PerimeterListener-callback (``on_perimeter_afstand`` in main.py) neemt zelf
    de lock. ``MQTTClient.connected`` wordt vanuit de paho-thread gezet en
    elders alleen informatief gelezen (enkelvoudige bool).

Configuratie:
    ThingSpeak-credentials komen uit omgevingsvariabelen / ``.env``
    (python-dotenv), zodat er geen geheimen in de broncode staan.
"""

import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

class MQTTClient:
    """
    MQTT client voor de Smart Vault.

    ThingSpeak:
        field1 = licht (lux)
        field2 = temperatuur (C)

    Doel:
        Publiceert meetwaarden naar het ThingSpeak-kanaal via MQTT (QoS 0,
        niet retained).

    Werking:
        De constructor leest credentials uit de omgeving; ``connect()`` start
        de verbinding en de paho-netwerkthread; ``stuur_*`` publiceert een
        ``field1=...&field2=...``-payload op ``channels/<id>/publish``;
        ``close()`` stopt de thread en verbreekt de verbinding.

    Gedeelde state / threads:
        Raakt ``VaultState`` niet. Wordt vanuit de cloud-thread van main.py
        aangeroepen; de callbacks draaien in de paho-thread.
    """

    MQTT_HOST = "mqtt3.thingspeak.com"
    MQTT_PORT = 1883
    MQTT_KEEPALIVE = 60

    CHANNEL_ID = "3529335"

    def __init__(self):
        """Leest de ThingSpeak-credentials en maakt de paho-client aan (nog niet verbonden).

        Werking (stap voor stap):
            1. Lees THINGSPEAK_MQTT_CLIENT_ID, _USERNAME, _PASSWORD en
               THINGSPEAK_CHANNEL_ID uit de omgeving (via ``.env``).
            2. Ontbreekt client-id, gebruikersnaam of wachtwoord -> ``RuntimeError``
               (main.py vangt dit op en print dan alleen telemetrie).
            3. Bouw het publish-topic ``channels/<channel_id>/publish``.
            4. Maak de ``mqtt.Client`` (callback API versie 2), zet de
               inloggegevens en koppel de connect/disconnect-callbacks.

        Parameters: geen.
        Retourwaarde: geen (constructor).
        Raises: RuntimeError bij ontbrekende credentials.
        Gedeelde state: geen ``VaultState``.
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

        if not all([
            self.client_id,
            self.username,
            self.password
        ]):
            raise RuntimeError(
                "ThingSpeak MQTT credentials ontbreken. "
                "Controleer de environment variables."
            )

        self.topic = f"channels/{self.channel_id}/publish"

        self.connected = False

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            self.client_id
        )

        self.client.username_pw_set(
            self.username,
            self.password
        )

        # Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    # ---------------------------------------------------------
    # MQTT callbacks
    # ---------------------------------------------------------

    def _on_connect(
        self,
        client,
        userdata,
        flags,
        reason_code,
        properties
    ):
        """Paho-callback (draait in de paho-netwerkthread) na een verbindingspoging.

        Werking: bij ``reason_code == 0`` wordt ``self.connected`` True,
        anders False met een foutmelding.

        Parameters (paho callback API v2): client, userdata, flags,
        reason_code (0 = succes), properties; alleen ``reason_code`` wordt
        gebruikt.
        Retourwaarde: geen.
        Gedeelde state: schrijft ``self.connected`` (geen lock nodig voor een
        enkele bool); geen ``VaultState``.
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
        """Paho-callback (paho-netwerkthread) bij het verbreken van de verbinding.

        Werking: zet ``self.connected`` op False en print de reden. Paho
        probeert zelf automatisch opnieuw te verbinden zolang ``loop_start``
        actief is.

        Parameters (paho callback API v2): client, userdata,
        disconnect_flags, reason_code, properties.
        Retourwaarde: geen.
        Gedeelde state: schrijft ``self.connected``; geen ``VaultState``.
        """
        self.connected = False

        print(
            f"MQTT disconnected: {reason_code}"
        )

    # ---------------------------------------------------------
    # Connect
    # ---------------------------------------------------------

    def connect(self):
        """Verbindt met de ThingSpeak-broker en start de achtergrondthread.

        Werking: ``client.connect`` naar mqtt3.thingspeak.com:1883 (keepalive
        60 s) en daarna ``loop_start()``, dat in een eigen thread het
        netwerkverkeer, keepalive en callbacks afhandelt zodat de
        aanroeper niet blokkeert.

        Parameters: geen.
        Retourwaarde: geen. Kan een exceptie gooien als de broker onbereikbaar
        is (main.py vangt die op en gaat door zonder telemetrie).
        Gedeelde state: geen ``VaultState``; start de paho-thread.
        """

        print(
            f"Connecting to MQTT broker: {self.MQTT_HOST}"
        )

        self.client.connect(
            self.MQTT_HOST,
            self.MQTT_PORT,
            self.MQTT_KEEPALIVE
        )

        # MQTT netwerkverkeer in achtergrondthread
        self.client.loop_start()

    # ---------------------------------------------------------
    # Sensor data versturen
    # ---------------------------------------------------------

    def stuur_sensorwaarden(
        self,
        temperatuur,
        licht
    ):
        """
        Stuurt Smart Vault sensordata naar ThingSpeak.

        field1 = licht
        field2 = temperatuur

        Werking: bouwt een payload ``field1=<lux>&field2=<temp>&status=...``,
        publiceert die met QoS 0 (geen retain) en controleert de
        returncode van paho.

        Parameters:
            temperatuur (float): graden Celsius (2 decimalen).
            licht (float): lux (1 decimaal).

        Retourwaarde: True bij succesvol aanbieden aan paho
        (``MQTT_ERR_SUCCESS``), anders False. Dit bevestigt niet dat
        ThingSpeak het bericht ook verwerkt heeft.

        Gedeelde state: geen ``VaultState``. Wordt enkel in de losse test
        onderaan gebruikt; de hoofdapplicatie gebruikt ``stuur_telemetrie``.
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
    # Telemetrie van de volledige kluis versturen
    # ---------------------------------------------------------

    def stuur_telemetrie(self, lux, temperatuur, afstand_cm, status_code, status):
        """
        Stuurt de kluis-telemetrie naar ThingSpeak.

        field1 = licht (lux)
        field2 = temperatuur (C)
        field3 = perimeter afstand (cm)
        field4 = status (0=vergrendeld, 1=2FA, 2=geopend, 3=alarm)

        Werking: bouwt een payload met vier velden plus ``status=<modus>``
        en publiceert die met QoS 0 (geen retain). Het ThingSpeak-limiet van
        minstens 15 s tussen updates wordt door de aanroeper bewaakt
        (TELEMETRY_INTERVAL_S in de cloud-thread).

        Parameters:
            lux (float): lichtsterkte (1 decimaal).
            temperatuur (float): graden Celsius (2 decimalen).
            afstand_cm (float): perimeterafstand in cm (1 decimaal).
            status_code (int): modus als getal, uit ``vault_state.MODE_CODES``
                (ook 4 = LOCKOUT bestaat daar).
            status (str): modus als tekst, in het ThingSpeak-statusveld.

        Retourwaarde: True als paho het bericht heeft aanvaard, anders False.

        Gedeelde state: geen ``VaultState``; de cloud-thread geeft een
        snapshot mee die onder ``state.lock`` werd gemaakt.
        """

        payload = (
            f"field1={lux:.1f}"
            f"&field2={temperatuur:.2f}"
            f"&field3={afstand_cm:.1f}"
            f"&field4={status_code:d}"
            f"&status={status}"
        )

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
    # Cleanup
    # ---------------------------------------------------------

    def close(self):
        """Stopt de MQTT-thread en verbreekt de ThingSpeak-verbinding.

        Werking: ``loop_stop()`` stopt de paho-netwerkthread, daarna
        ``disconnect()``. Wordt in de ``finally`` van ``main()`` aangeroepen.

        Parameters: geen.
        Retourwaarde: geen.
        Gedeelde state: geen ``VaultState``.
        """

        print("Closing MQTT connection...")

        self.client.loop_stop()
        self.client.disconnect()

        print("MQTT connection closed.")


class PerimeterListener:
    """
    Lokale MQTT subscriber op de Pi 5 voor de perimeter-afstand van de Pico WH.
    De callback krijgt de afstand in cm.

    Doel:
        Ontvangt de afstandsmetingen van de Pico WH (perimetersensor buiten
        de kluis) via een lokale MQTT-broker (bv. Mosquitto op de Pi 5) en
        geeft ze door aan de applicatie.

    Werking:
        ``connect()`` verbindt en start de paho-thread; bij succesvolle
        verbinding wordt geabonneerd op ``vault/perimeter/distance``. Elk
        bericht wordt als float geparsed en aan ``on_afstand`` gegeven.

    Gedeelde state / threads:
        De callbacks draaien in de paho-netwerkthread, niet in de
        hoofdthread. ``on_afstand`` (main.on_perimeter_afstand) neemt zelf
        ``state.lock``; deze klasse raakt ``VaultState`` niet.
    """

    BROKER = "127.0.0.1"
    PORT = 1883
    TOPIC = "vault/perimeter/distance"

    def __init__(self, on_afstand):
        """Maakt de lokale MQTT-subscriber aan (nog niet verbonden).

        Parameters:
            on_afstand (callable): functie ``f(afstand_cm: float)`` die bij
                elk geldig bericht wordt aangeroepen, in de paho-thread.

        Werking: bewaart de callback, maakt een paho-client (callback API v2)
        met vast client-id ``Pi5_SmartVault_Master`` en koppelt
        ``on_connect``/``on_message``.

        Retourwaarde: geen (constructor).
        Gedeelde state: geen ``VaultState``.
        """
        self.on_afstand = on_afstand

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="Pi5_SmartVault_Master"
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Paho-callback na (her)verbinding: abonneert op het perimeter-topic.

        Werking: bij ``reason_code == 0`` wordt ``subscribe(TOPIC, qos=0)``
        aangeroepen. Dit gebeurt in de callback zodat het abonnement na
        elke automatische herverbinding opnieuw wordt gelegd.

        Parameters (paho callback API v2): client, userdata, flags,
        reason_code, properties.
        Retourwaarde: geen. Gedeelde state: geen; draait in de paho-thread.
        """
        if reason_code == 0:
            print(f"[MQTT] Verbonden met lokale broker ({self.BROKER}). Subscribed op {self.TOPIC}")
            client.subscribe(self.TOPIC, qos=0)
        else:
            print(f"[MQTT] Verbinding mislukt met code: {reason_code}")

    def _on_message(self, client, userdata, msg):
        """Paho-callback bij een bericht op het perimeter-topic.

        Werking: decodeer de payload als UTF-8, parse naar float en roep
        ``on_afstand`` aan. Ongeldige payloads (geen getal) worden stil
        genegeerd zodat één foutief bericht de netwerkthread niet stoort.

        Parameters: client, userdata, msg (``msg.payload`` bevat de afstand
        in cm als tekst).
        Retourwaarde: geen.
        Gedeelde state: geen rechtstreeks; de callback ``on_afstand`` neemt
        ``state.lock``.
        """
        try:
            afstand = float(msg.payload.decode("utf-8").strip())
        except ValueError:
            return

        self.on_afstand(afstand)

    def connect(self):
        """Verbindt met de lokale broker en start de paho-netwerkthread.

        Werking: ``connect`` naar 127.0.0.1:1883 (keepalive 60 s) en
        ``loop_start()``. Een onbereikbare broker geeft alleen een
        waarschuwing; het systeem werkt dan zonder perimeterdata (de
        meting veroudert na PERIMETER_STALE_S en wordt genegeerd).

        Parameters: geen. Retourwaarde: geen.
        Gedeelde state: geen ``VaultState``; start de paho-thread.
        """
        try:
            self.client.connect(self.BROKER, self.PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"[MQTT WAARSCHUWING] Lokale broker nog niet bereikbaar: {e}")

    def close(self):
        """Stopt de paho-netwerkthread en verbreekt de lokale verbinding.

        Parameters: geen. Retourwaarde: geen.
        Gedeelde state: geen ``VaultState``; aangeroepen in de ``finally``
        van ``main()``.
        """
        self.client.loop_stop()
        self.client.disconnect()


# -------------------------------------------------------------
# Losse test
# -------------------------------------------------------------

if __name__ == "__main__":

    mqtt_client = MQTTClient()

    try:
        mqtt_client.connect()

        # Alleen testwaarden
        mqtt_client.stuur_sensorwaarden(
            temperatuur=22.5,
            licht=250.0
        )

    finally:
        mqtt_client.close()