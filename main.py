import network
import uasyncio as asyncio
from machine import Pin, PWM, I2C
import config
from umqtt.simple import MQTTClient

# Import your LCD and TM1637 libraries here

# --- GLOBAL VARIABLES ---
visitor_count = 0
system_armed = True

# --- HARDWARE SETUP ---
# Define your pins here (Servo, LEDs, PIR, Buzzer)
pir_sensor = Pin(0, Pin.IN, Pin.PULL_DOWN)
servo = PWM(Pin(15))
servo.freq(50)


# --- MQTT SETUP ---
def mqtt_connect():
    client = MQTTClient("pico_client", config.MQTT_BROKER, user=config.MQTT_USER, password=config.MQTT_PWD,
                        port=config.MQTT_PORT, ssl=True)
    client.set_callback(mqtt_callback)
    client.connect()
    print("Connected to MQTT")
    return client


def mqtt_callback(topic, msg):
    global system_armed, visitor_count
    message = msg.decode()
    print(f"Received: {message}")

    # Remote Control Logic
    if message == "RESET":
        visitor_count = 0
    elif message == "ARM":
        system_armed = True
    elif message == "DISARM":
        system_armed = False


# --- ASYNC TASKS ---

# Task 1: Sensor Loop (Runs continuously)
async def sensor_loop(client):
    global visitor_count
    while True:
        if pir_sensor.value() == 1:
            print("Motion Detected!")

            # Logic: Update Count
            visitor_count += 1

            # Logic: Send MQTT Update
            try:
                client.publish("iot/motion", str(visitor_count))
            except:
                print("MQTT Publish Failed")

            # Logic: Trigger Alarm if Armed
            if system_armed:
                # Add your buzzer/servo code here
                pass

            # Debounce (Wait 3 seconds before next read)
            await asyncio.sleep(3)

            # Small delay to let other tasks run
        await asyncio.sleep(0.1)


# Task 2: MQTT Listener (Checks for incoming messages)
async def mqtt_listener(client):
    while True:
        try:
            client.check_msg()
        except:
            pass
        await asyncio.sleep(0.2)


# Task 3: Web Server (Simple Async Implementation)
async def web_server():
    import socket
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    s.setblocking(False)  # CRITICAL: Make socket non-blocking

    while True:
        try:
            # Try to accept a connection
            cl, addr = s.accept()
            print('Client connected from', addr)
            request = cl.recv(1024)
            # Send HTML response (use your generate_html function)
            cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n<h1>IoT System Online</h1>')
            cl.close()
        except OSError:
            # No client connected, just continue
            pass
        await asyncio.sleep(0.1)


# --- MAIN EXECUTION ---
async def main():
    # Connect to WiFi first (use your existing code)
    # ...

    # Connect MQTT
    client = mqtt_connect()
    client.subscribe("iot/control")

    # Schedule all tasks to run together
    asyncio.create_task(sensor_loop(client))
    asyncio.create_task(mqtt_listener(client))
    asyncio.create_task(web_server())

    # Keep the main loop running
    while True:
        await asyncio.sleep(1)


# Start the Async System
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("System Stopped")