# Smart Vault project — Hardware, sensors, and actuators

**Sources:** Uploaded hardware/code text files, the English hardware and setup
exports under `txt-files\docs\`, and the uploaded connection diagram. The Dutch
web pages are translations, not separate evidence.

## Explanation video prompt

```text
Create an 8–10 minute hardware explanation video for the Smart Vault using
the uploaded project sources and connection diagram.

Explain the roles of the BH1750 light sensor, LM35 through the MCP3008,
potentiometer, button, SSD1306 OLED, RGB LED, relay, stepper/driver, and Pico
2 W ultrasonic perimeter node. Narrate the pin map from the hardware
documentation, carefully distinguishing BCM GPIO numbers from physical header
pin numbers and Raspberry Pi pins from Pico pins. Explain that the OLED uses
SPI1 while the MCP3008 uses SPI0 according to the current documentation/code
exports. Teach how I2C addressing and the shared SDA/SCL bus work for the BH1750;
how SPI clock, MOSI, MISO, and chip select transfer ADC data on SPI0; and how
SPI1 sends display data to the OLED using DC/reset signals but no MISO/CS wire.
Explain signal direction and function without implying that labels
such as OLED SDA/SCL mean I2C in this SPI connection.

Use the diagram as a visual aid, but explicitly call out its documented
differences from the current code and the fact that physical wiring has not
been independently verified. Explain electrical safety limits and what still
needs checking against component datasheets; do not give an unverified wiring
instruction or assume GPIO can power a motor. End with a subsystem-by-subsystem
verification checklist and a concise pin/bus summary.

Cite exact uploaded project source filenames/sections. Separate facts from
inferences and flag anything the sources cannot establish.
```

## Extensive project quiz prompt

```text
Build exactly 45 Smart Vault hardware exam questions (never exceed the
Notebook limit of 50) using the uploaded project
sources and diagram. Cover sensor purpose, analog-to-digital conversion,
MCP3008 channels, I2C/SPI bus assignment, GPIO roles, OLED signal names,
button/LED, relay and stepper-driver roles, Pico sonar, and electrical safety.

Include 8 component-function questions, 8 pin/bus interpretation questions,
8 signal-path questions, 15 fault-finding scenarios, and 6 safety/design
questions. Across the bus questions, test I2C addressing, SPI clock/data flow,
the distinct roles of SPI0 and SPI1, and why the OLED's SDA/SCL silkscreen does
not make this SPI connection I2C. Ask me to distinguish BCM from physical pins, SPI labels from I2C
labels, and Pi pins from Pico pins. Do not rely on diagram details that the
hardware page identifies as incorrect or unreconciled.

Put questions before the separated answer key. Every answer must cite a
source filename/section. For uncertain wiring, state that it requires
verification rather than guessing. Include an answer rationale and identify
whether it came from code, documentation, or the diagram. Finish with an
interactive practical viva and keep a list of missed pins, buses, and safety
concepts.
```
