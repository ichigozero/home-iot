import json
import machine
import sys
import time
import ubinascii

import wifimgr
from bme280 import BME280
from umqtt.simple import MQTTClient

import config

CLIENT_ID = ubinascii.hexlify(machine.unique_id())


def run():
    try:
        connect_wifi()
        msg = get_sensor_readings()
        publish(msg)
    except Exception as exc:
        sys.print_exception(exc)
        show_error()

    if not is_debug_mode():
        deepsleep()


def connect_wifi():
    wlan = wifimgr.get_connection()

    if wlan is None:
        print('Could not initialize the network connection')

        if is_debug_mode():
            while True:
                pass
        else:
            print('Rebooting...')
            machine.reset()


def get_sensor_readings():
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


def publish(msg):
    print('Publishing msg: {}'.format(msg))
    print('Publishing topic: {}'.format(config.MQTT_TOPIC))

    client = MQTTClient(
        client_id=CLIENT_ID,
        server=config.MQTT_SERVER
    )
    client.connect()
    client.publish(
        topic=config.MQTT_TOPIC.encode(),
        msg=msg.encode()
    )
    time.sleep(1)
    client.disconnect()


def show_error():
    led = machine.Pin(config.LED_PIN, machine.Pin.OUT)
    for _ in range(3):
        led.on()
        time.sleep(0.5)
        led.off()
        time.sleep(0.5)
        led.on()


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
