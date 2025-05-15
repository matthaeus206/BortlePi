import sys
import time
import board
import digitalio
import supervisor
import gc
import adafruit_veml7700
from collections import deque
from typing import Optional, Dict

# Function to log exceptions to a file and halt
def log_and_halt(exc: Exception):
    try:
        with open("/error_log.txt", "a") as log:
            log.write(f"\n\n--- Exception at {time.monotonic()} ---\n")
            sys.print_exception(exc, log)
    except Exception as write_err:
        sys.print_exception(write_err)
    # Halt further execution
    while True:
        pass

# Wrap all logic in try/except to catch uncaught exceptions
try:
    # Disable auto-reload for stability
    supervisor.disable_autoreload()

    # --- CONFIGURATION ---
    BORTLE_THRESHOLDS = [
        (0.01, 1), (0.08, 2), (0.3, 3),
        (1.0, 4), (4.0, 5), (10.0, 6),
        (30.0, 7), (100.0, 8),
    ]
    LED_PINS = {
        "green": board.GP2,
        "yellow": board.GP4,
        "red": board.GP3,
    }
    READ_RETRY_LIMIT = 5           # tries before re-init sensor
    SMOOTH_WINDOW_SIZE = 5         # samples for moving average
    LOOP_INTERVAL = 1.0            # seconds between updates

    # --- INITIALIZATION ---
    def init_sensor() -> Optional[adafruit_veml7700.VEML7700]:
        """Initialize VEML7700 on GP0/GP1; return None on failure."""
        import busio
        try:
            i2c = busio.I2C(scl=board.GP1, sda=board.GP0)
            while not i2c.try_lock():
                pass
            devices = i2c.scan()
            i2c.unlock()
            print("I2C devices found:", [hex(d) for d in devices])
            if 0x10 not in devices:
                print("! VEML7700 not found at 0x10!")
            sensor = adafruit_veml7700.VEML7700(i2c)
            print("✔ VEML7700 initialized")
            return sensor
        except Exception as e:
            print(f"! Sensor init failed: {e}")
            return None

    def init_leds() -> Dict[str, digitalio.DigitalInOut]:
        """Setup LEDs; return dict of color->DigitalInOut."""
        leds: Dict[str, digitalio.DigitalInOut] = {}
        for color, pin in LED_PINS.items():
            try:
                d = digitalio.DigitalInOut(pin)
                d.direction = digitalio.Direction.OUTPUT
                d.value = False
                leds[color] = d
            except Exception as e:
                print(f"! LED init error ({color}): {e}")
        return leds

    # --- BORTLE SCALE LOGIC ---
    def lux_to_bortle(lux: float) -> int:
        """Map lux to Bortle scale (1-9)."""
        for threshold, scale in BORTLE_THRESHOLDS:
            if lux < threshold:
                return scale
        return 9

    # --- SENSOR READING & LED UPDATE ---
    def read_lux(sensor: Optional[adafruit_veml7700.VEML7700],
                 retries: int = READ_RETRY_LIMIT) -> float:
        """Attempt sensor.lux with retries; return -1 on complete failure."""
        if sensor is None:
            return -1.0
        for attempt in range(1, retries + 1):
            try:
                return sensor.lux
            except Exception as e:
                print(f"  Read error #{attempt}: {e}")
                time.sleep(0.1)
        return -1.0

    def update_led_states(scale: int, leds: Dict[str, digitalio.DigitalInOut]) -> None:
        """Set LED outputs based on the current Bortle scale."""
        if "green" in leds:
            leds["green"].value = (scale <= 3)
        if "yellow" in leds:
            leds["yellow"].value = (4 <= scale <= 5)
        if "red" in leds:
            leds["red"].value = (scale >= 6)

    # --- MAIN LOOP ---
    def main():
        sensor = init_sensor()
        leds = init_leds()
        lux_history = deque(maxlen=SMOOTH_WINDOW_SIZE)
        next_time = time.monotonic()

        while True:
            lux = read_lux(sensor)
            if lux < 0:
                print("Lux: sensor unavailable -> reinitializing")
                sensor = init_sensor()
            else:
                lux_history.append(lux)
                avg_lux = sum(lux_history) / len(lux_history)
                print(f"Lux: {lux:.2f}  (avg {avg_lux:.2f})")
                scale = lux_to_bortle(avg_lux)
                print(f"Bortle scale: {scale}")
                update_led_states(scale, leds)

            print(f"Free RAM: {gc.mem_free()} bytes\n")

            # maintain consistent loop timing
            next_time += LOOP_INTERVAL
            sleep_duration = next_time - time.monotonic()
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            else:
                next_time = time.monotonic()

    # Entry point
    main()

except Exception as e:
    log_and_halt(e)
