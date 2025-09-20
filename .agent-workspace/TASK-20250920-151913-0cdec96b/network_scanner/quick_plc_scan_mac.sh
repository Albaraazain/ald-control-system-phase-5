#!/usr/bin/env bash
set -euo pipefail

echo "=== Network Topology (macOS) ==="
echo "-- Interfaces w/169.254 --"
ifconfig -a | awk '/^[a-z0-9]+: /{iface=$1} /inet 169\.254/{print iface, $0}'
echo
echo "-- Routes for 169.254.0.0/16 --"
netstat -rn | grep -E '^169\.254' || true
echo
echo "-- ARP cache (169.254) --"
arp -an | grep '169.254' || true
echo

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCANNER="$SCRIPT_DIR/scan_linklocal_plcs.py"

echo "=== Quick PLC Discovery (ARP hosts + UDP discovery) ==="
python3 "$SCANNER" --mode quick --ethernet-ip --bacnet --timeout 0.8 --json-out "${SCRIPT_DIR}/results_quick.json"
echo

echo "=== /24 Sweep on each 169.254 interface (ports 502,102,44818) ==="
python3 "$SCANNER" --mode sweep --cidr 24 --ports 502,102,44818 --timeout 0.6 --json-out "${SCRIPT_DIR}/results_sweep.json"
echo

if command -v nmap >/dev/null 2>&1; then
  echo "=== nmap pass (if present) on union of targets ==="
  python3 "$SCANNER" --mode all --nmap --timeout 0.6 --json-out "${SCRIPT_DIR}/results_all.json"
else
  echo "(nmap not found; skip)"
fi

echo "Done. JSON results in:"
ls -1 "${SCRIPT_DIR}"/results_*.json 2>/dev/null || true

