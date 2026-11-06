---
type: guide
domein: IoT & Embedded
vak: IoT Essentials
status: actief
tags: [wiki/guide, iot-essentials, smart-vault, test-checklist, verification, video-dryrun]
bronnen: ["Wiki/Projects/IoT_Projectvoorstel_Smart_Vault.md", "Wiki/Guides/Smart_Vault_Bouw_en_Verificatiegids.md"]
aangemaakt: 2026-11-01
bijgewerkt: 2026-11-01
---
# 📋 Smart Vault: Fysieke Test-, Verificatie- & Video-Checklist

> [[Home|🏠 Home]] › [[Guides Overzicht|Gidsen]] › [[IoT_Projectvoorstel_Smart_Vault|Smart Vault]] › Fysieke Test- & Video-Checklist

**TL;DR:** Deze interactieve checklist leidt je stap voor stap door de complete fysieke acceptatietest en dry-run van de **Smart Vault** (Raspberry Pi 5 + Pico 2 W). Gebruik de selectievakjes (`- [ ]`) direct in Obsidian om alle subsysteemen, sensoren, actuatoren en cloud-integraties systematisch af te vinken alvorens de definitieve 5-minuten demonstratievideo op te nemen.

---

## 🛠️ Fase 0: Voorbereiding & Pre-Flight Checklist

Voer deze controles uit **voordat** je `main.py` start of de camera aanzet:

- [x] **1. Lokale Mosquitto Broker actief op Pi 5:**
  - Controleer via de terminal:
    ```bash
    sudo systemctl is-active mosquitto
    ```
  - *Indien inactief:* Start met `sudo systemctl enable --now mosquitto`.
- [x] **2. `.env` configuratiebestand aanwezig op de Pi 5:**
  - Bestand `/home/bart/Documents/Projects/IoT_SmartVault/.env` bevat de juiste sleutels:
    ```env
    THINGSPEAK_MQTT_CLIENT_ID=KR40OTsKJAM9KBgCGwE1IBQ
    THINGSPEAK_MQTT_USERNAME=KR40OTsKJAM9KBgCGwE1IBQ
    THINGSPEAK_MQTT_PASSWORD=jieGpRIkJ13nBPhXa2yAFR5g
    THINGSPEAK_CHANNEL_ID=3529335
    NTFY_TOPIC=tm_smart_vault_bart_2026
    BT_SPEAKER_MAC=33:A8:8C:0F:CC:A0
    ```
- [x] **3. Smartphone Push Alert Abonnement (ntfy.sh):**
  - App geopend op smartphone (Android of iOS).
  - Geabonneerd op topic: `tm_smart_vault_bart_2026` (of de waarde van `NTFY_TOPIC`).
  - Batterij-optimalisatie voor de ntfy-app op *Onbeperkt / Geen restricties* gezet.
- [x] **4. Standalone Microcontroller (Pico 2 W) Perimeter Node:**
  - Gevoed via USB/powerbank (volledig galvanisch gescheiden van Pi 5).
  - Verbonden met lokale Wi-Fi en publiceert afstanden naar `vault/perimeter/distance`.
- [x] **5. Bluetooth Speaker & Microfoon:**
  - Bluetooth speaker ingeschakeld, gekoppeld en luid genoeg gezet.
  - USB-microfoon ingeplugd in de Pi 5 (of `BYPASS_VOICE_2FA = True` in `vault_state.py` indien zonder microfoon getest wordt).
- [x] **6. 30-Seconden Hardware Diagnostic Check uitvoeren:**
  - Draai vanuit de projectmap:
    ```bash
    python3 preflight_check.py
    ```
  - Bevestig dat I2C, SPI (ADC), OLED, RGB LED, Relais/Motor en de knop allemaal groen vinken.

---

## 🔬 Fase 1: Fysieke Verificatietests (De 7 Scenario's)

Start de hoofdapplicatie op de Raspberry Pi 5:
```bash
python3 main.py
```

### Test 1: Ruststand & Analoog Cijferslot met Hysterese
* **Fysieke handeling:** Draai langzaam aan de 10k potentiometer van links (0) naar rechts (9) en terug.
* **Verwachte reacties:**
  - [x] **OLED:** Bovenbalk toont live telemetrie (`L: .. lx  T: .. C  A: .. cm`).
  - [x] **OLED:** Cijfer verandert vloeiend: `Code: [ 0 ] _ _` $\dots$ `Code: [ 9 ] _ _`.
  - [x] **Hysterese:** Op de grenzen tussen twee getallen flikkert het cijfer **niet** dankzij de 12-bit dode band.
  - [x] **RGB LED:** Brandt stabiel saffierblauw (standaard standby).
  - [x] **Motor & Relais:** Volledig stroomloos en koud (relais open).

