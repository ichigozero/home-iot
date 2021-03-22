package main

import (
	"io"
	"log"
	"os"

	"github.com/ichigozero/home-iot/rpi/kxr94-2050/go/internal/seismometer"
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
	driver := spi.NewMCP3204Driver(r)

	seismoData := make(chan seismometer.SeismoData)

	work := func() {
		go seismometer.CalculateSeismicIntensity(driver, seismoData)

		for {
			s := <-seismoData
			if s.IntensityScale > 0.5 {
				if s.Frame%20 == 0 {
					log.Printf("Scale: %g Frame: %d\n", s.IntensityScale, s.Frame)
				}
			}
		}
	}

	robot := gobot.NewRobot("SeismoBot",
		[]gobot.Connection{r},
		[]gobot.Device{driver},
		work,
	)

	robot.Start()
}
