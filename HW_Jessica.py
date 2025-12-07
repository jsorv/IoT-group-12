from machine import Pin, PWM, ADC, SoftI2C
from machine_i2c_lcd import I2cLcd
from time import sleep, time

# Define the LCD I2C address and dimensions
I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16

# Line for the PIR motion detector
miniPir = Pin(7, Pin.IN, Pin.PULL_DOWN)

# Initialize I2C and LCD objects
i2c = SoftI2C(sda=Pin(2), scl=Pin(3), freq=400000)

lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)

# Line for the buzzer warning, default OFF
pwm = PWM(Pin(5))  # buzzer connected to A1
pwm.freq(10000)
servo_val = 10000

# States
armed_mode = True       # waiting mode
alert_mode = False      # intrusion active

# Startup display
lcd.putstr("Security System Active")
sleep(2)
lcd.clear()
lcd.backlight_off()

try:
    while True:
        val = miniPir.value()
        sleep(0.05)  # reduce noise

        # ---------- FIRST HAND: ENTER ALERT MODE ----------
        if val == 1 and armed_mode:
            armed_mode = False
            alert_mode = True

            lcd.backlight_on()
            lcd.clear()
            lcd.putstr("ALERT")
            lcd.move_to(0, 1)
            lcd.putstr("Intruder")

            pwm.duty_u16(servo_val)
            sleep(2)
            pwm.duty_u16(0)

        # ---------- SECOND HAND: RESET SYSTEM ----------
        elif val == 1 and alert_mode:
            alert_mode = False
            armed_mode = True

            lcd.clear()
            lcd.putstr("System Reset")
            sleep(1)
            lcd.clear()
            lcd.backlight_off()

        sleep(0.1)

except KeyboardInterrupt:
    lcd.backlight_off()
    pwm.duty_u16(0)
               

except KeyboardInterrupt:
    # Turn off the display
    print("Keyboard interrupt")
    lcd.backlight_off()
    lcd.display_off()