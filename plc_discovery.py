
#!/usr/bin/env python3
"""
plc_discovery.py
----------------

Multi‑protocol PLC "discovery" helper that can:
  • Broadcast‑discover EtherNet/IP (CIP) devices (Allen‑Bradley, etc.) via pycomm3
  • Discover PROFINET devices via DCP (pnio-dcp or profi-dcp)
  • Sweep subnets for Modbus/TCP (port 502) and optionally query Device Identification
  • Sweep subnets for Siemens S7 endpoints (port 102)

Notes & dependencies:
  - CIP discovery requires:   pip install pycomm3
  - PROFINET DCP requires:    pip install pnio-dcp   (or)   pip install profi-dcp
      * Windows needs Npcap; Linux typically needs root for raw sockets.
  - Modbus enrichment (Device Identification) requires: pip install pymodbus

USAGE EXAMPLES
--------------
  # Discover CIP and PROFINET on your LAN (broadcast/DCP) and skip subnet scans
  python plc_discovery.py --protocols cip,profinet

  # Add Modbus and S7 sweeps across a /24
  python plc_discovery.py --subnets 192.168.1.0/24 --protocols modbus,s7

  # Everything (CIP+DCP+broadcast) plus targeted Modbus/S7 sweeps on two subnets
  python plc_discovery.py --subnets 192.168.1.0/24,10.10.0.0/24

  # If DCP fails to auto-pick your NIC, pass your local NIC IPv4 for PROFINET
  python plc_discovery.py --dcp-local-ip 192.168.1.50 --protocols profinet

DISCLAIMER
----------
Only scan networks you own or have explicit authorization to test.

References:
  - CIP broadcast discovery via pycomm3.CIPDriver.discover()
  - PROFINET DCP identify via pnio_dcp.DCP(...).identify_all()
  - Modbus Device Identification (MEI 0x2B/0x0E) via PyModbus read_device_information()

"""
import argparse
import asyncio
import ipaddress
import json
import logging
import socket
import sys
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Optional NIC enumeration for convenience
try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # noqa: N816

__version__ = "0.4.0"


@dataclass
class Finding:
    protocol: str
    ip: Optional[str] = None
    port: Optional[int] = None
    mac: Optional[str] = None
    name: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    extra: Dict[str, Any] = None  # raw identity or arbitrary fields


def get_local_ipv4_candidates() -> List[str]:
    """Return candidate local IPv4 addresses for this host (best-effort)."""
    candidates: List[str] = []
    # Prefer psutil if available
    if psutil:
        try:
            for ifname, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if getattr(a, "family", None) == socket.AF_INET and a.address != "127.0.0.1":
                        candidates.append(a.address)
        except Exception:
            pass
    # Fallback: hostname lookup (often unreliable on Linux)
    try:
        host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        for ip in host_ips:
            if ip and ip != "127.0.0.1" and ip not in candidates:
                candidates.append(ip)
    except Exception:
        pass
    return candidates


def choose_default_local_ipv4() -> Optional[str]:
    cands = get_local_ipv4_candidates()
    return cands[0] if cands else None


# ---------------------------- NIC helpers -------------------------------- #
def _ipv4_interface_from(ip: str, netmask: Optional[str]) -> Optional[ipaddress.IPv4Interface]:
    try:
        if netmask:
            return ipaddress.IPv4Interface(f"{ip}/{netmask}")
        # If no netmask, assume /24 as a reasonable local default
        return ipaddress.IPv4Interface(f"{ip}/255.255.255.0")
    except Exception:
        return None


