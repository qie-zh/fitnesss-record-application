from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
import asyncpg
import datetime
import os
from typing import Optional
import chat as chat_router  # noqa: E402

DATABASE_URL = os.getenv("DATABASE_URL")

pool: asyncpg.Pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    chat_router.pool = pool
    await chat_router.ensure_tables()
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.3.20:3002"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router.router)


# asyncpg 返回 Decimal 和 date 对象，不能直接 JSON 序列化
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
            ORDER BY exercise_name, date DESC  -- DISTINCT ON 取最新一条，以拿到最近使用的 muscle_group
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
                -- 窗口函数在 DISTINCT ON 过滤前计算，一次扫描同时得到最新记录和总次数
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

# ── 删除训练记录 ────────────────────────────────────────────
@app.delete("/api/workouts/{workout_id}", status_code=204)
async def delete_workout(workout_id: int):
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM workout_log WHERE id=$1", workout_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Not found")

# ── 更新训练记录 ────────────────────────────────────────────
@app.put("/api/workouts/{workout_id}")
async def update_workout(workout_id: int, w: WorkoutIn):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE workout_log
            SET date=$1, exercise_name=$2, muscle_group=$3,
                weight_kg=$4, sets=$5, reps=$6, duration_minutes=$7, notes=$8
            WHERE id=$9
            RETURNING *
            """,
            w.date, w.exercise_name, w.muscle_group,
            w.weight_kg, w.sets, w.reps, w.duration_minutes, w.notes,
            workout_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return to_json(row)


# ── 插入健身记录 ────────────────────────────────────────────
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
