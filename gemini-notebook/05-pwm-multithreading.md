# Presentation 5 — PWM and multithreading

**Source:** `5_PWM_Multithreading_v2.pptx`.

## Video prompt

```text
Create a 8–10 minute exam-preparation video using only Presentation 5.

Explain PWM as a way to control an output by varying a signal over time.
Define period, frequency, duty cycle, and the resulting effect on an LED or
other load. Compare the software/manual, gpiozero, and hardware-PWM approaches
shown in the slides, including their practical tradeoffs and the role of the
relevant Python libraries.

Then teach threads and multithreading: what a thread is, why concurrent tasks
can help a responsive IoT application, how fast and slow loops can coexist,
and the advantages and risks discussed in the presentation. Walk through the
LED dimming examples with and without a separate thread. Explain what the
thread-checking examples establish, and distinguish concurrency from a
guarantee that code runs simultaneously.

Use a timing illustration in words, connect each concept to an observable
behavior, and end with a decision guide for when to use PWM and when
multithreading is useful. Do not add synchronization details not covered by
the slides; identify them as further study if needed. Cite slide/section.
```

## Extensive quiz prompt

```text
Create exactly 45 exam questions (never exceed the Notebook limit of 50),
based only on Presentation 5.
Cover PWM and duty cycle, software versus hardware PWM, the library examples,
threads, concurrency, pros and cons, slow/fast task behavior, thread inspection,
and the LED dimming examples.

Use 8 terminology questions, 8 predict-the-output or timing questions, 8
compare/choose questions, 15 code-behavior or troubleshooting scenarios, and
6 oral-exam explanations. Include calculations only if the slides provide
enough values. Avoid confusing PWM frequency with duty cycle or claiming
threads automatically make every task faster.

Show questions first and a separate answer key afterward. Explain each answer
with slide/section citations; for code questions, state which details are
directly shown and which are inferred. Finish with an interactive quiz mode
that asks one question at a time, waits for me, and adapts follow-up questions
to my mistakes.
```
