import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class ZwaailichtTests(unittest.TestCase):
    def test_warning_blinks_red_and_off_without_waiting(self):
        gpiozero = types.ModuleType("gpiozero")
        gpiozero.RGBLED = Mock()
        spec = importlib.util.spec_from_file_location(
            "tested_zwaailicht", Path(__file__).resolve().parents[1] / "zwaailicht.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"gpiozero": gpiozero}):
            spec.loader.exec_module(module)
        licht = module.Zwaailicht()

        with patch.object(module.time, "monotonic", side_effect=[0.0, 0.16, 0.31]), \
                patch.object(module.time, "sleep") as sleep:
            for expected in [(1, 0, 0), (0, 0, 0), (1, 0, 0)]:
                licht.knipper_rood()
                self.assertEqual(licht.led.color, expected)
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
