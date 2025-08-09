import sys, time, board, digitalio, supervisor, gc, traceback
import busio, microcontroller
from watchdog import WatchDogMode
import adafruit_veml7700
from collections import deque
from typing import Optional, Dict

# ---- Board-specific: RP2040-Zero ----
SDA_PIN = board.GP0
SCL_PIN = board.GP1
HEARTBEAT_PIN = board.GP25  # onboard LED (optional)

# ---- Config ----
BORTLE_THRESHOLDS = [
    (0.01, 1), (0.08, 2), (0.3, 3),
    (1.0, 4), (4.0, 5), (10.0, 6),
    (30.0, 7), (100.0, 8),
]
LED_PINS = {"green": board.GP2, "yellow": board.GP4, "red": board.GP3}
READ_RETRY_LIMIT = 5
SMOOTH_WINDOW_SIZE = 5
LOOP_INTERVAL = 1.0

def log_and_halt(exc: Exception):
    try:
        with open("/error_log.txt", "a") as log:
            log.write(f"\n\n--- Exception at {time.monotonic()} ---\n")
            traceback.print_exception(exc, file=log)
    except Exception as write_err:
        traceback.print_exception(write_err)
    while True:
        pass

try:
    supervisor.disable_autoreload()

    # One shared I2C bus
    I2C = busio.I2C(scl=SCL_PIN, sda=SDA_PIN)

    # Optional: watchdog auto-reset on hangs
    microcontroller.watchdog.timeout = 8.0
    microcontroller.watchdog.mode = WatchDogMode.RESET

    # Optional: heartbeat LED
    hb = digitalio.DigitalInOut(HEARTBEAT_PIN)
    hb.direction = digitalio.Direction.OUTPUT
    hb.value = False

    def init_sensor() -> Optional[adafruit_veml7700.VEML7700]:
        try:
            while not I2C.try_lock():
                time.sleep(0.01)
            devices = I2C.scan()
            I2C.unlock()
            print("I2C devices:", [hex(d) for d in devices])
            if 0x10 not in devices:
                print("! VEML7700 not found at 0x10")
                return None
            s = adafruit_veml7700.VEML7700(I2C)

            # Dark-sky tuning (handle naming differences across lib versions)
            try:
                if hasattr(s, "light_integration_time"):
                    s.light_integration_time = s.ALS_800MS
                elif hasattr(adafruit_veml7700, "INTEGRATION_800MS"):
                    s.integration_time = adafruit_veml7700.INTEGRATION_800MS
                if hasattr(s, "light_gain"):
                    s.light_gain = s.ALS_GAIN_2
                elif hasattr(adafruit_veml7700, "GAIN_2"):
                    s.gain = adafruit_veml7700.GAIN_2
            except Exception:
                pass

            print("✔ VEML7700 initialized")
            return s
        except Exception as e:
            print(f"! Sensor init failed: {e}")
            return None

    def init_leds() -> Dict[str, digitalio.DigitalInOut]:
        leds = {}
        for color, pin in LED_PINS.items():
            try:
                d = digitalio.DigitalInOut(pin)
                d.direction = digitalio.Direction.OUTPUT
                d.value = False
                leds[color] = d
            except Exception as e:
                print(f"! LED init error ({color}): {e}")
        return leds

    def lux_to_bortle(lux: float) -> int:
        for threshold, scale in BORTLE_THRESHOLDS:
            if lux < threshold:
                return scale
        return 9

    def read_lux(sensor: Optional[adafruit_veml7700.VEML7700],
                 retries: int = READ_RETRY_LIMIT) -> float:
        if sensor is None:
            return -1.0
        for attempt in range(1, retries + 1):
            try:
                return sensor.lux
            except Exception as e:
                print(f"  Read error #{attempt}: {e}")
                time.sleep(0.1 * attempt)  # simple backoff
        return -1.0

    def update_led_states(scale: int, leds: Dict[str, digitalio.DigitalInOut]) -> None:
        if "green" in leds:
            leds["green"].value = (scale <= 3)
        if "yellow" in leds:
            leds["yellow"].value = (4 <= scale <= 5)
        if "red" in leds:
            leds["red"].value = (scale >= 6)

    def main():
        sensor = init_sensor()
        leds = init_leds()
        lux_history = deque(maxlen=SMOOTH_WINDOW_SIZE)
        next_time = time.monotonic()
        ema = None
        alpha = 0.3

        while True:
            microcontroller.watchdog.feed()

            lux = read_lux(sensor)
            if lux < 0:
                print("Lux: sensor unavailable -> reinitializing")
                sensor = init_sensor()
            else:
                ema = lux if ema is None else (alpha * lux + (1 - alpha) * ema)
                lux_history.append(lux)
                avg_lux = sum(lux_history) / len(lux_history)
                smoothed = ema
                print(f"Lux: {lux:.3f} (avg {avg_lux:.3f}, ema {smoothed:.3f})")
                scale = lux_to_bortle(smoothed)
                print(f"Bortle scale: {scale}")
                update_led_states(scale, leds)

            # Heartbeat blink (brief)
            hb.value = True
            time.sleep(0.02)
            hb.value = False

            print(f"Free RAM: {gc.mem_free()} bytes\n")
            next_time += LOOP_INTERVAL
            sleep_duration = next_time - time.monotonic()
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            else:
                next_time = time.monotonic()

    main()

except Exception as e:
    log_and_halt(e)
