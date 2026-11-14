"""Opt-in owner-memory API for the existing authenticated loopback portal.

No automatic chat recording or model context injection. No remote access.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .owner_memory import OwnerMemoryStore, MemoryError


class RememberRequest(BaseModel):
    scope: str = Field(min_length=1, max_length=40)
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=2000)
    provenance: str = Field(min_length=1, max_length=160)
    consent: bool = False


def _store() -> OwnerMemoryStore:
    if os.environ.get("LXRION_OWNER_MEMORY_ENABLED") != "1":
        raise HTTPException(status_code=412, detail="Owner memory is disabled")
    path = os.environ.get("LXRION_OWNER_MEMORY_DB", "")
    if not path:
        raise HTTPException(status_code=412, detail="Owner memory database is not configured")
    try:
        return OwnerMemoryStore(Path(path))
    except (MemoryError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Owner memory storage unavailable") from exc


def create_memory_router(require_token: Callable[[str | None], None]) -> APIRouter:
    router = APIRouter(prefix="/api/memory", tags=["owner-memory"])

    @router.get("/status")
    def status(authorization: str | None = Header(default=None)) -> dict:
        require_token(authorization)
        return {
            "enabled": os.environ.get("LXRION_OWNER_MEMORY_ENABLED") == "1",
            "automaticChatRetention": False,
            "automaticModelContextInjection": False,
            "requiresOwnerApproval": True,
        }

    @router.post("/items")
    def remember(request: RememberRequest, authorization: str | None = Header(default=None)) -> dict:
        require_token(authorization)
        try:
            return _store().remember(**request.model_dump())
        except MemoryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/items")
    def items(scope: str | None = None, limit: int = Query(default=50, ge=1, le=100),
              authorization: str | None = Header(default=None)) -> dict:
        require_token(authorization)
        try:
            return {"items": _store().list(scope=scope, limit=limit)}
        except MemoryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/search")
    def search(q: str = Query(min_length=1, max_length=150), limit: int = Query(default=10, ge=1, le=30),
               authorization: str | None = Header(default=None)) -> dict:
        require_token(authorization)
        try:
            return {"items": _store().search(q, limit=limit)}
        except MemoryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.delete("/items/{scope}/{key}")
    def forget(scope: str, key: str, authorization: str | None = Header(default=None)) -> dict:
        require_token(authorization)
        try:
            return {"forgotten": _store().forget(scope=scope, key=key)}
        except MemoryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
