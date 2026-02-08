"""
Sky Quality Meter for RP2040-Zero
Measures light pollution using VEML7700 sensor
"""
import time
import board
import digitalio
import busio
import microcontroller
import supervisor
import gc
from watchdog import WatchDogMode
import adafruit_veml7700
from collections import deque

# ========== CONFIGURATION ==========

# RP2040-Zero I2C pins
I2C_SDA = board.GP0
I2C_SCL = board.GP1

# LED indicators
LED_GREEN = board.GP2   # Bortle 1-3 (excellent)
LED_YELLOW = board.GP4  # Bortle 4-5 (moderate)
LED_RED = board.GP3     # Bortle 6-9 (poor)
HEARTBEAT_LED = board.GP25  # Onboard LED

# Bortle scale thresholds (lux -> scale)
BORTLE_SCALE = [
    (0.01, 1),   # Excellent dark sky
    (0.08, 2),
    (0.3, 3),
    (1.0, 4),
    (4.0, 5),
    (10.0, 6),
    (30.0, 7),
    (100.0, 8),
    (float('inf'), 9)  # Worst light pollution
]

# Timing & smoothing
LOOP_INTERVAL = 1.0      # seconds between readings
SMOOTH_WINDOW = 5        # rolling average window
EMA_ALPHA = 0.3          # exponential moving average weight

# Error handling
MAX_READ_RETRIES = 5
MAX_INIT_FAILURES = 10
WATCHDOG_TIMEOUT = 8.0


# ========== HARDWARE SETUP ==========

class Hardware:
    """Manages all hardware initialization"""
    
    def __init__(self):
        supervisor.disable_autoreload()
        
        # I2C bus (shared)
        self.i2c = busio.I2C(scl=I2C_SCL, sda=I2C_SDA)
        
        # Watchdog for auto-recovery
        microcontroller.watchdog.timeout = WATCHDOG_TIMEOUT
        microcontroller.watchdog.mode = WatchDogMode.RESET
        
        # LEDs
        self.leds = self._init_leds()
        self.heartbeat = self._init_heartbeat()
        
        # Sensor
        self.sensor = None
        self.init_sensor()
    
    def _init_leds(self):
        """Initialize RGB status LEDs"""
        leds = {}
        pins = {
            'green': LED_GREEN,
            'yellow': LED_YELLOW,
            'red': LED_RED
        }
        
        for color, pin in pins.items():
            try:
                led = digitalio.DigitalInOut(pin)
                led.direction = digitalio.Direction.OUTPUT
                led.value = False
                leds[color] = led
            except Exception as e:
                print(f"⚠ LED init failed ({color}): {e}")
        
        return leds
    
    def _init_heartbeat(self):
        """Initialize onboard LED for heartbeat"""
        try:
            led = digitalio.DigitalInOut(HEARTBEAT_LED)
            led.direction = digitalio.Direction.OUTPUT
            led.value = False
            return led
        except Exception as e:
            print(f"⚠ Heartbeat LED failed: {e}")
            return None
    
    def init_sensor(self):
        """Initialize VEML7700 light sensor"""
        try:
            self.sensor = adafruit_veml7700.VEML7700(self.i2c)
            
            # Configure for dark sky measurement (CircuitPython 9.x API)
            self.sensor.light_integration_time = 800  # ms
            self.sensor.light_gain = 2.0              # gain multiplier
            
            print("✓ VEML7700 sensor initialized")
            return True
            
        except Exception as e:
            print(f"✗ Sensor init failed: {e}")
            self.sensor = None
            return False
    
    def heartbeat_blink(self):
        """Quick heartbeat pulse"""
        if self.heartbeat:
            self.heartbeat.value = True
            time.sleep(0.02)
            self.heartbeat.value = False
    
    def set_leds(self, bortle_scale):
        """Update LED states based on Bortle scale"""
        self.leds.get('green', lambda: None).value = (bortle_scale <= 3)
        self.leds.get('yellow', lambda: None).value = (4 <= bortle_scale <= 5)
        self.leds.get('red', lambda: None).value = (bortle_scale >= 6)


