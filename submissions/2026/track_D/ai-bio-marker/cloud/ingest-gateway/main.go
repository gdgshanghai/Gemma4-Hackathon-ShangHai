// Package main — ingest-gateway
//
// Responsibility: mTLS gRPC termination point for edge→cloud communication.
// Validates incoming feature.v1.FeatureBundle messages, authenticates the edge
// gateway via mTLS, applies backpressure, and writes validated bundles to the
// feature-store for persistence.
//
// This is the first cloud-side service in the "sense → infer → decide" pipeline.
package main

import (
	"fmt"
	"os"
)

func main() {
	fmt.Println("ingest-gateway: stub — replace with mTLS gRPC server + feature-store writer")
	os.Exit(0)
}
