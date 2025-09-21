# ALD Control System - Operational Runbook

## Overview

This operational runbook provides comprehensive procedures for deploying, monitoring, maintaining, and troubleshooting the ALD Control System in production environments.

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Production Environment                       │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Application   │  │   Database      │  │   PLC Hardware  │ │
│  │                 │  │                 │  │                 │ │
│  │ • Python 3.9+   │  │ • PostgreSQL    │  │ • Modbus TCP/IP │ │
│  │ • Async Services │  │ • Connection    │  │ • Industrial    │ │
│  │ • DI Container   │  │   Pool          │  │   Controllers   │ │
│  │ • Security Layer │  │ • Transactions  │  │ • Process I/O   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   Monitoring & Logging                      │ │
│  │ • Performance Metrics • Health Checks • Security Events    │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Deployment Procedures

### Pre-Deployment Checklist

#### Environment Setup
- [ ] Python 3.9 or later installed
- [ ] Required system packages installed
- [ ] Database server accessible and configured
- [ ] PLC network connectivity verified
- [ ] Security policies configured
- [ ] Monitoring systems ready

#### Configuration Verification
- [ ] Environment variables set correctly
- [ ] Database connection string configured
- [ ] PLC connection parameters verified
- [ ] Security settings appropriate for environment
- [ ] Log levels and destinations configured

#### Security Validation
- [ ] Credentials encrypted and stored securely
- [ ] Network access restricted appropriately
- [ ] File permissions set correctly (600 for sensitive files)
- [ ] Rate limiting configured
- [ ] Security monitoring enabled

### Deployment Steps

#### 1. Environment Preparation
```bash
# Create virtual environment
python -m venv production_env
source production_env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
export PLC_HOSTNAME="192.168.1.100"
export PLC_PORT="502"
export SECURITY_DEFAULT_LEVEL="HIGH"
export LOG_LEVEL="INFO"
```

#### 2. Database Setup
```bash
# Run database migrations
python run_migrations.py

# Verify database connectivity
python -c "from src.test_connections import test_database_connection; test_database_connection()"

# Initialize database schema if needed
python -c "from src.db import initialize_schema; initialize_schema()"
```

#### 3. PLC Configuration
```bash
# Test PLC connectivity
python -c "from src.test_connections import test_plc_connection; test_plc_connection()"

# Verify parameter mappings
python tools/plc_cli/validate_parameters.py

# Test bulk parameter reading
python tools/debug/test_bulk_parameter_read.py
```

#### 4. Application Startup
```bash
# Start main application
python src/main.py

# Verify services are running
python -c "from src.connection_monitor import check_all_services; check_all_services()"

# Check performance metrics
python quick_performance_check.py
```

### Post-Deployment Verification

#### Health Checks
```bash
# System health check
curl http://localhost:8080/health

# Database health
python -c "from src.db import health_check; print(health_check())"

# PLC connectivity
python -c "from src.plc.manager import plc_manager; print(plc_manager.health_check())"

# Parameter logging status
python -c "from src.data_collection.service import get_service_status; print(get_service_status())"
```

#### Performance Validation
```bash
# Run performance benchmark
python benchmark_performance_continuous_logging.py

# Validate 1-second logging intervals
python test_continuous_parameter_logging.py

# Check resource usage
python -c "import psutil; print(f'Memory: {psutil.virtual_memory().percent}%, CPU: {psutil.cpu_percent()}%')"
```

## Monitoring and Alerting

### Key Performance Indicators (KPIs)

#### System Performance
- **Parameter Logging Interval**: Target 1.0 ±0.01 seconds
- **End-to-End Cycle Time**: Target <500ms (current baseline 650-1600ms)
- **Database Response Time**: Target <100ms for bulk operations
- **PLC Communication Time**: Target <200ms for bulk reads
- **Memory Usage**: Target <200MB sustained
- **CPU Usage**: Target <50% sustained

#### Application Metrics
- **Command Processing Rate**: Commands/minute
- **Recipe Execution Success Rate**: Percentage of successful executions
- **Error Rate**: Errors per hour across all services
- **Connection Uptime**: PLC and database connection availability
- **Data Quality**: Percentage of successful parameter reads

#### Security Metrics
- **Failed Authentication Attempts**: Count per hour
- **Rate Limit Violations**: Count per hour
- **Security Events**: Count and severity distribution
- **Credential Rotation Status**: Last rotation timestamps
- **Access Control Violations**: Unauthorized access attempts

### Monitoring Implementation

#### Health Check Endpoints
```python
# Application health
GET /health
{
    "status": "healthy",
    "services": {
        "plc": "connected",
        "database": "connected",
        "parameter_logger": "running"
    },
    "timestamp": "2024-01-01T12:00:00Z"
}

# Performance metrics
GET /metrics
{
    "parameter_logging_interval": 1.001,
    "database_response_time": 45,
    "plc_response_time": 123,
    "memory_usage_mb": 145,
    "cpu_usage_percent": 23.5
}
```

