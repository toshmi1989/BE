"""Phase 17 — Authentication & organization APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.domain.auth_service import (
    AuthContext,
    create_study_for_org,
    login_user,
    register_user,
    require_auth,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: str
    organization_name: str
    organization_slug: str | None = None
    role: str = "ADMIN"


class LoginIn(BaseModel):
    email: str
    password: str
    organization_id: UUID | None = None


class StudyCreateIn(BaseModel):
    study_key: str
    title: str | None = None
    sponsor: str | None = None
    product: str | None = None
    dose: str | None = None


@router.post("/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    return register_user(
        db,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        organization_name=payload.organization_name,
        organization_slug=payload.organization_slug,
        role=payload.role,
    )


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    return login_user(
        db,
        email=payload.email,
        password=payload.password,
        organization_id=payload.organization_id,
    )


@router.get("/me")
def me(auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    return {
        "user_id": str(auth.user_id),
        "email": auth.email,
        "display_name": auth.display_name,
        "organization_id": str(auth.organization_id) if auth.organization_id else None,
        "role": auth.role,
    }


@router.post("/studies")
def create_study(
    payload: StudyCreateIn,
    auth: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    auth.require("create_study")
    assert auth.organization_id is not None
    row = create_study_for_org(
        db,
        organization_id=auth.organization_id,
        study_key=payload.study_key,
        created_by_user_id=auth.user_id,
        title=payload.title,
        sponsor=payload.sponsor,
        product=payload.product,
        dose=payload.dose,
    )
    return {
        "study_id": str(row.id),
        "study_key": row.study_key,
        "organization_id": str(row.organization_id),
        "lifecycle": row.lifecycle,
        "title": row.title,
    }
