#!/usr/bin/env python3
"""
scan_linklocal_plcs.py

macOS-friendly discovery of PLC-like devices on 169.254.0.0/16 (link‑local) networks.

Capabilities (no external deps):
- Parse interfaces with 169.254.x.x via `ifconfig` output
- Parse ARP cache for 169.254 entries via `arp -an`
- Async TCP scan for common PLC ports: 502 (Modbus), 102 (Siemens S7), 44818 (EtherNet/IP),
  20000 (DNP3)
- EtherNet/IP (CIP) ListIdentity UDP broadcast on 44818
- BACnet Who-Is UDP broadcast on 47808 (0xBAC0)
- Optional nmap integration if present (not required)

Outputs concise human-readable results and optional JSON.

Usage examples:
  python3 scan_linklocal_plcs.py --mode quick --ethernet-ip --bacnet --json-out results.json
  python3 scan_linklocal_plcs.py --mode sweep --cidr 24 --ports 502,102,44818 --timeout 0.5
  python3 scan_linklocal_plcs.py --mode arp --nmap

Note: Scanning an entire /16 (65,536 hosts) is slow. Prefer arp/quick or /24 sweeps.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
import re
import shlex
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional, Set, Tuple


# ----------------------------- Utilities & Types -----------------------------


@dataclass
class InterfaceInfo:
    name: str
    ipv4: str
    netmask: str  # dotted
    broadcast: Optional[str]


@dataclass
class PortResult:
    port: int
    state: str  # open|closed|filtered|unreachable
    banner: Optional[str] = None


@dataclass
class DeviceCandidate:
    ip: str
    iface: Optional[str]
    ports: Dict[int, PortResult]
    tags: List[str]
    extra: Dict[str, str]


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def run_cmd(cmd: str) -> str:
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return out.decode(errors="ignore")
    except subprocess.CalledProcessError as exc:
        return exc.output.decode(errors="ignore")


def hex_mask_to_dotted(hexmask: str) -> str:
    # macOS ifconfig shows like 0xffff0000
    try:
        if hexmask.startswith("0x"):
            val = int(hexmask, 16)
            return socket.inet_ntoa(struct.pack("!I", val))
    except Exception:
        pass
    return hexmask


def parse_ifconfig_linklocal() -> List[InterfaceInfo]:
    text = run_cmd("ifconfig -a")
    interfaces: List[InterfaceInfo] = []
    current = None
    for line in text.splitlines():
        if not line:
            continue
        if not line.startswith("\t") and ": flags=" in line:
            # New interface header, e.g., "en0: flags=..."
            name = line.split(":", 1)[0].strip()
            current = name
            continue
        if current is None:
            continue
        m = re.search(r"\sinet\s(\d+\.\d+\.\d+\.\d+)\snetmask\s(0x[0-9a-fA-F]+|\d+\.\d+\.\d+\.\d+)(?:\sbroadcast\s(\d+\.\d+\.\d+\.\d+))?",
                      line)
        if m:
            ip = m.group(1)
            if ip.startswith("169.254."):
                netmask = hex_mask_to_dotted(m.group(2))
                broadcast = m.group(3) if m.lastindex and m.lastindex >= 3 else None
                interfaces.append(InterfaceInfo(current, ip, netmask, broadcast))
    return interfaces


def parse_arp_linklocal() -> List[Tuple[str, str, str]]:
    """Return list of (ip, mac, iface) for 169.254.* entries in ARP cache."""
    text = run_cmd("arp -an")
    results: List[Tuple[str, str, str]] = []
    for line in text.splitlines():
        # Example: ? (169.254.57.35) at 00:30:de:ad:be:ef on en0 ifscope [ethernet]
        m = re.search(r"\((169\.254\.\d+\.\d+)\) at ([0-9a-fA-F:]{11,}) on (\S+)", line)
        if m:
            ip, mac, iface = m.group(1), m.group(2), m.group(3)
            results.append((ip, mac, iface))
    return results


def choose_networks(interfaces: List[InterfaceInfo], cidr: int) -> List[ipaddress.IPv4Network]:
    nets: List[ipaddress.IPv4Network] = []
    for inf in interfaces:
        try:
            network = ipaddress.IPv4Network(
                f"{inf.ipv4}/{cidr}", strict=False
            )
            nets.append(network)
        except Exception:
            continue
    return nets


def ip_is_linklocal(ip: str) -> bool:
    try:
        return ipaddress.IPv4Address(ip).is_link_local
    except Exception:
        return False


# ------------------------------ Async TCP Scan -------------------------------


async def tcp_connect(ip: str, port: int, timeout: float) -> Tuple[str, int, str, Optional[str]]:
    try:
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        # best-effort tiny banner read without sending first, for services that greet
        banner = None
        try:
            writer.write(b"\r\n")
            await writer.drain()
            await asyncio.sleep(0.05)
            if reader.at_eof():
                banner = None
            else:
                data = await asyncio.wait_for(reader.read(64), timeout=0.2)
                if data:
                    banner = data.decode(errors="ignore").strip()
        except Exception:
            pass
        writer.close()
        with contextlib_suppress(asyncio.CancelledError):
            await writer.wait_closed()
        return (ip, port, "open", banner)
    except (ConnectionRefusedError, OSError):
        # host up, port closed
        return (ip, port, "closed", None)
    except asyncio.TimeoutError:
        return (ip, port, "filtered", None)
    except Exception:
        return (ip, port, "unreachable", None)


class contextlib_suppress:
    def __init__(self, *exceptions):
        self.exceptions = exceptions

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return exc_type is not None and issubclass(exc_type, self.exceptions)


async def scan_tcp_ports(hosts: Iterable[str], ports: List[int], timeout: float, concurrency: int) -> Dict[str, Dict[int, PortResult]]:
    sem = asyncio.Semaphore(concurrency)
    results: Dict[str, Dict[int, PortResult]] = {}

    async def worker(ip: str, port: int):
        async with sem:
            ip_, port_, state, banner = await tcp_connect(ip, port, timeout)
            results.setdefault(ip_, {})[port_] = PortResult(port_, state, banner)

    tasks: List[asyncio.Task] = []
    for ip in hosts:
        for port in ports:
            tasks.append(asyncio.create_task(worker(ip, port)))
    if tasks:
        await asyncio.gather(*tasks)
    return results


# ------------------------- Protocol Hints / Enrichment -----------------------


async def modbus_device_id(ip: str, port: int = 502, timeout: float = 0.6) -> Optional[str]:
    """Try Modbus Read Device Identification (MEI 0x2B/0x0E). Returns short string or None."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        # MBAP header: tid=1, pid=0, length=6 (unit+PDU), unit=0x01
        pdu = bytes([0x2B, 0x0E, 0x01, 0x00, 0x00])
        mbap = struct.pack("!HHHB", 1, 0, len(pdu) + 1, 1)
        writer.write(mbap + pdu)
        await writer.drain()
        data = await asyncio.wait_for(reader.read(256), timeout=timeout)
        writer.close()
        with contextlib_suppress(asyncio.CancelledError):
            await writer.wait_closed()
        if not data or len(data) < 9:
            return None
        # naive extract: look for printable tail
        tail = data[-120:]
        txt = bytes([b for b in tail if 32 <= b <= 126]).decode(errors="ignore").strip()
        return txt or "Modbus device"
    except Exception:
        return None


