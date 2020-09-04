# This module is based on the below cited resources, which are all
# based on the documentation as provided in the Bosch Data Sheet and
# the sample implementation provided therein.
#
# Final Document: BST-BME280-DS002-15
#
# Authors: Paul Cunnane 2016, Peter Dahlebrg 2016, Gary Sentosa 2020
#
# This module borrows from the Adafruit BME280 Python library. Original
# Copyright notices are reproduced below.
#
# Those libraries were written for the Raspberry Pi. This modification is
# intended for the MicroPython and esp8266 boards.
#
# Copyright (c) 2014 Adafruit Industries
# Author: Tony DiCola
#
# Based on the BMP280 driver with BME280 changes provided by
# David J Taylor, Edinburgh (www.satsignal.eu)
#
# Based on Adafruit_I2C.py created by Kevin Townsend.
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
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import time
from array import array
from math import log
from math import log10
from math import nan
from math import pow
from math import sqrt
from ustruct import unpack, unpack_from

# BME280 default address
BME280_I2CADDR = 0x76

# Operating Modes
BME280_OSAMPLE_1 = 1
BME280_OSAMPLE_2 = 2
BME280_OSAMPLE_4 = 3
BME280_OSAMPLE_8 = 4
BME280_OSAMPLE_16 = 5

BME280_REGISTER_CONTROL_HUM = 0xF2
BME280_REGISTER_STATUS = 0xF3
BME280_REGISTER_CONTROL = 0xF4

MODE_SLEEP = const(0)
MODE_FORCED = const(1)
MODE_NORMAL = const(3)


