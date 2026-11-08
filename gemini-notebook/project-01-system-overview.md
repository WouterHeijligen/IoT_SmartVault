# Smart Vault project — Architecture and IoT value loop

**Sources:** Uploaded project text files, `txt-files\docs\index.txt`,
`txt-files\docs\code.txt`, and the uploaded connection diagram.

## Explanation video prompt

```text
Create a 8–10 minute project explanation video using the uploaded Smart Vault
project sources. Teach the system as an IoT solution and map it to the
Information-Value Loop: sensing/creating data, communicating, aggregating,
analyzing, and acting.

Trace the main components and data paths: Raspberry Pi 5 application,
Raspberry Pi Pico 2 W perimeter node, sensors, local MQTT broker, OLED/RGB
indicator, relay/stepper, ThingSpeak telemetry, and ntfy notifications. Explain
which components sense, transport, process, display, or act. Use the uploaded
connection diagram as visual context, but do not treat it as proof of physical
wiring. Distinguish current implementation from planned features and from
claims in the checklist. The voice factor is described as bypassed by default
in the current documentation; state that carefully and do not present planned
behavior as implemented.

Narrate one normal access flow and one alarm/telemetry flow. Close with the
project's educational value, limitations, and a clear component/data-flow
recap. Ground every project-specific claim in an uploaded source and cite its
filename or section. If sources conflict or do not establish a fact, say so.
```

## Extensive project quiz prompt

```text
Create exactly 45 project exam questions (never exceed the Notebook limit of
50) from the uploaded Smart Vault sources.
Test whether I can explain the architecture, map the Information-Value Loop,
trace sensor-to-action data paths, identify component roles, and distinguish
the Pi 5 from the Pico 2 W.

Include 8 architecture/component questions, 10 data-flow tracing questions,
10 application scenarios (normal input, alarm, perimeter, telemetry), 8
current-versus-planned implementation questions, and 9 oral-defense questions
about design rationale and limitations. Mix short answer, diagram narration,
multiple choice, and scenario questions. Make the learner explain reasoning,
not merely name components.

Show all questions first, then a separate answer key with source filenames and
sections. Explicitly flag conflicts across the docs, code exports, diagram,
or checklist; prefer direct current-code evidence for implementation claims.
Never assume physical wiring has been verified. Finish with an interactive
viva mode, one question at a time, and track weak concepts.
```
