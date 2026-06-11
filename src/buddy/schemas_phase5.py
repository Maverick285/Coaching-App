"""Pydantic schemas for Phase 5 (blocked apps + override system)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# --- Blocked-app rules ----------------------------------------------------


class BlockedAppRuleCreate(BaseModel):
    goal_id: int
    package_name: str = Field(min_length=1, max_length=256)
    block_tier: int = Field(default=3, ge=3, le=4)


class BlockedAppRuleOut(BaseModel):
    id: int
    goal_id: int
    package_name: str
    block_tier: int
    is_active: bool


class BlockedAppRulesListResponse(BaseModel):
    rules: list[BlockedAppRuleOut]


class ActiveBlockOut(BaseModel):
    """The phone polls this to learn what to block right now."""

    package_name: str
    block_tier: int
    goal_id: int
    session_id: int


class ActiveBlocksResponse(BaseModel):
    blocks: list[ActiveBlockOut]
    override_window_open: bool = False
    override_expires_at: datetime | None = None


# --- Override requests ----------------------------------------------------


class OverrideRequestCreate(BaseModel):
    package_name: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=1000)
    session_id: int | None = None
    goal_id: int | None = None
    intervention_id: int | None = None
    active_minutes: int = Field(default=15, ge=1, le=240)


class OverrideRequestOut(BaseModel):
    id: int
    requested_at: datetime
    session_id: int | None
    goal_id: int | None
    intervention_id: int | None
    package_name: str
    reason: str
    approver_label: str
    sms_status: str
    sms_detail: str
    status: Literal["pending", "approved", "expired", "rejected"]
    redeemed_at: datetime | None
    expires_at: datetime | None
    active_minutes: int
    # `code` is only echoed back in dev mode (see settings.override_dev_mode);
    # in production the user has to get it from the approver via SMS.
    code_dev_echo: str | None = None


class OverrideRedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=16)


class OverrideRedeemResponse(BaseModel):
    request: OverrideRequestOut
    success: bool
    message: str
