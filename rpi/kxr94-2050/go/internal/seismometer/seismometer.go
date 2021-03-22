package seismometer

import (
	"math"
	"time"

	"gobot.io/x/gobot/drivers/spi"
)

const adcToGal = 1.13426
const targetFPS = 200
const accelFrame = targetFPS * 0.3
const loopDelta = 1.0 / targetFPS

// SeismoData represents channel which contains seismometer real time data
type SeismoData struct {
	Frame          int
	IntensityScale float64
}

// CalculateSeismicIntensity calculates raw seismic intensity scale
// of KXR94-2050 accelerometer values in a real time
func CalculateSeismicIntensity(driver *spi.MCP3204Driver, c chan SeismoData) {
	xyzADC := [3]*ringBuffer{
		newRingBuffer(targetFPS),
		newRingBuffer(targetFPS),
		newRingBuffer(targetFPS),
	}
	xyzGals := [3]float32{0, 0, 0}
	xyzAccel := [3]float32{0, 0, 0}

	accel := newRingBuffer(targetFPS * 5)

	targetTime := time.Now()
	frame := 0

	var seismicScale float64

	for {
		frame++

		for i := 0; i < 3; i++ {
			result, _ := driver.Read(i)
			xyzADC[i].push(float32(result))

			adcSum := xyzADC[i].getSum()
			offset := adcSum / float32(xyzADC[i].size)
			xyzGals[i] = xyzGals[i]*0.94 + float32(result)*0.06
			xyzAccel[i] = (xyzGals[i] - offset) * adcToGal
		}

		accel.push(getCompositeAcceleration(xyzAccel))
		continuousAccel := accel.getSortedValues()[accelFrame]

		if continuousAccel > 0 {
			seismicScale = 2*math.Log10(float64(continuousAccel)) + 0.94
		} else {
			seismicScale = 0
		}

		select {
		case c <- SeismoData{
			Frame:          frame,
			IntensityScale: seismicScale,
		}:
		default:
		}

		if frame > math.MaxUint16 {
			frame = math.MaxUint16 % targetFPS
		}

		// Make sure the program does not exceed the specified FPS
		targetTime.Add(time.Millisecond * (loopDelta * 1000))
		sleepTime := targetTime.Sub(time.Now())

		time.Sleep(sleepTime)
	}
}

func getCompositeAcceleration(xyzAccel [3]float32) float32 {
	return float32(math.Sqrt(
		math.Pow(float64(xyzAccel[0]), 2) +
			math.Pow(float64(xyzAccel[1]), 2) +
			math.Pow(float64(xyzAccel[2]), 2),
	))
}
