# Copyright (c) 2020 Gary Sentosa (ichigozero)
# Copyright (c) 2017 takuya (P2PQuake)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import atexit
import collections
import datetime
import json
import logging
import math
import sys
import threading
import time
import uuid

import click
import paho.mqtt.client as mqtt
from gpiozero import Buzzer
from gpiozero import LED
from gpiozero import LEDBoard
from gpiozero import MCP3204

ADC_RESOLUTION = 4095  # 12-bit
REFERENCE_VOLTAGE = 3300  # mV
VOLTAGE_PER_G = REFERENCE_VOLTAGE / 5  # mV
OFFSET_VOLTAGE = REFERENCE_VOLTAGE / 2  # mV
GAL = 980.665  # cm/s^2

TARGET_FPS = 200
ACCEL_FRAME = int(TARGET_FPS * 0.3)
LOOP_DELTA = 1./TARGET_FPS
MAX_32_BIT_INT = 2147483647

SCALE_LED_CHARSETS = {
    '0': (0, 0, 0, 0, 0, 0, 0, 0),
    '1': (0, 1, 1, 0, 0, 0, 0, 0),
    '2': (1, 1, 0, 1, 1, 0, 1, 0),
    '3': (1, 1, 1, 1, 0, 0, 1, 0),
    '4': (0, 1, 1, 0, 0, 1, 1, 0),
    '5L': (1, 0, 1, 1, 0, 1, 1, 0),
    '5H': (1, 0, 1, 1, 0, 1, 1, 1),
    '6L': (1, 0, 1, 1, 1, 1, 1, 0),
    '6H': (1, 0, 1, 1, 1, 1, 1, 1),
    '7': (1, 1, 1, 0, 0, 0, 0, 0),
}

lock = threading.Lock()


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with lock:
                if cls not in cls._instances:
                    cls._instances[cls] = (
                        super(Singleton, cls)
                        .__call__(*args, **kwargs)
                    )

        return cls._instances[cls]


class Seismometer(metaclass=Singleton):
    def __init__(self, callback=None, callback_interval=0.1):
        self._adc = [
            MCP3204(channel=0),
            MCP3204(channel=1),
            MCP3204(channel=2)
        ]
        self._task_thread = None
        self._task_running = False
        self.ready = False
        self.frame = 0
        self.xyz_accel = [0, 0, 0]
        self.seismic_scale = 0

    def start_calculation(self, callback=None, callback_interval=0.1):
        self._task_thread = threading.Thread(
            target=self._calculate_seismic_scale,
            daemon=True,
            args=(callback, callback_interval)
        )
        self._task_running = True
        self._task_thread.start()

    def stop_calculation(self):
        self._task_running = False
        self._task_thread.join()
        self._task_thread = None

        self.frame = 0
        self.xyz_accel = [0, 0, 0]
        self.seismic_scale = 0

    def get_user_friendly_formatted_seismic_scale(self):
        if self.seismic_scale < 4.5:
            output_scale = str(round(max(0, self.seismic_scale)))
        elif 4.5 <= self.seismic_scale < 5:
            output_scale = '5L'
        elif 5 <= self.seismic_scale < 5.5:
            output_scale = '5H'
        elif 5.5 <= self.seismic_scale < 6:
            output_scale = '6L'
        elif 6 <= self.seismic_scale < 6.5:
            output_scale = '6H'
        else:
            output_scale = '7'

        return output_scale

    def _calculate_seismic_scale(self, callback, callback_interval):
        xyz_raw_g = [
            collections.deque(maxlen=TARGET_FPS),
            collections.deque(maxlen=TARGET_FPS),
            collections.deque(maxlen=TARGET_FPS)
        ]
        xyz_filtered_g = [0, 0, 0]

        accel_values = collections.deque(maxlen=TARGET_FPS * 5)
        scale_reached_non_zero = False

        target_time = time.time()

        while self._task_running:
            for i in range(3):
                g_value = self._to_gforce(self._adc[i].raw_value)
                xyz_raw_g[i].append(g_value)

                offset = sum(xyz_raw_g[i]) / len(xyz_raw_g[i])
                xyz_filtered_g[i] = xyz_filtered_g[i] * 0.94 + g_value * 0.06
                self.xyz_accel[i] = (xyz_filtered_g[i] - offset) * GAL

            accel_values.append(
                self._calculate_composite_acceleration(self.xyz_accel))

            try:
                continous_accel = sorted(accel_values)[-ACCEL_FRAME]

                if continous_accel > 0:
                    self.seismic_scale = 2 * math.log10(continous_accel) + 0.94
                else:
                    self.seismic_scale = 0
            except IndexError:
                pass

            if self.frame % int(TARGET_FPS * callback_interval) == 0:
                callback(self)

            target_time += LOOP_DELTA
            sleep_time = target_time - time.time()

            if sleep_time > 0:
                time.sleep(sleep_time)

            self.frame += 1

            if self.frame >= MAX_32_BIT_INT:
                self.frame = MAX_32_BIT_INT % TARGET_FPS

            if not self.ready:
                if self.seismic_scale > 0:
                    scale_reached_non_zero = True
                else:
                    if scale_reached_non_zero:
                        self.ready = True


    @classmethod
    def _to_gforce(cls, adc_value):
        analog_voltage = (adc_value / ADC_RESOLUTION) * REFERENCE_VOLTAGE
        analog_voltage -= OFFSET_VOLTAGE

        return analog_voltage / VOLTAGE_PER_G

    @classmethod
    def _calculate_composite_acceleration(cls, xyz_accel):
        return math.sqrt(
            (xyz_accel[0] ** 2)
            + (xyz_accel[1] ** 2)
            + (xyz_accel[2] ** 2)
        )


