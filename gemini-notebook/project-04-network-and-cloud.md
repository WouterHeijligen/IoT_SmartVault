# Smart Vault project — MQTT, telemetry, and notifications

**Sources:** Uploaded `mqtt_client.txt`, `pico_2w_code.txt`,
`notificaties.txt`, other project code exports, and the project documentation.

## Explanation video prompt

```text
Create an 8–10 minute Smart Vault networking explanation video from the
uploaded project sources.

Trace the Pico 2 W perimeter measurement over Wi-Fi/MQTT to the Mosquitto
broker on the Pi and the Pi subscriber. Separately trace the Pi's telemetry
fields to ThingSpeak and alarm/lockout messages to ntfy. Explain the role of
the MQTT topic, broker, publisher, subscriber, cloud service, and notification
service. Distinguish periodic telemetry from event-triggered alerts and
explain which sensor values/statuses are described by the sources.

Discuss limitations exactly as documented: the setup describes unencrypted
MQTT transport and an educational closed-network configuration; do not call
it secure. Be careful about the selected PIN digit being included in
telemetry if that is stated by the uploaded sources. Do not include real
credentials, access tokens, channel secrets, or private network details. If
the code exports and docs disagree about field numbers, timing, or topic
names, highlight the discrepancy and cite both.

Finish with an end-to-end data-flow recap and a safe configuration checklist.
Use citations to uploaded filenames/sections and do not infer delivery
guarantees.
```

## Extensive project quiz prompt

```text
Create exactly 45 project networking exam questions (never exceed the
Notebook limit of 50) using the uploaded Smart
Vault source files and docs. Cover local MQTT roles/topics, Pico publishing,
Pi subscription, ThingSpeak telemetry, data fields, ntfy alerts, periodic
versus event-triggered messages, and network/security limitations.

Include 8 protocol vocabulary questions, 8 message-flow traces, 15
troubleshooting scenarios, 8 data-interpretation questions, and 6 questions
on security/privacy and system limitations. Ask what component publishes,
subscribes, or consumes each message. Never include or request real secrets,
and do not claim encrypted transport or guaranteed delivery.

Show the questions first and the answer key separately. Include reasoning and
citations by source filename/section. Where sources conflict, identify the
conflict and do not choose without evidence. Finish with interactive
one-at-a-time mode and a list of concepts I need to review.
```
