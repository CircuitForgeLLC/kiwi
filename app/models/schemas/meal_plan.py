# app/models/schemas/meal_plan.py
"""Pydantic schemas for meal planning endpoints."""
from __future__ import annotations

from datetime import date as _date

from pydantic import BaseModel, Field, field_validator


VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}


class CreatePlanRequest(BaseModel):
    week_start: _date
    meal_types: list[str] = Field(default_factory=lambda: ["dinner"])

    @field_validator("week_start")
    @classmethod
    def must_be_monday(cls, v: _date) -> _date:
        if v.weekday() != 0:
            raise ValueError("week_start must be a Monday (weekday 0)")
        return v


class UpsertSlotRequest(BaseModel):
    recipe_id: int | None = None
    servings: float = Field(2.0, gt=0)
    custom_label: str | None = None


class SlotSummary(BaseModel):
    id: int
    plan_id: int
    day_of_week: int
    meal_type: str
    recipe_id: int | None
    recipe_title: str | None
    servings: float
    custom_label: str | None


class PlanSummary(BaseModel):
    id: int
    week_start: str
    meal_types: list[str]
    slots: list[SlotSummary]
    created_at: str


class RetailerLink(BaseModel):
    retailer: str
    label: str
    url: str


class GapItem(BaseModel):
    ingredient_name: str
    needed_raw: str | None      # e.g. "2 cups" from recipe text
    have_quantity: float | None  # from pantry
    have_unit: str | None
    covered: bool               # True = pantry has it
    retailer_links: list[RetailerLink] = Field(default_factory=list)


class ShoppingListResponse(BaseModel):
    plan_id: int
    gap_items: list[GapItem]
    covered_items: list[GapItem]
    disclosure: str | None = None  # affiliate disclosure text when links present


class PrepTaskSummary(BaseModel):
    id: int
    recipe_id: int | None
    task_label: str
    duration_minutes: int | None
    sequence_order: int
    equipment: str | None
    is_parallel: bool
    notes: str | None
    user_edited: bool


class PrepSessionSummary(BaseModel):
    id: int
    plan_id: int
    scheduled_date: str
    status: str
    tasks: list[PrepTaskSummary]


class UpdatePrepTaskRequest(BaseModel):
    duration_minutes: int | None = None
    sequence_order: int | None = None
    notes: str | None = None
    equipment: str | None = None
