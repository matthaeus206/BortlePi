# main.py  (MicroPython)
#
# RP2350-Matrix + TSL25911 sky brightness -> Bortle 1..9
# Display: background color (Bortle palette) + centered white digit
#
# Hardware assumptions:
#   - WS2812 8x8 matrix data pin: GPIO25
#   - I2C bus: SDA=GPIO6, SCL=GPIO7 (same pins Waveshare uses in their example)
#   - TSL25911 I2C address: 0x29
#
# Notes:
#   - This is "SQM-like", not a factory-calibrated photometer.
#   - You WILL want to tune CAL_A and CAL_B after one or two reference nights.

import time, math
from machine import I2C, Pin
import neopixel

# ----------------------------
# User-tunable configuration
# ----------------------------

# Display brightness scaling (0.05..0.4 is sane at night)
BG_BRIGHT = 0.18
DIGIT_BRIGHT = 0.35

# Calibration (SQM-like):
#   sqm_est = CAL_A * log10(raw_brightness) + CAL_B
#
# Start values: reasonable-ish placeholders.
# You'll tune these using a known site / reference device / known SQM app reading.
CAL_A = -2.5
CAL_B = 21.5

# Smoothing (EMA): closer to 1.0 = slower changes, less flicker
EMA_ALPHA = 0.85

# How often to update (seconds)
UPDATE_PERIOD = 1.0

# ----------------------------
# RP2350-Matrix WS2812 config
# ----------------------------

W, H = 8, 8
NUM_LEDS = W * H
LED_PIN = 25
np = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), NUM_LEDS)

# Many matrices are wired serpentine. If your image is scrambled:
#   - flip SERPENTINE
#   - or flip X/Y
SERPENTINE = True
FLIP_X = False
FLIP_Y = False

def xy_to_i(x, y):
    if FLIP_X:
        x = (W - 1) - x
    if FLIP_Y:
        y = (H - 1) - y
    if SERPENTINE and (y % 2 == 1):
        x = (W - 1) - x
    return y * W + x

def scale(rgb, k):
    return (int(rgb[0] * k), int(rgb[1] * k), int(rgb[2] * k))

def fill(rgb, k=1.0):
    c = scale(rgb, k)
    for i in range(NUM_LEDS):
        np[i] = c
    np.write()

# Your linked Bortle palette:
# 1 black, 2 gray, 3 blue, 4 green, 5 yellow, 6 orange, 7 red, 8 pink, 9 white
# (dimmed via BG_BRIGHT)
BORTLE_BG = {
    1: (0,   0,   0),      # black
    2: (50,  50,  50),     # gray
    3: (0,   0,   255),    # blue
    4: (0,   255, 0),      # green
    5: (255, 255, 0),      # yellow
    6: (255, 140, 0),      # orange
    7: (255, 0,   0),      # red
    8: (255, 0,   180),    # pink/magenta
    9: (255, 255, 255),    # white
}

# 3x5 digit font
DIGITS_3x5 = {
    0: [0b111,0b101,0b101,0b101,0b111],
    1: [0b010,0b110,0b010,0b010,0b111],
    2: [0b111,0b001,0b111,0b100,0b111],
    3: [0b111,0b001,0b111,0b001,0b111],
    4: [0b101,0b101,0b111,0b001,0b001],
    5: [0b111,0b100,0b111,0b001,0b111],
    6: [0b111,0b100,0b111,0b101,0b111],
    7: [0b111,0b001,0b010,0b010,0b010],
    8: [0b111,0b101,0b111,0b101,0b111],
    9: [0b111,0b101,0b111,0b001,0b111],
}

def draw_digit_centered(d, rgb=(255, 255, 255), k=DIGIT_BRIGHT):
    d = int(d)
    glyph = DIGITS_3x5.get(d)
    if glyph is None:
        return
    fg = scale(rgb, k)
    # Center 3x5 in 8x8: x=2..4, y=1..5
    x0, y0 = 2, 1
    for r in range(5):
        bits = glyph[r]
        for c in range(3):
            if (bits >> (2 - c)) & 1:
                np[xy_to_i(x0 + c, y0 + r)] = fg

