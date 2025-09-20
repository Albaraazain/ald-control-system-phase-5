# Headless Launcher Guide

The ALD Control System now runs headlessly (no web UI). This guide explains how to start/stop the backend service and run diagnostics.

## Quick Start

### 1) Environment Setup
```bash
./scripts/setup_environment.sh
```

### 2) Configure `.env`
Create a `.env` with your Supabase credentials:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

### 3) Start the Core Service
```bash
python main.py --demo                       # simulation
python main.py --plc real --ip 192.168.1.50 --port 502
```

Or use the helper:
```bash
./start_ald_system.sh
```

## Scripts

- `scripts/start_main_service.sh` – start backend quickly
- `scripts/doctor.sh` – run connectivity diagnostics
- `stop_ald_system.sh` – stop any running backend process

## Notes
 
- This backend runs headlessly; no web UI is included.
