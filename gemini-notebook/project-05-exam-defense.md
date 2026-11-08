# Smart Vault project — Integrated exam defense

**Sources:** All uploaded Smart Vault text files, documentation, and the
connection diagram.

## Explanation video prompt

```text
Create a 10–12 minute oral-exam preparation video about the Smart Vault
project, using all uploaded project sources.

Structure it as a student defense: problem and intended value; Information-
Value Loop; system architecture; hardware and pin/bus choices; software and
state behavior; MQTT/cloud/notifications; testing evidence; limitations and
future verification. Include a narrated explanation of one normal access
flow, one alarm flow, and one perimeter/cloud flow. For each, explain the
trigger, data path, decision, output/action, and evidence source.

Do not treat the diagram as proof of physical wiring. Distinguish current
code, documentation, checklist assertions, and planned design. Identify
important inconsistencies or unknowns instead of smoothing them over. State
that the project is an educational prototype, not a production security
system. Do not reproduce credentials or private details.

End with ten likely examiner follow-up questions and model answer outlines.
For each project-specific statement, cite the uploaded filename/section.
Keep slide-theory claims distinct from project-specific implementation claims.
```

## Extensive project quiz prompt

```text
Act as a demanding but fair examiner for a Smart Vault project defense. Use
all uploaded Smart Vault source files, docs, and the diagram. Create exactly
45 questions (never exceed the Notebook limit of 50), covering:
- 8 questions on the problem, intended value, and Information-Value Loop;
- 8 questions on system architecture and component responsibilities;
- 8 questions on hardware, signals, pin numbering, I2C/SPI, and electrical
  safety;
- 8 questions on software modules, state transitions, filtering, alarms, and
  actuation;
- 7 questions on MQTT, ThingSpeak, ntfy, and data interpretation;
- 6 questions on test evidence, limitations, security/privacy, and unresolved
  discrepancies.

Use a mix of short oral questions, explain-a-diagram questions, sequence
traces, scenario/fault questions, compare/justify questions, and a few
multiple-choice checks. Include follow-ups that probe whether I understand
why, not just what. Ask me to distinguish facts from assumptions and planned
features from current implementation. Never assume physical wiring is
verified; never disclose or ask for secrets.

First provide only the questions. On request, provide a separate answer guide
with reasoning and citations to uploaded source filenames/sections. Explicitly
mark any question whose answer is uncertain because the sources conflict or
do not establish it. Then offer to conduct the viva interactively, one
question at a time, adapting difficulty and maintaining a concise list of
weak areas.
```