---

### Test 2: Brute-Force Beveiliging & Snelle Lockout (10s)
* **Fysieke handeling:** Voer 3 opeenvolgende keren een verkeerde code in (bijv. `0 - 0 - 0`).
* **Verwachte reacties:**
  - [x] **Poging 1 & 2:** OLED toont *"FOUTE CODE!"* en toont resterende pogingen. RGB knippert 3s rood.
  - [x] **Poging 3:** Kluis springt direct in `LOCKOUT`.
  - [x] **OLED Aftelklok:** Scherm toont live countdown van 10 seconden (`0:10`, `0:09` $\dots$ `0:00`).
  - [x] **RGB LED:** Schakelt naar gedimd zacht rood (30%).
  - [x] **Akoestisch signaal:** Korte lockout-piep over de Bluetooth speaker.
  - [x] **Smartphone Push:** ntfy melding verschijnt direct:  
    *`SMART VAULT: 3x foute pincode. Kluis 10 seconden geblokkeerd.`*
  - [x] **Auto-Herstel:** Na 10 seconden springt de kluis automatisch terug naar blauw (`PIN_INPUT`).

---

### Test 3: Optische Sabotagedetectie (Licht > 50 Lux)
* **Fysieke handeling:** Zorg dat de kluis gesloten is in `PIN_INPUT` (inwendige lux < 50). Licht het deksel op of schijn met een gsm-zaklamp op de BH1750.
* **Verwachte reacties:**
  - [x] **OLED:** Toont direct **`ALARM!`** met reden **`BRAAK! (.. lx)`**.
  - [x] **RGB LED:** Flitst snel rood/uit als een politie-zwaailicht.
  - [x] **Akoestisch alarm:** De sirene (`sirene.wav`) loeit elke 4 seconden over de Bluetooth speaker.
  - [x] **Smartphone Push:** ntfy melding binnen 1 seconde:  
    *`SMART VAULT ALARM: BRAAK! (.. lx) (Lux=.., Temp=..C)`*
  - [x] **Reset:** Druk 1x op de fysieke drukknop $\rightarrow$ Sirene stopt direct, display en LED keren terug naar blauw.

---

### Test 4: Thermische Oververhittingsdetectie (LM35 > 30 °C)
* **Fysieke handeling:** Klem de LM35 sensor tussen je vingers of verwarm zachtjes tot boven 30 °C.
* **Verwachte reacties:**
  - [x] **Filterverificatie:** Pas na 10 opeenvolgende metingen (> 1 seconde aaneengesloten) slaat het alarm aan (voorkomt pieken).
  - [x] **OLED:** Toont **`ALARM!`** met reden **`BRAND! T=30.x C`**.
  - [x] **Actuatoren:** Rood knipperend zwaailicht + pulserende Bluetooth sirene.
  - [x] **Smartphone Push:** ntfy melding met actuele temperatuur.
  - [x] **Reset:** Laat sensor afkoelen (< 30 °C) en druk op de fysieke knop om te ontgrendelen.

---

### Test 5: Draadloze Perimeter & Loitering (Pico 2 W Radar)
* **Fysieke handeling:** Ga binnen 40 cm voor de ultrasone sensor staan (bijv. op 25 cm). Blijf **15 seconden stil voor de kluis staan** zonder de potmeter of knop aan te raken.
* **Verwachte reacties:**
  - [x] **OLED Telemetrie:** Toont live de afstand (bijv. `A: 25.0 cm`) en een waarschuwingsindicator `[!PAD!]`.
  - [x] **Loitering Trigger:** Na 15 seconden aaneengesloten aanwezigheid slaat het systeem in alarm.
  - [x] **OLED:** Toont **`LOITER > 15s`**.
  - [x] **Actuatoren & Push:** Zwaailicht, sirene en ntfy smartphone alert.
  - [x] **Reset:** Druk 1x op de fysieke knop om het alarm te wissen.

---