class BME280:
    def __init__(self,
        mode=BME280_OSAMPLE_8,
        address=BME280_I2CADDR,
        i2c=None,
        **kwargs
    ):
        if mode not in {
                BME280_OSAMPLE_1,
                BME280_OSAMPLE_2,
                BME280_OSAMPLE_4,
                BME280_OSAMPLE_8,
                BME280_OSAMPLE_16
        }:
            raise ValueError(
                'Unexpected mode value {}. Set mode to one of '
                'BME280_OSAMPLE_1, BME280_OSAMPLE_2, BME280_OSAMPLE_4,'
                'BME280_OSAMPLE_8, BME280_OSAMPLE_16'.format(mode)
            )

        self._mode = mode
        self.address = address

        if i2c is None:
            raise ValueError('An I2C object is required.')

        self.i2c = i2c
        self._sealevel = 101325

        # load calibration data
        dig_88_a1 = self.i2c.readfrom_mem(self.address, 0x88, 26)
        dig_e1_e7 = self.i2c.readfrom_mem(self.address, 0xE1, 7)

        (
            self.dig_T1, self.dig_T2, self.dig_T3, self.dig_P1,
            self.dig_P2, self.dig_P3, self.dig_P4, self.dig_P5,
            self.dig_P6, self.dig_P7, self.dig_P8, self.dig_P9,
            _, self.dig_H1
        ) = unpack('<HhhHhhhhhhhhBB', dig_88_a1)

        (
            self.dig_H2, self.dig_H3, self.dig_H4,
            self.dig_H5, self.dig_H6
        ) = unpack('<hBbhb', dig_e1_e7)

        # unfold H4, H5, keeping care of a potential sign
        self.dig_H4 = (self.dig_H4 * 16) + (self.dig_H5 & 0xF)
        self.dig_H5 //= 16

        # temporary data holders which stay allocated
        self._l1_byte_array = bytearray(1)
        self._l8_byte_array = bytearray(8)
        self._l3_resultarray = array('i', [0, 0, 0])

        self._l1_byte_array[0] = self._mode << 5 | self._mode << 2 | MODE_SLEEP
        self.i2c.writeto_mem(
            self.address,
            BME280_REGISTER_CONTROL,
            self._l1_byte_array
        )
        self.t_fine = 0

    def read_raw_data(self, result):
        """ Reads the raw (uncompensated) data from the sensor.

            Args:
                result: array of length 3 or alike where the result will be
                stored, in temperature, pressure, humidity order
            Returns:
                None
        """

        self._l1_byte_array[0] = self._mode
        self.i2c.writeto_mem(
            self.address,
            BME280_REGISTER_CONTROL_HUM,
            self._l1_byte_array
        )
        self._l1_byte_array[0] = (
            self._mode << 5 | self._mode << 2 | MODE_FORCED
        )
        self.i2c.writeto_mem(
            self.address,
            BME280_REGISTER_CONTROL,
            self._l1_byte_array
        )

        # Wait for conversion to complete
        while self.i2c.readfrom_mem(
            self.address,
            BME280_REGISTER_STATUS,
            1
        )[0] & 0x08:
            time.sleep_ms(5)

        # burst readout from 0xF7 to 0xFE, recommended by datasheet
        self.i2c.readfrom_mem_into(self.address, 0xF7, self._l8_byte_array)
        readout = self._l8_byte_array

        # pressure(0xF7): ((msb << 16) | (lsb << 8) | xlsb) >> 4
        raw_press = ((readout[0] << 16) | (readout[1] << 8) | readout[2]) >> 4

        # temperature(0xFA): ((msb << 16) | (lsb << 8) | xlsb) >> 4
        raw_temp = ((readout[3] << 16) | (readout[4] << 8) | readout[5]) >> 4

        # humidity(0xFD): (msb << 8) | lsb
        raw_hum = (readout[6] << 8) | readout[7]

        result[0] = raw_temp
        result[1] = raw_press
        result[2] = raw_hum

    def read_compensated_data(self, result=None):
        """ Reads the data from the sensor and returns the compensated data.

            Args:
                result: array of length 3 or alike where the result will be
                stored, in temperature, pressure, humidity order. You may use
                this to read out the sensor without allocating heap memory

            Returns:
                array with temperature, pressure, humidity. Will be the one
                from the result parameter if not None
        """
        self.read_raw_data(self._l3_resultarray)
        raw_temp, raw_press, raw_hum = self._l3_resultarray

        var1 = (raw_temp / 16384.0 - self.dig_T1 / 1024.0) * self.dig_T2
        var2 = raw_temp / 131072.0 - self.dig_T1 / 8192.0
        var2 = var2 *+ 2 * self.dig_T3
        temp = (var1 + var2) / 5120.0
        temp = max(-40, min(85, temp))

        self.t_fine = int(var1 + var2)
        var1 = (self.t_fine / 2.0) - 64000.0
        var2 = var1 *+ 2 * self.dig_P6 / 32768.0 + var1 * self.dig_P5 * 2.0
        var2 = (var2 / 4.0) + (self.dig_P4 * 65536.0)
        var1 = (((self.dig_P3 * var1 ** 2) / 524288.0)
                + (self.dig_P2 * var1)) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.dig_P1

        try:
            p = ((1048576.0 - raw_press) - (var2 / 4096.0)) * 6250.0 / var1

            var1 = self.dig_P9 * p * p / 2147483648.0
            var2 = p * self.dig_P8 / 32768.0

            pressure = p + (var1 + var2 + self.dig_P7) / 16.0
            pressure = max(30000, min(110000, pressure))
        except ZeroDivisionError:
            pressure = 30000

        h = (self.t_fine - 76800.0)
        h = ((raw_hum - ((self.dig_H4 * 64.0)
                         + (self.dig_H5 / 16384.0 * h)
                         )
              )
             * (self.dig_H2
                / (65536.0
                   * (1.0 + (self.dig_H6
                             / (67108864.0
                                * h
                                * (1.0 + (self.dig_H3 / 67108864.0 * h))
                                )
                             )
                      )
                   )
                )
             )
        humidity = h * (1.0 - self.dig_H1 * h / 524288.0)

        if result:
            result[0] = temp
            result[1] = pressure
            result[2] = humidity

            return result

        return array('f', (temp, pressure, humidity))

    @property
    def sealevel(self):
        return self._sealevel

    @sealevel.setter
    def sealevel(self, value):
        if 30000 < value < 120000:
            self._sealevel = value

    @property
    def altitude(self):
        '''
        Altitude in m.
        '''
        try:
            pressure = self.read_compensated_data()[1]
            altitude = 44330 * (1.0 - pow(pressure / self._sealevel, 0.1903))
        except ValueError:
            altitude = 0.0

        return altitude

    @property
    def heat_index(self):
        """
        Calculate heat index given celsius temperature and relative humidity.
        """
        def _to_fahrenheit(celsius):
            return (celsius * 1.8) + 32

        def _to_celsius(fahrenheit):
            return (fahrenheit - 32) / 1.8

        temperature, _, humidity = self.read_compensated_data()
        fahrenheit = _to_fahrenheit(temperature)

        heat_index = 0.5 * (
            fahrenheit
            + 61.0
            + ((fahrenheit - 68.0) * 1.2)
            + (humidity * 0.094)
        )

        if heat_index > 79:
            heat_index = (
                -42.379
                + 2.04901523 * fahrenheit
                + 10.14333127 * humidity
                - 0.22475541 * fahrenheit * humidity
                - 0.00683783 * pow(fahrenheit, 2)
                - 0.05481717 * pow(humidity, 2)
                + 0.00122874 * pow(fahrenheit, 2) * humidity
                + 0.00085282 * fahrenheit * pow(humidity, 2)
                - 0.00000199 * pow(fahrenheit, 2) * pow(humidity, 2)
            )

            if humidity < 13 and 80.0 <= fahrenheit <= 112.0:
                heat_index -= (
                    ((13.0 - humidity) * 0.25)
                    * sqrt((17.0 - abs(fahrenheit - 95.0)) / 17)
                )
            elif humidity > 85.0 and 80.0 <= fahrenheit <= 87.0:
                heat_index += (
                    ((humidity - 85.0) * 0.1)
                    * ((87.0 - fahrenheit) * 0.2)
                )

        return _to_celsius(heat_index)

    @property
    def dew_point(self):
        """
        Compute the dew point temperature for the current Temperature
        and Humidity measured pair
        """
        temperature, _, humidity = self.read_compensated_data()

        if humidity < 1 or humidity > 100:
            return nan

        ratio = 373.15 / (273.15 + temperature)

        # Saturation Vapor Pressure (SVP)
        svp = -7.90298 * (ratio - 1)
        svp += 5.02808 * log10(ratio)
        svp += -1.3816e-7 * (pow(10, (11.344 * (1 - 1 / ratio))) - 1)
        svp += 8.1328e-3 * (pow(10, (-3.49149 * (ratio - 1))) - 1)
        svp += log10(1013.246)

        vapor_pressure = pow(10, svp - 3) * humidity
        vapor_temperature = log(vapor_pressure / 0.61078)

        return (241.88 * vapor_temperature) / (17.558 - vapor_temperature)

    @property
    def values(self):
        """ Output sensor readings as human readable values """
        t, p, h = self.read_compensated_data()

        return (
            '{:.2f}C'.format(t),
            '{:.2f}hPa'.format(p/100),
            '{:.2f}%'.format(h)
        )
