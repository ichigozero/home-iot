# About
Simple seismometer built with KXR94-2050 accelerometer.

This is an improved version of
[rpi-seismometer](https://www.p2pquake.net/dev/rpi_seismometer/how_to_make/).

# Wiring
See below diagram for wiring reference.

![seismometer-wiring](/rpi/kxr94-2050/diagram/seismometer.jpg)

# Installation

```bash
   $ python -m venv venv
   $ source venv/bin/activate
   $ pip3 install -r requirements
```

# Usage

1. Run `sudo pigpiod` to start pigpio daemon
2. Run `export GPIOZERO_PIN_FACTORY=pigpio`
3. Run either one of the following command:

## Printing out seismic scale to console only

```bash
$ python3 seismometer.py detect-earthquakes [OPTIONS]
```

### OPTIONS

```
   -h, --help                       Print this help text and exit
   -v, --verbose                    Print out seismic reading verbosely
   -i, --interval                   The time interval for printing out seismic
```

## Printing out and publish seismic scale to MQTT broker

```bash
$ python3 seismometer.py detect-publish-earthquakes [OPTIONS] BROKER TOPIC
```

Where,

- `BROKER` is the IP address or hostname for MQTT broker
- `TOPIC` is MQTT topics

### OPTIONS

```
   -h, --help                       Print this help text and exit
   -v, --verbose                    Print out seismic reading verbosely
   -i, --interval                   The time interval for publishing seismic
                                    reading to MQTT broker
```

# Acknowledgment
Credit to [p2pquake-takuya](https://github.com/p2pquake/rpi-seismometer)
for original seismometer specification and code.
