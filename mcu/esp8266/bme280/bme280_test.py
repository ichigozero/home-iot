from utime import sleep
from machine import I2C
from machine import Pin

from bme280 import BME280

i2c = I2C(scl=Pin(5), sda=Pin(4))
bme280 = BME280(i2c=i2c)

while True:
    print(bme280.values)
    sleep(1)