def ethernetip_list_identity(broadcast_ip: str, bind_ip: Optional[str], timeout: float = 1.0, iface: Optional[str] = None) -> List[Dict[str, str]]:
    """Send EtherNet/IP ListIdentity (UDP/44818 broadcast). Returns list of dicts."""
    results: List[Dict[str, str]] = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        if bind_ip:
            try:
                sock.bind((bind_ip, 0))
            except Exception:
                pass
        # Encapsulation header: command=0x0063 (ListIdentity), length=0, session=0, status=0,
        # context=8 bytes, options=0
        header = struct.pack("<HHII8sI", 0x0063, 0, 0, 0, b"scanPLCs", 0)
        sock.sendto(header, (broadcast_ip, 44818))
        t_end = time.time() + timeout
        while time.time() < t_end:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                break
            ip, _ = addr
            name = _cip_guess_product_name(data)
            results.append({
                "ip": ip,
                "proto": "EtherNet/IP",
                "product": name or "(unknown)",
                "iface": iface or "",
            })
    except Exception:
        pass
    return results


def _cip_guess_product_name(packet: bytes) -> Optional[str]:
    """Heuristic: last bytes are [name_len][name][state]. Extract printable name."""
    if len(packet) < 60:
        return None
    tail = packet[-70:]
    # Look for plausible [len, ascii..., state]
    for i in range(len(tail) - 2, 0, -1):
        length = tail[i]
        if 1 <= length <= 64 and i - length >= 1:
            candidate = tail[i - length : i]
            try:
                s = candidate.decode("ascii")
            except Exception:
                continue
            if all(32 <= ord(c) <= 126 for c in s):
                return s.strip()
    return None


