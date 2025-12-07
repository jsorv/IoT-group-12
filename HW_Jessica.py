from machine import Pin, PWM, ADC, SoftI2C
from machine_i2c_lcd import I2cLcd
from umqtt.simple import MQTTClient
from time import sleep, time
import config
import network
import socket
import ssl
import sys

# WIFI SETUP - CONNECTION
ssid = config.ssid
pwd = config.pwd

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, pwd)

max_retries = 10
retries = 0
#Waits for the connection to established
#Waits for maximun 20 seconds before continuing
while not wlan.isconnected() and retries < max_retries:
    print(f"Attempt {retries + 1}/{max_retries}...")
    sleep(2)
    retries += 1
    
if wlan.isconnected():
    print(f"Congratulations WiFi connected succesfully!")
else:
    print("Oh no!Failed to connect to the Wi-Fi!")
    sys.exit()

# set up socket and listen on port 80
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)  # Listen for incoming connections

print('[INFO] Listening on', addr)


#MQTT BROKER SETUP:
broker = "421b822c7f5243ffba8964c47409268d.s1.eu.hivemq.cloud"
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.verify_mode = ssl.CERT_NONE

client = MQTTClient(
    client_id=b'hello',
    server=config.MQTT_BROKER,
    port=config.MQTT_PORT,               # TLS port for HiveMQ
    user=config.MQTT_USER,
    password=config.MQTT_PWD,
    ssl=context              # <- keep context as TA requires
)

client.connect()


# Define the LCD I2C address and dimensions
I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16

# Line for the PIR motion detector
miniPir = Pin(7, Pin.IN, Pin.PULL_DOWN)

# Initialize I2C and LCD objects
i2c = SoftI2C(sda=Pin(2), scl=Pin(3), freq=400000)

lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)

# Line for the buzzer warning, default OFF
pwm = PWM(Pin(5))  # buzzer connected to A1
pwm.freq(10000)
servo_val = 10000

# States
armed_mode = True       # waiting mode
alert_mode = False      # intrusion active

# Startup display
lcd.putstr("Security System Active")
sleep(2)
lcd.clear()
lcd.backlight_off()

#HTML Code display
status_char = "System Active"
# generate html
def generate_html(status):
    html = f"""\
    HTTP/1.1 200 OK
    Content-Type: text/html

    <!DOCTYPE html>
    <html>
      <head><title>Security alarm system</title></head>
      <body>
          <h1 style='color:red, text-align:center'>SECURITY ALARM SYSTEM</h1>
          <h2>Status: {status}</h2>
          <p>This is static content for now.</p>
      </body>
    </html>
    """
    return str(html)

try:
    while True:
        val = miniPir.value()
        sleep(0.05)  # reduce noise

        # ---------- FIRST HAND: ENTER ALERT MODE ----------
        if val == 1 and armed_mode:
            armed_mode = False
            alert_mode = True

            lcd.backlight_on()
            lcd.clear()
            lcd.putstr("ALERT")
            lcd.move_to(0, 1)
            lcd.putstr("Intruder")

            pwm.duty_u16(servo_val)
            sleep(2)
            pwm.duty_u16(0)

        # ---------- SECOND HAND: RESET SYSTEM ----------
        elif val == 1 and alert_mode:
            alert_mode = False
            armed_mode = True

            lcd.clear()
            lcd.putstr("System Reset")
            sleep(1)
            lcd.clear()
            lcd.backlight_off()

        try:
            cl, addr = s.accept()
            print('[INFO] Client connected from', addr)
            request = cl.recv(1024)
            print('[INFO] Request:', request)

            # send static HTML
            response = generate_html(status_char)
            cl.send(response)
            cl.close()

        except OSError:
            pass  # No client connected; continue loop

        sleep(0.1)

except KeyboardInterrupt:
    lcd.backlight_off()
    pwm.duty_u16(0)
               

except KeyboardInterrupt:
    # Turn off the display
    print("Keyboard interrupt")
    lcd.backlight_off()
    lcd.display_off()
