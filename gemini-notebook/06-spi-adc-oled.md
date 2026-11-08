# Presentation 6 — ADC, SPI, and OLED

**Source:** `6_SPI_ADC_OLED_v2.pptx`.

## Video prompt

```text
Create a 10–12 minute exam-preparation video using only Presentation 6.

Start with why an analog sensor needs an ADC before a digital computer can
process its value. Explain analog-to-digital conversion and the MCP3008
example, including its channels and the SPI connection shown. Contrast
synchronous and asynchronous communication at the level taught, then explain
SPI's clock, controller/peripheral relationship, data lines, and chip select.
Walk through the slides' SPI read/write and write_readinto example and explain
how the returned bytes become an ADC value without inventing code details.

Next explain display choices and the SSD1306 OLED over SPI: its role, the
connection shown, software/library setup, test program, image output, and the
no-CS wiring case. Mention the Internet-radio/MPD material only as the
application example it is; do not let it distract from the ADC/SPI/OLED
learning goals.

Use a clear signal-flow narrative from analog input to converted value to
display. Contrast SPI with I2C only where the slides support it. Cite
slide/section, and call out any wiring or data-conversion detail that cannot
be confirmed from the slides.
```

## Extensive quiz prompt

```text
Generate exactly 45 exam questions (never exceed the Notebook limit of 50)
from Presentation 6 only. Cover ADC
motivation and conversion, MCP3008 channels and connections, synchronous
communication, SPI signals and transactions, write_readinto, interpreting
returned ADC data, OLED types, SSD1306 SPI wiring, no-CS operation, software,
and the application examples.

Use 8 terminology/concept questions, 8 signal-flow or transaction-order
questions, 8 code/result interpretation questions, 15 troubleshooting
scenarios, and 6 explain/compare questions. Include numerical conversion
questions only when the necessary resolution/reference details are explicitly
available in the slides; otherwise ask what information is missing.

Present the questions before the separated answer key. For each answer,
explain the reasoning and cite slide/section. Do not assume SPI pin numbers,
MCP3008 command bits, or OLED wiring beyond what the source states. End with
an interactive viva mode that asks one item at a time and tracks missed
concepts.
```
