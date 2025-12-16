import network
import time
import socket
import ssl
import ujson
from machine import Pin, PWM, I2C
from umqtt.simple import MQTTClient
from machine_i2c_lcd import I2cLcd
import config

# ==========================================
# 1. HARDWARE CONFIGURATION
# ==========================================

# Pin Definitions
PIR_PIN = 28        # Motion Sensor Input
SERVO_PIN = 15      # Servo Motor Control
BUZZER_PIN = 16     # Buzzer Output
LCD_SDA = 0         # I2C Data
LCD_SCL = 1         # I2C Clock

# Servo Settings (SG90)
SERVO_LOCKED = 1500   # Approx 0 degrees
SERVO_UNLOCKED = 8000 # Approx 180 degrees
pwm_servo = PWM(Pin(SERVO_PIN))
pwm_servo.freq(50)

# LCD Settings (16x2 I2C)
I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16
i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL), freq=400000)

try:
    lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)
except Exception as e:
    print("LCD Error:", e)
    lcd = None

# Initialize Sensors
pir = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)
buzzer = Pin(BUZZER_PIN, Pin.OUT)

# ==========================================
# 2. MQTT SETTINGS
# ==========================================
TOPIC_STATUS = b"home/security/status"   # Pico sends updates here
TOPIC_CONTROL = b"home/security/control" # Pico listens for commands here

# ==========================================
# 3. SYSTEM STATE
# ==========================================
# 0 = DISARMED (Safe Mode)
# 1 = ARMED (Security Mode)
# 2 = ALERT (Intruder Detected)
current_state = 1 

# ==========================================
# 4. HELPER FUNCTIONS
# ==========================================

def control_servo(position):
    """Moves servo to LOCKED or UNLOCKED position"""
    if position == "UNLOCK":
        pwm_servo.duty_u16(SERVO_UNLOCKED)
    else:
        pwm_servo.duty_u16(SERVO_LOCKED)
    time.sleep(0.5)
    pwm_servo.duty_u16(0) # Stop signal to prevent jitter

def update_display(line1, line2=""):
    """Writes text to the LCD screen"""
    if lcd:
        lcd.clear()
        lcd.putstr(line1)
        if line2:
            lcd.move_to(0, 1)
            lcd.putstr(line2)

def send_status(client, msg):
    """Publishes JSON system state to MQTT"""
    try:
        # JSON formatting for Cloud Integration requirement
        payload = ujson.dumps({"status": msg, "device": "PicoW", "ts": time.time()})
        client.publish(TOPIC_STATUS, payload)
        print(f"[MQTT] Sent: {payload}")
    except Exception as e:
        print("MQTT Publish Error:", e)

def mqtt_callback(topic, msg):
    """Handles incoming commands from Mobile App"""
    global current_state
    command = msg.decode().upper()
    print(f"[MQTT] Command: {command}")
    
    if command == "UNLOCK":
        print(">> DISARMING SYSTEM")
        current_state = 0
        control_servo("UNLOCK")
        buzzer.value(0)
        update_display("DISARMED", "Access Granted")
        send_status(client, "DISARMED")
        
    elif command == "LOCK" or command == "RESET":
        print(">> ARMING SYSTEM")
        current_state = 1
        control_servo("LOCK")
        buzzer.value(0)
        update_display("SYSTEM ARMED", "Monitoring...")
        send_status(client, "ARMED")

def connect_network():
    """Connects to Wi-Fi and MQTT Broker"""
    # 1. Wi-Fi Connection
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.ssid, config.pwd)
    
    print("Connecting to Wi-Fi...")
    retry = 0
    while not wlan.isconnected() and retry < 15:
        time.sleep(1)
        retry += 1
        print(".")
        
    if wlan.isconnected():
        print("Wi-Fi Connected:", wlan.ifconfig()[0])
        update_display("Wi-Fi OK", wlan.ifconfig()[0])
    else:
        update_display("Wi-Fi Failed", "Check Config")
        raise RuntimeError("Wi-Fi Connection Failed")

    # 2. MQTT Connection (SSL for Security Requirement)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_NONE
    
    client = MQTTClient(
        client_id=b"pico_guard_01",
        server=config.MQTT_BROKER,
        port=config.MQTT_PORT,
        user=config.MQTT_USER,
        password=config.MQTT_PWD,
        ssl=context,
        keepalive=60
    )
    client.set_callback(mqtt_callback)
    client.connect()
    client.subscribe(TOPIC_CONTROL)
    print("MQTT Connected")
    return client

# ==========================================
# 5. MAIN LOOP
# ==========================================

try:
    client = connect_network()
    
    # Set Initial State
    control_servo("LOCK")
    update_display("SYSTEM ARMED", "Monitoring...")
    send_status(client, "ARMED")
    
    while True:
        # 1. Check for remote commands (Non-blocking)
        client.check_msg()
        
        # 2. Sensor Logic (Only check if ARMED)
        if current_state == 1:
            if pir.value() == 1:
                print("!!! MOTION DETECTED !!!")
                current_state = 2 # Trigger Alert
                
                # Activate Outputs
                update_display("!! ALERT !!", "Intruder Detect")
                send_status(client, "INTRUDER_DETECTED")
                
        # 3. Alert Mode Logic (Cycle Buzzer)
        if current_state == 2:
            buzzer.value(1)
            time.sleep(0.1)
            buzzer.value(0)
            time.sleep(0.1)
        
        # 4. Prevent CPU overload
        time.sleep(0.1) 

except Exception as e:
    print("Critical System Error:", e)
    if lcd: update_display("System Error", "Restarting...")
    # machine.reset() # Optional: Auto-restart on crash