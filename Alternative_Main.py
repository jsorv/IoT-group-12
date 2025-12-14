import network
import time
import socket
import ssl
from machine import Pin, PWM, I2C
from umqtt.simple import MQTTClient
from machine_i2c_lcd import I2cLcd
import config

# ==========================================
# 1. HARDWARE CONFIGURATION
# ==========================================

# --- Pins ---
PIR_PIN = 28        # Motion Sensor (Input)
SERVO_PIN = 15      # Servo Motor (PWM)
BUZZER_PIN = 16     # Buzzer (Output)
LCD_SDA = 0         # LCD Data
LCD_SCL = 1         # LCD Clock
LED_PIN = "LED"     # Onboard LED

# --- Servo Settings ---
SERVO_MIN = 1000    # Approximate value for 0 degrees (Locked)
SERVO_MAX = 9000    # Approximate value for 180 degrees (Unlocked)
pwm_servo = PWM(Pin(SERVO_PIN))
pwm_servo.freq(50)

# --- LCD Settings ---
I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16
i2c = I2C(0, sda=Pin(LCD_SDA), scl=Pin(LCD_SCL), freq=400000)
try:
    lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)
except Exception as e:
    print("LCD not found:", e)
    lcd = None

# --- Other Sensors ---
pir = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)
buzzer = Pin(BUZZER_PIN, Pin.OUT)
led = Pin(LED_PIN, Pin.OUT)

# ==========================================
# 2. MQTT CONFIGURATION
# ==========================================
TOPIC_STATUS = b"home/security/status"   # Pico publishes here
TOPIC_CONTROL = b"home/security/control" # Pico subscribes here

# ==========================================
# 3. GLOBAL VARIABLES & STATE
# ==========================================
# States: 
# 0 = DISARMED (Safe, door unlocked)
# 1 = ARMED (Monitoring for motion, door locked)
# 2 = ALERT (Motion detected! Alarm sounding)
system_state = 1 

# ==========================================
# 4. FUNCTIONS
# ==========================================

def set_servo(position):
    """Moves servo to Locked (0) or Unlocked (1) position"""
    if position == 1:
        pwm_servo.duty_u16(SERVO_MAX) # Unlock
    else:
        pwm_servo.duty_u16(SERVO_MIN) # Lock
    time.sleep(0.5)

def update_lcd(line1, line2=""):
    """Helper to write text to LCD"""
    if lcd:
        lcd.clear()
        lcd.putstr(line1)
        if line2:
            lcd.move_to(0, 1)
            lcd.putstr(line2)

def mqtt_callback(topic, msg):
    """Handles incoming commands from Mobile App"""
    global system_state
    print(f"[MQTT] Received: {msg} on {topic}")
    
    command = msg.decode().upper()
    
    if command == "UNLOCK":
        print("Command: UNLOCK SYSTEM")
        system_state = 0 # Disarmed
        set_servo(1)     # Open lock
        buzzer.value(0)  # Silence alarm
        update_lcd("System Disarmed", "Welcome!")
        client.publish(TOPIC_STATUS, b"DISARMED")
        
    elif command == "RESET" or command == "LOCK":
        print("Command: RESET/ARM SYSTEM")
        system_state = 1 # Armed
        set_servo(0)     # Lock door
        buzzer.value(0)  # Silence alarm
        update_lcd("System Armed", "Monitoring...")
        client.publish(TOPIC_STATUS, b"ARMED")

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.ssid, config.pwd)
    
    print(f"Connecting to Wi-Fi '{config.ssid}'...")
    max_wait = 20
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print("waiting for connection...")
        time.sleep(1)
        
    if wlan.status() != 3:
        raise RuntimeError('Network connection failed')
    else:
        print('Wi-Fi Connected! IP:', wlan.ifconfig()[0])
        if lcd: 
            update_lcd("Wi-Fi Connected", wlan.ifconfig()[0])
            time.sleep(2)

def connect_mqtt():
    # SSL Context for HiveMQ
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_NONE
    
    client = MQTTClient(
        client_id=b"pico_security_system",
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
    print("MQTT Connected & Subscribed")
    return client

# ==========================================
# 5. MAIN LOOP
# ==========================================

try:
    # Initial Setup
    connect_wifi()
    client = connect_mqtt()
    
    # Default State: Armed
    set_servo(0) # Lock
    update_lcd("System Armed", "Monitoring...")
    client.publish(TOPIC_STATUS, b"ARMED")
    
    last_pir_check = 0
    
    while True:
        try:
            client.check_msg() # Check for MQTT commands
            
            # --- LOGIC: CHECK SENSOR ---
            if system_state == 1: # Only check motion if ARMED
                if pir.value() == 1:
                    print("MOTION DETECTED!")
                    system_state = 2 # Switch to ALERT mode
                    
                    # Output Control: Alarm
                    client.publish(TOPIC_STATUS, b"INTRUDER_ALERT")
                    update_lcd("!!! ALERT !!!", "Intruder Detect")
                    led.on()
            
            # --- LOGIC: ALERT STATE ---
            if system_state == 2:
                # Beep Buzzer
                buzzer.value(1)
                time.sleep(0.2)
                buzzer.value(0)
                time.sleep(0.2)
                
            # --- LOGIC: DISARMED STATE ---
            if system_state == 0:
                led.off()
                # Do nothing, just wait for "LOCK" command
            
            time.sleep(0.1) # Small delay to prevent CPU hogging
            
        except OSError as e:
            print("Error in loop:", e)
            # Optional: Reconnect logic could go here

except Exception as e:
    print("Critical Error:", e)
    if lcd: update_lcd("System Error", "Restarting...")
    # machine.reset() # Uncomment to auto-reset on crash