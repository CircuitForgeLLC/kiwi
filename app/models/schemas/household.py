"""Pydantic schemas for household management endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class HouseholdCreateResponse(BaseModel):
    household_id: str
    message: str


class HouseholdMember(BaseModel):
    user_id: str
    joined_at: str
    is_owner: bool


class HouseholdStatusResponse(BaseModel):
    in_household: bool
    household_id: str | None = None
    is_owner: bool = False
    members: list[HouseholdMember] = Field(default_factory=list)
    max_seats: int = 4


class HouseholdInviteResponse(BaseModel):
    invite_url: str
    token: str
    expires_at: str


class HouseholdAcceptRequest(BaseModel):
    household_id: str
    token: str


class HouseholdAcceptResponse(BaseModel):
    message: str
    household_id: str


class HouseholdRemoveMemberRequest(BaseModel):
    user_id: str
