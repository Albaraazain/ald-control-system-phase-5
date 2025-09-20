#!/usr/bin/env bash
# Run connectivity tests for ALD Control System
set -euo pipefail

# Allow passing through additional env overrides, e.g.:
# LOG_LEVEL=DEBUG PLC_TYPE=simulation scripts/doctor.sh

python main.py --doctor

