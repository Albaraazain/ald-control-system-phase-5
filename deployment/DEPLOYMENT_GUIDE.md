# ALD Control System - Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the ALD Control System to production environments with zero-downtime capabilities, monitoring, and automated rollback procedures.

## Prerequisites

### System Requirements
- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum, 8GB recommended
- 50GB disk space for logs and data
- Network access to PLC and Supabase

### Required Environment Variables
```bash
# Core Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
MACHINE_ID=your-unique-machine-id

# PLC Configuration
PLC_TYPE=real  # or 'simulation' for testing
PLC_HOST=192.168.1.100
PLC_PORT=502

# Production Settings
LOG_LEVEL=INFO
STATUS_LOG_INTERVAL=300
GRAFANA_PASSWORD=your-secure-password
```

## Quick Start

### 1. Environment Setup
```bash
# Clone and navigate to deployment directory
cd deployment/

# Copy and configure environment file
cp config/production.env.example config/production.env
# Edit config/production.env with your values

# Verify prerequisites
./scripts/health-check.sh --help
```

### 2. Initial Deployment
```bash
# Build and deploy with monitoring
docker-compose -f docker-compose.prod.yml up -d

# Verify deployment
./scripts/health-check.sh --url http://localhost:8000 --json

# Check logs
docker-compose -f docker-compose.prod.yml logs -f ald-control
```

### 3. Access Monitoring
- **Application**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **Grafana**: http://localhost:3000 (admin/your-password)
- **Prometheus**: http://localhost:9090
- **HAProxy Stats**: http://localhost:8404/stats

## Deployment Strategies

### Blue-Green Deployment (Recommended)
```bash
# Automated blue-green deployment
./scripts/deploy.sh \
    --environment production \
    --strategy blue-green \
    --tag v1.2.3

# Manual blue-green switch
./scripts/deploy.sh \
    --environment production \
    --strategy blue-green \
    --tag v1.2.3 \
    --dry-run  # Test first
```

**Process:**
1. Deploy new version to "green" environment
2. Health check green environment
3. Switch load balancer traffic
4. Decommission old "blue" environment

### Rolling Deployment
```bash
# Rolling update (minimal downtime)
./scripts/deploy.sh \
    --environment production \
    --strategy rolling \
    --tag v1.2.3
```

### Canary Deployment
```bash
# Gradual rollout (5% → 100%)
./scripts/deploy.sh \
    --environment production \
    --strategy canary \
    --tag v1.2.3
```

## Health Checks

### Application Health
```bash
# Basic health check
curl -f http://localhost:8000/health/basic

# Comprehensive health check
curl -s http://localhost:8000/health | jq '.'

# Automated health monitoring
./scripts/health-check.sh \
    --url http://localhost:8000 \
    --retries 10 \
    --interval 5
```

### System Health
```bash
# Check all services
docker-compose -f docker-compose.prod.yml ps

# Check resource usage
docker stats

# Check logs for errors
docker-compose -f docker-compose.prod.yml logs --tail=100 ald-control
```

## Monitoring and Alerting

### Key Metrics
- **PLC Connection**: `ald_plc_connected`
- **Database Connection**: `ald_database_connected`
- **Parameter Logging Interval**: `ald_parameter_logging_interval`
- **Memory Usage**: `ald_memory_usage_mb`
- **Error Rates**: `ald_*_errors_total`

### Critical Alerts
- **System Down**: `up{job="ald-control"} == 0`
- **PLC Connection Lost**: `ald_plc_connected == 0`
- **Critical Delay**: `ald_parameter_logging_interval > 3.0`
- **High Memory**: `ald_memory_usage_mb > 800`

### Grafana Dashboards
Access pre-configured dashboards at http://localhost:3000:
- **System Overview**: Key metrics and health status
- **PLC Monitoring**: PLC-specific metrics and performance
- **Performance Dashboard**: Response times and throughput
- **Alerts Dashboard**: Active alerts and notifications

## Rollback Procedures

### Emergency Rollback
```bash
# Immediate rollback to last known good version
./scripts/rollback.sh --environment production --yes

# Rollback to specific version
./scripts/rollback.sh \
    --environment production \
    --method version \
    --version v1.2.2 \
    --yes
```

### Manual Rollback
```bash
# Interactive rollback with version selection
./scripts/rollback.sh --method manual
```

### Rollback Verification
```bash
# Verify rollback success
./scripts/health-check.sh --retries 5

# Check application version
curl -s http://localhost:8000/health | jq '.services'

# Monitor for stability
watch -n 5 './scripts/health-check.sh --basic --quiet'
```

