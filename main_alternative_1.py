import network
import uasyncio as asyncio
from machine import Pin, PWM, I2C, unique_id
import ubinascii
from umqtt.robust import MQTTClient
import config  # Ensure config.py is on the Pico
import time

# Assumes machine_i2c_lcd.py is saved on the Pico
try:
    from machine_i2c_lcd import I2cLcd
    LCD_AVAILABLE = True
except ImportError:
    LCD_AVAILABLE = False
    print("LCD Library not found")

# --- CONFIGURATION ---
CORRECT_PIN = "1995"   # Password for unlocking
DEBOUNCE_TIME = 3      # Seconds to ignore new motion
SERVO_OPEN_VAL = 4800  # Adjust for 90 degrees (approx)
SERVO_CLOSE_VAL = 1600 # Adjust for 0 degrees (approx)

# --- GLOBAL STATE VARIABLES ---
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
lcd = None
if LCD_AVAILABLE:
    try:
        # Note: Check your specific I2C Pins (SDA/SCL)
        i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000) 
        # Note: Address is often 0x27 or 0x3F. Change if needed.
        lcd = I2cLcd(i2c, 0x27, 2, 16) 
        lcd.clear()
        try:
            lcd.backlight_on() # Ensure backlight is on if supported
        except:
            pass
    except Exception as e:
        print(f"LCD Init Error: {e}")

# --- HELPER FUNCTIONS ---
def update_lcd(line1, line2=""):
    if lcd:
        try:
            lcd.clear()
            lcd.putstr(line1)
            if line2:
                lcd.move_to(0, 1)
                lcd.putstr(line2)
        except:
            pass

def access_granted():
    global failed_attempts, system_status
    print("ACCESS GRANTED")
    system_status = "Access Granted"
    failed_attempts = 0
    update_lcd("Welcome Home!")
    
    # Open Door
    servo.duty_u16(SERVO_OPEN_VAL)
    buzzer.value(1)
    time.sleep(0.2)
    buzzer.value(0)
    
    # Keep open for 5 seconds then close
    time.sleep(5) 
    servo.duty_u16(SERVO_CLOSE_VAL)
    update_lcd("System Armed")
    system_status = "Secure"

def trigger_alarm():
    global system_status, is_locked_out
    print("ALARM TRIGGERED")
    system_status = "ALARM ACTIVE"
    update_lcd("ALARM!", "Intruder Alert")
    
    # Alarm sequence
    for _ in range(5):
        buzzer.value(1)
        time.sleep(0.5)
        buzzer.value(0)
        time.sleep(0.5)
    
    # Reset lockout after alarm
    is_locked_out = False
    system_status = "Secure"
    update_lcd("System Armed")

# --- MQTT SETUP ---
def mqtt_callback(topic, msg):
    global failed_attempts, is_locked_out, visitor_count
    try:
        command = msg.decode().strip()
        print(f"MQTT Received: {command}")
        
        if is_locked_out:
            print("System Locked Out")
            return

        if command == CORRECT_PIN:
            access_granted()
        elif command == "RESET":
            visitor_count = 0
            print("Counter Reset")
            update_lcd("Counter Reset")
            time.sleep(1)
            update_lcd("System Armed")
        elif command == "ARM":
             update_lcd("System Armed")
        else:
            # Wrong Password Logic
            failed_attempts += 1
            print(f"Wrong PIN. Attempts: {failed_attempts}")
            if failed_attempts >= 3:
                is_locked_out = True
                trigger_alarm()
            else:
                update_lcd("Wrong PIN", f"Try {failed_attempts}/3")
                
    except Exception as e:
        print(f"Callback Error: {e}")

# --- ASYNC TASKS ---

async def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"Connecting to {config.ssid}...")
        wlan.connect(config.ssid, config.pwd)
        while not wlan.isconnected():
            await asyncio.sleep(1)
    print(f"WiFi Connected: {wlan.ifconfig()[0]}")
    update_lcd("WiFi Connected", wlan.ifconfig()[0])
    await asyncio.sleep(2)
    update_lcd("System Armed")

async def mqtt_loop(client):
    while True:
        try:
            client.check_msg()
        except OSError:
            print("MQTT Check Error")
        await asyncio.sleep(0.1)

async def sensor_loop(client):
    global visitor_count, system_status
    last_trigger = 0
    
    while True:
        if pir.value() == 1:
            now = time.time()
            if (now - last_trigger) > DEBOUNCE_TIME:
                print("Motion Detected!")
                last_trigger = now
                visitor_count += 1
                
                # Update Status if not in Alarm mode
                if system_status == "Secure":
                    update_lcd("Motion Detected", f"Count: {visitor_count}")
                
                # Publish to MQTT
                try:
                    client.publish(b"iot/motion", str(visitor_count).encode())
                except:
                    print("MQTT Publish Fail")
                    
        await asyncio.sleep(0.1)

# --- WEB SERVER (Dynamic AJAX) ---
html_template = """
<!DOCTYPE html>
<html>
<head>
<title>IoT Security</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>
setInterval(function() {
  fetch('/status').then(r => r.json()).then(d => {
    document.getElementById("cnt").innerHTML = d.count;
    document.getElementById("sts").innerHTML = d.status;
  });
}, 2000);
</script>
<style>
body { font-family: sans-serif; text-align: center; margin-top: 50px; }
.box { border: 2px solid #333; padding: 20px; margin: 20px; display: inline-block; }
</style>
</head>
<body>
  <h1>Intrusion System</h1>
  <div class="box">Status: <span id="sts">Loading...</span></div>
  <div class="box">Intrusions: <span id="cnt">0</span></div>
</body>
</html>
"""

async def web_server():
    import socket
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(5)
    s.setblocking(False)
    
    print("Web Server Started")
    
    while True:
        try:
            cl, addr = s.accept()
            request = cl.recv(1024)
            req_str = str(request)
            
            # API Endpoint for JSON
            if '/status' in req_str:
                response = 'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n'
                response += '{"count": ' + str(visitor_count) + ', "status": "' + system_status + '"}'
            else:
                response = 'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n' + html_template
                
            cl.send(response)
            cl.close()
        except OSError:
            pass
        await asyncio.sleep(0.1)

# --- MAIN EXECUTION ---
async def main():
    await wifi_connect()
    
    # Generate unique ID
    client_id = ubinascii.hexlify(unique_id())
    
    # SSL Context
    import ssl
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_NONE
    
    client = MQTTClient(
        client_id=client_id,
        server=config.MQTT_BROKER,
        port=config.MQTT_PORT,
        user=config.MQTT_USER,
        password=config.MQTT_PWD,
        ssl=context
    )
    client.set_callback(mqtt_callback)
    client.connect()
    client.subscribe(b"iot/control")
    print("MQTT Connected")

    # Start Tasks
    asyncio.create_task(mqtt_loop(client))
    asyncio.create_task(sensor_loop(client))
    asyncio.create_task(web_server())
    
    while True:
        await asyncio.sleep(1)

# Run
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("System Stopped")