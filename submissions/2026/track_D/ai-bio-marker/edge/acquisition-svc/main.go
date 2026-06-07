// Package main — acquisition-svc
//
// Responsibility: read ADC streams from the BCI headset, timestamp every frame,
// tag with data residency, and emit signal.v1.Frame messages downstream.
//
// Target: ARM Cortex-M55 gateway running Linux (AlmaLinux / RHEL).
// In production the ADC HAL is bare-metal; this stub reads from a synthetic fixture.
package main

import (
	"fmt"
	"os"
)

func main() {
	fmt.Println("acquisition-svc: stub — replace with real ADC HAL integration")
	os.Exit(0)
}
