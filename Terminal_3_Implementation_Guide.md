# Terminal 3: Parameter Service Implementation Guide

## Overview

Terminal 3 is the Parameter Service component of the 3-terminal ALD control system. It provides **parameter control command processing** with validation, safety interlocks, and coordination with Terminal 1 for PLC hardware access.

## Key Architecture Principles

### 🚨 CRITICAL SAFETY RULE
**Terminal 3 NEVER directly accesses PLC hardware. All parameter updates must be coordinated through Terminal 1 via database communication.**

### Primary Responsibilities
1. **Parameter Control Command Processing**: Listen for and process parameter control commands
2. **Parameter Validation**: Safety checks, range validation, critical parameter interlocks
3. **Terminal 1 Coordination**: Database-driven communication for PLC parameter updates
4. **Audit Logging**: Track all parameter changes with complete audit trail

## Implementation Components

### Core Service: `parameter_service.py`
```bash
# Run Terminal 3 Parameter Service
python parameter_service.py --log-level INFO

# Configuration options
python parameter_service.py --max-retries 5 --retry-delay 10 --log-level DEBUG
```

**Key Features:**
- Standalone service with independent event loop
- Realtime + polling fallback for command processing
- Database coordination with Terminal 1
- Emergency coordination protocols
- Health monitoring and metrics

### Coordination Module: `src/terminal_coordination/parameter_coordinator.py`
```python
from src.terminal_coordination.parameter_coordinator import parameter_coordinator

# Coordinate parameter update with Terminal 1
success = await parameter_coordinator.coordinate_parameter_update(command)

# Monitor coordination health
health = await parameter_coordinator.get_coordination_health()
```

**Coordination Features:**
- Atomic request/response pattern with Terminal 1
- Request timeout handling (30s default)
- Retry logic with exponential backoff
- Health monitoring and success rate tracking
- Emergency stop coordination

## Database Architecture

### Coordination Table: `plc_parameter_requests`
```sql
-- Terminal 3 creates parameter requests for Terminal 1
INSERT INTO plc_parameter_requests (
    terminal_3_command_id,
    machine_id,
    parameter_name,
    component_parameter_id,
    target_value,
    data_type,
    status
) VALUES (...);

-- Terminal 1 processes and updates status
UPDATE plc_parameter_requests
SET status = 'completed', actual_value = 123.45
WHERE id = request_id;
```

### Key Tables Used
- `parameter_control_commands`: Main command table (processed by Terminal 3)
- `plc_parameter_requests`: Coordination table with Terminal 1
- `component_parameters_full`: Parameter configuration and validation rules
- `terminal_coordination`: Cross-terminal health and discovery

## Parameter Processing Flow

### 1. Command Reception
```
Database Insert/Realtime → Terminal 3 → Validation → Coordination Request
```

### 2. Validation Process
- Parameter existence verification
- Range checking (min/max values)
- Writability validation
- Safety interlocks for critical parameters
- Machine state verification (no critical changes during recipe execution)

### 3. Terminal 1 Coordination
```
Terminal 3                          Terminal 1
    |                                   |
    | 1. Create plc_parameter_request   |
    |---------------------------------->|
    |                                   | 2. Claim request
    |                                   | 3. Execute PLC write
    |                                   | 4. Update status & actual_value
    | 5. Monitor completion             |
    |<----------------------------------|
    | 6. Finalize command               |
```

### 4. Status Updates
- `parameter_control_commands.executed_at`: Terminal 3 claims command
- `parameter_control_commands.completed_at`: Final completion status
- `plc_parameter_requests`: Full coordination lifecycle tracking

## Safety Features

### Parameter Validation
```python
# Safety checks implemented
if param_row.get('is_critical', False):
    # Check if recipe is running
    if machine_status == 'processing':
        return {"valid": False, "error": "Cannot modify critical parameters during recipe execution"}

# Range validation
if min_value is not None and target_value < min_value:
    return {"valid": False, "error": f"Target value {target_value} below minimum {min_value}"}
```

### Emergency Coordination
- Emergency stop propagates to all pending requests
- Automatic timeout handling for orphaned requests
- Graceful degradation when Terminal 1 is unavailable

### Request Timeout Protection
- 30-second default timeout for each request
- Exponential backoff for retries
- Automatic cleanup of old requests

## Testing and Validation

### Test Utility: `test_parameter_service.py`
```bash
# Create test parameter commands
python test_parameter_service.py --create-test-commands --count 5

# Monitor command processing
python test_parameter_service.py --create-test-commands --monitor

# Check coordination health
python test_parameter_service.py --health-check

# Clean up test data
python test_parameter_service.py --cleanup
```

### Integration Testing
```bash
# Test parameter validation
python test_parameter_service.py --test-validation

# Monitor coordination status
python test_parameter_service.py --coordination-status
```

## Database Migration

### Apply Migration: `migrations/20250921_terminal_3_coordination.sql`
```sql
-- Creates required tables and functions for coordination
\i migrations/20250921_terminal_3_coordination.sql
```

**Migration Creates:**
- `plc_parameter_requests` table with status tracking
- Coordination functions for Terminal 1 (`claim_plc_parameter_request`, etc.)
- Health monitoring views
- Cleanup and timeout functions
- Database triggers for Terminal 1 notifications

## Monitoring and Health

### Health Metrics
```python
health = await parameter_coordinator.get_coordination_health()
# Returns:
# {
#     "last_hour_requests": 15,
#     "pending": 2,
#     "completed": 12,
#     "failed": 1,
#     "success_rate_percent": 92.3,
#     "coordination_healthy": True
# }
```

