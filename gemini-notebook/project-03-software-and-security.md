# Smart Vault project — Software, state machine, and safeguards

**Sources:** Uploaded code text files, the English code/overview exports under
`txt-files\docs\`, and the repository documentation. Use the English exports
only; the Dutch web pages are translations of the same evidence.

## Explanation video prompt

```text
Create a 8–10 minute software walkthrough video using the uploaded Smart Vault
source exports and documentation.

Explain the application structure and shared VaultState, the operating modes
documented in the sources, and how button input, sensor/display work,
actuation, cloud work, and voice recognition are separated. Trace code entry,
wrong-code lockout, alarm detection/reset, motor actuation, and telemetry.
Explain the purpose of filtering/hysteresis, threshold checks, stale perimeter
measurements, and the relay interlock only to the extent established by the
source code/documentation.

Be precise about implementation status: use the code exports and current
documentation as evidence; do not repeat unverified checklist claims as fact.
Distinguish implemented behavior from planned behavior and physical validation.
The source contains a Vosk voice-recognition path and sets
`BYPASS_VOICE_2FA = False`; explain that path without revealing its configured
passphrase or claiming that microphone/model operation was independently
verified on hardware. Explain limitations:
this is an educational prototype, not a production security system. Do not
recommend bypassing safeguards. End with a state-transition summary and a
short explanation of what evidence would be needed to confirm behavior on
physical hardware.

Cite source filename and section/function where possible. If source exports
disagree, report the discrepancy rather than silently choosing a value.
```

## Extensive project quiz prompt

```text
Generate exactly 45 Smart Vault software exam questions (never exceed the
Notebook limit of 50) from the uploaded
source-code text files and project documentation. Cover module roles, shared
state, state/mode transitions, input handling, digit hysteresis, sensor
filtering and alarm conditions, lockout, relay/stepper control, notification
and telemetry paths, and implementation limitations.

Use 8 code/module comprehension questions, 10 state-trace questions, 10
fault/scenario questions, 8 concurrency/data-flow questions, and 9 questions
about safety, evidence, and planned-versus-implemented behavior. Include
questions that require predicting the next state for a given event sequence.
Do not assume runtime results that cannot be deduced from the sources, and do
not present the project as production-secure.

Show questions first, then a separate answer key. For every answer cite the
source file and relevant section/function. Label code-derived facts separately
from documentation claims and identify unresolved conflicts. End with an
interactive viva mode that asks one scenario at a time and tracks my weak
state transitions and reasoning.
```
