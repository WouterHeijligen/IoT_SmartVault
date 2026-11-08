# Presentation 4 — I2C, MQTT, and ThingSpeak

**Source:** `4_I2C_MQTT_v2.pptx`.

## Video prompt

```text
Create a 10–12 minute exam-preparation video using only Presentation 4.

Teach the chapter in two connected parts. First explain I2C: SDA and SCL,
device addressing, the shared bus, pull-up resistors, the transaction/signaling
ideas in the slides, and how the Raspberry Pi reads the BH1750 light sensor.
Then explain MQTT: broker, client, publisher, subscriber, topic, message, and
quality of service. Walk through Mosquitto setup/testing and show how a Python
publisher can deliver sensor data to a subscriber. Explain how ThingSpeak
fits as a cloud aggregation/visualization service and trace the
BMP280-to-MQTT-to-ThingSpeak example.

Make the distinction between local sensor-bus communication (I2C) and
message-based network communication (MQTT) explicit. Use a single end-to-end
example to connect sensor measurement, transport, aggregation, and display.
Explain QoS tradeoffs as the slides describe them; do not promise exactly-once
delivery unless the source supports it. End with a diagram-like verbal summary
and the most common protocol mix-ups.

Ground every technical claim in the slides and cite slide/section. Flag any
broker or cloud configuration detail that may depend on the current service
version.
```

## Extensive quiz prompt

```text
Build exactly 45 exam questions (never exceed the Notebook limit of 50) from
Presentation 4 only. Cover I2C wiring and
signals, addresses, pull-ups, read/write flow, BH1750, MQTT roles and topics,
publish/subscribe, QoS, Mosquitto, Python client use, ThingSpeak, and the
BMP280 data path.

Include 8 protocol vocabulary questions, 8 compare-I2C-with-MQTT questions,
8 sequence/trace questions, 15 troubleshooting scenarios, and 6 application
or design-justification questions. Include at least one scenario where the
learner must identify which protocol belongs on which connection. Do not
require unstated register values, credentials, or service configuration.

Show questions first; put the answer key in a separate section. Explain the
reasoning and cite the source slide/section for each answer. For troubleshooting
questions, explain the diagnostic sequence, not just the final fix. Clearly
label any ambiguity in the source. Offer an interactive one-at-a-time mode
that waits for my response and records missed concepts.
```
