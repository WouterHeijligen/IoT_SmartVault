# Pico 2 W perimeter node

CircuitPython firmware for the Raspberry Pi Pico 2 W. It measures distance with an
RCWL-9610A sonar (trigger/echo mode) and publishes it over Wi-Fi to the MQTT broker
on the Raspberry Pi 5, topic `vault/perimeter/distance` (plain number in cm, every 0.5 s).
The Pi uses it to flag loitering (closer than 40 cm).

## Wiring

| Sensor | Pico 2 W pin |
|---|---|
| VCC | pin 36 (3V3 OUT) |
| GND | pin 38 |
| TRIG | pin 32 (GP27) |
| ECHO | pin 34 (GP28) |

With VCC on 3.3 V the ECHO signal is 3.3 V, so no voltage divider is needed. If you
power the sensor from 5 V (pin 40), put a 1 k / 2 k divider on ECHO.

## Install

1. Flash CircuitPython 11.x for the Pico 2 W.
2. Copy `code.py` to the `CIRCUITPY` drive.
3. Copy `settings.toml.example` to `settings.toml` on the drive and fill in your Wi-Fi
   name and password and the IP address of the Pi (`hostname -I` on the Pi).
   `settings.toml` holds credentials and is ignored by Git.
4. Copy these libraries from the Adafruit CircuitPython bundle into `lib/`:
   `adafruit_hcsr04`, `adafruit_minimqtt`, `adafruit_connection_manager`, `adafruit_ticks`.

## Broker on the Pi

Mosquitto only listens locally by default. Create `/etc/mosquitto/conf.d/pico.conf`:

```
listener 1883
allow_anonymous true
```

Restart with `sudo systemctl restart mosquitto` and check with
`mosquitto_sub -t vault/perimeter/distance`. Anonymous access is fine for a closed
project network only.
