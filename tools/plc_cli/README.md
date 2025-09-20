PLC CLI Tools

Purpose
- Quick, safe connectivity and I/O checks to a PLC before running full flows.
- Validate byte order (word/byte swapping) for 32‑bit values.
- Exercise specific Modbus types (coil, holding, input) with explicit types (float, int32, int16).

Prereqs
- Python 3.9+
- Dependencies from repo `requirements.txt` (pymodbus required for real PLC):
  - `pip install -r requirements.txt`
- `.env` at repo root with SUPABASE_URL/KEY and MACHINE_ID (only needed for simulation/DB tests).

Quick Start (Simulation)
- `python tools/plc_cli/plc_cli.py connect-test --mode simulation`
- `python tools/plc_cli/plc_cli.py write-coil --addr 10 --value on --mode simulation`
- `python tools/plc_cli/plc_cli.py read-coil --addr 10 --mode simulation`

Quick Start (Real PLC)
- Example float read at address 2066 with specific byte order:
  - `python tools/plc_cli/plc_cli.py read-reg --addr 2066 --type float --space holding --host 10.5.5.80 --byte-order badc`
- Toggle a coil (write ON):
  - `python tools/plc_cli/plc_cli.py write-coil --addr 10 --value on --host 10.5.5.80`

Byte Order Helpers
- Read registers and print all interpretations:
  - `python tools/plc_cli/plc_cli.py interpret --addr 2066 --space holding --host 10.5.5.80`

Notes
- Supported byte orders: `abcd` (big‑endian), `badc` (big‑byte/little‑word), `cdab` (little‑byte/big‑word), `dcba` (little‑endian).
- If using `--mode real`, the CLI talks directly to the Modbus TCP device; it does not change any schema or app state.

