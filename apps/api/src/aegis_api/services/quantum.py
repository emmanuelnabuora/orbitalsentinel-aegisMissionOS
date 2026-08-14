"""QuantumShield: crypto inventory and PQC readiness scoring."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import NotFoundError
from aegis_api.models.crypto import QUANTUM_VULNERABLE, CryptoRecord
from aegis_api.repositories.assets import AssetRepository
from aegis_api.repositories.crypto import CryptoRepository
from aegis_api.schemas.quantum import CryptoRecordCreate, QuantumReadiness
from aegis_api.services.audit import AuditService


class QuantumService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CryptoRepository(session)
        self.assets = AssetRepository(session)
        self.audit = AuditService(session)

    async def register(self, data: CryptoRecordCreate, *, actor_id: uuid.UUID) -> CryptoRecord:
        if await self.assets.get(data.asset_id) is None:
            raise NotFoundError("Asset not found")
        record = CryptoRecord(**data.model_dump())
        self.repo.add(record)
        await self.session.flush()
        self.audit.record(
            actor_id=actor_id,
            action="crypto.registered",
            resource_type="crypto_record",
            resource_id=record.id,
            detail={"algorithm": data.algorithm},
        )
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def readiness(self) -> QuantumReadiness:
        records, total = await self.repo.list(limit=10000)
        if total == 0:
            return QuantumReadiness(
                score=0,
                total_records=0,
                pqc_ready_records=0,
                vulnerable_records=0,
                vulnerable_by_algorithm={},
                exposed_assets=[],
                recommendations=["Register crypto inventory to begin PQC readiness assessment."],
            )

        ready = [r for r in records if r.pqc_ready]
        vulnerable = [r for r in records if r.algorithm.upper() in QUANTUM_VULNERABLE]
        by_algo: dict[str, int] = {}
        exposed: set[str] = set()
        for r in vulnerable:
            by_algo[r.algorithm.upper()] = by_algo.get(r.algorithm.upper(), 0) + 1
            exposed.add(r.asset.name)

        score = round(100 * len(ready) / total)
        recs: list[str] = []
        if by_algo.get("RSA"):
            recs.append(
                f"Migrate {by_algo['RSA']} RSA key exchange/signature use(s) to "
                "ML-KEM (key establishment) and ML-DSA (signatures)."
            )
        ecc = sum(v for k, v in by_algo.items() if k in ("ECDSA", "ECDH", "ED25519", "X25519"))
        if ecc:
            recs.append(f"Replace {ecc} elliptic-curve usage(s); prioritize external-facing TLS.")
        expiring = [r for r in vulnerable if r.expires_at is not None]
        if expiring:
            recs.append("Rotate expiring vulnerable certificates directly to hybrid PQC chains.")
        if not recs:
            recs.append("Inventory is quantum-resistant. Maintain crypto-agility policies.")

        return QuantumReadiness(
            score=score,
            total_records=total,
            pqc_ready_records=len(ready),
            vulnerable_records=len(vulnerable),
            vulnerable_by_algorithm=by_algo,
            exposed_assets=sorted(exposed),
            recommendations=recs,
        )
