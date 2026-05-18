"""Festival planner routes — registered in main so reload always exposes planner APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from db import get_db
from routes.festival_important_days import ReminderToggleBody, toggle_important_day_reminder
from routes.festival_predictor import (
    CreateEventBody,
    FestivalUpdateSavingsBody,
    create_planned_event,
    festival_event_details,
    update_festival_savings,
)

router = APIRouter(prefix="/festivals", tags=["Festival Planner"])


@router.post("/{user_id}/planner/event")
def post_planner_event(user_id: int, body: CreateEventBody, conn=Depends(get_db)):
    return create_planned_event(user_id, body, conn)


@router.put("/{user_id}/planner/reminder/{event_id}")
def put_planner_reminder(
    user_id: int, event_id: int, body: ReminderToggleBody, conn=Depends(get_db)
):
    return toggle_important_day_reminder(user_id, event_id, body, conn)


@router.put("/{user_id}/planner/savings")
def put_planner_savings(user_id: int, body: FestivalUpdateSavingsBody, conn=Depends(get_db)):
    return update_festival_savings(user_id, body, conn)


@router.get("/{user_id}/planner/event-details/{festival_name}")
def get_planner_event_details(
    user_id: int,
    festival_name: str,
    festival_date: str | None = None,
    refresh: bool = True,
    conn=Depends(get_db),
):
    return festival_event_details(user_id, festival_name, festival_date, refresh, conn)
