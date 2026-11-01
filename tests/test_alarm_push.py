import ast
from pathlib import Path
import threading
import types
import unittest
from unittest.mock import Mock


class AlarmPushTests(unittest.TestCase):
    def test_alarm_repeats_after_two_minutes_even_across_reset(self):
        source = Path(__file__).resolve().parents[1].joinpath("main.py").read_text(
            encoding="utf-8"
        )
        function = next(
            node for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and node.name == "thread_cloud"
        )
        state = types.SimpleNamespace(
            running=True, lock=threading.Lock(), mode="ALARM", lux=0,
            temp_c=35, perimeter_cm=100, current_digit=0, alarm_reason="BRAND",
            alarm_notified=False, lockout_push_pending=False,
        )
        clock = types.SimpleNamespace(now=0.0)
        samples = iter([
            (30, "ALARM"), (60, "PIN_INPUT"), (61, "ALARM"),
            (119, "ALARM"), (120, "ALARM"), (239, "ALARM"),
            (240, "ALARM"),
        ])

        def advance(_):
            try:
                clock.now, state.mode = next(samples)
                if state.mode == "PIN_INPUT":
                    state.alarm_notified = False
            except StopIteration:
                state.running = False

        sent_at = []
        notifications = Mock()
        notifications.stuur_push.side_effect = lambda _: sent_at.append(clock.now)
        namespace = dict(
            state=state,
            time=types.SimpleNamespace(
                monotonic=lambda: clock.now, time=lambda: clock.now, sleep=advance
            ),
            ALARM_PUSH_INTERVAL_S=120, TELEMETRY_INTERVAL_S=15,
            MODE_CODES={}, mqtt=Mock(), notificaties=notifications,
        )
        exec(compile(ast.Module(body=[function], type_ignores=[]), "main.py", "exec"),
             namespace)
        namespace["thread_cloud"]()
        self.assertEqual(sent_at, [0, 120, 240])


if __name__ == "__main__":
    unittest.main()
