// Package main — preprocess-svc
//
// Responsibility: consume signal.v1.Frame messages, apply band-pass filtering,
// ICA artifact removal (ocular, muscular), and band-power computation.
// Outputs cleaned frames to feature-codec.
//
// Runs on the edge gateway; must operate offline when cloud is unreachable.
package main

import (
	"fmt"
	"os"
)

func main() {
	fmt.Println("preprocess-svc: stub — replace with DSP pipeline (filtering, ICA, band-power)")
	os.Exit(0)
}
