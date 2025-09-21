# Network Latency Stress Testing Suite

Comprehensive network latency and timeout stress testing for the continuous parameter logging system, targeting the critical 1-second logging interval constraint.

## Overview

This testing suite validates system behavior under extreme network conditions including high latency, packet loss, jitter, bandwidth throttling, and timeout edge cases. The tests are specifically designed to validate the continuous parameter logging system's ability to maintain its 1-second target logging interval under network stress.

## Critical Issues Identified

Based on analysis of the continuous parameter logging system, several critical timing vulnerabilities have been identified:

- **650-1600ms total latency** exceeds the 1-second logging window under normal conditions
- **Sequential blocking operations** prevent real-time performance
- **No connection pooling** compounds database latency issues
- **100-500ms PLC read latency** per operation, amplified by network conditions
- **200-800ms database operations** without timeout controls

## Test Components

### 1. Network Latency Stress Test (`test_network_latency_stress.py`)

Comprehensive stress test that validates system behavior under various network conditions:

#### Network Conditions Tested
- **High Latency**: 500ms - 5000ms latency simulation
- **Packet Loss**: 5% - 50% packet drop rates
- **Network Jitter**: Variable latency patterns up to 1000ms variance
- **Bandwidth Throttling**: 56k modem to 1Mbps connection simulation
- **Combined Conditions**: Worst-case scenarios with multiple constraints

#### Key Metrics Measured
- PLC operation latency under network stress
- Database operation latency under network stress
- Continuous logging timing accuracy
- Timeout behavior validation
- Connection recovery timing

### 2. Network Simulation Utilities (`network_simulation_utils.py`)

Provides network simulation capabilities using Linux traffic control (tc/netem):

#### Features
- Network latency simulation with jitter
- Packet loss simulation
- Bandwidth throttling
- Real-time network monitoring
- Timeout configuration analysis
- Performance baseline measurement

### 3. Test Runner Script (`run_network_latency_stress_test.sh`)

Automated test execution with comprehensive reporting:

#### Features
- Prerequisites checking
- System information collection
- Pre-test validation
- Automated test execution
- Results analysis
- HTML report generation
- Cleanup and recovery

## Usage

### Quick Start

```bash
# Basic test (3 minutes, requires root for full network simulation)
sudo ./tools/debug/run_network_latency_stress_test.sh

# Extended test (10 minutes)
sudo ./tools/debug/run_network_latency_stress_test.sh 600

# Test without network simulation (limited functionality)
./tools/debug/run_network_latency_stress_test.sh 180
```

### Manual Test Execution

```bash
# Setup environment
cd /path/to/ald-control-system-phase-5
python -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt

# Run individual components
python tools/debug/test_network_latency_stress.py
python tools/debug/network_simulation_utils.py
```

## Prerequisites

### Required Packages
- **Python 3.7+** with asyncio support
- **iproute2** package for tc (traffic control) - `sudo apt-get install iproute2`
- **Project dependencies** from requirements.txt

### Permissions
- **Root privileges** required for full network simulation using tc/netem
- **Database access** configured in .env file
- **PLC access** configured (if available)

### System Requirements
- **Linux OS** with tc/netem support (optimal)
- **macOS/Windows** limited network simulation capabilities
- **Network interfaces** available for traffic control

## Test Results Interpretation

### Success Criteria
- **Latency Budget**: Total operation latency should stay under 1000ms
- **Timing Accuracy**: 95%+ of logging intervals should be on-time (±100ms)
- **Network Resilience**: 70%+ success rate under all network conditions
- **Recovery Performance**: Connection recovery within configured timeouts

### Critical Findings Classification

#### ✅ PASS Conditions
- Average latency < 800ms under normal conditions
- 95%+ timing accuracy for continuous logging
- Successful recovery from all simulated network failures
- No timeouts under reasonable network stress

#### ⚠️ WARNING Conditions
- Average latency 800-1200ms (approaching limit)
- Timing accuracy 80-95% (marginal performance)
- Some failures under extreme network conditions
- Occasional timeouts under high latency

#### ❌ FAIL Conditions
- Average latency > 1200ms (exceeds constraint)
- Timing accuracy < 80% (unacceptable drift)
- Systematic failures under network stress
- Frequent timeouts or connection failures

## Network Simulation Details

### TC/Netem Commands Used