def bacnet_who_is(broadcast_ip: str, bind_ip: Optional[str], timeout: float = 1.0, iface: Optional[str] = None) -> List[Dict[str, str]]:
    """Send BACnet Who-Is (UDP/47808 broadcast). Return list of responders (IP only)."""
    results: List[Dict[str, str]] = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        if bind_ip:
            try:
                sock.bind((bind_ip, 0))
            except Exception:
                pass
        # Minimal BVLC (Original-Broadcast-NPDU) + NPDU + APDU (Who-Is)
        # BVLC: type=0x81, function=0x0b, length=0x0008 (entire BVLC PDU length)
        # NPDU: version=0x01, control=0x00 (no DNET/SNET fields present)
        # APDU: PDUType=0x10 (unconfirmed service request), ServiceChoice=0x08 (Who-Is)
        payload = bytes([0x81, 0x0B, 0x00, 0x08, 0x01, 0x00, 0x10, 0x08])
        sock.sendto(payload, (broadcast_ip, 47808))
        t_end = time.time() + timeout
        while time.time() < t_end:
            try:
                _data, addr = sock.recvfrom(2048)
            except socket.timeout:
                break
            ip, _ = addr
            results.append({
                "ip": ip,
                "proto": "BACnet",
                "iface": iface or "",
            })
    except Exception:
        pass
    return results


def which(cmd: str) -> Optional[str]:
    path = shutil_which(cmd)
    return path


def shutil_which(cmd: str) -> Optional[str]:
    for p in os.environ.get("PATH", "").split(os.pathsep):
        f = os.path.join(p, cmd)
        if os.path.isfile(f) and os.access(f, os.X_OK):
            return f
    return None


def try_nmap(hosts: List[str], ports: List[int], os_detect: bool = False) -> Optional[str]:
    nmap = which("nmap")
    if not nmap:
        return None
    port_list = ",".join(str(p) for p in ports)
    args = [nmap, "-n", "-T4", "--open", "-p", port_list]
    if os_detect:
        args.append("-O")
    # Chunk host list to avoid super long shell cmds
    out_all = []
    chunk = 256
    for i in range(0, len(hosts), chunk):
        sub = hosts[i:i+chunk]
        cmd = " ".join(shlex.quote(a) for a in args + sub)
        out_all.append(run_cmd(cmd))
    return "\n".join(out_all)


