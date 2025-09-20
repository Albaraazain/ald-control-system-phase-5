# Network Scanner (169.254 Link‑Local) — macOS Quick Guide

This folder contains lightweight tools to discover PLC‑like devices on link‑local networks (169.254.0.0/16) from macOS, without external Python dependencies.

- `scan_linklocal_plcs.py`: Async scanner for TCP ports and UDP broadcasts (EtherNet/IP, BACnet), optional nmap integration.
- `quick_plc_scan_mac.sh`: One‑shot helper that prints topology, runs quick discovery, per‑/24 sweeps, and an optional nmap pass.

## Quick Start (macOS)

1. Open Terminal and change into this folder:
   `cd .agent-workspace/TASK-20250920-151913-0cdec96b/network_scanner`
2. Ensure Python 3 is available (macOS often has it):
   - If missing, install via Homebrew: `brew install python`
3. (Optional) Install nmap for deeper fingerprints: `brew install nmap`
4. Run the quick helper (creates JSON outputs here):
   `./quick_plc_scan_mac.sh`
   - If you see a permission error: `chmod +x quick_plc_scan_mac.sh`

Tip: At least one interface must have a 169.254.x.x address (APIPA). Plug directly into the device or a switch and macOS will typically auto‑assign 169.254.x.x.

## Common Tasks & Sample Commands

- List link‑local interfaces and ARP entries only:
  `python3 scan_linklocal_plcs.py --mode arp`

- Fast discovery on ARP‑seen hosts + UDP broadcasts:
  `python3 scan_linklocal_plcs.py --mode quick --ethernet-ip --bacnet --timeout 0.8 --json-out results_quick.json`

- Per‑/24 sweep from each 169.254 interface on common PLC ports:
  `python3 scan_linklocal_plcs.py --mode sweep --cidr 24 --ports 502,102,44818 --timeout 0.6 --json-out results_sweep.json`

- Combine quick + sweep and include nmap (if installed):
  `python3 scan_linklocal_plcs.py --mode all --nmap --timeout 0.6 --json-out results_all.json`

- Target a specific interface (e.g., `en0`):
  `python3 scan_linklocal_plcs.py --mode quick --iface en0 --ethernet-ip --bacnet`

- Tame resource usage on small Macs:
  `python3 scan_linklocal_plcs.py --mode sweep --concurrency 128 --timeout 1.0`

- Optional nmap OS detect (may require sudo on macOS):
  `python3 scan_linklocal_plcs.py --mode nmap --ports 502,102,44818 --os-detect`

## What The Tool Does

- Parses `ifconfig` for 169.254 interfaces and `arp -an` for cached neighbors.
- Async TCP connect scans common PLC ports: 502 (Modbus), 102 (Siemens S7), 44818 (EtherNet/IP), 20000 (DNP3).
- Attempts Modbus “Read Device Identification” on 502/tcp when open.
- Sends EtherNet/IP ListIdentity (UDP/44818) and BACnet Who‑Is (UDP/47808) broadcasts when requested.
- Optionally runs `nmap` against discovered/swept hosts if present.

## Interpreting Results

- Console shows sections like:
  - `Link-local interfaces` — each 169.254 interface found.
  - `Quick/Sweep TCP scan` — progress summary.
  - `Candidates:` — lines per host, e.g.: `169.254.1.10: 502/open, 102/closed  [modbus-tcp]  id='Acme PLC ...'`
    - Port states: `open`, `closed` (host reachable), `filtered` (timeout), `unreachable` (errors).
    - Tags: `modbus-tcp`, `siemens-s7`, `ethernet-ip`, `dnp3`.
  - `UDP discovery responders:` — devices answering EtherNet/IP or BACnet broadcasts; may include guessed product name.
- JSON (if `--json-out` used) includes: `interfaces`, `arp`, `devices[IP].ports{state,banner}`, `tags`, `extra.modbus_ident`, `udp_discovery`, and raw `nmap` text (when run).

## Safety & Scope Notes

- Use only on networks you own or have authorization to test.
- Default focus is 169.254/16; scanning larger ranges is slow. Prefer ARP/quick or /24 sweeps.
- High concurrency can spike CPU/connection limits; reduce with `--concurrency` and increase `--timeout` if needed.
- UDP broadcasts (EtherNet/IP/BACnet) are lightweight; still avoid noisy repeated runs on shared networks.
- `nmap -O` (when `--os-detect`) may require sudo on macOS.

## Troubleshooting

- “No 169.254.x.x interfaces found. Nothing to scan.”
  - Ensure a cable connection to the device or set the interface to obtain an address automatically (APIPA).
- “(nmap not found; skip)”
  - Install: `brew install nmap`, or omit `--nmap`.
- Empty results
  - Try `--mode all`, raise `--timeout`, or widen to `--cidr 16` (with caution); cap with `--max-hosts`.

---
Maintainer note: These tools are self‑contained and macOS‑friendly; no Python packages required. Optional `nmap` enhances details but is not mandatory.
