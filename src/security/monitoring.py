"""
Security Monitoring and Alerting Module

This module provides comprehensive security monitoring, threat detection,
and alerting capabilities for the ALD control system.
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum
import hashlib
from src.log_setup import logger


class ThreatLevel(Enum):
    """Security threat levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEvent(Enum):
    """Types of security events to monitor."""
    CREDENTIAL_ACCESS = "credential_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_PLC_ACCESS = "suspicious_plc_access"
    DATABASE_ABUSE = "database_abuse"
    INPUT_VALIDATION_FAILURE = "input_validation_failure"
    FILE_ACCESS_VIOLATION = "file_access_violation"
    AUTHENTICATION_FAILURE = "authentication_failure"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    CONFIGURATION_TAMPERING = "configuration_tampering"
    NETWORK_ANOMALY = "network_anomaly"


@dataclass
class SecurityAlert:
    """Security alert data structure."""
    event_type: SecurityEvent
    threat_level: ThreatLevel
    timestamp: float
    source_ip: Optional[str]
    user_id: Optional[str]
    machine_id: Optional[str]
    description: str
    metadata: Dict[str, Any]
    alert_id: str

    def __post_init__(self):
        """Generate alert ID if not provided."""
        if not self.alert_id:
            alert_data = f"{self.event_type.value}:{self.timestamp}:{self.source_ip}:{self.description}"
            self.alert_id = hashlib.md5(alert_data.encode()).hexdigest()[:16]


