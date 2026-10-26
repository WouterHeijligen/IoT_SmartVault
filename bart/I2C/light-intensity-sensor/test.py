import time      # Voor tijdsvertragingen (pauzes tussen metingen)
import board     # Bevat de hardware-definities van de GPIO-pinnen van je bord
import busio     # Handelt hardware-communicatiebussen af (I2C, SPI, UART)

# ==============================================================================
# 1. HARDWARE & I2C-BUS INITIALISATIE
# ==============================================================================

# Wijs de fysieke pinnen toe voor het I2C-protocol:
# Op de Raspberry Pi zijn dit standaard:
# - SCL (Serial Clock): GPIO 3 (fysieke pin 5)
# - SDA (Serial Data):  GPIO 2 (fysieke pin 3)
scl_pin = board.SCL   # Kloklijn: synchroniseert wanneer bits worden uitgelezen
sda_pin = board.SDA   # Datalijn: hierover gaan de daadwerkelijke data-bits

# Initialiseer de I2C-controller van de Pi met deze pinnen
i2c = busio.I2C(scl_pin, sda_pin)

# ==============================================================================
# 2. SENSOR CONSTANTEN (Conform BH1750 Datasheet)
# ==============================================================================

# Het I2C-adres van de sensor op de bus (met ADO-pin aan GND of niet aangesloten)
ADDRESS = 0x23  

# Het commando om continue meting in Hoge Resolutie (1 lux resolutie) te starten.
# We pakken dit in een 'bytearray' in omdat de hardware-bus ruwe bytes verwacht.
# 0x10 in hexadecimaal is het getal 16 in decimaal (zie datasheet instructietabel).
COMMAND_HIGH_RES = bytearray([0x10])

# ==============================================================================
# 3. MEETFUNCTIE
# ==============================================================================

def get_value(i2c_bus, addr):
    """
    Communiceert met de sensor over I2C, leest 2 bytes uit en
    rekent deze om naar een reële lichtsterkte in Lux.
    """
    # Maak een lege buffer aan van exact 2 bytes om de meetdata in op te vangen.
    # [0, 0] in het geheugen.
    result = bytearray(2)

    # Voer een gecombineerde schrijf- en leesoperatie uit op de bus:
    # 1. 'writeto': Stuur commando 0x10 naar sensor-adres 0x23 (zegt: "voer meting uit")
    # 2. 'readfrom': Wacht en lees direct de 2 teruggestuurde bytes in onze 'result'-buffer
    i2c_bus.writeto_then_readfrom(addr, COMMAND_HIGH_RES, result)

    # De sensor stuurt de 16-bit meting opgeknipt in twee aparte 8-bit bytes:
    # result[0] = Hoge byte (Most Significant Byte - MSB)
    # result[1] = Lage byte (Least Significant Byte - LSB)
    #
    # Om deze twee bytes weer aan elkaar te lijmen tot één getal:
    # 1. result[0] << 8 : Schuif de 8 bits van de eerste byte 8 plekken naar links.
    # 2. | result[1]    : Plak de 8 bits van de tweede byte er via bitwise OR achteraan.
    # 3. / 1.2          : Vaste optische kalibratiefactor volgens het Rohm BH1750 datasheet.
    lux = ((result[0] << 8) | result[1]) / 1.2
    
    # Geef de berekende lichtwaarde terug aan de aanroeper
    return lux

# ==============================================================================
# 4. HOOFDPROGRAMMA (Meetlus)
# ==============================================================================

print("Starting BH1750 Light Sensor...")

try:
    # Oneindige lus om continu te blijven meten tot de gebruiker stopt
    while True:
        # Vraag exclusieve toegang tot de I2C-bus (bus locken).
        # Dit voorkomt dat een ander script tegelijkertijd data over dezelfde draden stuurt.
        if i2c.try_lock():
            try:
                # Roep onze functie aan om de actuele lux-waarde op te halen
                lux_val = get_value(i2c, ADDRESS)
                
                # Toon de waarde in de terminal, afgerond op 2 cijfers achter de komma (.2f)
                print(f"{lux_val:.2f} Lux")
            finally:
                # 'finally' voert ALTIJD uit, zelfs als er een fout optreedt in de try-code.
                # Dit garandeert dat de I2C-bus altijd weer netjes wordt vrijgegeven (unlocked).
                i2c.unlock()

        # Wacht 1 seconde voordat we de volgende meting uitvoeren
        time.sleep(1)

except KeyboardInterrupt:
    # Vangt Ctrl+C af zodat het script netjes en zonder lelijke foutmelding afsluit
    print("\nStopped by user.")
