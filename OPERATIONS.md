# OPERATIONS

This guide covers day‑to‑day operations: setup, switching PLC modes, running doctor tests, tuning logs, and DHCP tips for real PLCs.

**CLI Quickstart (aldctl)**
- Install deps (once per machine):
  - `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Launch interactive menu (Typer + Questionary):
  - `aldctl menu`
  - Use it to: choose PLC mode (Simulation/Real), set IP/hostname/discovery, run Doctor, and start/stop the service.
- Non‑interactive one‑liners (scriptable):
  - Set simulation mode: `aldctl plc set --mode simulation`
  - Set real by IP: `aldctl plc set --mode real --ip 192.168.1.50 --port 502`
  - Set real by hostname + discovery: `aldctl plc set --mode real --hostname plc.local --auto-discover`
  - Run doctor checks: `aldctl doctor run` (≙ `python main.py --doctor`)
  - Start service: `aldctl service start` (≙ `python main.py`)
  - Stop service: `aldctl service stop`

**Setup**
- Python 3.10+ recommended.
- Create venv and install deps:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
- Create `.env` from `.env.example` and fill required keys:
  - `SUPABASE_URL`, `SUPABASE_KEY`, `MACHINE_ID` (must exist in your Supabase `machines` table).
- Start the service:
  - `python main.py`

**Switching PLC Mode**
- CLI (preferred, overrides `.env` for this run):
  - Simulation demo: `python main.py --demo`
  - Explicit simulation: `python main.py --plc simulation`
  - Real PLC by IP: `python main.py --plc real --ip 192.168.1.50 --port 502`
  - Real PLC by hostname (mDNS/DNS): `python main.py --plc real --hostname plc.local`
  - Enable network discovery fallback: `python main.py --plc real --auto-discover`
  - Set Modbus 32‑bit byte/word order: `python main.py --byte-order badc`
- .env (persists across runs):
  - `PLC_TYPE=simulation|real`
  - Optional: `PLC_IP`, `PLC_PORT`, `PLC_HOSTNAME`, `PLC_AUTO_DISCOVER=true|false`, `PLC_BYTE_ORDER=abcd|badc|cdab|dcba`

**Doctor Tests**
- One‑shot connectivity suite (Supabase, health table, realtime, PLC):
  - `python main.py --doctor`
- Interpreting results:
  - All PASS → ready to run.
  - Supabase FAIL → critical; fix `.env` before running the service.
  - PLC FAIL → service still starts; connection monitor retries in background.
  - Realtime FAIL → system falls back to polling.
- Deeper debug scripts (optional):
  - PLC: `python tools/debug/debug/test_plc_connection.py`
  - Supabase: `python tools/debug/debug/test_supabase_connection.py`
  - Valve control: `python tools/debug/debug/test_valve_control.py 1 --duration 2000`

**Log Level & Files**
- Environment (global): set `LOG_LEVEL=DEBUG|INFO|WARNING|ERROR|CRITICAL` and optional `LOG_FILE=path.log`.
- CLI (per run, overrides env): `python main.py --log-level DEBUG --log-file machine_control.log`
- Logging updates at runtime are honored by existing handlers.

**Real PLC on DHCP Networks (Tips)**
- Prefer hostnames when available: set `--hostname plc.local` or `PLC_HOSTNAME=plc.local` (mDNS/Bonjour).
- Enable discovery fallback on dynamic networks: `--auto-discover` or `PLC_AUTO_DISCOVER=true`.
- Reserve a DHCP lease:
  - Get PLC MAC from device label or vendor tool.
  - Create a DHCP reservation on the router for a stable IP.
- Verify reachability:
  - `ping <hostname-or-ip>`; check ARP: `arp -a`; optional scan (ops owned networks only): `nmap -p 502 <subnet>/24`.
- Confirm firewall rules allow Modbus/TCP (port 502) between controller and PLC.
- If values look byte‑swapped, adjust `PLC_BYTE_ORDER` (`badc` default; try `abcd|cdab|dcba`).

**Quick Commands**
- Run service in simulation with verbose logs: `LOG_LEVEL=DEBUG python main.py --demo`
- Run service against a real PLC: `python main.py --plc real --ip 192.168.1.50 --port 502`
- Doctor then exit: `python main.py --doctor`
