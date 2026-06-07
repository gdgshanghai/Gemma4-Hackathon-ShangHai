#!/usr/bin/env python3
"""
fl-aggregator — stub

Responsibility: federated learning weight aggregator.
Receives gradient/weight updates from edge deployments, performs secure
aggregation (FedAvg), and distributes updated global model weights.

Privacy invariant: raw patient data NEVER leaves its origin domain.
Only model weight deltas cross the network boundary.

TODO: replace with secure aggregation protocol + weight distribution service.
"""

import sys


def main() -> None:
    print("fl-aggregator: stub — replace with FedAvg aggregator + secure weight distribution")
    sys.exit(0)


if __name__ == "__main__":
    main()
