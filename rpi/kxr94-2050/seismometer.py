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
import math
import threading
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


class Seismometer:
    def __init__(self):
        self._adc = [
            MCP3204(channel=0),
            MCP3204(channel=1),
            MCP3204(channel=2)
        ]
        self._frame = 0
        self._task_running = False
        self._task_thread = threading.Thread(
            target=self._calculate_seismic_scale,
            daemon=True
        )
        self.xyz_accel = [0, 0, 0]
        self.seismic_scale = 0

    def start_calculation(self):
        self._task_running = True
        self._task_thread.start()

    def stop_calculation(self):
        self._task_running = False
        self._task_thread.join()

    def _calculate_seismic_scale(self):
        xyz_raw_g = [
            collections.deque(maxlen=TARGET_FPS),
            collections.deque(maxlen=TARGET_FPS),
            collections.deque(maxlen=TARGET_FPS)
        ]
        xyz_filtered_g = [0, 0, 0]
        accel_values = collections.deque(maxlen=TARGET_FPS * 5)

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

            target_time += LOOP_DELTA
            sleep_time = target_time - time.time()

            if sleep_time > 0:
                time.sleep(sleep_time)

            self._frame += 1

            if self._frame >= MAX_32_BIT_INT:
                self._frame = MAX_32_BIT_INT % TARGET_FPS

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