#### Log Monitoring
```bash
# Monitor application logs
tail -f logs/application.log | grep ERROR

# Monitor performance logs
tail -f logs/performance.log

# Monitor security logs
tail -f logs/security.log | grep -E "(CRITICAL|ERROR)"

# Monitor PLC communication
tail -f logs/plc.log | grep -E "(connection|error)"
```

#### Alert Configuration

##### Critical Alerts (Immediate Response)
- **Service Down**: Any core service stops responding
- **PLC Connection Lost**: Hardware communication failure
- **Database Connection Lost**: Database connectivity issues
- **Security Breach**: Critical security events
- **Memory/CPU Exhaustion**: Resource utilization >90%

##### Warning Alerts (Response within 1 hour)
- **Performance Degradation**: Response times >2x normal
- **High Error Rate**: Error rate >5% for any service
- **Rate Limit Violations**: Unusual rate limit activity
- **Disk Space Low**: <10% disk space remaining
- **Certificate Expiration**: Certificates expiring within 7 days

##### Info Alerts (Response within 24 hours)
- **Configuration Changes**: System configuration modifications
- **Scheduled Maintenance**: Planned maintenance windows
- **Performance Trends**: Long-term performance trend analysis
- **Credential Rotation**: Successful credential rotations

## Maintenance Procedures

### Daily Maintenance

#### Health Checks
```bash
# Run daily health check script
./scripts/daily_health_check.sh

# Check log file sizes and rotate if needed
./scripts/log_rotation.sh

# Verify backup integrity
./scripts/verify_backups.sh

# Update performance baseline
python baseline_performance_measurement.py
```

#### Performance Monitoring
```bash
# Check current performance metrics
python quick_performance_check.py

# Analyze performance trends
python tools/performance_analysis.py --period=24h

# Check for memory leaks
python tools/memory_analysis.py

# Validate database performance
python test_database_connectivity_stress.py --duration=300
```

### Weekly Maintenance

#### Security Reviews
```bash
# Security audit
python scripts/security_audit.py

# Review access logs
python tools/log_analysis.py --type=access --period=7d

# Check credential rotation status
python -c "from src.security.credential_manager import check_rotation_status; check_rotation_status()"

# Update security configurations
python scripts/update_security_config.py
```

#### Performance Optimization
```bash
# Comprehensive performance benchmark
python benchmark_performance_continuous_logging.py --full-suite

# Database optimization
python database_optimization_demo.py

# Clean up old log files
find logs/ -name "*.log" -mtime +7 -delete

# Optimize database indices
python scripts/database_maintenance.py --optimize-indices
```

### Monthly Maintenance

#### System Updates
```bash
# Update Python dependencies
pip install -r requirements.txt --upgrade

# Run security vulnerability scan
python scripts/vulnerability_scan.py

# Update documentation
python scripts/generate_documentation.py

# Archive old logs and data
python scripts/archive_old_data.py --older-than=30d
```

#### Capacity Planning
```bash
# Analyze resource utilization trends
python tools/capacity_analysis.py --period=30d

# Project future resource needs
python tools/capacity_planning.py

# Review database growth
python tools/database_growth_analysis.py

# Plan for hardware upgrades
python tools/hardware_planning.py
```

## Troubleshooting Guide

### Common Issues

#### PLC Connection Issues

**Symptom**: PLC connection failures or timeouts
```bash
# Diagnosis
python -c "from src.plc.manager import plc_manager; print(plc_manager.get_status())"
python tools/debug/test_network_connectivity.py

# Resolution
1. Check network connectivity: ping PLC_HOSTNAME
2. Verify PLC is responding: telnet PLC_HOSTNAME 502
3. Check firewall settings
4. Restart PLC connection: python scripts/restart_plc_connection.py
5. Review PLC logs for hardware issues
```

**Symptom**: Broken pipe errors during PLC communication
```bash
# Diagnosis
grep "Broken pipe" logs/plc.log
python tools/debug/test_broken_pipe_recovery.py

# Resolution
1. Check for network interruptions
2. Verify PLC load and response times
3. Adjust timeout settings in configuration
4. Implement connection retry logic (already implemented)
5. Monitor for hardware issues
```

#### Database Performance Issues

**Symptom**: Slow database queries or timeouts
```bash
# Diagnosis
python test_database_connectivity_stress.py
python tools/debug/analyze_slow_queries.py

# Resolution
1. Check database server resources
2. Analyze query execution plans
3. Rebuild database indices: python scripts/rebuild_indices.py
4. Optimize connection pool settings
5. Consider database server upgrade
```