def get_broadcast_candidates(prefer_non_global: bool = True) -> List[str]:
    """Compute candidate IPv4 broadcast addresses from local interfaces.

    - Prefers interface-scoped broadcasts over 255.255.255.255 on macOS where
      global broadcast often fails with OSError(Errno 49).
    - Falls back to 255.255.255.255 if nothing else is available.
    """
    broadcasts: List[str] = []
    seen: set[str] = set()

    # Prefer psutil when present (gives netmask and broadcast)
    if psutil:
        try:
            for ifname, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if getattr(a, "family", None) == socket.AF_INET and a.address != "127.0.0.1":
                        # Use provided broadcast if available; otherwise compute from netmask
                        bcast = getattr(a, "broadcast", None)
                        if not bcast and getattr(a, "netmask", None):
                            iface = _ipv4_interface_from(a.address, a.netmask)
                            if iface is not None:
                                bcast = str(iface.network.broadcast_address)
                        if bcast and bcast not in seen:
                            broadcasts.append(bcast)
                            seen.add(bcast)
        except Exception:
            pass

    # If nothing found, try to derive from hostname-resolved IPs with /24
    if not broadcasts:
        for ip in get_local_ipv4_candidates():
            iface = _ipv4_interface_from(ip, None)
            if iface is not None:
                bcast = str(iface.network.broadcast_address)
                if bcast not in seen:
                    broadcasts.append(bcast)
                    seen.add(bcast)

    # Fallback to global broadcast
    if not broadcasts or not prefer_non_global:
        if "255.255.255.255" not in seen:
            broadcasts.append("255.255.255.255")

    # Keep stable order, remove duplicates already ensured via 'seen'
    return broadcasts


# ---------------------------- CIP (EtherNet/IP) ---------------------------- #
def discover_cip(
    logger: logging.Logger,
    broadcast_addrs: Optional[Sequence[str]] = None,
    timeout: float = 2.0,
) -> Tuple[List[Finding], Optional[str]]:
    """Discover EtherNet/IP (CIP) devices using pycomm3 broadcast ListIdentity.

    On macOS, global broadcast (255.255.255.255) can fail with OSError Errno 49.
    Supplying interface-scoped broadcast(s) via `broadcast_addrs` avoids this.
    """
    try:
        from pycomm3 import CIPDriver  # type: ignore
    except Exception as e:
        return [], f"pycomm3 not available: {e}"

    # Inspect signature to check if current pycomm3 supports 'broadcast_address' and 'timeout'
    supports_addr = False
    supports_timeout = False
    try:
        import inspect  # local import to keep top clean

        sig = inspect.signature(CIPDriver.discover)
        supports_addr = any(p.name == "broadcast_address" for p in sig.parameters.values())
        supports_timeout = any(p.name == "timeout" for p in sig.parameters.values())
    except Exception:
        # Be conservative: call bare discover() if introspection fails
        supports_addr = False
        supports_timeout = False

    # Determine which broadcast addresses to try
    addrs: List[str] = []
    if broadcast_addrs:
        for a in broadcast_addrs:
            try:
                ipaddress.IPv4Address(a)
                addrs.append(a)
            except Exception:
                logger.debug("Ignoring invalid broadcast address: %s", a)
    else:
        addrs = get_broadcast_candidates(prefer_non_global=True)

    results: List[Finding] = []
    errors: List[str] = []

    def _call_discover_once(addr: Optional[str]):
        try:
            if supports_addr and supports_timeout:
                return CIPDriver.discover(broadcast_address=addr, timeout=timeout)  # type: ignore[arg-type]
            if supports_addr and not supports_timeout:
                return CIPDriver.discover(broadcast_address=addr)  # type: ignore[arg-type]
            if not supports_addr and supports_timeout:
                return CIPDriver.discover(timeout=timeout)
            return CIPDriver.discover()
        except OSError as oe:
            msg = str(oe)
            # macOS specific: Errno 49 - Can't assign requested address when sending to 255.255.255.255
            if getattr(oe, "errno", None) == 49 or "Errno 49" in msg or "Can't assign requested address" in msg:
                hint = (
                    "macOS cannot send global broadcast. Try --cip-broadcast with your interface's "
                    f"broadcast (e.g., {', '.join(get_broadcast_candidates())})."
                )
                errors.append(f"{msg} — {hint}")
                return None
            errors.append(msg)
            return None
        except Exception as e:
            errors.append(str(e))
            return None

    # Try each broadcast address; stop deduplicating identities later
    tried_any = False
    if addrs:
        for addr in addrs:
            tried_any = True
            identities = _call_discover_once(addr)
            for ident in identities or []:
                ip = ident.get("ip_address")
                vendor = ident.get("vendor")
                model = ident.get("product_name")
                extra = dict(ident)
                extra["probe"] = "cip-broadcast"
                results.append(
                    Finding(protocol="ethernet-ip/cip", ip=ip, vendor=vendor, model=model, extra=extra)
                )
    else:
        # As a last resort, attempt the library default
        identities = _call_discover_once(None)
        for ident in identities or []:
            ip = ident.get("ip_address")
            vendor = ident.get("vendor")
            model = ident.get("product_name")
            extra = dict(ident)
            extra["probe"] = "cip-broadcast"
            results.append(Finding(protocol="ethernet-ip/cip", ip=ip, vendor=vendor, model=model, extra=extra))

    logger.info("CIP discovered %d device(s) (tried %s)", len(results), ",".join(addrs) if addrs else "default")
    if results:
        return results, None
    # No results; surface best error hint if present
    err = "; ".join(errors) if errors else ("No CIP devices responded" if tried_any else "No broadcast attempted")
    return results, err


