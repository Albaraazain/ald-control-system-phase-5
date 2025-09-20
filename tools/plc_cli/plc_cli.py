#!/usr/bin/env python3
"""
Focused PLC CLI for connectivity + typed read/write with byte order control.

Supports two modes:
- real: use Modbus TCP via PLCCommunicator (pymodbus required)
- simulation: route to SimulationPLC through plc_manager for quick local checks
"""
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add repo to path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.plc.manager import plc_manager
from src.config import PLC_CONFIG  # pulls defaults/IP from env


def _load_env():
    env = REPO_ROOT / '.env'
    if env.exists():
        load_dotenv(env)


def _get_byte_order(args):
    if args.byte_order:
        os.environ['PLC_BYTE_ORDER'] = args.byte_order
    return os.environ.get('PLC_BYTE_ORDER', 'badc')


def _ensure_mode(args):
    mode = args.mode or os.environ.get('PLC_TYPE', 'real')
    if mode not in ('real', 'simulation'):
        raise SystemExit(f"Invalid mode: {mode} (use 'real' or 'simulation')")
    os.environ['PLC_TYPE'] = mode
    return mode


def _mk_communicator(args):
    # Lazy import to avoid pymodbus requirement when in simulation
    from src.plc.communicator import PLCCommunicator
    host = args.host or os.environ.get('PLC_IP', PLC_CONFIG.get('ip_address')) or '127.0.0.1'
    port = int(args.port or os.environ.get('PLC_PORT', PLC_CONFIG.get('port', 502)) or 502)
    bo = _get_byte_order(args)
    hostname = args.hostname
    auto_disc = args.auto_discover
    comm = PLCCommunicator(
        plc_ip=host, port=port, hostname=hostname, auto_discover=auto_disc, byte_order=bo
    )
    if not comm.connect():
        raise SystemExit(f"Failed to connect to PLC at {hostname or host}:{port}")
    return comm


def cmd_connect_test(args):
    mode = _ensure_mode(args)
    _get_byte_order(args)
    if mode == 'simulation':
        ok = sys_run(async_fn=plc_manager.initialize, plc_type='simulation')
        print(f"SIM CONNECT: {'OK' if ok else 'FAIL'}")
        return 0 if ok else 2
    else:
        comm = _mk_communicator(args)
        print("REAL CONNECT: OK")
        comm.disconnect()
        return 0


def sys_run(async_fn, *a, **kw):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(async_fn(*a, **kw))


def cmd_read_coil(args):
    mode = _ensure_mode(args)
    if mode == 'simulation':
        ok = sys_run(plc_manager.initialize, plc_type='simulation')
        if not ok:
            raise SystemExit("Simulation PLC init failed")
        vals = sys_run(plc_manager.plc.read_coils, args.addr, args.count)
        print(vals)
        sys_run(plc_manager.disconnect)
    else:
        comm = _mk_communicator(args)
        vals = comm.read_coils(args.addr, count=args.count)
        print(vals)
        comm.disconnect()


def cmd_write_coil(args):
    mode = _ensure_mode(args)
    val = True if str(args.value).lower() in ('1', 'on', 'true', 't') else False
    if mode == 'simulation':
        ok = sys_run(plc_manager.initialize, plc_type='simulation')
        if not ok:
            raise SystemExit("Simulation PLC init failed")
        ok = sys_run(plc_manager.plc.write_coil, args.addr, val)
        print('OK' if ok else 'FAIL')
        sys_run(plc_manager.disconnect)
    else:
        comm = _mk_communicator(args)
        print('OK' if comm.write_coil(args.addr, val) else 'FAIL')
        comm.disconnect()


def cmd_read_reg(args):
    mode = _ensure_mode(args)
    _get_byte_order(args)
    if mode == 'simulation':
        ok = sys_run(plc_manager.initialize, plc_type='simulation')
        if not ok:
            raise SystemExit("Simulation PLC init failed")
        if args.type == 'float' or args.type == 'int32':
            # Use our shimmed helpers in SimulationPLC
            fn = 'read_holding_register' if args.space == 'holding' else 'read_holding_register'
            val = sys_run(getattr(plc_manager.plc, fn), args.addr)
            print(val)
        elif args.type == 'int16':
            # Not modeled in simulation precisely; return 0. Use real for exact behavior.
            print(0)
        sys_run(plc_manager.disconnect)
    else:
        comm = _mk_communicator(args)
        bo = os.environ.get('PLC_BYTE_ORDER', 'badc')
        if args.space == 'holding':
            if args.type == 'float':
                val = comm.read_float(args.addr)
            elif args.type == 'int32':
                val = comm.read_integer_32bit(args.addr)
            elif args.type == 'int16':
                res = comm.client.read_holding_registers(args.addr, count=1, slave=comm.slave_id)
                val = None if res.isError() else res.registers[0]
            else:
                raise SystemExit('Unsupported type')
        else:  # input space
            res = comm.client.read_input_registers(args.addr, count=2 if args.type in ('float','int32') else 1, slave=comm.slave_id)
            if res.isError():
                comm.disconnect()
                raise SystemExit(f"Read failed: {res}")
            if args.type == 'int16':
                val = res.registers[0]
            else:
                r0, r1 = res.registers
                import struct
                if bo in ('abcd','cdab'):
                    words = (r0, r1)
                else:
                    words = (r1, r0)
                if args.type == 'float':
                    fmt_words = '>HH' if bo in ('abcd','badc') else '<HH'
                    fmt_val = '>f' if bo in ('abcd','badc') else '<f'
                    packed = struct.pack(fmt_words, *words)
                    val = struct.unpack(fmt_val, packed)[0]
                elif args.type == 'int32':
                    fmt_words = '>HH' if bo in ('abcd','badc') else '<HH'
                    fmt_val = '>i' if bo in ('abcd','badc') else '<i'
                    packed = struct.pack(fmt_words, *words)
                    val = struct.unpack(fmt_val, packed)[0]
                else:
                    raise SystemExit('Unsupported type')
        print(val)
        comm.disconnect()