def show_bortle(b):
    b = int(max(1, min(9, b)))
    fill(BORTLE_BG[b], BG_BRIGHT)
    draw_digit_centered(b, (255, 255, 255), DIGIT_BRIGHT)
    np.write()

# ----------------------------
# TSL25911 (TSL2591-family) driver
# ----------------------------

class TSL25911:
    # Registers (TSL2591 family style)
    _ADDR = 0x29
    _CMD  = 0xA0  # command bit | auto-increment

    REG_ENABLE   = 0x00
    REG_CONTROL  = 0x01
    REG_CHAN0_L  = 0x14
    REG_CHAN1_L  = 0x16

    ENABLE_PON   = 0x01
    ENABLE_AEN   = 0x02

    # Gain values (AGAIN) and multipliers (approx standard TSL2591)
    GAIN_MAP = [
        (0x00, 1),
        (0x01, 25),
        (0x02, 428),
        (0x03, 9876),
    ]

    # Integration time (ATIME) options:
    # ATIME register value; integration time = (256 - ATIME) * 2.73ms
    ATIME_OPTIONS = [
        (0xFF, 2.73),
        (0xF6, 27.3),
        (0xD5, 100.0),
        (0xC0, 200.0),
        (0x00, 700.0),
    ]

    def __init__(self, i2c, address=_ADDR):
        self.i2c = i2c
        self.addr = address

        # start at moderate settings
        self.atime = 0xC0  # ~200ms
        self.gain_idx = 1  # 25x

        self._enable()
        self.set_timing_gain(self.atime, self.gain_idx)

    def _w8(self, reg, val):
        self.i2c.writeto_mem(self.addr, self._CMD | reg, bytes([val & 0xFF]))

    def _r8(self, reg):
        return self.i2c.readfrom_mem(self.addr, self._CMD | reg, 1)[0]

    def _r16(self, reg_l):
        b = self.i2c.readfrom_mem(self.addr, self._CMD | reg_l, 2)
        return b[0] | (b[1] << 8)

    def _enable(self):
        # Power on + ALS enable
        self._w8(self.REG_ENABLE, self.ENABLE_PON)
        time.sleep_ms(5)
        self._w8(self.REG_ENABLE, self.ENABLE_PON | self.ENABLE_AEN)
        time.sleep_ms(5)

    def set_timing_gain(self, atime, gain_idx):
        self.atime = atime
        self.gain_idx = max(0, min(3, gain_idx))
        gain_reg, _ = self.GAIN_MAP[self.gain_idx]
        # CONTROL: (AGAIN << 4) | ATIME (some variants use different packing;
        # this matches common TSL2591 drivers: CONTROL lower bits for ATIME, upper for gain)
        # Many boards accept CONTROL = (gain << 4) | atime
        self._w8(self.REG_CONTROL, ((gain_reg & 0x03) << 4) | (self.atime & 0xFF))
        # wait for integration to produce fresh data
        time.sleep_ms(int(self.integration_ms() + 10))

    def integration_ms(self):
        # compute from atime
        return (256 - self.atime) * 2.73

    def gain_mult(self):
        return self.GAIN_MAP[self.gain_idx][1]

    def read_channels(self):
        ch0 = self._r16(self.REG_CHAN0_L)
        ch1 = self._r16(self.REG_CHAN1_L)
        return ch0, ch1

    def auto_range_read(self, target_low=200, target_high=50000, max_iters=6):
        """
        Auto-adjust gain/integration to keep channel0 within a useful range.
        Returns (ch0, ch1, atime_ms, gain_mult)
        """
        for _ in range(max_iters):
            ch0, ch1 = self.read_channels()

            # Detect saturation-ish (16-bit max)
            if ch0 >= 65000 or ch1 >= 65000:
                # too bright -> reduce sensitivity
                if self.gain_idx > 0:
                    self.set_timing_gain(self.atime, self.gain_idx - 1)
                    continue
                # reduce integration if possible
                if self.atime != 0xFF:
                    # step to shorter integration (choose next shorter option)
                    self._step_integration(shorter=True)
                    continue
                return ch0, ch1, self.integration_ms(), self.gain_mult()

            # Too dim -> increase sensitivity
            if ch0 < target_low:
                if self.atime != 0x00:
                    self._step_integration(shorter=False)
                    continue
                if self.gain_idx < 3:
                    self.set_timing_gain(self.atime, self.gain_idx + 1)
                    continue
                return ch0, ch1, self.integration_ms(), self.gain_mult()

            # Too bright but not saturated -> decrease sensitivity
            if ch0 > target_high:
                if self.gain_idx > 0:
                    self.set_timing_gain(self.atime, self.gain_idx - 1)
                    continue
                if self.atime != 0xFF:
                    self._step_integration(shorter=True)
                    continue

            # In range
            return ch0, ch1, self.integration_ms(), self.gain_mult()

        # fallback
        ch0, ch1 = self.read_channels()
        return ch0, ch1, self.integration_ms(), self.gain_mult()

    def _step_integration(self, shorter):
        # Move to next integration preset
        opts = [v for v, _ in self.ATIME_OPTIONS]
        idx = opts.index(self.atime) if self.atime in opts else 3  # default to ~200ms slot
        if shorter:
            idx = max(0, idx - 1)
        else:
            idx = min(len(opts) - 1, idx + 1)
        self.set_timing_gain(opts[idx], self.gain_idx)

    def lux_like(self, ch0, ch1, atime_ms, gain_mult):
        """
        A lux-like scalar (good for log mapping), using a common TSL2591-style formula.
        We primarily need a monotonic brightness metric for calibration.
        """
        # Avoid division by zero / nonsense
        if ch0 <= 0:
            return 1e-6

        # "Counts per lux" factor (CPL) from common TSL2591 implementations
        LUX_DF = 408.0
        cpl = (atime_ms * gain_mult) / LUX_DF
        if cpl <= 0:
            return 1e-6

        # IR-corrected term (common approach)
        # lux = ( (ch0 - ch1) * (1 - (ch1 / ch0)) ) / cpl
        ir = ch1 / ch0
        lux = ((ch0 - ch1) * (1.0 - ir)) / cpl
        if lux <= 0:
            # still return something usable for log mapping
            return max((ch0 - ch1) / cpl, 1e-6)
        return lux

