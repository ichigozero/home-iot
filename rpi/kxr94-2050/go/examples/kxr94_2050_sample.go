package main

import (
	"fmt"
	"time"

	"gobot.io/x/gobot"
	"gobot.io/x/gobot/drivers/spi"
	"gobot.io/x/gobot/platforms/raspi"
)

const adcResolution float32 = 4096                 // 12-bit
const referenceVoltage float32 = 3300              // mV
const voltagePerG float32 = referenceVoltage / 5   // mV
const offsetVoltage float32 = referenceVoltage / 2 // mV
const gal float32 = 980.665                        // cm/s^2

func main() {
	r := raspi.NewAdaptor()
	adc := spi.NewMCP3204Driver(r)

	var axis [3]float32

	work := func() {
		gobot.Every(100*time.Millisecond, func() {
			for i := 0; i < 3; i++ {
				result, _ := adc.Read(i)

				axis[i] = float32(result) / adcResolution * referenceVoltage
				axis[i] -= offsetVoltage
				axis[i] /= voltagePerG
				axis[i] *= gal
			}

			fmt.Printf("X: %g Y: %g Z: %g", axis[0], axis[1], axis[2])
		})
	}

	robot := gobot.NewRobot("accelBot",
		[]gobot.Connection{r},
		[]gobot.Device{adc},
		work,
	)

	robot.Start()
}
