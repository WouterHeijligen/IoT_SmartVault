#!/usr/bin/env python3

from gpiozero import Button

from zwaailicht import Zwaailicht
from sensors import Sensors
from mqtt_client import MQTTClient
from vault_lock import VaultLock
from display import Display
from voice import VoiceRecognition


button = Button(4, pull_up=True)

licht = Zwaailicht()
sensors = Sensors()
mqtt = MQTTClient()
vault = VaultLock()
display = Display()
voice = VoiceRecognition()


def main():

    print("==============================")
    print(" SMART VAULT")
    print("==============================")

    licht.groen()

    display.toon_tekst(
        "SMART VAULT",
        "Systeem gereed"
    )

    try:

        while True:

            button.wait_for_press()

            print("Knop ingedrukt")

            # Sensoren uitlezen
            metingen = sensors.lees_alles()

            temperatuur = metingen["temperatuur"]
            lichtwaarde = metingen["licht"]

            print(
                f"Temperatuur: {temperatuur:.1f} C"
            )

            print(
                f"Licht: {lichtwaarde}"
            )
            potentiometer = metingen["potentiometer"]
            print(
                f"Potentiometer: {potentiometer}"
            )

            # Toon op OLED
            display.toon_tekst(
                "SENSOREN",
                f"T:{temperatuur:.1f} L:{lichtwaarde:.0f} P:{potentiometer}"
            )

            # Naar MQTT
            mqtt.stuur_sensorwaarden(
                temperatuur,
                lichtwaarde
            )

            # Zwaailicht testen
            licht.alarm(
                aantal=5,
                snelheid=0.2
            )

            licht.groen()

            button.wait_for_release()

    except KeyboardInterrupt:

        print("\nSmart Vault stoppen...")

    finally:

        licht.close()
        sensors.close()
        mqtt.close()
        vault.close()
        display.close()
        voice.close()  # Als voice wordt gebruikt
        button.close()

        print("Smart Vault veilig afgesloten")


if __name__ == "__main__":
    main()