# --------------------- CIP Unicast (ListIdentity) ------------------------- #
def cip_list_identity_targets(logger: logging.Logger, ips: Sequence[str]) -> Tuple[List[Finding], Optional[str]]:
    """Query specific IPs with CIP ListIdentity over unicast TCP (pycomm3).

    Useful when broadcast discovery is blocked or the device is not on the
    same L2 segment. If a host refuses TCP/44818, it's likely not EtherNet/IP.
    """
    try:
        from pycomm3 import CIPDriver  # type: ignore
    except Exception as e:
        return [], f"pycomm3 not available: {e}"

    results: List[Finding] = []
    errors: List[str] = []
    for ip in ips:
        ip = ip.strip()
        if not ip:
            continue
        try:
            logger.debug("CIP unicast ListIdentity -> %s", ip)
            ident = CIPDriver.list_identity(ip)
        except Exception as e:  # pycomm3 raises CommError on connect/refused/timeouts
            errors.append(f"{ip}: {e}")
            continue
        if ident:
            vendor = ident.get("vendor")
            model = ident.get("product_name")
            extra = dict(ident)
            extra["probe"] = "cip-unicast"
            results.append(
                Finding(protocol="ethernet-ip/cip", ip=ip, vendor=vendor, model=model, extra=extra)
            )
        else:
            errors.append(f"{ip}: no identity returned")

    if results:
        logger.info("CIP unicast identified %d/%d target(s)", len(results), len([i for i in ips if i.strip()]))
    return results, "; ".join(errors) if errors and not results else None

# -------------------------- PROFINET (DCP Identify) ----------------------- #
def discover_profinet(logger: logging.Logger, local_ip: Optional[str]) -> Tuple[List[Finding], Optional[str]]:
    """Discover PROFINET devices using DCP Identify (pnio-dcp or profi-dcp)."""
    DCP = None
    err_msgs: List[str] = []
    try:
        from pnio_dcp import DCP as _DCP  # type: ignore
        DCP = _DCP
    except Exception as e:
        err_msgs.append(f"pnio-dcp not available: {e}")
        try:
            from profi_dcp import DCP as _DCP  # type: ignore
            DCP = _DCP
        except Exception as e2:
            err_msgs.append(f"profi-dcp not available: {e2}")

    if DCP is None:
        return [], "; ".join(err_msgs) if err_msgs else "Neither pnio-dcp nor profi-dcp installed"

    try:
        ip = local_ip or choose_default_local_ipv4()
        if not ip:
            return [], "Could not determine a local IPv4; pass --dcp-local-ip"
        dcp = DCP(ip)
        devices = dcp.identify_all()  # returns list of Device objects
    except Exception as e:
        return [], f"DCP identify failed: {e}"

    findings: List[Finding] = []
    for dev in devices or []:
        # The Device object attributes differ slightly by lib; use defensive getattr
        ip_addr = getattr(dev, "ip_address", None) or getattr(dev, "ip", None)
        mac = getattr(dev, "mac_address", None) or getattr(dev, "mac", None)
        name = getattr(dev, "name_of_station", None) or getattr(dev, "nameofstation", None) or getattr(dev, "name", None)
        vendor = getattr(dev, "vendor_name", None) or getattr(dev, "vendor", None)
        model = getattr(dev, "product_name", None) or getattr(dev, "model", None)
        # Try to stringify the object for raw details if available
        try:
            raw = dev.__dict__
        except Exception:
            raw = {"repr": repr(dev)}
        findings.append(Finding(protocol="profinet-dcp", ip=ip_addr, mac=mac, name=name, vendor=vendor, model=model, extra=raw))
    logger.info("PROFINET DCP identified %d device(s)", len(findings))
    return findings, None


