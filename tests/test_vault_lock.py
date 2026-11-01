import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


class DigitalPin:
    def __init__(self, pin):
        self.pin = pin
        self.history = []
        self.deinitialized = False

    @property
    def value(self):
        return self.history[-1]

    @value.setter
    def value(self, value):
        if type(value) is not bool:
            raise TypeError("Digital pin values must be bool")
        self.history.append(value)

    def switch_to_output(self, *, value):
        self.value = value

    def deinit(self):
        self.deinitialized = True


class VaultLockTests(unittest.TestCase):
    def setUp(self):
        board = types.ModuleType("board")
        for number in (24, 17, 27, 22, 23):
            setattr(board, f"D{number}", number)
        digitalio = types.ModuleType("digitalio")
        digitalio.DigitalInOut = DigitalPin
        spec = importlib.util.spec_from_file_location(
            "tested_vault_lock", Path(__file__).resolve().parents[1] / "vault_lock.py"
        )
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"board": board, "digitalio": digitalio}):
            spec.loader.exec_module(self.module)
        self.vault = self.module.VaultLock()

    def test_motion_preserves_active_low_relay_and_step_contract(self):
        self.assertTrue(self.vault.relais.value)
        self.assertTrue(all(not coil.value for coil in self.vault.coils))
        for method, direction in ((self.vault.open, False), (self.vault.sluit, True)):
            with self.subTest(direction=direction):
                def check_motion(*, stappen, vooruit):
                    self.assertFalse(self.vault.relais.value)
                    self.assertEqual(stappen, 3072)
                    self.assertEqual(vooruit, direction)

                with patch.object(self.vault, "_draai", side_effect=check_motion), \
                        patch.object(self.module.time, "sleep"):
                    method()
                self.assertTrue(self.vault.relais.value)

    def test_step_sequence_and_shutdown_use_safe_electrical_levels(self):
        with patch.object(self.module.time, "sleep"):
            self.vault._draai(4)
        patterns = list(zip(*(coil.history[1:-1] for coil in self.vault.coils)))
        self.assertEqual(patterns, [
            (True, True, False, False),
            (False, True, True, False),
            (False, False, True, True),
            (True, False, False, True),
        ])
        self.assertTrue(all(not coil.value for coil in self.vault.coils))
        self.vault.relais.value = False
        self.vault.stroomloos()
        self.assertTrue(self.vault.relais.value)
        self.vault.close()
        self.assertTrue(self.vault.relais.value)
        self.assertTrue(self.vault.relais.deinitialized)
        self.assertTrue(all(coil.deinitialized for coil in self.vault.coils))


if __name__ == "__main__":
    unittest.main()
