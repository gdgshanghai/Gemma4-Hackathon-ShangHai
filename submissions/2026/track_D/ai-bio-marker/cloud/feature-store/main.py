#!/usr/bin/env python3
"""
feature-store — stub

Responsibility: versioned persistence and replay of feature.v1.FeatureBundle messages.
Serves as the single source of truth for cloud-side inference inputs.
Backed by an object store (MinIO in dev, S3-compatible in production).

TODO: replace with actual object-store client + schema-aware read/write paths.
"""

import sys


def main() -> None:
    print("feature-store: stub — replace with object-store backed FeatureBundle persistence")
    sys.exit(0)


if __name__ == "__main__":
    main()