### Test 6: Geautoriseerde Toegang (Cijferslot + Spraak 2FA + Motor-Interlock)
* **Fysieke handeling:**
  1. Draai potmeter naar **`4`** $\rightarrow$ Druk knop (`Code: [ 4 ] _ _`).
  2. Draai potmeter naar **`7`** $\rightarrow$ Druk knop (`Code: [ 4 ] 7 _`).
  3. Draai potmeter naar **`2`** $\rightarrow$ Druk knop (`Code: [ 4 ] 7 2`).
* **Verwachte reacties:**
  - [x] **Factor 1 Succes:** OLED toont *"FACTOR 1 (PIN): OK!"* $\rightarrow$ *"SPREEK WACHTWOORD IN"*.
  - [x] **RGB LED:** Schakelt over naar **oranje/amber**.
  - [x] **Factor 2 (Vosk Edge AI):** Zeg duidelijk in de microfoon: **`"open"`**.
  - [x] **Authorised State:** OLED toont `** KLUIS GEOPEND **`, RGB wordt helder **groen**.
  - [x] **Relais Safety Interlock:** Relais klikt hoorbaar **AAN** (relais-LED licht op).
  - [x] **Mechanische Opening:** 28BYJ-48 stappenmotor draait 3072 stappen om de kluis fysiek open te duwen.
  - [x] **Zero-Standby Power:** Relais schakelt direct **UIT** zodra de motor stilstaat (motor blijft 100% koud in open stand).
  - [x] **Sluiten:** Druk op de knop $\rightarrow$ Relais klikt AAN, motor draait 3072 stappen terug, kluis sluit, relais schakelt uit, LED keert terug naar blauw.

---

### Test 7: Cloud Fleet Telemetrie (ThingSpeak MQTT)
* **Fysieke handeling:** Open het openbare ThingSpeak dashboard (Channel `3529335`) op laptop of tablet.
* **Verwachte reacties (elke 15 seconden een nieuwe datapunten):**
  - [x] **Field 1 (Licht):** Piekt omhoog bij Test 3 (sabotage).
  - [x] **Field 2 (Temperatuur):** Piekt omhoog bij Test 4 (brand).
  - [x] **Field 3 (Perimeter Afstand):** Zakt naar ~25 cm bij Test 5 (loitering).
  - [x] **Field 4 (Status Code):** Wisselt correct tussen 0 (PIN), 1 (2FA), 2 (Open), 3 (Alarm), 4 (Lockout).
  - [x] **Field 5 (Cijfer):** Volgt synchroon het geselecteerde cijfer (0 t/m 9).

---

## 🎬 Fase 2: Checklist voor de 5-Minuten Demonstratievideo

Zodra alle 7 tests hierboven een groen vinkje hebben, staat de opstelling 100% scherp voor de video.

- [ ] **Camerakader:** Zowel het OLED-scherm, de RGB LED, het relais/motor-mechanisme én de smartphone (met ntfy open) liggen duidelijk zichtbaar in beeld.
- [ ] **Draaiboek Volgorde:**
  1. *[0:00 - 1:00] Introductie & Architectuur:* Toon ruststand (blauw), leg de 2 breadboards en de Information-Value Loop kort uit.
  2. *[1:00 - 1:45] Perimeter Loitering:* Laat iemand 15s voor de Pico staan $\rightarrow$ loiter-alarm triggert op gsm en speaker.
  3. *[1:45 - 2:30] Sabotage & Lockout:* Deksel optillen $\rightarrow$ lichtalarm; demonstreer daarna 3 foute codes $\rightarrow$ 10s countdown.
  4. *[2:30 - 4:00] Legitieme Ontgrendeling:* Cijfers 4-7-2 invoeren, *"open"* inspreken $\rightarrow$ relais klikt $\rightarrow$ deksel schuift open.
  5. *[4:00 - 5:00] Cloud & Conclusie:* Toon live grafieken op ThingSpeak en sluit af met de geleerde bussen (I2C, SPI, MQTT, PWM).
- [ ] **Schone Shutdown:** Beëindig de demonstratie met `Ctrl+C` in de terminal en controleer dat `vault.stroomloos()`, `deinit()` en pin-cleanup foutloos worden uitgevoerd.


---

## 🎙️ Gesproken Video-Script: Uitleg van de Information-Value Loop (Duur: ~60 sec)

