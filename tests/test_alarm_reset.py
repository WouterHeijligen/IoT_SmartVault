import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock

import vault_state
from vault_state import VaultState


class AlarmResetTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1].joinpath("main.py").read_text(
            encoding="utf-8"
        )
        self.functions = {
            node.name: node for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef)
        }
        self.state = VaultState()
        self.state.mode = "ALARM"
        self.state.alarm_reason = "BRAND"
        self.state.temp_c = 25.0
        self.state.lux = 10.0
        self.state.sensor_ts = 10.0
        self.state.alarm_safe_since = 7.0
        self.clock = types.SimpleNamespace(now=10.0)
        self.output = Mock()

    def press_button(self):
        self.state.running = True
        namespace = dict(
            state=self.state,
            button=types.SimpleNamespace(value=False),
            time=types.SimpleNamespace(
                monotonic=lambda: self.clock.now,
                sleep=lambda _: setattr(self.state, "running", False),
            ),
            print=self.output,
        )
        exec(compile(ast.Module(
            body=[self.functions["thread_button"]], type_ignores=[]
        ), "main.py", "exec"), namespace)
        namespace["thread_button"]()
        self.assertFalse(any(
            "[FOUT" in str(call) for call in self.output.call_args_list
        ), self.output.call_args_list)

    def sensor_cycle(self, temp_c=25.0, lux=10.0, cached=False, error=False):
        self.state.running = True
        sensors = Mock(laatste_lux_ts=self.state.sensor_ts)
        sensors.lees_potmeter_raw.return_value = 0
        sensors.lees_temperatuur.return_value = temp_c
        if error:
            sensors.lees_temperatuur.side_effect = OSError("Sensor disconnected")

        def read_lux():
            if not cached:
                sensors.laatste_lux_ts = self.clock.now
            return lux

        sensors.lees_licht.side_effect = read_lux
        display = Mock()
        namespace = dict(
            state=self.state, sensors=sensors, display=display,
            time=types.SimpleNamespace(
                monotonic=lambda: self.clock.now,
                sleep=lambda _: setattr(self.state, "running", False),
            ),
            print=self.output,
        )
        for name in (
            "FIRE_CONFIRM_READINGS", "TEMP_FIRE_THRESHOLD_C",
            "LUX_SABOTAGE_THRESHOLD", "HYSTERESIS_10BIT", "LOITER_ALARM_S",
            "PERIMETER_STALE_S", "MAX_PIN_ATTEMPTS", "VOICE_PASSPHRASE",
        ):
            namespace[name] = getattr(vault_state, name)
        exec(compile(ast.Module(
            body=[self.functions["thread_sensors_and_display"]], type_ignores=[]
        ), "main.py", "exec"), namespace)
        namespace["thread_sensors_and_display"]()
        if not error:
            self.assertFalse(any(
                "[FOUT" in str(call) for call in self.output.call_args_list
            ), self.output.call_args_list)
            self.assertEqual(
                display.toon_kluisscherm.call_args.kwargs["alarm_veilig"],
                self.state.alarm_reset_allowed(self.clock.now),
            )

    def test_button_cannot_reset_while_temperature_or_light_is_unsafe(self):
        for temp_c, lux in (
            (35.0, 10.0), (25.0, 60.0), (28.1, 10.0), (25.0, 40.1),
            (float("nan"), 10.0), (25.0, float("inf")), (25.0, -1.0),
        ):
            with self.subTest(temp_c=temp_c, lux=lux):
                self.state.temp_c = temp_c
                self.state.lux = lux
                self.press_button()
                self.assertEqual(self.state.mode, "ALARM")
                self.assertEqual(self.state.alarm_reason, "BRAND")

    def test_button_cannot_reset_without_stable_recovery(self):
        for safe_since in (None, 7.01):
            with self.subTest(safe_since=safe_since):
                self.state.alarm_safe_since = safe_since
                self.press_button()
                self.assertEqual(self.state.mode, "ALARM")

    def test_button_cannot_reset_on_missing_or_stale_sensor_readings(self):
        for sensor_ts in (None, 9.0, 11.0):
            with self.subTest(sensor_ts=sensor_ts):
                self.state.sensor_ts = sensor_ts
                self.press_button()
                self.assertEqual(self.state.mode, "ALARM")

    def test_loiter_reset_requires_fresh_valid_distance_outside_perimeter(self):
        self.state.alarm_requires_perimeter = True
        for distance, timestamp in (
            (39.0, 10.0), (100.0, 0.0), (float("nan"), 10.0),
            (float("inf"), 10.0),
        ):
            with self.subTest(distance=distance, timestamp=timestamp):
                self.state.perimeter_cm = distance
                self.state.perimeter_ts = timestamp
                self.press_button()
                self.assertEqual(self.state.mode, "ALARM")

        self.state.perimeter_cm = 40.0
        self.state.perimeter_ts = 10.0
        self.press_button()
        self.assertEqual(self.state.mode, "PIN_INPUT")
        self.assertFalse(self.state.alarm_requires_perimeter)

    def test_motor_must_stop_before_recovery(self):
        self.state.motor_busy = True
        self.sensor_cycle()
        self.assertIsNone(self.state.alarm_safe_since)
        self.press_button()
        self.assertEqual(self.state.mode, "ALARM")

    def test_denied_reset_keeps_siren_active(self):
        self.state.temp_c = 35.0
        self.press_button()
        self.state.running = True
        notifications = Mock()
        namespace = dict(
            state=self.state, notificaties=notifications, vault=Mock(), licht=Mock(),
            time=types.SimpleNamespace(
                time=lambda: self.clock.now,
                sleep=lambda _: setattr(self.state, "running", False),
            ),
        )
        exec(compile(ast.Module(
            body=[self.functions["thread_actuators"]], type_ignores=[]
        ), "main.py", "exec"), namespace)
        namespace["thread_actuators"]()
        notifications.sirene.assert_called_once_with()
        notifications.stop_sirene.assert_not_called()

    def test_button_resets_after_stable_safe_readings(self):
        self.state.temp_c = 28.0
        self.state.lux = 40.0
        self.press_button()
        self.assertEqual(self.state.mode, "PIN_INPUT")
        self.assertEqual(self.state.alarm_reason, "")
        self.assertIsNone(self.state.alarm_safe_since)

    def test_sensor_worker_requires_three_seconds_and_restarts_after_unsafe_sample(self):
        self.state.alarm_safe_since = None
        for step in range(7):
            self.clock.now = 10.0 + step * 0.5
            self.sensor_cycle()
            self.assertEqual(
                self.state.alarm_reset_allowed(self.clock.now), step == 6
            )

        self.clock.now = 13.1
        self.sensor_cycle(temp_c=29.0)
        self.assertIsNone(self.state.alarm_safe_since)
        for step in range(7):
            self.clock.now = 13.5 + step * 0.5
            self.sensor_cycle()
            self.assertEqual(
                self.state.alarm_reset_allowed(self.clock.now), step == 6
            )

    def test_sensor_failure_or_reading_gap_restarts_recovery(self):
        for failure in ("exception", "gap", "cached"):
            with self.subTest(failure=failure):
                self.state.sensor_ts = 10.0
                self.state.alarm_safe_since = 7.0
                self.clock.now = 12.0
                self.output.reset_mock()
                self.sensor_cycle(
                    cached=failure == "cached", error=failure == "exception"
                )
                self.assertFalse(self.state.alarm_reset_allowed(self.clock.now))
                if failure == "exception":
                    self.assertTrue(any(
                        "Sensor disconnected" in str(call)
                        for call in self.output.call_args_list
                    ))

    def test_loiter_alarm_records_distance_requirement(self):
        self.state.mode = "PIN_INPUT"
        self.state.loiter_since = 0.0
        self.state.last_activity = 0.0
        self.state.loitering_alert = True
        self.state.perimeter_cm = 25.0
        self.state.perimeter_ts = 20.0
        self.clock.now = 20.0
        self.sensor_cycle()
        self.assertEqual(self.state.mode, "ALARM")
        self.assertTrue(self.state.alarm_requires_perimeter)
        self.assertIsNone(self.state.alarm_safe_since)

    def test_incoming_unsafe_distance_immediately_restarts_loiter_recovery(self):
        self.state.alarm_requires_perimeter = True
        namespace = dict(
            state=self.state, LOITER_DISTANCE_CM=vault_state.LOITER_DISTANCE_CM,
            time=types.SimpleNamespace(monotonic=lambda: self.clock.now),
        )
        exec(compile(ast.Module(
            body=[self.functions["on_perimeter_afstand"]], type_ignores=[]
        ), "main.py", "exec"), namespace)
        namespace["on_perimeter_afstand"](25.0)
        namespace["on_perimeter_afstand"](100.0)
        self.assertIsNone(self.state.alarm_safe_since)
        self.assertFalse(self.state.alarm_reset_allowed(self.clock.now))

    def test_closing_unlocked_vault_is_unchanged(self):
        self.state.mode = "UNLOCKED"
        self.state.lock_executed = True
        self.state.temp_c = 35.0
        self.press_button()
        self.assertEqual(self.state.mode, "PIN_INPUT")
        self.assertFalse(self.state.lock_executed)