# ---------------------------- TCP Sweep Helpers --------------------------- #
async def tcp_probe(ip: str, port: int, timeout: float) -> bool:
    """Return True if TCP connect succeeds within `timeout`."""
    try:
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def sweep_subnets_for_port(
    subnets: Sequence[str], port: int, timeout: float, concurrency: int, max_hosts: int
) -> List[str]:
    """Return list of IPs with `port` open across given CIDRs (respecting max_hosts)."""
    hosts: List[str] = []
    for cidr in subnets:
        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except Exception:
            continue
        for ip in net.hosts():
            hosts.append(str(ip))
            if len(hosts) >= max_hosts:
                break
        if len(hosts) >= max_hosts:
            break

    sem = asyncio.Semaphore(concurrency)
    found: List[str] = []

    async def worker(ip: str):
        async with sem:
            if await tcp_probe(ip, port, timeout):
                found.append(ip)

    await asyncio.gather(*(worker(h) for h in hosts))
    return found


# ------------------------ Modbus (port 502 + ID) -------------------------- #
def _pymodbus_read_device_id(ip: str, port: int, timeout: float) -> Optional[Dict[str, Any]]:
    """Try to read Modbus 'Device Identification' via PyModbus, return dict or None."""
    try:
        from pymodbus.client import ModbusTcpClient  # type: ignore
    except Exception:
        return None

    client = ModbusTcpClient(ip, port=port, timeout=timeout)
    if not client.connect():
        client.close()
        return None

    def _try_call(unit_param_name: str, unit: int):
        try:
            return getattr(client, "read_device_information")(**{unit_param_name: unit})
        except TypeError:
            return None
        except Exception:
            return None

    response = None
    # Try common unit identifiers
    for unit in (0xFF, 1, 0):
        for pname in ("unit", "slave", "device_id"):
            response = _try_call(pname, unit)
            if response and not getattr(response, "isError", lambda: False)():
                break
        if response and not getattr(response, "isError", lambda: False)():
            break

    result: Optional[Dict[str, Any]] = None
    if response and not getattr(response, "isError", lambda: False)():
        # PyModbus response typically has .information mapping object_id -> bytes/string
        info = getattr(response, "information", None)
        if isinstance(info, dict):
            cleaned: Dict[str, Any] = {}
            for k, v in info.items():
                if isinstance(v, (bytes, bytearray)):
                    try:
                        cleaned[str(k)] = v.decode(errors="ignore")
                    except Exception:
                        cleaned[str(k)] = repr(v)
                else:
                    cleaned[str(k)] = v
            result = cleaned
        else:
            result = {"raw": repr(response)}
    client.close()
    return result


async def scan_modbus(subnets: Sequence[str], timeout: float, concurrency: int, max_hosts: int) -> List[Finding]:
    """Scan for Modbus/TCP endpoints and enrich with Device Identification if possible."""
    ips = await sweep_subnets_for_port(subnets, port=502, timeout=timeout, concurrency=concurrency, max_hosts=max_hosts)
    findings: List[Finding] = []
    for ip in ips:
        ident = _pymodbus_read_device_id(ip, 502, timeout=timeout)
        extra: Dict[str, Any] = {"probe": "modbus-sweep"}
        if ident:
            extra["device_identification"] = ident
        findings.append(Finding(protocol="modbus-tcp", ip=ip, port=502, extra=extra))
    return findings


# ---------------- Targeted Modbus/S7 single-host checks ------------------- #
def modbus_ident_targets(logger: logging.Logger, ips: Sequence[str], timeout: float) -> List[Finding]:
    """Query specific IPs for Modbus/TCP Device Identification (if pymodbus present)."""
    out: List[Finding] = []
    for ip in ips:
        ip = ip.strip()
        if not ip:
            continue
        logger.debug("Modbus Device Identification -> %s:502", ip)
        ident = _pymodbus_read_device_id(ip, 502, timeout=timeout)
        extra: Dict[str, Any] = {"probe": "modbus-target"}
        if ident:
            extra["device_identification"] = ident
        out.append(Finding(protocol="modbus-tcp", ip=ip, port=502, extra=extra))
    return out


def s7_check_targets(logger: logging.Logger, ips: Sequence[str], timeout: float) -> List[Finding]:
    """Check specific IPs for open TCP/102 (Siemens S7)."""
    out: List[Finding] = []
    for ip in ips:
        ip = ip.strip()
        if not ip:
            continue
        try:
            logger.debug("S7 TCP/102 presence check -> %s:102", ip)
            ok = asyncio.run(tcp_probe(ip, 102, timeout))
        except Exception:
            ok = False
        if ok:
            out.append(Finding(protocol="siemens-s7", ip=ip, port=102, extra={"probe": "s7-target"}))
    return out