> [!tip] Instructie voor de Video (Minuut 0:00 - 1:00)
> Gebruik onderstaand gesproken draaiboek tijdens de opening van de demonstratievideo. Dit toont de docent direct dat jullie het theoretische kernconcept van IoT Essentials (de **Information-Value Loop**: *Create → Communicate → Aggregate → Analyze → Act*) 100% beheersen en direct koppelen aan jullie fysieke hardware.
>
> De tekst kan door één persoon worden ingesproken of verdeeld worden over **Spreker 1 (Bart)** en **Spreker 2 (Wouter)**. Tussen vierkante haken `[Actie]` staat wat je op dat moment met de camera toont of aanwijst.

### Variant A: Duo-Script (Bart & Wouter)

* **[0:00 - 0:10] Spreker 1 (Bart):**  
  `[Camera: Totaaloverzicht van de opstelling — kluisdoos in ruststand met blauwe LED en OLED actief]`  
  *"Welkom bij de demonstratie van onze Smart Vault voor IoT Essentials. In dit project demonstreren we de complete IoT Information-Value Loop: van fysieke sensordetectie tot edge-besluitvorming, cloud-synchronisatie en fysieke actie."*

* **[0:10 - 0:25] Spreker 2 (Wouter):**  
  `[Camera: Zoom in op de sensoren: Pico met ultrasoon, potmeter en BH1750 in de kluisdoos]`  
  *"De cyclus begint bij **Create**: onze sensoren meten continu de fysieke wereld. Een standalone Pico 2 W meet naderende personen via een ultrasone radarsensor. Binnenin meten we braak via een BH1750 lichtsensor, brand via een LM35 temperatuursensor en cijferinvoer via een analoge potmeter."*

* **[0:25 - 0:38] Spreker 1 (Bart):**  
  `[Camera: Wijs de communicatielijnen aan: Wi-Fi antenne Pico, I2C/SPI Dupont-draden naar de Pi]`  
  *"Vervolgens **Communicate**: de Pico verstuurt zijn afstandsdata draadloos via **Wi-Fi en MQTT** naar onze lokale Mosquitto broker op de Pi 5. De sensoren en het OLED-scherm communiceren lokaal razendsnel via industriële **I2C- en SPI-bussen**."*

* **[0:38 - 0:50] Spreker 2 (Wouter):**  
  `[Camera: Wijs Pi 5 en OLED scherm aan]`  
  *"In de fase **Aggregate** bundelt onze multithreaded controller alle meetwaarden thread-safe in één centrale state en streamt telemetrie naar ThingSpeak. Daarna **Analyze**: onze Edge-logica en een offline Vosk AI-spraakmodel analyseren direct of er sprake is van sabotage, brand, loitering of een correcte 2FA-passphrase."*

* **[0:50 - 1:02] Spreker 1 (Bart):**  
  `[Camera: Wijs relais, stappenmotor, RGB LED en smartphone aan]`  
  *"En tenslotte **Act**, waar de daadwerkelijke waarde ontstaat: bij gevaar activeert het systeem een rood zwaailicht, een Bluetooth sirene en een directe ntfy push-notificatie op onze smartphone. En bij een geautoriseerde ontgrendeling schakelt een 5V veiligheidsrelais stroom naar de stappenmotor om de kluis fysiek open te duwen!"*

---

### Variant B: Solo-Script (Compact door één spreker)

> *"Welkom bij de Smart Vault. Ons project implementeert de complete IoT Information-Value Loop:*  
> *1. **Create:** Een standalone Pico 2 W bewaakt de perimeter met ultrasoon, terwijl de Pi 5 lichtsterkte, temperatuur, potmeter-invoer en spraak registreert.*  
> *2. **Communicate:** De Pico streamt data draadloos via Wi-Fi en MQTT naar de Pi 5, terwijl de sensoren lokaal via hardware I2C- en SPI-bussen praten.*  
> *3. **Aggregate:** De multithreaded state machine verzamelt alle data thread-safe en synchroniseert periodiek met het ThingSpeak cloud-dashboard.*  
> *4. **Analyze:** Onze edge-logica en een lokaal Vosk AI-spraakmodel detecteren direct brand, sabotage, loitering of een geldige 2FA-passphrase.*  
> *5. **Act:** Dit resulteert in directe actie: een rood zwaailicht, Bluetooth sirene en smartphone push-notificatie bij alarm, en een hardware-geïsoleerd relais dat de stappenmotor voedt om de kluis fysiek te openen. Laten we de scenario's bekijken!"*

---
*Laatst bewerkt door AI op: 2026-11-01 15:15*