class LightReadingFreshnessTests(unittest.TestCase):
    def test_cached_light_reading_does_not_refresh_its_timestamp(self):
        source = Path(__file__).resolve().parents[1].joinpath("sensors.py").read_text(
            encoding="utf-8"
        )
        sensor_class = next(
            node for node in ast.parse(source).body
            if isinstance(node, ast.ClassDef) and node.name == "Sensors"
        )
        namespace = dict(time=types.SimpleNamespace(monotonic=lambda: 10.0))
        exec(compile(ast.Module(body=[sensor_class], type_ignores=[]),
                     "sensors.py", "exec"), namespace)
        sensors = namespace["Sensors"].__new__(namespace["Sensors"])
        sensors.i2c = Mock()
        sensors.laatste_lux = 12.0
        sensors.laatste_lux_ts = 5.0
        sensors.i2c.try_lock.return_value = False

        self.assertEqual(sensors.lees_licht(), 12.0)
        self.assertEqual(sensors.laatste_lux_ts, 5.0)

        sensors.i2c.try_lock.return_value = True
        sensors.i2c.readfrom_into.side_effect = (
            lambda address, buffer: buffer.__setitem__(slice(None), b"\x00\x18")
        )
        self.assertEqual(sensors.lees_licht(), 20.0)
        self.assertEqual(sensors.laatste_lux_ts, 10.0)


if __name__ == "__main__":
    unittest.main()
