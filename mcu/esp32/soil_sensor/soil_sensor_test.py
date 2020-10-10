from utime import sleep

from soil_sensor import SoilSensor

sensor = SoilSensor(
    adc_pin=36,
    air_value=3500,
    water_value=1400
)

while True:
    print(sensor.read_data())
    sleep(1)