class SecurityMonitor:
    """Real-time security monitoring and threat detection."""

    def __init__(self, alert_threshold: int = 100):
        """
        Initialize security monitor.

        Args:
            alert_threshold: Maximum number of alerts to keep in memory
        """
        self.alert_threshold = alert_threshold
        self.alerts: deque = deque(maxlen=alert_threshold)
        self.event_counts: Dict[SecurityEvent, int] = defaultdict(int)
        self.threat_patterns: Dict[str, List[SecurityAlert]] = defaultdict(list)
        self.blocked_ips: set = set()
        self.monitoring_active = False
        self._alert_callbacks: List[callable] = []

    def start_monitoring(self):
        """Start security monitoring."""
        self.monitoring_active = True
        logger.info("Security monitoring started")

    def stop_monitoring(self):
        """Stop security monitoring."""
        self.monitoring_active = False
        logger.info("Security monitoring stopped")

    def add_alert_callback(self, callback: callable):
        """
        Add callback function for alert notifications.

        Args:
            callback: Function to call when alert is triggered
        """
        self._alert_callbacks.append(callback)

    def record_security_event(self,
                            event_type: SecurityEvent,
                            threat_level: ThreatLevel,
                            description: str,
                            source_ip: Optional[str] = None,
                            user_id: Optional[str] = None,
                            machine_id: Optional[str] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> SecurityAlert:
        """
        Record a security event and generate alert if necessary.

        Args:
            event_type: Type of security event
            threat_level: Severity of the threat
            description: Human-readable description
            source_ip: Source IP address if applicable
            user_id: User ID if applicable
            machine_id: Machine ID if applicable
            metadata: Additional event metadata

        Returns:
            SecurityAlert object
        """
        if not self.monitoring_active:
            return None

        alert = SecurityAlert(
            event_type=event_type,
            threat_level=threat_level,
            timestamp=time.time(),
            source_ip=source_ip,
            user_id=user_id,
            machine_id=machine_id,
            description=description,
            metadata=metadata or {},
            alert_id=""
        )

        # Store alert
        self.alerts.append(alert)
        self.event_counts[event_type] += 1

        # Analyze threat patterns
        self._analyze_threat_patterns(alert)

        # Log the alert
        self._log_security_alert(alert)

        # Trigger callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

        return alert

    def _analyze_threat_patterns(self, alert: SecurityAlert):
        """Analyze incoming alerts for threat patterns."""
        pattern_key = f"{alert.source_ip}:{alert.event_type.value}"
        self.threat_patterns[pattern_key].append(alert)

        # Keep only recent alerts (last 1 hour)
        cutoff_time = time.time() - 3600
        self.threat_patterns[pattern_key] = [
            a for a in self.threat_patterns[pattern_key]
            if a.timestamp > cutoff_time
        ]

        # Check for suspicious patterns
        recent_alerts = self.threat_patterns[pattern_key]
        if len(recent_alerts) >= 5:  # 5+ alerts from same IP in 1 hour
            self._trigger_ip_block(alert.source_ip, recent_alerts)

    def _trigger_ip_block(self, ip: str, alerts: List[SecurityAlert]):
        """Trigger IP blocking for suspicious activity."""
        if ip and ip not in self.blocked_ips:
            self.blocked_ips.add(ip)

            block_alert = SecurityAlert(
                event_type=SecurityEvent.NETWORK_ANOMALY,
                threat_level=ThreatLevel.HIGH,
                timestamp=time.time(),
                source_ip=ip,
                user_id=None,
                machine_id=None,
                description=f"IP {ip} blocked due to suspicious activity pattern",
                metadata={
                    "trigger_alerts": len(alerts),
                    "blocked_ip": ip,
                    "auto_block": True
                },
                alert_id=""
            )

            self.alerts.append(block_alert)
            logger.warning(f"Security: Blocked IP {ip} due to suspicious activity")

    def _log_security_alert(self, alert: SecurityAlert):
        """Log security alert with appropriate severity."""
        alert_data = {
            "alert_id": alert.alert_id,
            "event_type": alert.event_type.value,
            "threat_level": alert.threat_level.value,
            "timestamp": alert.timestamp,
            "description": alert.description,
            "source_ip": alert.source_ip,
            "user_id": alert.user_id,
            "machine_id": alert.machine_id,
            "metadata": alert.metadata
        }

        if alert.threat_level == ThreatLevel.CRITICAL:
            logger.critical(f"SECURITY ALERT: {json.dumps(alert_data)}")
        elif alert.threat_level == ThreatLevel.HIGH:
            logger.error(f"SECURITY ALERT: {json.dumps(alert_data)}")
        elif alert.threat_level == ThreatLevel.MEDIUM:
            logger.warning(f"SECURITY ALERT: {json.dumps(alert_data)}")
        else:
            logger.info(f"SECURITY ALERT: {json.dumps(alert_data)}")

    def is_ip_blocked(self, ip: str) -> bool:
        """Check if an IP address is blocked."""
        return ip in self.blocked_ips

    def unblock_ip(self, ip: str) -> bool:
        """
        Unblock an IP address.

        Args:
            ip: IP address to unblock

        Returns:
            True if IP was blocked and is now unblocked, False otherwise
        """
        if ip in self.blocked_ips:
            self.blocked_ips.remove(ip)
            logger.info(f"Security: Unblocked IP {ip}")
            return True
        return False

    def get_recent_alerts(self, hours: int = 24) -> List[SecurityAlert]:
        """
        Get recent security alerts.

        Args:
            hours: Number of hours to look back

        Returns:
            List of recent security alerts
        """
        cutoff_time = time.time() - (hours * 3600)
        return [alert for alert in self.alerts if alert.timestamp > cutoff_time]

    def get_threat_statistics(self) -> Dict[str, Any]:
        """Get security threat statistics."""
        recent_alerts = self.get_recent_alerts(24)

        threat_by_level = defaultdict(int)
        threat_by_type = defaultdict(int)

        for alert in recent_alerts:
            threat_by_level[alert.threat_level.value] += 1
            threat_by_type[alert.event_type.value] += 1

        return {
            "monitoring_active": self.monitoring_active,
            "total_alerts_24h": len(recent_alerts),
            "blocked_ips": len(self.blocked_ips),
            "threat_by_level": dict(threat_by_level),
            "threat_by_type": dict(threat_by_type),
            "alerts_in_memory": len(self.alerts)
        }

    async def send_alert_notification(self, alert: SecurityAlert):
        """
        Send alert notification (placeholder for integration with notification system).

        Args:
            alert: Security alert to send
        """
        # This is a placeholder for integration with notification systems
        # (email, SMS, Slack, etc.)
        logger.info(f"Alert notification would be sent: {alert.alert_id}")


# Global security monitor instance
_security_monitor: Optional[SecurityMonitor] = None


def get_security_monitor() -> SecurityMonitor:
    """Get the global security monitor instance."""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor


def record_security_event(event_type: SecurityEvent,
                        threat_level: ThreatLevel,
                        description: str,
                        **kwargs) -> Optional[SecurityAlert]:
    """
    Convenience function to record security events.

    Args:
        event_type: Type of security event
        threat_level: Severity of the threat
        description: Human-readable description
        **kwargs: Additional arguments for the alert

    Returns:
        SecurityAlert object if monitoring is active, None otherwise
    """
    monitor = get_security_monitor()
    return monitor.record_security_event(
        event_type=event_type,
        threat_level=threat_level,
        description=description,
        **kwargs
    )


def start_security_monitoring():
    """Start global security monitoring."""
    monitor = get_security_monitor()
    monitor.start_monitoring()


def stop_security_monitoring():
    """Stop global security monitoring."""
    monitor = get_security_monitor()
    monitor.stop_monitoring()


def is_ip_blocked(ip: str) -> bool:
    """Check if an IP address is blocked."""
    monitor = get_security_monitor()
    return monitor.is_ip_blocked(ip)


# Security decorators and context managers

def require_security_check(event_type: SecurityEvent,
                         threat_level: ThreatLevel = ThreatLevel.MEDIUM):
    """
    Decorator to add security monitoring to functions.

    Args:
        event_type: Type of security event to monitor
        threat_level: Threat level for failed operations
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                # Log successful security-sensitive operation
                record_security_event(
                    event_type=event_type,
                    threat_level=ThreatLevel.LOW,
                    description=f"Successful {func.__name__} operation",
                    metadata={"function": func.__name__, "success": True}
                )
                return result
            except Exception as e:
                # Log failed security-sensitive operation
                record_security_event(
                    event_type=event_type,
                    threat_level=threat_level,
                    description=f"Failed {func.__name__} operation: {str(e)}",
                    metadata={"function": func.__name__, "error": str(e)}
                )
                raise
        return wrapper
    return decorator


class SecurityContext:
    """Context manager for security-monitored operations."""

    def __init__(self, event_type: SecurityEvent, description: str,
                 threat_level: ThreatLevel = ThreatLevel.MEDIUM, **metadata):
        """
        Initialize security context.

        Args:
            event_type: Type of security event
            description: Description of the operation
            threat_level: Threat level for failed operations
            **metadata: Additional metadata
        """
        self.event_type = event_type
        self.description = description
        self.threat_level = threat_level
        self.metadata = metadata

    def __enter__(self):
        """Enter security context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit security context and record event."""
        if exc_type is None:
            # Success
            record_security_event(
                event_type=self.event_type,
                threat_level=ThreatLevel.LOW,
                description=f"Successful {self.description}",
                metadata={**self.metadata, "success": True}
            )
        else:
            # Failure
            record_security_event(
                event_type=self.event_type,
                threat_level=self.threat_level,
                description=f"Failed {self.description}: {str(exc_val)}",
                metadata={**self.metadata, "error": str(exc_val)}
            )