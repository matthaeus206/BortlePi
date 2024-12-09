import time
import board
import busio
import digitalio
import adafruit_veml7700

# Setup I2C for the VEML7700
try:
    i2c = busio.I2C(board.GP1, board.GP0)
    veml7700 = adafruit_veml7700.VEML7700(i2c)
except Exception as e:
    print(f"Error initializing I2C or VEML7700: {e}")
    veml7700 = None  # Continue without the sensor

# Setup LEDs with a dictionary for easier management
led_pins = {
    "green": board.GP2,
    "yellow": board.GP4,
    "red": board.GP3,
}

leds = {}
for color, pin in led_pins.items():
    try:
        led = digitalio.DigitalInOut(pin)
        led.direction = digitalio.Direction.OUTPUT
        leds[color] = led
    except Exception as e:
        print(f"Error initializing {color} LED on pin {pin}: {e}")

# Function to map lux value to Bortle scale
def get_bortle_scale(lux):
    thresholds = [
        (0.01, 1), (0.08, 2), (0.3, 3),
        (1.0, 4), (4.0, 5), (10.0, 6),
        (30.0, 7), (100.0, 8)
    ]
    for threshold, scale in thresholds:
        if lux < threshold:
            return scale
    return 9

# Function to update LEDs based on Bortle scale
def update_leds(bortle_scale):
    led_states = {
        "green": bortle_scale <= 3,
        "yellow": 4 <= bortle_scale <= 5,
        "red": bortle_scale >= 6,
    }
    for color, state in led_states.items():
        if color in leds:
            leds[color].value = state

while True:
    try:
        # Read ambient light level in lux
        if veml7700:
            lux = veml7700.lux
        else:
            lux = -1  # Fallback value when sensor is not initialized
        print(f"Lux: {lux:.2f}" if lux >= 0 else "Lux: Sensor unavailable")
        
        # Determine Bortle scale
        bortle_scale = get_bortle_scale(lux) if lux >= 0 else 9
        print(f"Bortle Scale: {bortle_scale}")
        
        # Update LEDs based on Bortle scale
        update_leds(bortle_scale)

    except Exception as e:
        # Log the error and continue
        print(f"Error during main loop: {e}")

    # Wait for a second before reading again
    time.sleep(1)