**Symptom**: Connection pool exhaustion
```bash
# Diagnosis
python -c "from src.performance.async_database_pool import get_pool_status; print(get_pool_status())"

# Resolution
1. Increase max_connections in configuration
2. Check for connection leaks in application
3. Implement connection timeout reduction
4. Monitor application connection usage patterns
```

#### Performance Issues

**Symptom**: Parameter logging intervals exceeding 1 second
```bash
# Diagnosis
python test_continuous_parameter_logging.py
python tools/debug/analyze_timing_issues.py

# Resolution
1. Check PLC response times
2. Optimize bulk parameter reading
3. Reduce database transaction overhead
4. Implement async pipeline optimizations
5. Monitor system resource usage
```

**Symptom**: High memory usage or memory leaks
```bash
# Diagnosis
python tools/debug/memory_profiling.py
python -c "import psutil; print(psutil.virtual_memory())"

# Resolution
1. Restart application services
2. Check for unclosed connections
3. Analyze memory usage patterns
4. Implement garbage collection optimization
5. Review large data structures
```

#### Security Issues

**Symptom**: High rate of authentication failures
```bash
# Diagnosis
grep "authentication" logs/security.log | tail -100
python tools/security/analyze_auth_failures.py

# Resolution
1. Check for brute force attacks
2. Implement additional rate limiting
3. Review authentication logs
4. Update security policies
5. Consider IP blocking for repeated failures
```

**Symptom**: Rate limiting violations
```bash
# Diagnosis
grep "rate.limit" logs/security.log
python -c "from src.security.rate_limiter import get_status; print(get_status())"

# Resolution
1. Analyze request patterns
2. Adjust rate limiting thresholds
3. Implement request queuing
4. Review client behavior
5. Consider load balancing
```

### Emergency Procedures

#### System Recovery

**Complete System Failure**
1. **Assessment**: Determine scope of failure
2. **Isolation**: Isolate affected components
3. **Recovery**: Restore from backups
4. **Validation**: Verify system functionality
5. **Monitoring**: Enhanced monitoring during recovery

**Data Loss Prevention**
1. **Immediate Backup**: Create emergency backup
2. **Stop Processing**: Halt data modification operations
3. **Assess Damage**: Determine extent of data loss
4. **Recovery Plan**: Implement data recovery procedures
5. **Validation**: Verify data integrity

#### Security Incidents

**Security Breach Response**
1. **Containment**: Isolate affected systems
2. **Assessment**: Determine breach scope
3. **Notification**: Alert security team and stakeholders
4. **Forensics**: Collect evidence and analyze
5. **Recovery**: Restore secure operations
6. **Review**: Post-incident analysis and improvements

**Credential Compromise**
1. **Immediate Action**: Rotate all affected credentials
2. **Access Review**: Audit all access logs
3. **System Scan**: Check for unauthorized changes
4. **Monitoring**: Enhanced security monitoring
5. **Prevention**: Implement additional security measures

## Performance Optimization

### System Tuning

#### Database Optimization
```bash
# Connection pool tuning
export DATABASE_MAX_CONNECTIONS=50
export DATABASE_CONNECTION_TIMEOUT=30

# Query optimization
python scripts/analyze_query_performance.py
python scripts/update_database_indices.py

# Connection pool monitoring
python tools/debug/monitor_connection_pool.py
```

#### PLC Communication Optimization
```bash
# Bulk read configuration
export PLC_BULK_READ_SIZE=50
export PLC_READ_TIMEOUT=5000

# Connection management
export PLC_CONNECTION_RETRY_INTERVAL=5
export PLC_MAX_RECONNECT_ATTEMPTS=3

# Performance testing
python tools/debug/test_plc_bulk_performance.py
```

#### Application Performance
```bash
# Async optimization
export ASYNCIO_TASK_POOL_SIZE=100
export PARAMETER_LOGGING_INTERVAL=1.0

# Memory management
export PYTHON_GC_THRESHOLD="700,10,10"

# Performance monitoring
python tools/performance/continuous_monitoring.py
```

### Capacity Planning

#### Resource Monitoring
- **CPU Usage**: Target <50% average, <80% peak
- **Memory Usage**: Target <200MB average, <500MB peak
- **Network I/O**: Monitor PLC and database traffic
- **Disk I/O**: Monitor log files and database writes
- **Storage**: Plan for log rotation and data archival

#### Scaling Strategies
- **Vertical Scaling**: Increase server resources
- **Connection Pooling**: Optimize database connections
- **Load Distribution**: Distribute PLC communication load
- **Data Archival**: Implement automated data archival
- **Service Separation**: Consider microservices architecture

This operational runbook provides comprehensive guidance for maintaining a reliable, secure, and high-performance ALD control system in production environments.