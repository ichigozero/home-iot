# About
ESP8266 temperature monitor with BME280 sensor.

This program will perform temperature readings for given time interval.
The readings will be sent to MQTT broker.

# Requirements
- MicroPython firmware v1.14 for ESP8266
- MQTT broker (e.g. mosquitto)

# Wiring
See below diagram for wiring reference.

![esp8266-wiring](/mcu/esp8266/diagram/esp8266_wiring.jpg)

# Installation

1. Edit `src/config.py` accordingly
2. Copy all files in `../common/src` and `src` directories to ESP8266
   root directory

# Usage

1. Slide the toggle switch to the left (see diagram) to enter debug mode
2. Find `EspWifiManager` access point and connect to it with `nodemcu8266`
   as password
3. Access `192.168.4.1` with a browser
4. Connect ESP8266 to your local access point
5. Slide the toggle switch to the right (see diagram) and push the reset button

# License

MIT