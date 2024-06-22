import time
import board
import busio
import digitalio
import adafruit_veml7700

# Setup I2C for the VEML7700
i2c = busio.I2C(board.GP1, board.GP0)
veml7700 = adafruit_veml7700.VEML7700(i2c)

# Setup LEDs
led_green = digitalio.DigitalInOut(board.GP2)
led_green.direction = digitalio.Direction.OUTPUT
led_red = digitalio.DigitalInOut(board.GP3)
led_red.direction = digitalio.Direction.OUTPUT
led_yellow = digitalio.DigitalInOut(board.GP4)
led_yellow.direction = digitalio.Direction.OUTPUT

# Function to map lux value to Bortle scale
def get_bortle_scale(lux):
    if lux < 0.01:
        return 1
    elif lux < 0.08:
        return 2
    elif lux < 0.3:
        return 3
    elif lux < 1.0:
        return 4
    elif lux < 4.0:
        return 5
    elif lux < 10:
        return 6
    elif lux < 30:
        return 7
    elif lux < 100:
        return 8
    else:
        return 9

while True:
    # Read ambient light level in lux
    lux = veml7700.lux
    print("Lux:", lux)
    
    # Determine Bortle scale
    bortle_scale = get_bortle_scale(lux)
    print("Bortle Scale:", bortle_scale)
    
    # Light up LEDs based on Bortle scale
    if bortle_scale <= 3:
        led_green.value = True
        led_yellow.value = False
        led_red.value = False
    elif 4 <= bortle_scale <= 5:
        led_green.value = False
        led_yellow.value = True
        led_red.value = False
    else:
        led_green.value = False
        led_yellow.value = False
        led_red.value = True
    
    # Wait for a second before reading again
    time.sleep(1)
