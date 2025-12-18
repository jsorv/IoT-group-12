import network
import time
import socket
import ssl
import ujson  # Using JSON for structured data
from machine import Pin, PWM, I2C
from umqtt.simple import MQTTClient
from machine_i2c_lcd import I2cLcd
import config

# ==========================================
# 1. HARDWARE CONFIGURATION
# ==========================================

# --- Pins ---
# Adjust these to match your actual wiring!
PIR_PIN = 28        # PIR Motion Sensor Input
SERVO_PIN = 15      # Servo Motor Control (PWM)
BUZZER_PIN = 16     # Buzzer Output
LCD_SDA = 0         # I2C Data
LCD_SCL = 1         # I2C Clock
LED_PIN = "LED"     # Onboard LED

# --- Servo Configuration ---
# Duty cycle for SG90 servo (approximate)
SERVO_LOCKED = 1500   # Adjust for 0 degrees
SERVO_UNLOCKED = 8000 # Adjust for 180 degrees
pwm_servo = PWM(Pin(SERVO_PIN))
pwm_servo.freq(50)

# --- LCD Configuration ---
I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16
i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL), freq=400000)

try:
    lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)
except Exception as e:
    print("LCD Error (Check wiring):", e)
    lcd = None

# --- Sensors & Actuators ---
pir = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)
buzzer = Pin(BUZZER_PIN, Pin.OUT)
led = Pin(LED_PIN, Pin.OUT)

# ==========================================
# 2. MQTT CONFIGURATION
# ==========================================
TOPIC_STATUS = b"home/security/status"   # Publish: System State
TOPIC_CONTROL = b"home/security/control" # Subscribe: Remote Commands

# ==========================================
# 3. SYSTEM STATE MANAGEMENT
# ==========================================
# 0 = DISARMED (Door Unlocked, Monitoring OFF)
# 1 = ARMED    (Door Locked, Monitoring ON)
# 2 = ALERT    (Intrusion Detected, Alarm ON)
current_state = 1 

# ==========================================
# 4. HELPER FUNCTIONS
# ==========================================

def control_servo(position):
    """Controls the locking mechanism"""
    if position == "UNLOCK":
        pwm_servo.duty_u16(SERVO_UNLOCKED)
    else:
        pwm_servo.duty_u16(SERVO_LOCKED)
    time.sleep(0.5)
    # Stop PWM to prevent jitter
    pwm_servo.duty_u16(0)

def update_display(line1, line2=""):
    """Updates the LCD screen if available"""
    if lcd:
        lcd.clear()
        lcd.putstr(line1)
        if line2:
            lcd.move_to(0, 1)
            lcd.putstr(line2)

def send_status(mqtt_client, status_msg):
    """Sends JSON status to Cloud"""
    payload = ujson.dumps({"status": status_msg, "device": "PicoW"})
    mqtt_client.publish(TOPIC_STATUS, payload)
    print(f"[MQTT] Published: {payload}")

def mqtt_callback(topic, msg):
    """Handles commands from Mobile App"""
    global current_state
    
    command = msg.decode().upper()
    print(f"[MQTT] Command Received: {command}")
    
    if command == "UNLOCK":
        print(">>> DISARMING SYSTEM")
        current_state = 0
        control_servo("UNLOCK")
        buzzer.value(0) # Silence alarm
        led.off()
        update_display("DISARMED", "Access Granted")
        # Acknowledge to App
        send_status(client, "DISARMED")
        
    elif command == "LOCK" or command == "RESET":
        print(">>> ARMING SYSTEM")
        current_state = 1
        control_servo("LOCK")
        buzzer.value(0)
        led.off()
        update_display("SYSTEM ARMED", "Monitoring...")
        send_status(client, "ARMED")

def connect_network():
    """Connects to Wi-Fi and MQTT"""
    # 1. Wi-Fi
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.ssid, config.pwd)
    
    print("Connecting to Wi-Fi...")
    retry = 0
    while not wlan.isconnected() and retry < 10:
        time.sleep(1)
        retry += 1
        print(".")
        
    if not wlan.isconnected():
        update_display("WiFi Error", "Retrying...")
        time.sleep(2)
        # machine.reset() # Optional: Reset if no wifi
        
    print("Wi-Fi Connected:", wlan.ifconfig()[0])
    update_display("Wi-Fi Connected", wlan.ifconfig()[0])
    
    # 2. MQTT (HiveMQ SSL)
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
    print("MQTT Connected!")
    return client

# ==========================================
# 5. MAIN EXECUTION LOOP
# ==========================================

try:
    client = connect_network()
    
    # Initial State
    control_servo("LOCK")
    update_display("SYSTEM ARMED", "Monitoring...")
    send_status(client, "ARMED")
    
    while True:
        # 1. Check for incoming MQTT messages (Non-blocking)
        client.check_msg()
        
        # 2. Sensor Logic (Only if ARMED)
        if current_state == 1:
            if pir.value() == 1:
                print("!!! MOTION DETECTED !!!")
                current_state = 2 # Change to Alert Mode
                
                # Trigger Outputs
                update_display("!! ALERT !!", "INTRUDER")
                send_status(client, "INTRUDER_DETECTED")
                led.on()
                
        # 3. Alert Mode Logic (Buzzer Alarm)
        if current_state == 2:
            # Create an annoying alarm sound
            buzzer.value(1)
            time.sleep(0.1)
            buzzer.value(0)
            time.sleep(0.1)
        
        # 4. Keepalive delay
        time.sleep(0.1)

except Exception as e:
    print("System Error:", e)
    if lcd: update_display("System Error", "Check Console")
    # client.disconnect()