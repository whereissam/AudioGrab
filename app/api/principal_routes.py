"""P22 Slice 4: API-key principal management + usage ledger.

Surface (mounted under /api):
  POST   /api/principals        -> mint a key (plaintext returned ONCE)
  GET    /api/principals        -> list principals (no hashes, no keys)
  DELETE /api/principals/{id}   -> deactivate a key
  GET    /api/usage             -> day-bucketed usage

Management routes are guarded by the legacy master ``API_KEY`` only — a
principal key can never mint or revoke keys. ``GET /api/usage`` accepts
either credential: a principal sees its own rows, the master key sees all.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..core.job_store import get_job_store
from .auth import verify_api_key, verify_master_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Principals"])


# ---------- Models ----------


class CreatePrincipalRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    daily_request_quota: Optional[int] = Field(default=None, ge=1)


class CreatePrincipalResponse(BaseModel):
    principal_id: str
    name: str
    api_key: str  # shown exactly once
    daily_request_quota: Optional[int] = None
    created_at: str


class PrincipalOut(BaseModel):
    principal_id: str
    name: str
    active: bool
    daily_request_quota: Optional[int] = None
    created_at: str
    last_used_at: Optional[str] = None


class UsageRow(BaseModel):
    principal_id: str
    day: str
    requests: int
    tokens: int


class UsageResponse(BaseModel):
    count: int
    usage: list[UsageRow]


def _to_out(row: dict) -> PrincipalOut:
    return PrincipalOut(
        principal_id=row["principal_id"],
        name=row["name"],
        active=bool(row.get("active")),
        daily_request_quota=row.get("daily_request_quota"),
        created_at=row["created_at"],
        last_used_at=row.get("last_used_at"),
    )


# ---------- Management (master key only) ----------


@router.post(
    "/principals",
    response_model=CreatePrincipalResponse,
    dependencies=[Depends(verify_master_key)],
)
async def create_principal(body: CreatePrincipalRequest):
    """Mint an API key. Store the returned `api_key` now — it is never
    shown again (only its hash is persisted)."""
    try:
        row = get_job_store().create_principal(
            name=body.name, daily_request_quota=body.daily_request_quota
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return CreatePrincipalResponse(**row)


@router.get(
    "/principals",
    response_model=list[PrincipalOut],
    dependencies=[Depends(verify_master_key)],
)
async def list_principals():
    """List issued principals (never includes key material)."""
    return [_to_out(r) for r in get_job_store().list_principals()]


@router.delete(
    "/principals/{principal_id}", dependencies=[Depends(verify_master_key)]
)
async def deactivate_principal(principal_id: str):
    """Deactivate a key. Deactivation is immediate; the row is kept for the
    usage ledger's referential history."""
    if not get_job_store().deactivate_principal(principal_id):
        raise HTTPException(
            status_code=404, detail=f"Principal {principal_id} not found"
        )
    return {"deactivated": principal_id}


# ---------- Usage (either credential) ----------


@router.get(
    "/usage", response_model=UsageResponse, dependencies=[Depends(verify_api_key)]
)
async def get_usage(
    request: Request,
    principal_id: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=90),
):
    """Day-bucketed usage. Principal callers see their own rows; the master
    key may pass `principal_id` or omit it for everything."""
    caller = getattr(request.state, "principal", None)
    if caller is not None:
        # A principal can only read itself, whatever it asked for.
        principal_id = caller["principal_id"]
    rows = get_job_store().get_usage(principal_id=principal_id, days=days)
    return UsageResponse(count=len(rows), usage=[UsageRow(**r) for r in rows])
