from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
import asyncpg
import datetime
import os
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://zhang:zh1998@postgres-rag:5432/fitness")

pool: asyncpg.Pool = None


@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)


@app.on_event("shutdown")
async def shutdown():
    await pool.close()


def to_json(row: asyncpg.Record) -> dict:
    d = {}
    for k, v in dict(row).items():
        if isinstance(v, Decimal):
            d[k] = float(v)
        elif isinstance(v, (datetime.date, datetime.datetime)):
            d[k] = v.isoformat()
        else:
            d[k] = v
    return d


# ── 词联想 ──────────────────────────────────────────────

@app.get("/api/suggest/exercise")
async def suggest_exercise(q: str = ""):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (exercise_name) exercise_name, muscle_group
            FROM workout_log
            WHERE exercise_name ILIKE $1
            ORDER BY exercise_name, date DESC
            LIMIT 10
            """,
            f"%{q}%",
        )
    return [{"exercise_name": r["exercise_name"], "muscle_group": r["muscle_group"]} for r in rows]


# ── 训练记录 ────────────────────────────────────────────

@app.get("/api/workouts/recent")
async def recent_workouts():
    async with pool.acquire() as conn:
        dates = await conn.fetch(
            "SELECT DISTINCT date FROM workout_log ORDER BY date DESC LIMIT 5"
        )
        result = []
        for d in dates:
            exercises = await conn.fetch(
                """
                SELECT id, exercise_name, weight_kg, sets, reps, duration_minutes, muscle_group
                FROM workout_log WHERE date = $1 ORDER BY id
                """,
                d["date"],
            )
            muscle_groups = list({e["muscle_group"] for e in exercises if e["muscle_group"]})
            result.append({
                "date": d["date"].isoformat(),
                "muscle_groups": muscle_groups,
                "exercises": [to_json(e) for e in exercises],
            })
    return result


@app.get("/api/workouts/by-muscle")
async def by_muscle(group: str = Query(...)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (exercise_name)
                exercise_name,
                date        AS latest_date,
                weight_kg   AS latest_weight_kg,
                sets        AS latest_sets,
                reps        AS latest_reps,
                duration_minutes AS latest_duration,
                COUNT(*) OVER (PARTITION BY exercise_name) AS total_sessions
            FROM workout_log
            WHERE muscle_group = $1
            ORDER BY exercise_name, date DESC, id DESC
            """,
            group,
        )
    return [to_json(r) for r in rows]


@app.get("/api/workouts/trend")
async def trend(exercise: str = Query(...)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT date,
                   MAX(weight_kg)  AS max_weight_kg,
                   SUM(sets)       AS total_sets,
                   MAX(reps)       AS max_reps,
                   SUM(duration_minutes) AS total_duration
            FROM workout_log
            WHERE exercise_name = $1
            GROUP BY date
            ORDER BY date ASC
            """,
            exercise,
        )
    return [to_json(r) for r in rows]


class WorkoutIn(BaseModel):
    date: datetime.date
    exercise_name: str
    muscle_group: str
    weight_kg: Optional[float] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = ""


@app.post("/api/workouts", status_code=201)
async def create_workout(w: WorkoutIn):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO workout_log
              (date, exercise_name, muscle_group, weight_kg, sets, reps, duration_minutes, notes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            RETURNING *
            """,
            w.date, w.exercise_name, w.muscle_group,
            w.weight_kg, w.sets, w.reps, w.duration_minutes, w.notes,
        )
    return to_json(row)
