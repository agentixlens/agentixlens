"""
routers/alerts.py — CRUD for dashboard alert rules
"""

import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from db.database import get_db
from models.schemas import AlertSchema

router = APIRouter()


@router.get("/alerts", response_model=List[AlertSchema])
async def list_alerts(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM alerts ORDER BY id") as cur:
        rows = await cur.fetchall()
    return [AlertSchema(**dict(r)) for r in rows]


@router.post("/alerts", response_model=AlertSchema)
async def create_alert(alert: AlertSchema, db: aiosqlite.Connection = Depends(get_db)):
    now = time.time()
    async with db.execute("""
        INSERT INTO alerts (project, name, condition, threshold, enabled, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (alert.project, alert.name, alert.condition, alert.threshold, int(alert.enabled), now)) as cur:
        alert_id = cur.lastrowid
    await db.commit()
    alert.id = alert_id
    return alert


@router.put("/alerts/{alert_id}", response_model=AlertSchema)
async def update_alert(
    alert_id: int, alert: AlertSchema, db: aiosqlite.Connection = Depends(get_db)
):
    await db.execute("""
        UPDATE alerts SET name=?, condition=?, threshold=?, enabled=?
        WHERE id=?
    """, (alert.name, alert.condition, alert.threshold, int(alert.enabled), alert_id))
    await db.commit()
    alert.id = alert_id
    return alert


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int, db: aiosqlite.Connection = Depends(get_db)):
    await db.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
    await db.commit()
    return {"deleted": alert_id}
