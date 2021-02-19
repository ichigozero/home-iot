# About
Tool to collect data sent by IoT devices to MQTT broker and save them
to InfluxDB. The data saved can be viewed later with analytic tools
such as Grafana.

# Requirements
This program is tested with the following applications:

- InfluxDB 1.8.3

# Installation

  ```bash
     $ python3 -m venv venv
     $ source venv/bin/activate
     $ pip3 install -r requirements.txt
  ```
# Prerequisites

Export the following environment variables.
Adjust the setting according to your environment setups.

```bash
   export $INFLUXDB_HOST=localhost
   export $INFLUXDB_PORT=8086
   export $INFLUXDB_USER=root
   export $INFLUXDB_PASSWORD=root
   export $INFLUXDB_DBNAME=sensor
```

# Collecting Data

Execute one of the commands below to collect readings from IoT devices.

Where,

- `BROKER` is the IP address or hostname for MQTT broker
- `TOPIC` is MQTT topics

## Thermometer

```bash
   $ python3 mqtt_receiver.py thermometer [OPTIONS] BROKER TOPIC
```

### OPTIONS

```
   -h, --help                       Print this help text and exit
   -v, --verbose                    Print out sensor reading verbosely
```

## Seismometer

```bash
   $ python3 mqtt_receiver.py seismometer [OPTIONS] BROKER TOPIC
```

### OPTIONS

```
   -h, --help                       Print this help text and exit
   -v, --verbose                    Print out sensor reading verbosely
   -a, --all-output                 Collect acceleration readings along with
                                    seismic scale
   -m, --min-scale                  Collect readings if current seismic scale
                                    above certain threshold
```

## Soil moisture sensor

```bash
   $ python3 mqtt_receiver.py soil-sensor [OPTIONS] BROKER TOPIC
```

### OPTIONS

```
   -h, --help                       Print this help text and exit
   -v, --verbose                    Print out sensor reading verbosely
```

# License

MIT