# ========== SENSOR READING ==========

class LuxReader:
    """Handles sensor reading with retries and smoothing"""
    
    def __init__(self, hardware):
        self.hw = hardware
        self.history = deque(maxlen=SMOOTH_WINDOW)
        self.ema = None
        self.failed_reads = 0
    
    def read(self):
        """Read lux value with retry logic"""
        if self.hw.sensor is None:
            return None
        
        for attempt in range(1, MAX_READ_RETRIES + 1):
            try:
                lux = self.hw.sensor.lux
                self.failed_reads = 0
                return lux
                
            except Exception as e:
                if attempt == MAX_READ_RETRIES:
                    print(f"✗ Read failed after {attempt} attempts: {e}")
                    self.failed_reads += 1
                else:
                    time.sleep(0.05 * attempt)  # Progressive backoff
        
        return None
    
    def smooth(self, lux):
        """Apply smoothing to reduce noise"""
        if lux is None:
            return None
        
        # Update EMA
        if self.ema is None:
            self.ema = lux
        else:
            self.ema = EMA_ALPHA * lux + (1 - EMA_ALPHA) * self.ema
        
        # Update rolling average
        self.history.append(lux)
        rolling_avg = sum(self.history) / len(self.history)
        
        return self.ema, rolling_avg


# ========== BORTLE SCALE CALCULATION ==========

def calculate_bortle_scale(lux):
    """Convert lux reading to Bortle scale (1-9)"""
    if lux is None or lux < 0:
        return None
    
    for threshold, scale in BORTLE_SCALE:
        if lux < threshold:
            return scale
    
    return 9


# ========== MAIN LOOP ==========

def main():
    print("\n" + "="*40)
    print("Sky Quality Meter - RP2040-Zero")
    print("="*40 + "\n")
    
    # Initialize hardware
    hw = Hardware()
    reader = LuxReader(hw)
    
    # Timing
    next_loop = time.monotonic()
    init_failures = 0
    
    # Main loop
    while True:
        try:
            # Read sensor
            lux = reader.read()
            
            if lux is None:
                # Sensor failed - try reinit
                init_failures += 1
                print(f"⟳ Reinitializing sensor (attempt {init_failures}/{MAX_INIT_FAILURES})...")
                
                if init_failures >= MAX_INIT_FAILURES:
                    print("✗ Sensor permanently failed - entering safe mode")
                    hw.set_leds(9)  # All red
                    while True:
                        hw.heartbeat_blink()
                        time.sleep(1)
                
                hw.init_sensor()
                time.sleep(0.5)
                continue
            
            # Reset failure counter on successful read
            init_failures = 0
            
            # Apply smoothing
            ema, rolling_avg = reader.smooth(lux)
            
            # Calculate Bortle scale
            bortle = calculate_bortle_scale(ema)
            
            # Update LEDs
            hw.set_leds(bortle)
            
            # Display readings
            print(f"Lux: {lux:.3f} | Avg: {rolling_avg:.3f} | EMA: {ema:.3f} | Bortle: {bortle}")
            print(f"RAM: {gc.mem_free()} bytes\n")
            
            # Heartbeat pulse
            hw.heartbeat_blink()
            
            # Sleep until next reading (precise timing)
            next_loop += LOOP_INTERVAL
            sleep_time = next_loop - time.monotonic()
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # We're running behind - reset timing
                next_loop = time.monotonic()
            
            # Feed watchdog at end of successful loop
            microcontroller.watchdog.feed()
            
        except Exception as e:
            print(f"✗ Loop error: {e}")
            # Don't feed watchdog - let it reset if error persists
            time.sleep(1)


# ========== ENTRY POINT ==========

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Critical error - log and halt
        print(f"\n{'='*40}")
        print(f"CRITICAL ERROR: {e}")
        print(f"{'='*40}\n")
        
        try:
            with open("/error_log.txt", "a") as log:
                log.write(f"\n--- Error at {time.monotonic()}s ---\n")
                log.write(f"{e}\n")
        except:
            pass
        
        # Halt with all LEDs on
        while True:
            time.sleep(1)
