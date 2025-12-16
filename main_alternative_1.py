import network
import uasyncio as asyncio
from machine import Pin, PWM, I2C, unique_id
import ubinascii
from umqtt.robust import MQTTClient
import config
import time
from machine_i2c_lcd import I2cLcd  # Ensure you have this lib saved on Pico

# --- CONFIGURATION ---
CORRECT_PIN = "1995"  # <--- SET YOUR PASSWORD HERE
DEBOUNCE_TIME = 3     # Seconds
SERVO_OPEN_VAL = 8000 # Adjust for your servo (approx 90 degrees) 
SERVO_CLOSE_VAL = 2000 # Adjust for your servo (approx 0 degrees)

# --- GLOBAL STATE VARIABLES ---
visitor_count = 0
failed_attempts = 0
is_locked_out = False
system_status = "Secure" # For Web Display

# --- HARDWARE SETUP ---
pir = Pin(0, Pin.IN, Pin.PULL_DOWN)
buzzer = Pin(16, Pin.OUT)
servo = PWM(Pin(15))
servo.freq(50)

# I2C LCD Setup (Check your specific SDA/SCL pins)
i2c = I2C(0, sda=Pin(8), scl=Pin(9), freq=400000) 
try:
    lcd = I2cLcd(i2c, 0x27, 2, 16) # Address 0x27 is standard
    lcd.clear()
except:
    print("LCD not found (Check wiring/Address)")
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
    update_lcd("Welcome Home!")
    
    # Open Door
    servo.duty_u16(SERVO_OPEN_VAL)
    buzzer.value(1) # Short beep
    time.sleep(0.2)
    buzzer.value(0)
    
    # Keep open for 5 seconds then close
    time.sleep(5) 
    servo.duty_u16(SERVO_CLOSE_VAL)
    update_lcd("System Armed")
    system_status = "Secure"

def trigger_alarm():
    global system_status
    print("ALARM TRIGGERED")
    system_status = "ALARM ACTIVE"
    update_lcd("ALARM!", "Intruder Alert")
    # Beep 5 times
    for _ in range(5):
        buzzer.value(1)
        time.sleep(0.5)
        buzzer.value(0)
        time.sleep(0.5)

# --- MQTT SETUP ---
def mqtt_callback(topic, msg):
    global failed_attempts, is_locked_out
    try:
        command = msg.decode().strip()
        print(f"MQTT Received: {command}")
        
        if is_locked_out:
            return

        if command == CORRECT_PIN:
            access_granted()
        elif command == "RESET":
            # Reset logic (if needed for counter)
            global visitor_count
            visitor_count = 0
        else:
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
    wlan.connect(config.ssid, config.pwd)
    print(f"Connecting to {config.ssid}...")
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
                
                # Update Status if not already in Alarm/Access mode
                if system_status == "Secure":
                    update_lcd("Motion Detected", f"Count: {visitor_count}")
                    # Revert to "Armed" after 2 sec (handled by sleep/logic)
                
                # Publish to MQTT
                try:
                    client.publish(b"iot/motion", str(visitor_count).encode())
                except:
                    print("MQTT Publish Fail")
                    
        await asyncio.sleep(0.1)

# --- WEB SERVER (Dynamic) ---
# This HTML uses JS to fetch status every 2 seconds (AJAX)
html_template = """
<!DOCTYPE html>
<html>
<head>
<title>Pico Security</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>
setInterval(function() {
  fetch('/status').then(response => response.json()).then(data => {
    document.getElementById("count").innerHTML = data.count;
    document.getElementById("status").innerHTML = data.status;
  });
}, 2000);
</script>
<style>
body { font-family: sans-serif; text-align: center; margin-top: 50px; }
h1 { color: #333; }
.stat { font-size: 24px; margin: 20px; }
</style>
</head>
<body>
  <h1>IoT Security System</h1>
  <div class="stat">Status: <span id="status">Loading...</span></div>
  <div class="stat">Visitors: <span id="count">0</span></div>
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
    
    print("Web Server Listening...")
    
    while True:
        try:
            cl, addr = s.accept()
            # Handle Request
            request = cl.recv(1024)
            req_str = str(request)
            
            # API Endpoint for JSON (used by JS)
            if '/status' in req_str:
                response = 'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n'
                response += '{"count": ' + str(visitor_count) + ', "status": "' + system_status + '"}'
            # Main Page
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
    
    # Generate unique ID for MQTT
    client_id = ubinascii.hexlify(unique_id())
    
    # Connect MQTT (SSL context from your original code)
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
    print("Stopped")