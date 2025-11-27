from machine import Pin
import tm1637 # for 4 digit 7-segment display(?)
import time
from utime import sleep

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
    elif val == 0:  # No motion detected
        if pir_state and (current_time - last_motion_time) > debounce_time:
            pir_state = False
            led.off() # turn off LED
            last_motion_time = current_time # Update the last motion time

    time.sleep(0.1)  # Small delay