### Log Monitoring
```bash
# Monitor Terminal 3 logs
tail -f logs/parameter_control.log

# Monitor all parameter-related activity
grep -r "PARAMETER COMMAND" logs/

# Health check logs
tail -f logs/parameter_control.log | grep "Health Check"
```

## Integration with Other Terminals

### Terminal 1 (PLC Data Service)
- **Coordination Pattern**: Database-driven request/response
- **Safety Protocol**: Terminal 3 never bypasses Terminal 1 for PLC access
- **Request Table**: `plc_parameter_requests`
- **Response Handling**: Status polling with timeout

### Terminal 2 (Recipe Service)
- **Parameter Coordination**: Respect machine state during recipe execution
- **Safety Interlocks**: Block critical parameter changes during processing
- **Emergency Coordination**: Shared emergency stop mechanisms

### Integration Coordinator
- **Health Reporting**: Terminal 3 reports status via terminal discovery service
- **Emergency Signals**: Participates in cross-terminal emergency coordination
- **Hardware Locks**: Respects distributed lock mechanisms

## Security Features

### Access Control
- Row Level Security (RLS) on coordination tables
- Machine ID-based request filtering
- Service role authentication
- Audit trail for all parameter changes

### Request Validation
- Command ownership verification
- Atomic claim operations to prevent race conditions
- Timeout protection against resource leaks
- Emergency override capabilities

## Performance Specifications

### Response Times
- **Command Processing**: <100ms (validation + coordination request creation)
- **Terminal 1 Coordination**: <5s (typical PLC operation + database round-trip)
- **Emergency Response**: <500ms (emergency stop propagation)

### Throughput
- **Parameter Commands**: >50 commands/second sustained
- **Coordination Requests**: >100 requests/second peak
- **Health Monitoring**: 1Hz with <10ms overhead

### Resource Usage
- **Memory**: <100MB typical operation
- **CPU**: <5% during normal parameter processing
- **Database Connections**: 2-3 connections (realtime + queries)

## Deployment Checklist

### Pre-Deployment
- [ ] Database migration applied (`20250921_terminal_3_coordination.sql`)
- [ ] Terminal 1 PLC Data Service running and healthy
- [ ] Service authentication configured
- [ ] Machine ID environment variable set

### Service Startup
```bash
# 1. Verify environment
export MACHINE_ID="ALD_MACHINE_001"
export LOG_LEVEL="INFO"

# 2. Run database migration (if not already applied)
psql -f migrations/20250921_terminal_3_coordination.sql

# 3. Start Terminal 3 Parameter Service
python parameter_service.py

# 4. Verify health
python test_parameter_service.py --health-check
```

### Health Verification
- [ ] Service starts without errors
- [ ] Realtime subscription established or polling active
- [ ] Terminal 1 coordination working (test with sample command)
- [ ] Health metrics showing >90% success rate
- [ ] Log output clean (no recurring errors)

## Troubleshooting

### Common Issues

#### 1. Terminal 1 Coordination Failures
```bash
# Check Terminal 1 status
python test_parameter_service.py --coordination-status

# Verify Terminal 1 is running and processing queue
# Check plc_parameter_requests table for stuck requests
```

#### 2. Realtime Connection Issues
```bash
# Service will fall back to polling automatically
# Check logs for realtime connection status:
tail -f logs/parameter_control.log | grep "realtime\|REALTIME"
```

#### 3. Parameter Validation Failures
```bash
# Check parameter configuration
# Verify component_parameters_full table has correct validation rules
# Test validation directly:
python test_parameter_service.py --test-validation
```

#### 4. High Coordination Timeout Rate
```bash
# Check Terminal 1 health and PLC connection
# Verify database performance
# Consider increasing timeout values via command line args
```

### Emergency Procedures

#### Emergency Stop All Parameter Operations
```python
# From Python console:
from src.terminal_coordination.parameter_coordinator import parameter_coordinator
await parameter_coordinator.emergency_stop_all_requests()
```

#### Database Cleanup
```sql
-- Clean up stuck requests
SELECT timeout_old_plc_parameter_requests(30);

-- Clean up old completed requests
SELECT cleanup_old_plc_parameter_requests(1);
```

## Future Enhancements

### Phase 2 Improvements
- [ ] Parameter change scheduling
- [ ] Batch parameter updates
- [ ] Parameter profile management
- [ ] Advanced safety interlocks

### Integration Enhancements
- [ ] Recipe parameter synchronization
- [ ] Real-time parameter monitoring
- [ ] Predictive parameter validation
- [ ] Cross-terminal parameter dependencies

## Support and Maintenance

### Regular Maintenance
```bash
# Weekly: Clean up old coordination requests
python test_parameter_service.py --cleanup

# Monthly: Review coordination health trends
python test_parameter_service.py --health-check

# Quarterly: Review parameter validation rules
# Check component_parameters_full for outdated constraints
```

### Performance Monitoring
- Monitor coordination success rates (target >95%)
- Track request processing times (target <5s average)
- Review emergency response times (target <500ms)
- Analyze parameter validation failure patterns

---

## Summary

Terminal 3 Parameter Service provides safe, validated parameter control with strict coordination through Terminal 1. The implementation ensures hardware safety through database-driven communication, comprehensive validation, and emergency coordination protocols. The service is designed for high availability, performance, and safety in the 3-terminal ALD control architecture.