from machine import Pin, PWM, ADC, SoftI2C
from machine_i2c_lcd import I2cLcd
from umqtt.simple import MQTTClient
from time import sleep, time
from ws2812 import WS2812
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
ip_info = wlan.ifconfig()
print("[INFO] IP address:", ip_info[0])


# set up socket and listen on port 80
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)  # Listen for incoming connections
s.setblocking(False)

print('[INFO] Listening on', addr)


#MQTT BROKER SETUP:
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

# LED colors
BLACK = (0, 0, 0)
RED   = (255, 0, 0)
GREEN = (0, 255, 0)

# Define the LCD I2C address and dimensions
I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16

# Line for the PIR motion detector
miniPir = Pin(7, Pin.IN,)

# Initialize I2C and LCD objects
i2c = SoftI2C(sda=Pin(2), scl=Pin(3), freq=400000)

lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)

# Line for the buzzer warning, default OFF
pwm = PWM(Pin(5))  # buzzer connected to A1
pwm.freq(10000)
servo_val = 10000
led = WS2812(16, 30)   # GP16, 1 LED

# LED helper functions
def led_red():
    led.pixels_fill(RED)
    led.pixels_show()

def led_green():
    led.pixels_fill(GREEN)
    led.pixels_show()

def led_off():
    led.pixels_fill(BLACK)
    led.pixels_show()

# PIR warm-up
print("Warming up PIR...")
sleep(30)
print("PIR ready")

# States
armed_mode = True       # waiting mode
alert_mode = False      # intrusion active
alert_start = 0
motion_latched = False
pir_counter = 0 #counter variable

# Startup display
lcd.putstr("Security System Active")
sleep(2)
lcd.clear()
lcd.backlight_off()
led_green()

#HTML Code display
status_char = "System Active"
# generate html
def generate_html(status):
    html = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + f"""\
<!DOCTYPE html>
<html>
  <head><title>Security alarm system</title></head>
  <body>
      <h1 style='color:red; text-align:center'>SECURITY ALARM SYSTEM</h1>
      <h2>Status: {status}</h2>
      <p>This is static content for now.</p>
  </body>
</html>
"""
    return str(html)


try:
    while True:
        val = miniPir.value()

        # --- WAIT FOR PIR TO GO LOW ---
        if motion_latched:
            if val == 0:
                motion_latched = False
                armed_mode = True
            sleep(0.05)
            continue

        # --- ALERT (ONCE PER MOTION) ---
        if val == 1 and armed_mode:
            armed_mode = False
            alert_mode = True
            alert_start = time()
            motion_latched = True

            pir_counter +=1
            mqtt_msg=str(pir_counter)
            try:
                client.publish("home/security/pir_count",mqtt_msg)
            except Exception as e:
                print("MQTT publish error:",e)

            led_red() #alert led
            
            lcd.backlight_on()
            lcd.clear()
            lcd.putstr("ALERT")
            lcd.move_to(0, 1)
            lcd.putstr("Intruder")

            pwm.duty_u16(servo_val)

        # --- STOP BUZZER + SYSTEM OFF ---
        if alert_mode and time() - alert_start > 2:
            pwm.duty_u16(0)
            alert_mode = False

            lcd.clear()
            lcd.putstr("Security System")
            lcd.move_to(0, 1)
            lcd.putstr("OFF")
            
            try:
                client.publish("home/security/state","OFF")
            except Exception as e:
                print("MQTT publish error:", e)
                
            led_green() #system off
            
            sleep(1)
            lcd.clear()
            lcd.backlight_off()

        # --- WEB CLIENT (non-blocking) ---
        try:
            cl, addr = s.accept()
        except OSError:
            cl = None  # No client waiting

        if cl:
            try:
                request = cl.recv(1024)  # read request
                cl.send(generate_html(status_char))  # send static HTML
            except OSError:
                pass
            finally:
                cl.close()

        sleep(0.05)

except KeyboardInterrupt:
    lcd.backlight_off()
    pwm.duty_u16(0)