# Presentation 3 — GPIO, electronics, and components

**Source:** `3_GPIO_LED_R_v2.pptx`.

## Video prompt

```text
Create a 10–12 minute visual teaching video using only Presentation 3.

Build the explanation from safe circuit fundamentals to Raspberry Pi GPIO:
GPIO purpose and configuration; voltage, current, resistance, and Ohm's law;
LED polarity and current-limiting resistors; resistor color codes; breadboard
connections; and the difference between driving a load directly and using a
driver or switching component. Explain the roles shown for ULN2003, relays,
optocouplers, and transistors without implying that they are interchangeable.
Then cover the LED, RGB LED, switch/input, LDR, ultrasonic distance sensor,
and stepper-motor examples, including the Python/GPIO concepts in the slides.

Use a narrated circuit walkthrough. Explain the reasoning behind each
connection, identify what the learner should verify before powering a circuit,
and use only values or wiring details visible in the source. Emphasize that
GPIO pins are not power supplies for motors and that the actual component
datasheet and circuit determine safe values. Do not create a pinout or resistor
value that is not shown in the slides. Finish with a troubleshooting checklist
and a short component-role recap.

Cite the source slide/section for electrical rules and examples. If a diagram
is unclear or a value is missing, explicitly say that it cannot be determined
from the sources.
```

## Extensive quiz prompt

```text
Create exactly 45 progressively harder questions (never exceed the Notebook
limit of 50), based only on Presentation 3. Cover GPIO inputs/outputs, BCM versus physical
pin awareness where taught, basic electronics and Ohm's law, LED polarity and
resistors, breadboards, drivers and switching devices, RGB LEDs, relays,
transistors/optocouplers, stepper motors, switches, LDRs, ultrasonic sensing,
and the code examples.

Include 8 concept/terminology questions, 8 circuit-reading or calculation
questions only where the slides provide enough data, 8 component-choice
questions, 15 fault-finding or predict-the-result scenarios, and 6 oral-exam
or safety questions. Mix multiple
choice, short answer, ordering, and oral explanation. State units in any
calculation and show each calculation in the key. Never infer a safe electrical
value from missing information.

Put all questions before the separate answer key. Explain why each answer is
right, why plausible distractors fail, and cite slide/section. Mark
source-insufficient questions as unanswerable rather than guessing. Finish
with an interactive practical-viva mode: one question at a time, wait for my
answer, then correct misconceptions and track weak areas.
```
