import network
import uasyncio as asyncio
import time
import ssl
import socket
import ujson
from machine import Pin, PWM, SoftI2C
from umqtt.simple import MQTTClient
from machine_i2c_lcd import I2cLcd
from ws2812 import WS2812
import config

# ==========================================
# 1. HARDWARE CONFIGURATION
# ==========================================
PIR_PIN = 7         # PIR Sensor
BUZZER_PIN = 5      # Buzzer
LCD_SDA = 2         # I2C Data
LCD_SCL = 3         # I2C Clock
LED_PIN = 16        # Neopixel LED
LED_COUNT = 30      # From your code

# Constants
DEBOUNCE_DELAY = 3  # Seconds between motion events
LOCKOUT_LIMIT = 3   # Max failed attempts
LOCKOUT_TIME = 60   # Seconds to lock system
WARMUP_TIME = 20    # Seconds to wait for PIR to stabilize

# LED Colors (R, G, B)
COLOR_BLACK = (0, 0, 0)
COLOR_RED   = (255, 0, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE  = (0, 0, 255)
COLOR_YELLOW= (255, 150, 0)

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
# PIR
pir = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)

# Buzzer
buzzer = PWM(Pin(BUZZER_PIN))
buzzer.freq(2000)
buzzer.duty_u16(0)

# LCD
i2c = SoftI2C(sda=Pin(LCD_SDA), scl=Pin(LCD_SCL), freq=400000)
try:
    lcd = I2cLcd(i2c, 0x27, 2, 16)
except Exception as e:
    print(f"LCD Init Error: {e}")
    lcd = None

# WS2812 LED
try:
    led = WS2812(LED_PIN, LED_COUNT)
except Exception as e:
    print(f"LED Init Error: {e}")
    led = None

# ==========================================
# 4. HELPER FUNCTIONS
# ==========================================
def set_led(color):
    if led:
        led.pixels_fill(color)
        led.pixels_show()

def buzzer_on():
    buzzer.duty_u16(30000)

def buzzer_off():
    buzzer.duty_u16(0)

def update_display(line1, line2=""):
    if lcd:
        try:
            lcd.clear()
            lcd.putstr(line1)
            if line2:
                lcd.move_to(0, 1)
                lcd.putstr(line2)
        except:
            pass

def control_servo(position):
    print(f"[SIMULATION] Servo moved to: {position}")

# ==========================================
# 5. ASYNC TASKS
# ==========================================

async def web_server():
    """Simple HTTP Server"""
    print("[WEB] Starting Server...")
    try:
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(5)
        s.setblocking(False)

        while True:
            try:
                conn, addr = s.accept()
                request = conn.recv(1024)
                state_str = ["DISARMED", "ARMED", "ALERT", "LOCKOUT"][current_state]
                response = f"""HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n
                <!DOCTYPE html>
                <html>
                  <head><title>Security System</title></head>
                  <body>
                      <h1 style='color:red; text-align:center'>SECURITY ALARM SYSTEM</h1>
                      <h2>Status: {state_str}</h2>
                      <h3>Failed Attempts: {failed_attempts}</h3>
                  </body>
                </html>"""
                conn.send(response)
                conn.close()
            except OSError:
                pass
            await asyncio.sleep(0.1)
    except Exception as e:
         print("Server Init Error:", e)

async def mqtt_loop(client):
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
    
    if current_state == 3 and cmd == "ADMIN_RESET":
        failed_attempts = 0
        current_state = 1
        update_display("SYSTEM RESET", "Attempts Cleared")
        set_led(COLOR_BLUE) # Back to armed color
        return

    if cmd == "UNLOCK":
        failed_attempts = 0
        current_state = 0
        control_servo("UNLOCK")
        buzzer_off()
        set_led(COLOR_GREEN)
        update_display("DISARMED", "Access Granted")
        client.publish(config.TOPIC_STATUS, b'{"status":"DISARMED"}')
        
    elif cmd == "LOCK":
        current_state = 1
        control_servo("LOCK")
        set_led(COLOR_BLUE)
        update_display("SYSTEM ARMED", "Monitoring...")
        client.publish(config.TOPIC_STATUS, b'{"status":"ARMED"}')
        
    elif cmd == "BAD_PIN":
        failed_attempts += 1
        update_display("INVALID PIN!", f"Attempts: {failed_attempts}/3")
        set_led(COLOR_YELLOW)
        buzzer_on()
        time.sleep(0.2)
        buzzer_off()
        
        if failed_attempts >= LOCKOUT_LIMIT:
            current_state = 3
            update_display("SYSTEM LOCKED", "Wait 60s...")
            set_led(COLOR_RED)
            client.publish(config.TOPIC_STATUS, b'{"status":"LOCKOUT"}')

async def sensor_loop(client):
    global current_state, last_motion_time
    
    # --- WARM UP PHASE ---
    print("Starting PIR Warmup...")
    update_display("System Start", "Warming Sensor..")
    set_led(COLOR_YELLOW)
    
    # Wait for sensor to settle (20 seconds)
    for i in range(WARMUP_TIME):
        if i % 5 == 0:
            print(f"Warming up... {WARMUP_TIME - i}s")
        await asyncio.sleep(1)
        
    print("PIR Ready.")
    update_display("SYSTEM ARMED", "Monitoring...")
    set_led(COLOR_BLUE)
    
    # --- MONITORING LOOP ---
    while True:
        if current_state == 1: # ARMED
            if pir.value() == 1:
                now = time.time()
                if (now - last_motion_time) > DEBOUNCE_DELAY:
                    print("Motion Detected!")
                    last_motion_time = now
                    current_state = 2 # ALERT
                    
                    update_display("!! ALERT !!", "Intruder Detect")
                    set_led(COLOR_RED)
                    client.publish(config.TOPIC_STATUS, b'{"status":"INTRUDER"}')
                    
        # State Actions
        if current_state == 2: # ALERT
            buzzer_on()
            await asyncio.sleep(0.5)
            buzzer_off()
            await asyncio.sleep(0.5)
        elif current_state == 3: # LOCKOUT
            buzzer_on()
            await asyncio.sleep(1)
            buzzer_off()
            await asyncio.sleep(2)
        else:
            await asyncio.sleep(0.1)

# ==========================================
# 6. MAIN SETUP
# ==========================================
async def main():
    set_led(COLOR_YELLOW)
    update_display("Connecting...", "Wi-Fi")
    
    # Wi-Fi
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.ssid, config.pwd)
    
    max_wait = 15
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        await asyncio.sleep(1)

    if wlan.status() != 3:
        update_display("WiFi Failed", "Check Config")
        set_led(COLOR_RED)
    else:
        print(f"Connected: {wlan.ifconfig()[0]}")
        update_display("Wi-Fi OK", "Connecting MQTT")
        
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
            
            # Start Tasks
            asyncio.create_task(web_server())
            asyncio.create_task(mqtt_loop(client))
            # Sensor loop includes the warmup now
            asyncio.create_task(sensor_loop(client))
            
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            print("Init Error:", e)
            update_display("MQTT Error", "Check Broker")

try:
    asyncio.run(main())
except Exception as e:
    print("Error:", e)