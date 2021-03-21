package main

import (
	"io"
	"log"
	"math"
	"os"
	"sort"
	"time"

	"gobot.io/x/gobot"
	"gobot.io/x/gobot/drivers/spi"
	"gobot.io/x/gobot/platforms/raspi"
)

const adcToGal = 1.13426
const targetFPS = 200
const accelFrame = targetFPS * 0.3
const loopDelta = 1.0 / targetFPS
const max32BitInt = 2147483647

var logFile *os.File

func initializeLogOutput() {
	logFile, err := os.OpenFile(
		"seismo.log",
		os.O_APPEND|os.O_CREATE|os.O_WRONLY,
		0644,
	)
	if err != nil {
		log.Fatal(err)
	}

	mw := io.MultiWriter(os.Stdout, logFile)
	log.SetOutput(mw)
}

func closeLogOutput() {
	logFile.Close()
}

func main() {
	initializeLogOutput()
	defer closeLogOutput()

	r := raspi.NewAdaptor()
	adc := spi.NewMCP3204Driver(r)

	xyzADC := [3]*ringBuffer{
		newRingBuffer(targetFPS),
		newRingBuffer(targetFPS),
		newRingBuffer(targetFPS),
	}

	xyzGals := [3]float32{0, 0, 0}
	xyzAccel := [3]float32{0, 0, 0}
	accel := newRingBuffer(targetFPS * 5)
	frame := 0
	targetTime := time.Now()

	var seismicScale float64

	work := func() {
		for {
			frame++

			for i := 0; i < 3; i++ {
				result, _ := adc.Read(i)
				xyzADC[i].append(float32(result))

				adcSum := xyzADC[i].getSum()
				offset := adcSum / float32(xyzADC[i].size)
				xyzGals[i] = xyzGals[i]*0.94 + float32(result)*0.06
				xyzAccel[i] = (xyzGals[i] - offset) * adcToGal
			}

			accel.append(getCompositeAcceleration(xyzAccel))
			continuousAccel := accel.getSortedValues()[accelFrame]

			if continuousAccel > 0 {
				seismicScale = 2*math.Log10(float64(continuousAccel)) + 0.94
			} else {
				seismicScale = 0
			}

			if seismicScale > 0.5 {
				if frame%(targetFPS/10) == 0 {
					log.Printf("Scale: %g Frame: %d\n", seismicScale, frame)
				}
			}

			if frame > max32BitInt {
				frame = max32BitInt % targetFPS
			}

			targetTime.Add(time.Millisecond * (loopDelta * 1000))
			sleepTime := targetTime.Sub(time.Now())

			time.Sleep(sleepTime)
		}
	}

	robot := gobot.NewRobot("seismoBot",
		[]gobot.Connection{r},
		[]gobot.Device{adc},
		work,
	)

	robot.Start()
}

func getCompositeAcceleration(xyzAccel [3]float32) float32 {
	return float32(math.Sqrt(
		math.Pow(float64(xyzAccel[0]), 2) +
			math.Pow(float64(xyzAccel[1]), 2) +
			math.Pow(float64(xyzAccel[2]), 2),
	))
}

type ringBuffer struct {
	values []float32
	size   int
	index  int
}

func newRingBuffer(size int) *ringBuffer {
	return &ringBuffer{
		values: make([]float32, size),
		size:   size,
	}
}

func (r *ringBuffer) append(value float32) {
	r.values[r.index] = value
	r.index = (r.index + 1) % r.size
}

func (r *ringBuffer) getSum() float32 {
	var sum float32 = 0

	for i := 0; i < r.size; i++ {
		sum += r.values[i]
	}

	return sum
}

func (r *ringBuffer) getSortedValues() []float32 {
	newValues := make([]float32, r.size)
	copy(newValues, r.values)

	sort.Slice(newValues, func(i, j int) bool {
		return newValues[i] > newValues[j]
	})

	return newValues
}
