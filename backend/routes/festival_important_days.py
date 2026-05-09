"""User-defined important days for the Festival Planner (birthdays, milestones, etc.)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import get_db

router = APIRouter(prefix="/festivals", tags=["Festival important days"])

# Match festival_predictor upcoming window (183 days from today).
HORIZON_DAYS = 183


def _horizon_end(today: date) -> date:
    return date.fromordinal(today.toordinal() + HORIZON_DAYS)


def _next_yearly_occurrence_from(month: int, day: int, today: date) -> date:
    """Next calendar date on month/day on or after today (handles Feb 29)."""
    for y in range(today.year, today.year + 3):
        try:
            cand = date(y, month, day)
        except ValueError:
            cand = date(y, month, 28)
        if cand >= today:
            return cand
    return date(today.year + 2, month, min(day, 28))


def _effective_date(stored: date, repeats_yearly: bool, today: date) -> Optional[date]:
    if repeats_yearly:
        return _next_yearly_occurrence_from(stored.month, stored.day, today)
    return stored


def _in_timeline_window(eff: date, today: date, horizon: date) -> bool:
    """Match festival list: strictly after today, on or before horizon."""
    return eff > today and eff <= horizon


def _row_to_payload(
    row: tuple[Any, ...],
    today: date,
) -> dict[str, Any]:
    rid, title, stored, notes, repeats = row[0], row[1], row[2], row[3], row[4]
    horizon = _horizon_end(today)
    eff = _effective_date(stored, repeats, today)
    if eff is None:
        in_win = False
        days_until: Optional[int] = None
    else:
        in_win = _in_timeline_window(eff, today, horizon)
        days_until = (eff - today).days if eff >= today else None
    return {
        "id": int(rid),
        "title": title,
        "event_date": stored.isoformat(),
        "notes": notes or "",
        "repeats_yearly": bool(repeats),
        "effective_date": eff.isoformat() if eff else None,
        "days_until": days_until,
        "in_timeline_window": in_win,
    }


class ImportantDayCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    event_date: date
    notes: str = Field(default="", max_length=4000)
    repeats_yearly: bool = False


class ImportantDayUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    event_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    repeats_yearly: Optional[bool] = None


@router.get("/{user_id}/important-days")
def list_important_days(user_id: int, conn=Depends(get_db)) -> dict[str, Any]:
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM users WHERE id = %s;", (user_id,))
        if not cur.fetchone():
            raise HTTPException(404, "User not found")
        cur.execute(
            """
            SELECT id, title, event_date, notes, repeats_yearly
            FROM user_important_days
            WHERE user_id = %s
            ORDER BY event_date ASC, id ASC;
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    today = date.today()
    return {"important_days": [_row_to_payload(r, today) for r in rows]}


@router.post("/{user_id}/important-days")
def create_important_day(user_id: int, body: ImportantDayCreate, conn=Depends(get_db)) -> dict[str, Any]:
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM users WHERE id = %s;", (user_id,))
        if not cur.fetchone():
            raise HTTPException(404, "User not found")
        cur.execute(
            """
            INSERT INTO user_important_days (user_id, title, event_date, notes, repeats_yearly)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, title, event_date, notes, repeats_yearly;
            """,
            (user_id, body.title.strip(), body.event_date, body.notes.strip() if body.notes else None, body.repeats_yearly),
        )
        row = cur.fetchone()
    finally:
        cur.close()

    today = date.today()
    return {"important_day": _row_to_payload(row, today)}


@router.put("/{user_id}/important-days/{event_id}")
def update_important_day(
    user_id: int, event_id: int, body: ImportantDayUpdate, conn=Depends(get_db)
) -> dict[str, Any]:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, title, event_date, notes, repeats_yearly FROM user_important_days WHERE id = %s AND user_id = %s;",
            (event_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Important day not found")
        title = body.title.strip() if body.title is not None else row[1]
        evd = body.event_date if body.event_date is not None else row[2]
        notes = row[3]
        if body.notes is not None:
            notes = body.notes.strip() if body.notes else None
        repeats = body.repeats_yearly if body.repeats_yearly is not None else row[4]
        cur.execute(
            """
            UPDATE user_important_days
            SET title = %s, event_date = %s, notes = %s, repeats_yearly = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id, title, event_date, notes, repeats_yearly;
            """,
            (title, evd, notes, repeats, event_id, user_id),
        )
        out = cur.fetchone()
    finally:
        cur.close()

    today = date.today()
    return {"important_day": _row_to_payload(out, today)}


@router.delete("/{user_id}/important-days/{event_id}")
def delete_important_day(user_id: int, event_id: int, conn=Depends(get_db)) -> dict[str, Any]:
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM user_important_days WHERE id = %s AND user_id = %s RETURNING id;",
            (event_id, user_id),
        )
        deleted = cur.fetchone()
        if not deleted:
            raise HTTPException(404, "Important day not found")
    finally:
        cur.close()
    return {"deleted": True, "id": event_id}