# ----------------------------------- CLI ------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Discover PLC-like devices on 169.254.x.x networks")
    p.add_argument("--mode", choices=["quick", "sweep", "arp", "nmap", "all"], default="quick",
                   help="quick=ARP IPs + TCP/UDP probes; sweep=/24 TCP scan; arp=just list; nmap=only nmap; all=quick+sweep")
    p.add_argument("--ports", default="502,102,44818,20000",
                   help="Comma-separated TCP ports to scan")
    p.add_argument("--timeout", type=float, default=0.6, help="TCP/UDP timeout seconds")
    p.add_argument("--concurrency", type=int, default=512, help="Concurrent TCP connections")
    p.add_argument("--cidr", type=int, default=24, help="CIDR to sweep per 169.254 iface (16-30)")
    p.add_argument("--max-hosts", type=int, default=4096, help="Safety cap for host count")
    p.add_argument("--iface", action="append", help="Limit to specific interface(s), e.g., en0")
    p.add_argument("--ethernet-ip", action="store_true", help="Send EtherNet/IP ListIdentity broadcast")
    p.add_argument("--bacnet", action="store_true", help="Send BACnet Who-Is broadcast")
    p.add_argument("--nmap", action="store_true", help="Also run nmap if present")
    p.add_argument("--os-detect", action="store_true", help="Use nmap -O (requires sudo)")
    p.add_argument("--json-out", help="Write JSON results to file path")
    return p.parse_args()


