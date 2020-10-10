import json
import machine
import sys
import time
import ubinascii

import wifimgr
from bme280 import BME280
from soil_sensor import SoilSensor
from umqtt.simple import MQTTClient

import config

CLIENT_ID = ubinascii.hexlify(machine.unique_id())


def run():
    connect_wifi()
    publish([
        {
            'msg': get_temperature_sensor_readings(),
            'topic': config.MQTT_TOPIC_TEMP
        },
        {
            'msg': get_soil_sensor_readings(config.ADC_PIN_1),
            'topic': config.MQTT_TOPIC_SOIL_1
        },
        {
            'msg': get_soil_sensor_readings(config.ADC_PIN_2),
            'topic': config.MQTT_TOPIC_SOIL_2
        },
    ])

    if not is_debug_mode():
        deepsleep()


def connect_wifi():
    wlan = wifimgr.get_connection()

    if wlan is None:
        print('Could not initialize the network connection')

        if is_debug_mode():
            # Start web server for connection manager
            wifimgr.start()
        else:
            print('Reconnecting in 1 second...')
            time.sleep(1)
            connect_wifi()


def get_temperature_sensor_readings():
    i2c = machine.I2C(
        scl=machine.Pin(config.SCL_PIN),
        sda=machine.Pin(config.SDA_PIN)
    )
    bme280 = BME280(i2c=i2c)
    temperature, _, humidity = bme280.read_compensated_data()

    return json.dumps({
        'temperature': temperature,
        'humidity': humidity,
        'heat_index': bme280.heat_index,
        'dew_point': bme280.dew_point
    })


def get_soil_sensor_readings(adc_pin):
    sensor = SoilSensor(
        adc_pin=adc_pin,
        air_value=config.AIR_VALUE,
        water_value=config.WATER_VALUE
    )

    moisture_value, moisture_level, _ = sensor.read_data()

    return json.dumps({
        'moisture_value': moisture_value,
        'moisture_level': moisture_level,
    })


def publish(data):
    client = MQTTClient(
        client_id=CLIENT_ID,
        server=config.MQTT_SERVER
    )
    client.connect()

    for msg_topic in data:
        msg = msg_topic['msg']
        topic = msg_topic['topic']

        print('Publishing msg: {}'.format(msg))
        print('Publishing topic: {}'.format(topic))

        client.publish(
            topic=topic.encode(),
            msg=msg.encode()
        )
        time.sleep(1)

    client.disconnect()


def is_debug_mode():
    debug = machine.Pin(
        config.DEBUG_PIN,
        machine.Pin.IN,
        machine.Pin.PULL_UP
    )

    if debug.value() == 0:
        print('Debug mode detected')
        return True

    return False


def deepsleep():
    print(
        'Going into deepsleep for {} seconds...'
        .format(config.LOG_INTERVAL)
    )

    rtc = machine.RTC()
    rtc.irq(trigger=rtc.ALARM0, wake=machine.DEEPSLEEP)
    rtc.alarm(rtc.ALARM0, config.LOG_INTERVAL * 1000)

    machine.deepsleep()


run()
