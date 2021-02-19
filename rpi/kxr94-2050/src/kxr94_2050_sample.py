import time

from gpiozero import MCP3204


ADC_RESOLUTION = 4096  # 12-bit
REFERENCE_VOLTAGE = 3300  # mV
VOLTAGE_PER_G = REFERENCE_VOLTAGE / 5  # mV
OFFSET_VOLTAGE = REFERENCE_VOLTAGE / 2  # mV
GAL = 980.665  # cm/s^2


def main():
    mcp3204 = [
        MCP3204(channel=0),
        MCP3204(channel=1),
        MCP3204(channel=2),
    ]
    tri_axis = [0, 0, 0]

    while True:
        for i in range(3):
            tri_axis[i] = (
                mcp3204[i].raw_value
                / ADC_RESOLUTION
                * REFERENCE_VOLTAGE
            )

            tri_axis[i] -= OFFSET_VOLTAGE
            tri_axis[i] /= VOLTAGE_PER_G
            tri_axis[i] *= GAL

        print(f'X: {tri_axis[0]} Y: {tri_axis[1]} Z: {tri_axis[2]}')
        time.sleep(0.1)


if __name__ == '__main__':
    main()
