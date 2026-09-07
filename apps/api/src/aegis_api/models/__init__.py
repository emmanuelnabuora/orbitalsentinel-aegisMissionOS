"""ORM models. Importing this package registers all tables on Base.metadata."""

from aegis_api.models.access import ApiKey, Invite
from aegis_api.models.alert import Alert
from aegis_api.models.asset import Asset, AssetDependency
from aegis_api.models.audit import AuditLog
from aegis_api.models.crypto import CryptoRecord
from aegis_api.models.incident import Incident, IncidentEvent
from aegis_api.models.ingestion import AssetEphemeris
from aegis_api.models.mission import Mission, MissionAsset
from aegis_api.models.notification import Notification, WorkspacePreference
from aegis_api.models.rbac import ApprovalRequest, CustomRole, CustomRolePermission
from aegis_api.models.report import Report
from aegis_api.models.scenario import Scenario
from aegis_api.models.threatintel import ThreatIndicator, ThreatMatch
from aegis_api.models.user import MFARecoveryCode, RefreshToken, User, UserRoleAssignment
from aegis_api.models.workspace import Workspace, WorkspaceMembership

__all__ = [
    "Alert",
    "ApiKey",
    "Invite",
    "Workspace",
    "WorkspacePreference",
    "WorkspaceMembership",
    "Asset",
    "AssetDependency",
    "ApprovalRequest",
    "AssetEphemeris",
    "CustomRole",
    "CustomRolePermission",
    "AuditLog",
    "CryptoRecord",
    "Incident",
    "IncidentEvent",
    "Mission",
    "Notification",
    "MissionAsset",
    "MFARecoveryCode",
    "Report",
    "Scenario",
    "RefreshToken",
    "ThreatIndicator",
    "ThreatMatch",
    "User",
    "UserRoleAssignment",
]
