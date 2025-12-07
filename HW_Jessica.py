from machine import Pin, PWM, ADC, SoftI2C
from machine_i2c_lcd import I2cLcd
from time import sleep, time

# Define the LCD I2C address and dimensions
I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16

#Line for the PIR motion detector
miniPir = Pin(7, Pin.IN)  

#Line for the buzzer warning
pwm = PWM(Pin(5)) #buzzer connected to A1
pwm.freq(10000)

# Initialize I2C and LCD objects
i2c = SoftI2C(sda=Pin(2), scl=Pin(3), freq=400000)

#Parameters for movement
pir_state =  False
last_motion_time = 0
debounce_time = 5


lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)

lcd.putstr("System Ready")
sleep(2)
lcd.clear()

try:
    while True:
        val = miniPir.value()
        current_time = time()
        
        
        if  miniPir.value() == 1 :
            
            if not pir_state or (current_time - last_motion_time) > debounce_time:
            
                # Clear the LCD
                lcd.clear()
                # Display two different messages on different lines
                # By default, it will start at (0,0) if the display is empty
                lcd.putstr("Motion Detected! Triggering Alert")
                pir_state = True
                last_motion_time = current_time
                pwm.duty_u16(10000)
                sleep(2)
                pwm.duty_u16(0)
                
                lcd.clear()
                # Starting at the second line (0, 1)
                lcd.putstr("Alert!")
                lcd.move_to(0, 1)
                lcd.putstr("Motion Detected")
                sleep(2)
                
        elif val == 0:
            
            if pir_state and (current_time - last_motion_time) > debounce_time:
                
                print("Motion cleared")
                pir_state = False
                
                lcd.clear()
                lcd.putstr("System Idle")
                
        sleep(0.1)
                

except KeyboardInterrupt:
    # Turn off the display
    print("Keyboard interrupt")
    lcd.backlight_off()
    lcd.display_off()