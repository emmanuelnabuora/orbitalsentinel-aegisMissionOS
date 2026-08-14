"""Domain enumerations. Stored as strings (portable across Postgres/SQLite)."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"  # full control, user management
    OPERATOR = "operator"  # create/update assets and missions
    ANALYST = "analyst"  # read + (later) annotate/investigate
    SOC_MANAGER = "soc_manager"  # analyst surfaces + alert/incident triage oversight
    INCIDENT_RESPONDER = "incident_responder"  # containment, evidence, response actions
    EXECUTIVE = "executive"  # read-only KPIs, reports
    AUDITOR = "auditor"  # read-only + audit log access
    VIEWER = "viewer"  # read-only


class AssetType(StrEnum):
    SATELLITE = "satellite"
    GROUND_STATION = "ground_station"
    ORBITAL_DATACENTER = "orbital_datacenter"
    NETWORK = "network"
    SERVER = "server"
    APPLICATION = "application"
    SENSOR = "sensor"


class AssetStatus(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class Criticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MissionStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    COMPLETED = "completed"


class AlertSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"


class CryptoKind(StrEnum):
    CERTIFICATE = "certificate"
    TLS_ENDPOINT = "tls_endpoint"
    VPN_TUNNEL = "vpn_tunnel"
    SSH_KEY = "ssh_key"
    DATA_AT_REST = "data_at_rest"


class IndicatorType(StrEnum):
    IP = "ip"
    DOMAIN = "domain"
    URL = "url"
    FILE_HASH = "file_hash"
    EMAIL = "email"


class ThreatCategory(StrEnum):
    MALWARE = "malware"
    PHISHING = "phishing"
    C2 = "c2"
    SCANNER = "scanner"
    APT = "apt"
    JAMMING = "jamming"
    UNKNOWN = "unknown"


class ReportKind(StrEnum):
    EXECUTIVE = "executive"
    MISSION_ASSURANCE = "mission_assurance"
    INCIDENT = "incident"
    THREAT_INTEL = "threat_intel"
    QUANTUM_READINESS = "quantum_readiness"
