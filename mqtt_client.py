#!/usr/bin/env python3

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
    """

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

    # ---------------------------------------------------------
    # Connect
    # ---------------------------------------------------------

    def connect(self):

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
    # Cleanup
    # ---------------------------------------------------------

    def close(self):

        print("Closing MQTT connection...")

        self.client.loop_stop()
        self.client.disconnect()

        print("MQTT connection closed.")


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