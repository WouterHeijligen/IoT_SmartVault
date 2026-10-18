# IoT_SmartVault
IoT Smart Vault Project

## Documentation

The documentation site covers the current implementation, Raspberry Pi setup,
hardware pin assignments, and known limitations:
[Smart Vault documentation](https://wouterheijligen.github.io/IoT_SmartVault/).
The site becomes available after GitHub Pages is enabled and the first deployment succeeds.
The included connection diagram is an **outdated draft**, not a verified wiring guide.

To preview locally, run `python -m http.server 8000 --bind 127.0.0.1 --directory docs`
and open <http://127.0.0.1:8000>.
Check the documentation with `python -m unittest discover -s tests -p "test_documentation.py"`.

In GitHub repository **Settings > Pages**, select **GitHub Actions** as the source.
The Documentation workflow checks pull requests targeting `master` and publishes
only after a push/merge to `master` (or a manual run on `master`).
See [documentation development](docs/development.html) for details.

## Installation

### 1. Create a Python virtual environment

From the Smart Vault project directory:

```bash
python3 -m venv env --system-site-packages
```

Activate the environment:

```bash
source env/bin/activate
```

### 2. Install the project dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure ThingSpeak MQTT

Create a `.env` file in the project directory:

```env
THINGSPEAK_MQTT_CLIENT_ID=your_client_id
THINGSPEAK_MQTT_USERNAME=your_username
THINGSPEAK_MQTT_PASSWORD=your_password
THINGSPEAK_CHANNEL_ID=your_channel_id
```

Do not commit this file to Git.

Add the following to `.gitignore`:

```gitignore
.env
env/
__pycache__/
.pyc
```

An `.env.example` fi*e can be committed instead*

```env
THINGSPEAK_MQTT_CLIENT_ID=
THINGSPEAK_MQTT_USERNAME=
THINGSPEAK_MQTT_PASSWORD=
THINGSPEAK_CHANNEL_ID=
```

### 4. Run the Smart Va*lt

Make sure the virtual environment is active:

```bash
source env/bin/activate
```

Then start the apllication:

```bash
python3 main.py
```

To leave the virtual environment:

```bash
deactivate
```