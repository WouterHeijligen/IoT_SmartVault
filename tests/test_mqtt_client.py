import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class TelemetryTests(unittest.TestCase):
    def test_sonar_centimeters_and_vault_status_use_separate_fields(self):
        mqtt = types.ModuleType("paho.mqtt.client")
        mqtt.MQTT_ERR_SUCCESS = 0
        mqtt_package = types.ModuleType("paho.mqtt")
        mqtt_package.client = mqtt
        paho = types.ModuleType("paho")
        paho.mqtt = mqtt_package
        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = Mock()
        spec = importlib.util.spec_from_file_location(
            "tested_mqtt_client", Path(__file__).resolve().parents[1] / "mqtt_client.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            "paho": paho,
            "paho.mqtt": mqtt_package,
            "paho.mqtt.client": mqtt,
            "dotenv": dotenv,
        }):
            spec.loader.exec_module(module)
        client = module.MQTTClient.__new__(module.MQTTClient)
        client.topic = "channels/test/publish"
        client.client = Mock()
        client.client.publish.return_value.rc = 0

        for digit in (0, 5, 9):
            with self.subTest(digit=digit):
                client.client.reset_mock()
                self.assertTrue(
                    client.stuur_telemetrie(42.0, 21.5, 123.4, 2, "UNLOCKED", digit)
                )
                client.client.publish.assert_called_once_with(
                    topic="channels/test/publish",
                    payload=(
                        "field1=42.0&field2=21.50&field3=123.4&field4=2"
                        f"&field5={digit}&status=UNLOCKED"
                    ),
                    qos=0,
                    retain=False,
                )


if __name__ == "__main__":
    unittest.main()
