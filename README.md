BortlePi: Bortle Scale Light Pollution Detector

This project uses a Waveshare RP2040-Zero microcontroller and a VEML7700 ambient light sensor to detect the Bortle scale of the night sky's brightness. The device indicates the level of light pollution using three LEDs (green, yellow, and red).
Components

    Waveshare RP2040-Zero
    VEML7700 Ambient Light Sensor
    Green LED
    Yellow LED
    Red LED
    Resistors (220 ohm recommended)
    Breadboard and jumper wires

Circuit Diagram
Connections
VEML7700 Sensor

    SDA (VEML7700) -> GP0 (RP2040-Zero)
    SCL (VEML7700) -> GP1 (RP2040-Zero)
    VCC (VEML7700) -> 3.3V (RP2040-Zero)
    GND (VEML7700) -> GND (RP2040-Zero)

LEDs

    Green LED -> GP2 (RP2040-Zero) with a 220 ohm resistor in series
    Yellow LED -> GP4 (RP2040-Zero) with a 220 ohm resistor in series
    Red LED -> GP3 (RP2040-Zero) with a 220 ohm resistor in series

Software
Required Libraries

You need the following libraries from the Adafruit CircuitPython Bundle:

    adafruit_veml7700.mpy
    adafruit_bus_device

Place these libraries in the lib folder on the CIRCUITPY drive of the RP2040-Zero.
Code

Save the provided code as code.py on the CIRCUITPY drive.
How It Works

    Initialization:
        Sets up I2C communication with the VEML7700 sensor.
        Initializes digital pins for the LEDs.

    Bortle Scale Mapping:
        The get_bortle_scale() function maps the ambient light level in lux to the Bortle scale.

    Main Loop:
        Continuously reads the ambient light level.
        Determines the Bortle scale based on the lux value.
        Lights up the appropriate LED based on the Bortle scale value:
            Green LED for Bortle scale 1-3 (dark skies)
            Yellow LED for Bortle scale 4-5 (moderate light pollution)
            Red LED for Bortle scale 6-9 (high light pollution)
        Pauses for a second before taking the next reading.

License

This project is open source and available under the MIT License. See the LICENSE file for more information.
Contributing

Contributions are welcome! Please open an issue or submit a pull request for any changes or improvements.
Acknowledgments

Thanks to Adafruit for providing the libraries and documentation for the VEML7700 and CircuitPython.
