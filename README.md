# 🌌 BortlePi – Night Sky Brightness Meter

**BortlePi** is a compact, real-time Bortle scale reader built using an RP2040-Zero microcontroller and a VEML7700 ambient light sensor. It provides immediate visual feedback on sky brightness through LEDs, making it ideal for astronomers and stargazers.

---

## 🛠️ Features

- **Real-Time Lux Measurement**: Utilizes the VEML7700 sensor to measure ambient light levels accurately.
- **Bortle Scale Mapping**: Translates lux readings into Bortle scale values (1–9) using a configurable threshold system.
- **Visual Indicators**: Three LEDs (green, yellow, red) indicate the current Bortle scale range.
- **Robust Operation**: Includes sensor read retries and automatic reinitialization on failure.
- **Resource Monitoring**: Displays available RAM for performance insights.

---

## 📦 Hardware Requirements

- **Microcontroller**: RP2040-Zero
- **Ambient Light Sensor**: VEML7700 breakout board
- **LEDs**: 3mm or 5mm LEDs in green, yellow, and red
- **Resistors**: Appropriate current-limiting resistors for LEDs
- **Wiring**: Jumper wires and breadboard or PCB for connections

---

## 🔌 Pin Configuration

### RP2040-Zero to VEML7700 Connections

| Function    | VEML7700 Pin | RP2040-Zero Pin | Notes                                                    |
|-------------|---------------|------------------|-----------------------------------------------------------|
| Power       | 3V3           | 3V3              | Power for VEML7700 (3.3V regulated from RP2040-Zero)      |
| I2C SDA     | SDA           | GP0 (GPIO0)      | I2C data line                                             |
| I2C SCL     | SCL           | GP1 (GPIO1)      | I2C clock line                                            |
| Ground      | GND           | GND              | Common ground                                             |
| VIN         | —             | Not connected    | Not used – only needed for 5V input (not applicable here) |

> ⚠️ **Note**: Connect only the 3V3 pin to power the VEML7700. Do not connect the VIN pin to avoid potential damage.

### RP2040-Zero LED Connections

| LED Color | RP2040-Zero Pin | GPIO  | Bortle Scale Range |
|-----------|------------------|-------|---------------------|
| Green     | GP2              | GPIO2 | 1–3                 |
| Yellow    | GP4              | GPIO4 | 4–5                 |
| Red       | GP3              | GPIO3 | 6–9                 |

---

## 🧠 Software Overview

The main script performs the following operations:

1. **Initialization**: Sets up I2C communication and configures LED pins.
2. **Sensor Reading**: Continuously reads lux values from the VEML7700 sensor.
3. **Data Smoothing**: Applies a moving average to stabilize readings.
4. **Bortle Scale Calculation**: Maps the averaged lux value to the corresponding Bortle scale.
5. **LED Update**: Illuminates the appropriate LED based on the Bortle scale.
6. **Error Handling**: Attempts to reinitialize the sensor upon read failures.
7. **Resource Monitoring**: Prints available RAM to the console for debugging.

---

## 🚀 Getting Started

1. **CircuitPython Setup**: Install CircuitPython on your RP2040-Zero.
2. **Library Installation**: Add the `adafruit_veml7700` library to the `lib` directory on your device.
3. **Code Deployment**: Upload the main script to your RP2040-Zero as `code.py`.
4. **Power Up**: Connect the device to a power source via USB.
5. **Observation**: Monitor the serial output for lux and Bortle scale readings; observe LED indicators for visual feedback.

---

## 📈 Bortle Scale Thresholds

The mapping from lux values to Bortle scale levels is defined as follows:

```python
BORTLE_THRESHOLDS = [
    (0.01, 1), (0.08, 2), (0.3, 3),
    (1.0, 4), (4.0, 5), (10.0, 6),
    (30.0, 7), (100.0, 8),
]
```

Lux values exceeding 100 default to Bortle scale 9.

---

## 📝 Notes

- Ensure only the 3V3 pin is used to power the VEML7700 sensor to prevent damage.
- The moving average window size and loop interval can be adjusted in the configuration section of the script to fine-tune responsiveness.
