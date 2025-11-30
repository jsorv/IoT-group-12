from machine import Pin
import tm1637 # for 4 digit 7-segment display(?)
import time
from utime import sleep
import network
import sys
import umqtt.robust import MQTTClient

# Intitalize PIR sensor on GPIO 0
pir = Pin(0, Pin.IN, Pin.PULL_DOWN)
led = Pin(2, Pin.OUT) # Initialize LED on GPIO 2
display = tm1637.TM1637(clk=Pin(5), dio=Pin(4)) # Initialize TM1637 display on GPIO 5 (CLK) and GPIO 4 (DIO)

pir_state = False # no motion detected at the start
last_motion_time = 0 # last motion time
debounce_time = 3  # 3 seconds debounce time
counter = 0 # motion event counter

display.number(counter) #screen reset

print("PIR Module Intialized")
time.sleep(1)  # Allow sensor to stabilize
print("Ready")

# initialise networking
#Change here the correct Wi-Fi settings
ssid = "change correct Wi-Fi name here" 
password = "Add your Wi-Fi password here"

# connect to wifi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

print(f"Connecting to Wi-Fi '{ssid}'...")

# This makes sure that the connection is created
max_retries = 10
retries = 0
#Waits for the connection to established
#Waits for maximun 20 seconds before continuing
while not wlan.isconnected() and retries < max_retries:
    print(f"Attempt {retries + 1}/{max_retries}...")
    time.sleep(2)
    retries += 1
    
#
if wlan.isconnected():
    print(f"Congratulations WiFi connected succesfully!")
else:
    print("Oh no!Failed to connect to the Wi-Fi!")
    sys.exit()

# Here we set up the MQTT-broker
#This is the Hive-MQ address
broker = "74c55c98d0f9464492456f0fd3b17079.s1.eu.hivemq.cloud"
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT) 
context.verify_mode = ssl.CERT_NONE
#Creating MQTT connection.Connection is using a testcredentials from HiveMQ.
client = MQTTClient(
        client_id=b'hello', 
        server=broker, 
        port=8883,
        user="iottestuser", 
        password="Abcd1234!", 
        ssl=context)
#Connect to client
client.connect()

# create the buzzer. Place the Pin to GP16
buzzer = Pin(16, Pin.OUT)

while True:
    val  = pir.value() # read PIR sensor value
    current_time = time.time()

    if val == 1:  # Motion detected
        if not pir_state or (current_time - last_motion_time) > debounce_time:
            print("Motion Detected!")
            counter += 1 # +1 when motion detected
            pir_state = True
            last_motion_time = current_time
            led.on()
            display.number(counter)  # Update display with new counter value
            last_motion_time = current_time
            #Sending the data to broker
            client.publish("iot/motion", "1")
            #The buzzer will give a soundmark every 0.2s
            buzzer.value(1)
            time.sleep(0.2)
            buzzer.value(0)
    elif val == 0:  # No motion detected
        if pir_state and (current_time - last_motion_time) > debounce_time:
            pir_state = False
            led.off() # turn off LED
            last_motion_time = current_time # Update the last motion time

    time.sleep(0.1)  # Small delay