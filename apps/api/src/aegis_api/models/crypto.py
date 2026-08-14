"""QuantumShield crypto inventory: what cryptography protects each asset."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_api.core.db import Base
from aegis_api.models.asset import Asset
from aegis_api.models.common import TimestampMixin, str_enum
from aegis_api.models.enums import CryptoKind

# NIST-selected PQC algorithms + symmetric primitives considered quantum-resistant
PQC_SAFE_ALGORITHMS = {"ML-KEM", "ML-DSA", "SLH-DSA", "FN-DSA", "AES-256-GCM", "CHACHA20-POLY1305"}
# Public-key algorithms broken by a cryptographically-relevant quantum computer
QUANTUM_VULNERABLE = {"RSA", "ECDSA", "ECDH", "DSA", "DH", "ED25519", "X25519"}


class CryptoRecord(TimestampMixin, Base):
    __tablename__ = "crypto_records"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[CryptoKind] = mapped_column(str_enum(CryptoKind), index=True)
    algorithm: Mapped[str] = mapped_column(sa.String(50), index=True)
    key_size: Mapped[int | None] = mapped_column(sa.Integer)
    subject: Mapped[str | None] = mapped_column(sa.String(300))
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    asset: Mapped[Asset] = relationship(lazy="selectin")

    @property
    def pqc_ready(self) -> bool:
        return self.algorithm.upper() in PQC_SAFE_ALGORITHMS
