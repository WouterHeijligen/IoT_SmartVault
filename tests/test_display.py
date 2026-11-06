import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock


class DisplayTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1].joinpath("display.py").read_text(
            encoding="utf-8"
        )
        display_class = next(
            node for node in ast.parse(source).body
            if isinstance(node, ast.ClassDef) and node.name == "Display"
        )
        self.busio = Mock()
        self.driver = Mock()
        namespace = dict(
            board=types.SimpleNamespace(D16=16, D6=6, D21=21, D20=20),
            busio=self.busio,
            digitalio=types.SimpleNamespace(
                DigitalInOut=Mock(side_effect=[Mock(), Mock()])
            ),
            adafruit_ssd1306=self.driver,
            ImageFont=Mock(),
        )
        exec(compile(ast.Module(body=[display_class], type_ignores=[]),
                     "display.py", "exec"), namespace)
        self.Display = namespace["Display"]

    def test_default_spi1_is_passed_to_driver_and_released_once(self):
        display = self.Display()
        self.busio.SPI.assert_called_once_with(clock=21, MOSI=20)
        self.driver.SSD1306_SPI.assert_called_once_with(
            128, 64, self.busio.SPI.return_value,
            display.oled_dc, display.oled_reset, None,
        )

        display.close()
        display.close()

        self.busio.SPI.return_value.deinit.assert_called_once_with()
        display.oled_dc.deinit.assert_called_once_with()
        display.oled_reset.deinit.assert_called_once_with()

    def test_injected_bus_is_used_but_not_released(self):
        spi = Mock()
        display = self.Display(spi=spi)
        self.busio.SPI.assert_not_called()
        self.assertIs(self.driver.SSD1306_SPI.call_args.args[2], spi)

        display.close()

        spi.deinit.assert_not_called()

    def test_clear_failure_releases_owned_bus_and_propagates(self):
        display = self.Display()
        display.oled.show.side_effect = OSError("SPI write failed")

        with self.assertRaisesRegex(OSError, "SPI write failed"):
            display.close()
        display.close()

        self.busio.SPI.return_value.deinit.assert_called_once_with()
        display.oled_dc.deinit.assert_called_once_with()
        display.oled_reset.deinit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
