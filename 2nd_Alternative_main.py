import network
import uasyncio as asyncio
from machine import Pin, PWM, I2C, unique_id
import ubinascii
from umqtt.robust import MQTTClient
import config
import time
from machine_i2c_lcd import I2cLcd
import ssl
import socket

# --- CONFIGURATION ---
CORRECT_PIN = "1995"      # User PIN
DEBOUNCE_TIME = 3         # Seconds between motion events
SERVO_OPEN_VAL = 8000     # Calibrated duty cycle for Open
SERVO_CLOSE_VAL = 2000    # Calibrated duty cycle for Closed

MQTT_TOPIC_MOTION = b"iot/motion"
MQTT_TOPIC_CONTROL = b"iot/control"
MQTT_TOPIC_ALARM = b"iot/alarm"

# --- GLOBAL STATE ---
visitor_count = 0
failed_attempts = 0
is_locked_out = False
system_status = "Secure"

# --- HARDWARE SETUP ---
pir = Pin(0, Pin.IN, Pin.PULL_DOWN)
buzzer = Pin(16, Pin.OUT)
servo = PWM(Pin(15))
servo.freq(50)

# I2C LCD Setup
i2c = I2C(0, sda=Pin(8), scl=Pin(9), freq=400000)
try:
    lcd = I2cLcd(i2c, 0x27, 2, 16)
    lcd.clear()
except Exception as e:
    print("LCD not found:", e)
    lcd = None

# --- HELPER FUNCTIONS ---
def update_lcd(line1, line2=""):
    if lcd:
        lcd.clear()
        lcd.putstr(line1)
        if line2:
            lcd.move_to(0, 1)
            lcd.putstr(line2)

def access_granted():
    global failed_attempts, system_status
    print("ACCESS GRANTED")
    system_status = "Access Granted"
    failed_attempts = 0
    update_lcd("Access granted", "Welcome!")
    
    # Open Lock
    servo.duty_u16(SERVO_OPEN_VAL)
    buzzer.value(1)
    time.sleep(0.2)
    buzzer.value(0)
    
    # Wait 5s then Lock
    time.sleep(5)
    servo.duty_u16(SERVO_CLOSE_VAL)
    update_lcd("System armed")
    system_status = "Secure"

def trigger_alarm():
    global system_status
    print("ALARM TRIGGERED")
    system_status = "ALARM ACTIVE"
    update_lcd("ALARM!", "Intruder Alert")
    
    # Alarm Beeps
    for _ in range(5):
        buzzer.value(1)
        time.sleep(0.5)
        buzzer.value(0)
        time.sleep(0.5)

# --- MQTT CALLBACK ---
def mqtt_callback(topic, msg):
    global failed_attempts, is_locked_out, visitor_count
    try:
        command = msg.decode().strip()
    except:
        command = str(msg)
    
    print(f"MQTT RX: {command}")

    if command == "UNLOCK":
        is_locked_out = False
        failed_attempts = 0
        update_lcd("Lockout cleared")
        return

    if is_locked_out:
        return

    if command == CORRECT_PIN:
        access_granted()
    elif command == "RESET":
        visitor_count = 0
        update_lcd("Counter reset")
    else:
        failed_attempts += 1
        print(f"Failed attempts: {failed_attempts}")
        if failed_attempts >= 3:
            is_locked_out = True
            trigger_alarm()
        else:
            update_lcd("Wrong PIN", f"Try {failed_attempts}/3")

# --- ASYNC TASKS ---
async def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.ssid, config.pwd)
    while not wlan.isconnected():
        await asyncio.sleep(1)
    print(f"WiFi Connected: {wlan.ifconfig()[0]}")
    update_lcd("WiFi Connected", wlan.ifconfig()[0])
    await asyncio.sleep(2)
    update_lcd("System armed")

async def mqtt_loop(client):
    while True:
        try:
            client.check_msg()
        except OSError:
            pass
        await asyncio.sleep(0.1)

async def sensor_loop(client):
    global visitor_count, system_status
    last_trigger = 0
    while True:
        if pir.value() == 1:
            now = time.time()
            if (now - last_trigger) > DEBOUNCE_TIME:
                last_trigger = now
                visitor_count += 1
                if system_status == "Secure":
                    update_lcd("Motion detected", f"Count: {visitor_count}")
                try:
                    client.publish(MQTT_TOPIC_MOTION, str(visitor_count).encode())
                except:
                    pass
        await asyncio.sleep(0.1)

# --- WEB SERVER ---
html_template = """<!DOCTYPE html>
<html>
<head><title>Pico Security</title>
<script>
setInterval(function(){
  fetch('/status').then(r=>r.json()).then(d=>{
    document.getElementById("c").innerHTML=d.count;
    document.getElementById("s").innerHTML=d.status;
  });
}, 2000);
</script>
</head>
<body style="text-align:center;font-family:sans-serif;margin-top:50px">
  <h1>Security System</h1>
  <h3>Status: <span id="s">Loading...</span></h3>
  <h3>Visitors: <span id="c">0</span></h3>
</body>
</html>
"""

async def web_server():
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(5)
    s.setblocking(False)
    
    while True:
        try:
            cl, addr = s.accept()
            req = cl.recv(1024).decode()
            if "/status" in req:
                resp = f'{{"count": {visitor_count}, "status": "{system_status}"}}'
                cl.send('HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n' + resp)
            else:
                cl.send('HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n' + html_template)
            cl.close()
        except OSError:
            pass
        await asyncio.sleep(0.1)

# --- MAIN ---
async def main():
    await wifi_connect()
    
    client_id = ubinascii.hexlify(unique_id())
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_NONE
    
    client = MQTTClient(client_id, config.MQTT_BROKER, port=config.MQTT_PORT, 
                        user=config.MQTT_USER, password=config.MQTT_PWD, ssl=context)
    client.set_callback(mqtt_callback)
    client.connect()
    client.subscribe(MQTT_TOPIC_CONTROL)
    print("MQTT Connected")

    asyncio.create_task(mqtt_loop(client))
    asyncio.create_task(sensor_loop(client))
    asyncio.create_task(web_server())
    
    while True:
        await asyncio.sleep(1)

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Stopped")
