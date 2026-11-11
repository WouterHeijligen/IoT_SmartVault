#!/usr/bin/env python3
import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()


class MQTTClient:
    MQTT_HOST = "mqtt3.thingspeak.com"
    MQTT_PORT = 1883
    MQTT_KEEPALIVE = 60

    CHANNEL_ID = "3529335"

    def __init__(self):
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

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(
        self,
        client,
        userdata,
        flags,
        reason_code,
        properties
    ):
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
        self.connected = False

        print(
            f"MQTT disconnected: {reason_code}"
        )

    def connect(self):
        print(
            f"Connecting to MQTT broker: {self.MQTT_HOST}"
        )

        self.client.connect(
            self.MQTT_HOST,
            self.MQTT_PORT,
            self.MQTT_KEEPALIVE
        )

        self.client.loop_start()

    def stuur_sensorwaarden(
        self,
        temperatuur,
        licht
    ):
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

    def stuur_telemetrie(self, lux, temperatuur, afstand_cm, status_code, status, cijfer):
        payload = (
            f"field1={lux:.1f}"
            f"&field2={temperatuur:.2f}"
            f"&field3={afstand_cm:.1f}"
            f"&field4={status_code:d}"
            f"&field5={cijfer:d}"
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

    def close(self):
        print("Closing MQTT connection...")

        self.client.loop_stop()
        self.client.disconnect()

        print("MQTT connection closed.")


class PerimeterListener:
    BROKER = "127.0.0.1"
    PORT = 1883
    TOPIC = "vault/perimeter/distance"

    def __init__(self, on_afstand):
        self.on_afstand = on_afstand

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="Pi5_SmartVault_Master"
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"[MQTT] Verbonden met lokale broker ({self.BROKER}). Subscribed op {self.TOPIC}")
            client.subscribe(self.TOPIC, qos=0)
        else:
            print(f"[MQTT] Verbinding mislukt met code: {reason_code}")

    def _on_message(self, client, userdata, msg):
        try:
            afstand = float(msg.payload.decode("utf-8").strip())
        except ValueError:
            return

        self.on_afstand(afstand)

    def connect(self):
        try:
            self.client.connect(self.BROKER, self.PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"[MQTT WAARSCHUWING] Lokale broker nog niet bereikbaar: {e}")

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == "__main__":

    mqtt_client = MQTTClient()

    try:
        mqtt_client.connect()

        mqtt_client.stuur_sensorwaarden(
            temperatuur=22.5,
            licht=250.0
        )

    finally:
        mqtt_client.close()
