import network
import uasyncio as asyncio
import time
import ssl
import socket
import ujson
from machine import Pin, SoftI2C # Changed from I2C to SoftI2C
from umqtt.simple import MQTTClient
from machine_i2c_lcd import I2cLcd
import config

# ==========================================
# 1. HARDWARE & CONSTANTS
# ==========================================
PIR_PIN = 28
BUZZER_PIN = 16
LCD_SDA = 0
LCD_SCL = 1

DEBOUNCE_DELAY = 3  # Seconds between motion events
LOCKOUT_LIMIT = 3   # Max failed attempts
LOCKOUT_TIME = 60   # Seconds to lock system

# ==========================================
# 2. GLOBAL STATE
# ==========================================
# 0=DISARMED, 1=ARMED, 2=ALERT, 3=LOCKOUT
current_state = 1
failed_attempts = 0
last_motion_time = 0

# ==========================================
# 3. SETUP HARDWARE
# ==========================================
pir = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)
buzzer = Pin(BUZZER_PIN, Pin.OUT)

# --- CHANGED TO SoftI2C ---
# SoftI2C works on any pins and avoids "bad SCL pin" errors
# Note: We removed the '0' (id) from the arguments
i2c = SoftI2C(sda=Pin(LCD_SDA), scl=Pin(LCD_SCL), freq=400000)

try:
    lcd = I2cLcd(i2c, 0x27, 2, 16)
except Exception as e:
    print(f"LCD Init Error: {e}")
    lcd = None

# ==========================================
# 4. HELPER FUNCTIONS
# ==========================================
def update_display(line1, line2=""):
    if lcd:
        try:
            lcd.clear()
            lcd.putstr(line1)
            if line2:
                lcd.move_to(0, 1)
                lcd.putstr(line2)
        except Exception as e:
            print(f"LCD Write Error: {e}")

def control_servo(position):
    """
    Simulates servo movement since hardware is missing.
    """
    print(f"[SIMULATION] Servo moved to: {position}")

# ==========================================
# 5. ASYNC TASKS
# ==========================================

async def web_server():
    """Simple HTTP Server for local status"""
    print("[WEB] Starting Server...")
    try:
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(5)
        s.setblocking(False) # Non-blocking socket

        while True:
            try:
                conn, addr = s.accept()
                request = conn.recv(1024)
                # Simple HTML Response
                state_str = ["DISARMED", "ARMED", "ALERT", "LOCKOUT"][current_state]
                response = f"""HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n
                <html><h1>System Status</h1>
                <h2>State: {state_str}</h2>
                <h2>Failed Attempts: {failed_attempts}</h2></html>"""
                conn.send(response)
                conn.close()
            except OSError:
                # No connection to accept
                pass
            except Exception as e:
                print("Web Server Error:", e)
            
            await asyncio.sleep(0.1)
    except Exception as e:
         print("Server Init Error:", e)

async def mqtt_loop(client):
    """Handles MQTT Messages"""
    global current_state, failed_attempts
    
    while True:
        try:
            client.check_msg()
        except OSError:
            print("MQTT Error")
        await asyncio.sleep(0.1)

def mqtt_callback(topic, msg):
    global current_state, failed_attempts
    
    cmd = msg.decode().upper()
    print(f"[MQTT] Received: {cmd}")
    
    # --- LOCKOUT LOGIC ---
    if current_state == 3:
        if cmd == "ADMIN_RESET":
            failed_attempts = 0
            current_state = 1
            update_display("SYSTEM RESET", "Attempts Cleared")
        return

    # --- PIN VERIFICATION LOGIC ---
    
    if cmd == "UNLOCK": # Correct PIN
        failed_attempts = 0
        current_state = 0
        control_servo("UNLOCK") # Calls the simulation function
        buzzer.value(0)
        update_display("DISARMED", "Access Granted")
        client.publish(config.TOPIC_STATUS, b'{"status":"DISARMED"}')
        
    elif cmd == "LOCK":
        current_state = 1
        control_servo("LOCK") # Calls the simulation function
        update_display("SYSTEM ARMED", "Monitoring...")
        client.publish(config.TOPIC_STATUS, b'{"status":"ARMED"}')
        
    elif cmd == "BAD_PIN": # Simulating Wrong PIN
        failed_attempts += 1
        print(f"Failed Attempt: {failed_attempts}")
        update_display("INVALID PIN!", f"Attempts: {failed_attempts}/3")
        
        if failed_attempts >= LOCKOUT_LIMIT:
            current_state = 3 # LOCKOUT
            update_display("SYSTEM LOCKED", "Wait 60s...")
            buzzer.value(1) # Long Alarm
            client.publish(config.TOPIC_STATUS, b'{"status":"LOCKOUT"}')

async def sensor_loop(client):
    """Monitors PIR Sensor with Debouncing"""
    global current_state, last_motion_time
    
    while True:
        if current_state == 1: # ARMED
            if pir.value() == 1:
                now = time.time()
                # Debounce Logic
                if (now - last_motion_time) > DEBOUNCE_DELAY:
                    print("Motion Detected!")
                    last_motion_time = now
                    current_state = 2 # ALERT
                    
                    update_display("!! ALERT !!", "Intruder Detect")
                    client.publish(config.TOPIC_STATUS, b'{"status":"INTRUDER"}')
                    
        if current_state == 2: # ALERT MODE
            buzzer.value(1)
            await asyncio.sleep(0.2)
            buzzer.value(0)
            await asyncio.sleep(0.2)
        elif current_state == 3: # LOCKOUT MODE
            # Pulse buzzer slowly
            buzzer.value(1)
            await asyncio.sleep(1)
            buzzer.value(0)
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(0.1)

# ==========================================
# 6. MAIN SETUP
# ==========================================
async def main():
    # Connect Wi-Fi
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.ssid, config.pwd)
    
    # Wait for connection with timeout
    max_wait = 10
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('waiting for connection...')
        await asyncio.sleep(1)

    if wlan.status() != 3:
        print('network connection failed')
        update_display("WiFi Failed", "Check Config")
    else:
        print("Wi-Fi Connected:", wlan.ifconfig()[0])
        update_display("Wi-Fi OK", wlan.ifconfig()[0])
        
        # Connect MQTT
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.verify_mode = ssl.CERT_NONE
            client = MQTTClient(b"pico_id", config.MQTT_BROKER, port=8883, 
                                user=config.MQTT_USER, password=config.MQTT_PWD, 
                                ssl=context)
            client.set_callback(mqtt_callback)
            client.connect()
            client.subscribe(config.TOPIC_CONTROL)
            print("MQTT Connected")
            
            # Start Concurrent Tasks
            asyncio.create_task(web_server())
            asyncio.create_task(mqtt_loop(client))
            asyncio.create_task(sensor_loop(client))
            
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            print("MQTT/Main Error:", e)
            update_display("MQTT Error", "Check Broker")

# Run
try:
    asyncio.run(main())
except Exception as e:
    print("Error:", e)