## Maintenance Procedures

### Backup Creation
```bash
# Create configuration backup
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    docker-compose.prod.yml \
    config/ \
    monitoring/ \
    haproxy/

# Database backup (if applicable)
# Follow your Supabase backup procedures
```

### Log Management
```bash
# Rotate logs
docker-compose -f docker-compose.prod.yml logs --tail=0 -f > /dev/null &
sleep 1 && kill $!

# Clean old logs
docker system prune -f --volumes

# Archive logs
docker-compose -f docker-compose.prod.yml logs --no-color > \
    "logs/ald-control-$(date +%Y%m%d).log"
```

### Security Updates
```bash
# Update base images
docker-compose -f docker-compose.prod.yml pull

# Rebuild with security patches
docker-compose -f docker-compose.prod.yml build --no-cache

# Deploy updated images
./scripts/deploy.sh --environment production --strategy blue-green
```

## Troubleshooting

### Common Issues

#### 1. PLC Connection Failed
```bash
# Check PLC connectivity
ping $PLC_HOST

# Verify PLC configuration
docker-compose -f docker-compose.prod.yml logs ald-control | grep -i plc

# Test PLC manually
python -c "
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('$PLC_HOST', $PLC_PORT)
print('Connected:', client.connect())
client.close()
"
```

#### 2. Database Connection Issues
```bash
# Check Supabase status
curl -s "$SUPABASE_URL/rest/v1/" \
    -H "apikey: $SUPABASE_KEY" \
    -H "Authorization: Bearer $SUPABASE_KEY"

# Verify environment variables
docker-compose -f docker-compose.prod.yml exec ald-control env | grep SUPABASE
```

#### 3. High Memory Usage
```bash
# Check memory consumption
docker stats ald-control-main

# Analyze memory leaks
docker-compose -f docker-compose.prod.yml exec ald-control \
    python -c "
import psutil
process = psutil.Process()
print(f'Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB')
print(f'Threads: {process.num_threads()}')
"
```

#### 4. Performance Issues
```bash
# Check parameter logging performance
curl -s http://localhost:8000/health | jq '.metrics'

# Monitor PLC response times
docker-compose -f docker-compose.prod.yml logs ald-control | \
    grep -i "response time"

# Check database performance
# Monitor via Grafana dashboard
```

### Emergency Procedures

#### Complete System Restart
```bash
# Graceful restart
docker-compose -f docker-compose.prod.yml restart ald-control

# Force restart
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

#### Emergency Stop
```bash
# Stop all services immediately
docker-compose -f docker-compose.prod.yml down --timeout 10

# Emergency rollback
./scripts/rollback.sh --environment production --yes
```

## Performance Optimization

### Resource Limits
Default container limits in `docker-compose.prod.yml`:
- **CPU**: 2 cores max, 0.5 cores reserved
- **Memory**: 1GB max, 512MB reserved

### Database Optimization
- Use connection pooling (implemented)
- Enable bulk operations (implemented)
- Monitor query performance via Grafana

### Network Optimization
- PLC communication uses optimized bulk reads
- Configurable timeouts and retries
- Connection reuse and pooling

## Security Considerations

### Network Security
- All services run in isolated Docker networks
- HAProxy provides SSL termination and rate limiting
- PLC communication uses secure protocols

### Application Security
- Secure credential management (implemented)
- Input validation and sanitization
- Rate limiting and DoS protection
- Security monitoring and alerting

### Access Control
- Change default passwords
- Use strong authentication for monitoring interfaces
- Implement network segmentation
- Regular security updates

## Support and Maintenance

### Regular Tasks
- **Daily**: Check health dashboards and logs
- **Weekly**: Review performance metrics and alerts
- **Monthly**: Update security patches and review backups
- **Quarterly**: Performance optimization and capacity planning

### Escalation Procedures
1. **Alert Triggered**: Check Grafana dashboard
2. **System Issue**: Review logs and health status
3. **Critical Failure**: Execute emergency procedures
4. **Data Loss Risk**: Immediate rollback and backup restoration

### Contact Information
- **Operations Team**: ops@yourcompany.com
- **Emergency Hotline**: +1-XXX-XXX-XXXX
- **Technical Support**: Escalate via your incident management system

---

**Last Updated**: 2025-09-21
**Version**: 1.0
**Reviewed By**: Deployment Specialist Agent