@click.group()
def cmd():
    pass


@cmd.command()
@click.option('--interval', '-i', default=0.1)
@click.option('--verbose', '-v', is_flag=True)
def detect_earthquakes(interval, verbose):
    if interval < 0.1:
        raise ValueError('Interval value should be at least 0.1 seconds')

    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    buzzer = Buzzer(3)
    status_led = LED(26)
    scale_led = LEDBoard(a=18, b=23, c=12, d=19, e=6, f=22, g=17, xdp=16)

    def _callback(self):
        logging.debug(
            '%s scale: %.4f frame: %d',
            datetime.datetime.now(),
            self.seismic_scale,
            self.frame
        )

    seismometer = Seismometer()
    seismometer.start_calculation(
        callback=_callback,
        callback_interval=interval
    )

    while True:
        seismic_scale = seismometer.seismic_scale
        scale_led.value = SCALE_LED_CHARSETS[
            seismometer.get_user_friendly_formatted_seismic_scale()]

        if seismometer.ready:
            if not status_led.is_lit:
                status_led.on()

            if seismic_scale >= 3.5:
                if not buzzer.is_active:
                    buzzer.on()
            else:
                buzzer.off()


@cmd.command()
@click.argument('broker')
@click.argument('topic')
@click.option('--interval', '-i', default=0.1)
@click.option('--verbose', '-v', is_flag=True)
def detect_publish_earthquakes(broker, topic, interval, verbose):
    if interval < 0.1:
        raise ValueError('Interval value should be at least 0.1 seconds')

    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    buzzer = Buzzer(3)
    status_led = LED(26)
    scale_led = LEDBoard(a=18, b=23, c=12, d=19, e=6, f=22, g=17, xdp=16)

    def _on_connect(client, userdata, flags, rc):
        if rc == 0:
            logging.info('Connected to broker')
            client.connected_flag = True
        else:
            logging.error('Connection to broker failed')

    client = mqtt.Client('seismometer-{}'.format(uuid.uuid4()))
    client.on_connect = _on_connect
    client.connected_flag = False
    client.connect(broker)

    client.loop_start()
    retry_count = 0

    while not client.connected_flag:
        if retry_count < 5:
            time.sleep(1)
            retry_count += 1
        else:
            logging.error('Maximum retry count has been exceeded')
            sys.exit()

    def _exit_handler():
        client.disconnect()
        client.loop_stop()

    atexit.register(_exit_handler)

    def _callback(self):
        if self.ready:
            message = json.dumps({
                'seismic_scale':  self.seismic_scale,
                'x_acceleration': self.xyz_accel[0],
                'y_acceleration': self.xyz_accel[1],
                'z_acceleration': self.xyz_accel[2],
            })

            client.publish(topic, message)
            logging.debug('Published message: %s', message)

    seismometer = Seismometer()
    seismometer.start_calculation(
        callback=_callback,
        callback_interval=interval
    )

    while True:
        seismic_scale = seismometer.seismic_scale
        scale_led.value = SCALE_LED_CHARSETS[
            seismometer.get_user_friendly_formatted_seismic_scale()]

        if seismometer.ready:
            if not status_led.is_lit:
                status_led.on()

            if seismic_scale >= 3.5:
                if not buzzer.is_active:
                    buzzer.on()
            else:
                buzzer.off()


def main():
    cmd()


if __name__ == '__main__':
    main()