# ----------------------------
# Bortle classification
# ----------------------------

def classify_bortle_from_sqm(sqm):
    # Higher SQM = darker = lower Bortle number
    if sqm >= 21.76: return 1
    if sqm >= 21.60: return 2
    if sqm >= 21.30: return 3
    if sqm >= 20.80: return 4
    if sqm >= 20.30: return 5
    if sqm >= 19.25: return 6
    if sqm >= 18.50: return 7
    if sqm >= 18.00: return 8
    return 9

# ----------------------------
# Main: I2C init, sensor, loop
# ----------------------------

# I2C bus on GPIO6/7 (matches Waveshare example)
i2c = I2C(1, sda=Pin(6), scl=Pin(7), freq=100_000)

# Optional: uncomment once to verify the sensor is visible (should include 0x29)
# print([hex(a) for a in i2c.scan()])

sensor = TSL25911(i2c, address=0x29)

ema_sqm = None

while True:
    # 1) Read sensor with auto-ranging
    ch0, ch1, at_ms, gain = sensor.auto_range_read()

    # 2) Convert to a monotonic brightness metric
    raw = sensor.lux_like(ch0, ch1, at_ms, gain)
    raw = max(raw, 1e-6)

    # 3) SQM-like conversion (log)
    sqm = CAL_A * math.log10(raw) + CAL_B

    # 4) Smooth to reduce flicker
    if ema_sqm is None:
        ema_sqm = sqm
    else:
        ema_sqm = EMA_ALPHA * ema_sqm + (1.0 - EMA_ALPHA) * sqm

    # 5) Classify to Bortle 1..9
    bortle = classify_bortle_from_sqm(ema_sqm)

    # 6) Display: color background + centered white digit
    show_bortle(bortle)

    time.sleep(UPDATE_PERIOD)
