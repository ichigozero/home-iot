# About
ESP32 decorative plant monitor with BME280 sensor and capacitive
soil sensor module.

This program will perform temperature and soil moisture readings for given
time interval. The readings will be sent to MQTT broker.

# Requirements
- MicroPython firmware v1.14 for ESP32
- MQTT broker (e.g. mosquitto)

# Wiring
See below diagram for wiring reference.

![esp32-wiring](/mcu/esp32/diagram/esp32_wiring.jpg)

# Installation

1. Edit `src/config.py` accordingly
2. Copy all files in `../common/src` and `src` directories to ESP32
   root directory

# Usage

1. Slide the toggle switch to upward (see diagram) to enter debug mode
2. Find `EspWifiManager` access point and connect to it with `nodemcu8266`
   as password
3. Access `192.168.4.1` with a browser
4. Connect ESP8266 to your local access point
5. Slide the toggle switch to the downward (see diagram) and push
   the reset button

# License

MIT