```bash
# High latency simulation
tc qdisc add dev lo root netem delay 1000ms 100ms

# Packet loss simulation
tc qdisc add dev lo root netem loss 15%

# Bandwidth throttling
tc qdisc add dev lo root tbf rate 256kbit burst 32kbit latency 50ms

# Combined worst-case
tc qdisc add dev lo root handle 1: netem delay 2000ms 500ms loss 20%
tc qdisc add dev lo parent 1:1 handle 10: tbf rate 128kbit burst 16kbit latency 50ms
```

### Monitoring Commands

```bash
# View active tc rules
tc qdisc show

# Clear all rules
tc qdisc del dev lo root

# Monitor network statistics
ss -tuln
ping -c 5 127.0.0.1
```

## Timeout Configuration Recommendations

Based on network stress testing results, the following timeout configurations are recommended:

### Current Issues
- **Connection timeout**: 10s may be insufficient under high latency
- **Operation retry delay**: 0.5s too aggressive for high-latency conditions
- **Max retries**: Fixed at 3, should be adaptive based on network conditions

### Recommended Adaptive Timeouts

| Network Condition | Connection Timeout | Operation Timeout | Retry Delay | Max Retries |
|---|---|---|---|---|
| Normal (< 100ms) | 10s | 5s | 0.5s | 2 |
| High Latency (500ms+) | 20s | 15s | 2s | 3 |
| Packet Loss (> 10%) | 15s | 10s | 1s | 5 |
| Extreme (2000ms+) | 30s | 25s | 5s | 3 |

### Implementation Strategy
1. **Dynamic timeout calculation** based on measured network conditions
2. **Circuit breaker pattern** for persistent failures
3. **Exponential backoff** with jitter for retries
4. **Connection pooling** to amortize connection overhead
5. **Parallel operations** to reduce total latency

## Integration with Continuous Integration

### Automated Testing
```yaml
# Example CI pipeline step
- name: Network Latency Stress Test
  run: |
    sudo ./tools/debug/run_network_latency_stress_test.sh 120
    if [ $? -ne 0 ]; then
      echo "Network stress test failed"
      exit 1
    fi
```

### Performance Regression Detection
- **Baseline measurements** stored for comparison
- **Performance thresholds** enforced in CI pipeline
- **Automated alerting** on regression detection

## Troubleshooting

### Common Issues

#### "Permission denied" for tc commands
```bash
# Run with sudo
sudo ./run_network_latency_stress_test.sh

# Or grant tc capabilities
sudo setcap cap_net_admin+ep $(which tc)
```

#### Network simulation not working
```bash
# Check tc availability
which tc

# Check kernel modules
lsmod | grep sch_netem

# Install missing packages
sudo apt-get install iproute2
```

#### Test timeouts or hangs
```bash
# Check for lingering tc rules
tc qdisc show

# Clear all rules
sudo tc qdisc del dev lo root

# Check database connectivity
python -c "from src.db import get_supabase; print(get_supabase().table('machines').select('id').limit(1).execute())"
```

### Log Analysis
- **Test logs**: Located in `test_results/network_latency_stress/`
- **System logs**: Check `/var/log/syslog` for network-related errors
- **Application logs**: Review continuous parameter logger output

## Future Enhancements

### Planned Improvements
1. **Real-time network condition detection** and adaptive timeout adjustment
2. **Distributed testing** across multiple network nodes
3. **Integration with network monitoring tools** (SNMP, Prometheus)
4. **Machine learning-based** timeout optimization
5. **Geographic latency simulation** for distributed deployments

### Additional Test Scenarios
- **DNS resolution failures** and fallback mechanisms
- **IPv6 vs IPv4** performance comparison
- **Mobile network simulation** (3G/4G/5G latency profiles)
- **Satellite connection simulation** (very high latency)
- **Network partition scenarios** (split-brain conditions)

## References

- [Linux Traffic Control Documentation](https://tldp.org/HOWTO/Traffic-Control-HOWTO/)
- [Network Emulation with Netem](https://wiki.linuxfoundation.org/networking/netem)
- [TCP Performance Tuning](https://www.kernel.org/doc/Documentation/networking/ip-sysctl.txt)
- [Continuous Parameter Logging Implementation](src/data_collection/continuous_parameter_logger.py)
- [PLC Communication Layer](src/plc/communicator.py)