def cmd_write_reg(args):
    mode = _ensure_mode(args)
    _get_byte_order(args)
    if mode == 'simulation':
        ok = sys_run(plc_manager.initialize)
        if not ok:
            raise SystemExit("Simulation PLC init failed")
        if args.type == 'float' or args.type == 'int32':
            fn = 'write_holding_register'
            ok = sys_run(getattr(plc_manager.plc, fn), args.addr, float(args.value))
            print('OK' if ok else 'FAIL')
        elif args.type == 'int16':
            ok = sys_run(plc_manager.plc.write_holding_register, args.addr, int(args.value))
            print('OK' if ok else 'FAIL')
        sys_run(plc_manager.disconnect)
    else:
        comm = _mk_communicator(args)
        if args.type == 'float':
            ok = comm.write_float(args.addr, float(args.value))
        elif args.type == 'int32':
            ok = comm.write_integer_32bit(args.addr, int(args.value))
        elif args.type == 'int16':
            res = comm.client.write_register(args.addr, int(args.value), slave=comm.slave_id)
            ok = not res.isError()
        else:
            raise SystemExit('Unsupported type')
        print('OK' if ok else 'FAIL')
        comm.disconnect()


def cmd_interpret(args):
    """Read 2 registers and print all interpretations for byte orders."""
    from src.plc.communicator import PLCCommunicator
    comm = _mk_communicator(args)
    res = comm.client.read_holding_registers(args.addr, count=2, slave=comm.slave_id)
    if res.isError():
        comm.disconnect()
        raise SystemExit(f"Read failed: {res}")
    r0, r1 = res.registers
    print(f"Raw: [{r0}, {r1}]  hex: [0x{r0:04x}, 0x{r1:04x}]")
    import struct
    combos = {
        'abcd': ('>HH', '>f', '>i'),
        'badc': ('>HH', '>f', '>i'),
        'cdab': ('<HH', '<f', '<i'),
        'dcba': ('<HH', '<f', '<i'),
    }
    for bo, (ph, pf, pi) in combos.items():
        if bo in ('abcd', 'cdab'):
            words = (r0, r1)
        else:
            words = (r1, r0)
        packed = struct.pack(ph, *words)
        fval = struct.unpack(pf, packed)[0]
        ival = struct.unpack(pi, packed)[0]
        print(f"{bo:>4} -> float={fval}, int32={ival}")
    comm.disconnect()


def build_parser():
    p = argparse.ArgumentParser(description='PLC CLI (connectivity + typed IO)')
    p.add_argument('--mode', choices=['real', 'simulation'], help='Target mode (default: env PLC_TYPE or real)')
    p.add_argument('--host', help='PLC IP for real mode')
    p.add_argument('--port', type=int, help='PLC port (default 502)')
    p.add_argument('--hostname', help='mDNS/DHCP hostname (optional)')
    p.add_argument('--auto-discover', action='store_true', help='Attempt network discovery for real mode')
    p.add_argument('--byte-order', choices=['abcd','badc','cdab','dcba'], help='32-bit byte order')

    sp = p.add_subparsers(dest='cmd', required=True)

    sp_ct = sp.add_parser('connect-test', help='Connect and report success')
    sp_ct.set_defaults(func=cmd_connect_test)

    sp_rc = sp.add_parser('read-coil', help='Read N coils (default 1)')
    sp_rc.add_argument('--addr', type=int, required=True)
    sp_rc.add_argument('--count', type=int, default=1)
    sp_rc.set_defaults(func=cmd_read_coil)

    sp_wc = sp.add_parser('write-coil', help='Write a coil ON/OFF')
    sp_wc.add_argument('--addr', type=int, required=True)
    sp_wc.add_argument('--value', required=True, help='on/off/1/0')
    sp_wc.set_defaults(func=cmd_write_coil)

    sp_rr = sp.add_parser('read-reg', help='Read register as specific type')
    sp_rr.add_argument('--addr', type=int, required=True)
    sp_rr.add_argument('--type', choices=['float','int32','int16'], required=True)
    sp_rr.add_argument('--space', choices=['holding','input'], default='holding')
    sp_rr.set_defaults(func=cmd_read_reg)

    sp_wr = sp.add_parser('write-reg', help='Write register as specific type')
    sp_wr.add_argument('--addr', type=int, required=True)
    sp_wr.add_argument('--type', choices=['float','int32','int16'], required=True)
    sp_wr.add_argument('--value', required=True)
    sp_wr.set_defaults(func=cmd_write_reg)

    sp_it = sp.add_parser('interpret', help='Read 2 regs and print float/int32 under all byte orders')
    sp_it.add_argument('--addr', type=int, required=True)
    sp_it.add_argument('--space', choices=['holding'], default='holding')
    sp_it.set_defaults(func=cmd_interpret)

    return p


def main():
    _load_env()
    parser = build_parser()
    args = parser.parse_args()
    rc = args.func(args)
    if isinstance(rc, int):
        sys.exit(rc)


if __name__ == '__main__':
    main()
