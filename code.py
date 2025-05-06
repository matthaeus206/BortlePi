import time
import board
import busio
import digitalio
import adafruit_veml7700
import supervisor
import gc

# Optional: Disable auto-reload for stability on some boards
supervisor.disable_autoreload()

# Constants
BORTLE_THRESHOLDS = [
    (0.01, 1), (0.08, 2), (0.3, 3),
    (1.0, 4), (4.0, 5), (10.0, 6),
    (30.0, 7), (100.0, 8)
]

LED_PINS = {
    "green": board.GP2,
    "yellow": board.GP4,
    "red": board.GP3,
}

def initialize_sensor():
    try:
        i2c = board.I2C()  # Automatically uses correct pins
        veml7700 = adafruit_veml7700.VEML7700(i2c)
        print("VEML7700 initialized.")
        return veml7700
    except Exception as e:
        print(f"Error initializing VEML7700: {e}")
        return None

def initialize_leds():
    leds = {}
    for color, pin in LED_PINS.items():
        try:
            led = digitalio.DigitalInOut(pin)
            led.direction = digitalio.Direction.OUTPUT
            leds[color] = led
        except Exception as e:
            print(f"Error initializing {color} LED on pin {pin}: {e}")
    return leds

def get_bortle_scale(lux):
    for threshold, scale in BORTLE_THRESHOLDS:
        if lux < threshold:
            return scale
    return 9  # Worst-case (brightest skies)

def update_leds(bortle_scale, leds):
    states = {
        "green": bortle_scale <= 3,
        "yellow": 4 <= bortle_scale <= 5,
        "red": bortle_scale >= 6,
    }
    for color, state in states.items():
        if color in leds:
            leds[color].value = state

def main():
    veml7700 = initialize_sensor()
    leds = initialize_leds()

    while True:
        try:
            if veml7700:
                try:
                    lux = veml7700.lux
                except Exception as e:
                    print(f"Sensor read error: {e}")
                    lux = -1
            else:
                lux = -1

            if lux >= 0:
                print(f"Lux: {lux:.2f}")
                bortle_scale = get_bortle_scale(lux)
            else:
                print("Lux: Sensor unavailable")
                bortle_scale = 9

            print(f"Bortle Scale: {bortle_scale}")
            update_leds(bortle_scale, leds)

            # Optional: Print free memory
            print(f"Free memory: {gc.mem_free()} bytes")

        except (OSError, RuntimeError, ValueError) as e:
            print(f"Main loop error: {e}")

        time.sleep(1)

if __name__ == "__main__":
    main()
