from machine import Pin, SPI, UART

# ------- Pins -------
DC_PIN = 8
RST_PIN = 12
MOSI_PIN = 11
SCK_PIN = 10
CS_PIN = 9

KEY0_PIN = 15
KEY1_PIN = 17

UART_TX_PIN = 4
UART_RX_PIN = 5

# ------- Interfaces -------
uart = UART(1, baudrate=115200, tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN))

spi = SPI(1, 30000_000, polarity=0, phase=0, sck=Pin(SCK_PIN), mosi=Pin(MOSI_PIN), miso=None)

# Control Pins for OLED
oled_cs = Pin(CS_PIN, Pin.OUT)
oled_dc = Pin(DC_PIN, Pin.OUT)
oled_rst = Pin(RST_PIN, Pin.OUT)

# Input Pins
key0 = Pin(KEY0_PIN, Pin.IN, Pin.PULL_UP)
key1 = Pin(KEY1_PIN, Pin.IN, Pin.PULL_UP)