# ------------------------ Siemens S7 (port 102) --------------------------- #
async def scan_s7(subnets: Sequence[str], timeout: float, concurrency: int, max_hosts: int) -> List[Finding]:
    """Scan for TCP/102 endpoints (S7). Note: simple TCP presence only, no banner/handshake."""
    ips = await sweep_subnets_for_port(subnets, port=102, timeout=timeout, concurrency=concurrency, max_hosts=max_hosts)
    return [Finding(protocol="siemens-s7", ip=ip, port=102, extra={"probe": "s7-sweep"}) for ip in ips]


# ------------------------------- CLI -------------------------------------- #
def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Multi-protocol PLC discovery helper")
    ap.add_argument(
        "--subnets",
        help="Comma-separated IPv4 CIDRs to sweep for Modbus/S7 (e.g., 192.168.1.0/24,10.10.0.0/24)",
        default="",
    )
    ap.add_argument(
        "--protocols",
        help="Comma-separated set from {cip,profinet,modbus,s7}. Default: all",
        default="cip,profinet,modbus,s7",
    )
    ap.add_argument("--timeout", type=float, default=0.6, help="Socket timeout in seconds (connect / Modbus ID)")
    ap.add_argument("--concurrency", type=int, default=256, help="Max concurrent connection attempts for sweeps")
    ap.add_argument("--max-hosts", type=int, default=2048, help="Cap total hosts to scan across all subnets")
    ap.add_argument("--dcp-local-ip", default=None, help="Local NIC IPv4 to use for PROFINET DCP (if needed)")
    ap.add_argument(
        "--cip-broadcast",
        default=None,
        help=(
            "Comma-separated IPv4 broadcast address(es) to use for CIP discovery. "
            "On macOS, prefer interface broadcasts (e.g., 192.168.1.255) over 255.255.255.255."
        ),
    )
    ap.add_argument(
        "--suggest-cip-broadcasts",
        action="store_true",
        help="Print detected broadcast addresses from local interfaces and exit",
    )
    ap.add_argument(
        "--cip-targets",
        default=None,
        help=(
            "Comma-separated IPs for unicast CIP ListIdentity (TCP/44818). "
            "Use this when you know device IPs or broadcast fails."
        ),
    )
    ap.add_argument(
        "--modbus-targets",
        default=None,
        help=(
            "Comma-separated IPs to probe Modbus/TCP (port 502) and read Device Identification."
        ),
    )
    ap.add_argument(
        "--s7-targets",
        default=None,
        help=(
            "Comma-separated IPs to check for Siemens S7 TCP/102 (presence only)."
        ),
    )
    ap.add_argument("--json", dest="json_out", default=None, help="Write JSON results to this path")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON to stdout")
    ap.add_argument("--verbose", "-v", action="count", default=0, help="Increase log verbosity")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    level = logging.WARNING - (10 * min(args.verbose, 2))
    logging.basicConfig(level=max(level, logging.DEBUG if args.verbose >= 2 else level), format="%(levelname)s: %(message)s")
    logger = logging.getLogger("plc_discovery")
    logger.info("plc_discovery version %s", __version__)

    requested = {p.strip().lower() for p in args.protocols.split(",") if p.strip()}
    subnets = [s.strip() for s in args.subnets.split(",") if s.strip()]

    # Broadcast suggestions helper
    if args.suggest_cip_broadcasts:
        cands = get_broadcast_candidates()
        print("Suggested CIP broadcast address(es) based on local NICs:")
        for c in cands:
            print(f"  - {c}")
        print("Note: On macOS, 255.255.255.255 often fails. Prefer an interface broadcast above.")
        return 0

    all_findings: List[Finding] = []
    errors: Dict[str, str] = {}

    # CIP
    if "cip" in requested:
        cip_addrs = None
        if args.cip_broadcast:
            cip_addrs = [a.strip() for a in args.cip_broadcast.split(",") if a.strip()]
        else:
            # On macOS, proactively avoid global broadcast by suggesting interface-scoped broadcasts
            cip_addrs = get_broadcast_candidates(prefer_non_global=True)
            if sys.platform == "darwin":
                logger.info(
                    "macOS detected — using interface broadcast(s) for CIP: %s",
                    ", ".join(cip_addrs) if cip_addrs else "<none>",
                )

        cip_findings, err = discover_cip(logger, broadcast_addrs=cip_addrs, timeout=max(args.timeout, 0.5))
        if err:
            errors["cip"] = err
        all_findings.extend(cip_findings)

    # CIP unicast targets
    if args.cip_targets:
        ips = [a.strip() for a in args.cip_targets.split(",") if a.strip()]
        cip_uni_findings, err = cip_list_identity_targets(logger, ips)
        if err:
            errors["cip-unicast"] = err
        all_findings.extend(cip_uni_findings)

    # PROFINET
    if "profinet" in requested:
        if sys.platform == "darwin":
            logger.warning(
                "PROFINET DCP on macOS has limitations (raw sockets/BPF). "
                "If discovery fails, run this on Linux/Windows or use CIP/Modbus/S7 alternatives."
            )
        dcp_findings, err = discover_profinet(logger, args.dcp_local_ip)
        if err:
            errors["profinet"] = err
        all_findings.extend(dcp_findings)

    # Async sweeps (Modbus + S7)
    async def run_sweeps() -> Tuple[List[Finding], List[Finding]]:
        modbus_results: List[Finding] = []
        s7_results: List[Finding] = []

        tasks = []
        if "modbus" in requested:
            tasks.append(scan_modbus(subnets, args.timeout, args.concurrency, args.max_hosts))
        if "s7" in requested:
            tasks.append(scan_s7(subnets, args.timeout, args.concurrency, args.max_hosts))

        if not tasks:
            return modbus_results, s7_results

        done = await asyncio.gather(*tasks)
        idx = 0
        if "modbus" in requested:
            modbus_results = done[idx]; idx += 1
        if "s7" in requested:
            s7_results = done[idx] if idx < len(done) else []
        return modbus_results, s7_results

    if "modbus" in requested or "s7" in requested:
        if not subnets:
            logger.warning("No --subnets provided; skipping Modbus/S7 sweeps")
        else:
            try:
                modbus_findings, s7_findings = asyncio.run(run_sweeps())
                all_findings.extend(modbus_findings)
                all_findings.extend(s7_findings)
            except Exception as e:
                if "modbus" in requested:
                    errors["modbus"] = f"sweep failed: {e}"
                if "s7" in requested:
                    errors["s7"] = f"sweep failed: {e}"

    # Targeted Modbus/S7 probes
    if args.modbus_targets:
        ips = [a.strip() for a in args.modbus_targets.split(",") if a.strip()]
        all_findings.extend(modbus_ident_targets(logger, ips, args.timeout))
    if args.s7_targets:
        ips = [a.strip() for a in args.s7_targets.split(",") if a.strip()]
        all_findings.extend(s7_check_targets(logger, ips, args.timeout))

    # Deduplicate by (protocol, ip, port)
    dedup: Dict[Tuple[str, Optional[str], Optional[int]], Finding] = {}
    for f in all_findings:
        key = (f.protocol, f.ip, f.port)
        if key not in dedup:
            dedup[key] = f
        else:
            # merge extras
            a = dedup[key].extra or {}
            b = f.extra or {}
            merged = {**a, **b}
            dedup[key].extra = merged

    results = list(dedup.values())
    # Output
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump([asdict(f) for f in results], fh, indent=2 if args.pretty else None)
        print(f"Wrote JSON results to {args.json_out}")

    # Human-readable table-ish
    if results:
        print("\nDiscovered devices:")
        print(" protocol         ip              port   vendor/model/name")
        print(" ---------------- --------------- ------ ------------------------------")
        for f in results:
            label_parts = [p for p in [f.vendor, f.model, f.name] if p]
            label = " / ".join(label_parts) if label_parts else ""
            print(f" {f.protocol:<15} {f.ip or '':<15} {str(f.port or ''):<6} {label}")
    else:
        print("No devices discovered.")

    if errors:
        print("\nNotes / errors:")
        for k, v in errors.items():
            print(f"  {k}: {v}")

    # Optionally pretty-print JSON to stdout
    if args.pretty:
        print("\nRaw JSON:")
        print(json.dumps([asdict(f) for f in results], indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