def unique(seq: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def main() -> int:
    args = parse_args()
    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]

    # Interfaces and ARP
    ifaces_all = parse_ifconfig_linklocal()
    if args.iface:
        ifaces_all = [i for i in ifaces_all if i.name in args.iface]
    if not ifaces_all:
        log("No 169.254.x.x interfaces found. Nothing to scan.")
        return 0

    log("Link-local interfaces:")
    for inf in ifaces_all:
        log(f"  {inf.name}: {inf.ipv4} mask {inf.netmask} bcast {inf.broadcast}")

    arp_entries = parse_arp_linklocal()
    arp_ips = [ip for (ip, _mac, iface) in arp_entries if (not args.iface or iface in args.iface)]
    if arp_ips:
        log(f"ARP cache has {len(arp_ips)} link-local entries")
    else:
        log("No 169.254 entries in ARP cache")

    candidates_quick = unique(arp_ips)

    # Build sweep networks
    sweep_networks = choose_networks(ifaces_all, args.cidr)
    sweep_hosts: List[str] = []
    for net in sweep_networks:
        # Avoid .0 and .255 for /24; iterate over hosts()
        for ip in net.hosts():
            s = str(ip)
            if s.startswith("169.254."):
                sweep_hosts.append(s)

    # Safety cap
    if len(sweep_hosts) > args.max_hosts:
        log(f"Sweeps capped to {args.max_hosts} of {len(sweep_hosts)} hosts; raise --max-hosts to override")
        sweep_hosts = sweep_hosts[: args.max_hosts]

    # Decide host lists
    hosts_quick = candidates_quick
    hosts_sweep = sweep_hosts

    all_devices: Dict[str, DeviceCandidate] = {}

    async def do_quick():
        if not hosts_quick:
            return
        log(f"Quick TCP scan of {len(hosts_quick)} ARP hosts on ports {ports}")
        res = await scan_tcp_ports(hosts_quick, ports, args.timeout, args.concurrency)
        for ip, prts in res.items():
            all_devices[ip] = DeviceCandidate(ip=ip, iface=None, ports=prts, tags=[], extra={})

    async def do_sweep():
        if not hosts_sweep:
            return
        log(f"Sweep TCP scan of {len(hosts_sweep)} hosts (/ {args.cidr}) on ports {ports}")
        res = await scan_tcp_ports(hosts_sweep, ports, args.timeout, args.concurrency)
        for ip, prts in res.items():
            # Only record hosts that responded at least with closed or open (i.e., were reachable)
            any_response = any(v.state in ("open", "closed") for v in prts.values())
            if any_response:
                all_devices[ip] = DeviceCandidate(ip=ip, iface=None, ports=prts, tags=[], extra={})

    async def do_enrich():
        # Tagging and Modbus ID attempts for open 502
        tasks: List[asyncio.Task] = []
        for dev in list(all_devices.values()):
            pmap = dev.ports
            if 502 in pmap and pmap[502].state == "open":
                dev.tags.append("modbus-tcp")
                tasks.append(asyncio.create_task(modbus_device_id(dev.ip)))
            if 102 in pmap and pmap[102].state == "open":
                dev.tags.append("siemens-s7")
            if 44818 in pmap and pmap[44818].state == "open":
                dev.tags.append("ethernet-ip")
            if 20000 in pmap and pmap[20000].state == "open":
                dev.tags.append("dnp3")
        if tasks:
            log("Probing Modbus device identification on hosts with 502/tcp open")
            mods = await asyncio.gather(*tasks)
            idx = 0
            for dev in list(all_devices.values()):
                if "modbus-tcp" in dev.tags:
                    info = mods[idx]
                    idx += 1
                    if info:
                        dev.extra["modbus_ident"] = info

    # Run desired modes
    loop = asyncio.get_event_loop()
    if args.mode in ("quick", "all"):
        loop.run_until_complete(do_quick())
    if args.mode in ("sweep", "all"):
        loop.run_until_complete(do_sweep())
    if all_devices:
        loop.run_until_complete(do_enrich())

    # Broadcast discoveries
    broadcast_results: List[Dict[str, str]] = []
    if args.ethernet_ip or args.bacnet:
        for inf in ifaces_all:
            bcast = inf.broadcast or "169.254.255.255"
            bind_ip = inf.ipv4
            if args.ethernet_ip:
                log(f"EtherNet/IP ListIdentity via {inf.name} -> {bcast}")
                broadcast_results += ethernetip_list_identity(bcast, bind_ip, timeout=args.timeout, iface=inf.name)
            if args.bacnet:
                log(f"BACnet Who-Is via {inf.name} -> {bcast}")
                broadcast_results += bacnet_who_is(bcast, bind_ip, timeout=args.timeout, iface=inf.name)

    # nmap optional
    nmap_txt: Optional[str] = None
    if args.nmap or args.mode == "nmap":
        host_union: List[str] = []
        if args.mode == "nmap":
            # Use sweep hosts if any, else ARP hosts
            host_union = hosts_sweep or hosts_quick
        else:
            host_union = list({*hosts_quick, *hosts_sweep})
        if host_union:
            log(f"nmap pass on {len(host_union)} hosts (if nmap present)")
            nmap_txt = try_nmap(host_union, ports, os_detect=args.os_detect)
            if nmap_txt:
                log("nmap results captured (truncated display)")
                print("\n".join(nmap_txt.splitlines()[:30]))

    # Summarize
    if not all_devices and not broadcast_results and not nmap_txt:
        log("No candidates found (try --sweep, larger --timeout, or --cidr 16 with caution)")
    else:
        log("Candidates:")
        for ip, dev in sorted(all_devices.items()):
            tags = ",".join(sorted(set(dev.tags)))
            states = ", ".join(f"{p}/{dev.ports[p].state}" for p in sorted(dev.ports))
            line = f"  {ip}: {states}"
            if tags:
                line += f"  [{tags}]"
            if dev.extra.get("modbus_ident"):
                line += f"  id='{dev.extra['modbus_ident'][:60]}'"
            print(line)
        if broadcast_results:
            log("UDP discovery responders:")
            for br in broadcast_results:
                prod = (f" product='{br['product']}'" if 'product' in br else "")
                print(f"  {br['ip']}  proto={br['proto']} iface={br.get('iface','')}{prod}")

    # JSON
    if args.json_out:
        out = {
            "interfaces": [asdict(i) for i in ifaces_all],
            "arp": arp_entries,
            "devices": {ip: {
                "ports": {str(p): asdict(pr) for p, pr in dev.ports.items()},
                "tags": dev.tags,
                "extra": dev.extra,
            } for ip, dev in all_devices.items()},
            "udp_discovery": broadcast_results,
            "nmap": nmap_txt,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(args.json_out, "w") as f:
            json.dump(out, f, indent=2)
        log(f"Wrote JSON to {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
