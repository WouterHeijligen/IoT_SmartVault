# Gemini Notebook study prompts

These are copy-ready prompts for the course presentations and the Smart Vault
project sources. Open the matching prompt file, then paste either its video
prompt or quiz prompt into NotebookLM/Gemini after adding the referenced
sources to the notebook.

## Course chapters

| Prompt file | Course source |
|---|---|
| `00-01-introduction.md` | Presentations 0 and 1, combined |
| `02a-single-board-computer-setup.md` | Presentation 2a |
| `02b-bash-python-workflow.md` | Presentation 2b |
| `03-gpio-electronics.md` | Presentation 3 |
| `04-i2c-mqtt.md` | Presentation 4 |
| `05-pwm-multithreading.md` | Presentation 5 |
| `06-spi-adc-oled.md` | Presentation 6 |
| `07-pico-circuitpython.md` | Presentation 7 |
| `08a-databases-web-server.md` | Presentation 8a |
| `08b-messaging-alerts.md` | Presentation 8b |
| `08c-ai-recognition.md` | Presentation 8c |

## Smart Vault project

The project prompt files focus on the system overview, hardware, software,
network/cloud integration, and an oral-exam style review.

## Study workflow

1. Use the chapter video prompt to build a concise explanation of the material.
2. Use that chapter's quiz prompt to generate and take a question bank.
3. Ask the notebook to revisit missed questions, explain the underlying
   misconception, and create a few new transfer questions.
4. For project questions, use the project files and diagram as sources. Ask
   NotebookLM to distinguish what the current code does from planned design,
   checklist claims, or anything that the sources do not establish.

All prompts ask for evidence from the uploaded sources. Slide numbering may not
be available in every NotebookLM answer; source titles or section headings are
acceptable citations when exact slide numbers cannot be verified.
