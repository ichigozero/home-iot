from array import array
from machine import ADC
from machine import Pin

UNCATEGORIZED = 0
VERY_WET = 1
WET = 2
DRY = 3


class SoilSensor:
    def __init__(self, adc_pin, air_value, water_value):
        self._adc = ADC(Pin(adc_pin))
        self._adc.atten(ADC.ATTN_11DB)

        self._air_value = air_value
        self._water_value = water_value

    def read_data(self):
        moisture_value = self._adc.read()
        moisture_level = self._to_percent(moisture_value)
        category = self._categorize_moisture_value(moisture_value)

        return array('i', (moisture_value, moisture_level, category))

    def _to_percent(self, moisture_value):
        if moisture_value < self._water_value:
            converted_value = 0
        elif moisture_value > self._air_value:
            converted_value = 100
        else:
            delta = moisture_value - self._water_value
            converted_value = int((delta / self._air_value) * 100)

        return converted_value

    def _categorize_moisture_value(self, moisture_value):
        intervals = int((self._air_value - self._water_value) / 3)
        upper_water_value = self._water_value + intervals
        lower_air_value = self._air_value - intervals

        if self._water_value <= moisture_value < upper_water_value:
            category = VERY_WET
        elif upper_water_value <= moisture_value < lower_air_value:
            category = WET
        elif lower_air_value <= moisture_value <= self._air_value:
            category = DRY
        else:
            category = UNCATEGORIZED

        return category
