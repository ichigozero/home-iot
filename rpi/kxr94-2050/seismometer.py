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

import collections
import datetime
import math
import time

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

adc = [MCP3204(channel=0), MCP3204(channel=1), MCP3204(channel=2)]

xyz_raw_g = [
    collections.deque(maxlen=TARGET_FPS),
    collections.deque(maxlen=TARGET_FPS),
    collections.deque(maxlen=TARGET_FPS)
]
xyz_filtered_g = [0, 0, 0]
xyz_accel = [0, 0, 0]

accel_values = collections.deque(maxlen=TARGET_FPS * 5)
frame = 0


def to_gforce(adc_value):
    analog_voltage = (adc_value / ADC_RESOLUTION) * REFERENCE_VOLTAGE
    analog_voltage -= OFFSET_VOLTAGE

    return analog_voltage / VOLTAGE_PER_G


def get_composite_acceleration(xyz_accel):
    return math.sqrt(
        (xyz_accel[0] ** 2)
        + (xyz_accel[1] ** 2)
        + (xyz_accel[2] ** 2)
    )


target_time = time.time()

while True:
    for i in range(3):
        g_value = to_gforce(adc[i].raw_value)
        xyz_raw_g[i].append(g_value)

        offset = sum(xyz_raw_g[i]) / len(xyz_raw_g[i])
        xyz_filtered_g[i] = xyz_filtered_g[i] * 0.94 + g_value * 0.06
        xyz_accel[i] = (xyz_filtered_g[i] - offset) * GAL

    accel_values.append(get_composite_acceleration(xyz_accel))

    try:
        continous_accel = sorted(accel_values)[-ACCEL_FRAME]
    except IndexError:
        continous_accel = 0

    if continous_accel > 0:
        seismic_scale = 2 * math.log10(continous_accel) + 0.94
    else:
        seismic_scale = 0

    if frame % (TARGET_FPS / 10) == 0:
        print(
            f'{datetime.datetime.now()}'
            f' scale: {seismic_scale}'
            f' frame: {frame}'
        )

    target_time += LOOP_DELTA
    sleep_time = target_time - time.time()

    if sleep_time > 0:
        time.sleep(sleep_time)

    frame += 1

    if frame >= MAX_32_BIT_INT:
        frame = MAX_32_BIT_INT % TARGET_FPS
