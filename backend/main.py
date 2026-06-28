from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
import asyncpg
import datetime
import os
import httpx
from typing import Optional

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
MINIMAX_EMBED_URL = "https://api.minimax.chat/v1/embeddings"
MINIMAX_CHAT_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"

DATABASE_URL = os.getenv("DATABASE_URL")

pool: asyncpg.Pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.3.20:3002"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class ChatRequest(BaseModel):
    message: str
    # 前端传入最近训练记录的文本摘要，直接拼进 prompt，无需再查库
    recent_workouts_text: str = ""


async def embed_query(text: str) -> list[float]:
    """把用户问题向量化，type=query 与存储端的 type=db 对应才能正确计算余弦相似度"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            MINIMAX_EMBED_URL,
            headers={"Authorization": f"Bearer {MINIMAX_API_KEY}"},
            json={"model": "embo-01", "texts": [text], "type": "query"},
        )
        resp.raise_for_status()
        return resp.json()["vectors"][0]


async def search_knowledge(embedding: list[float], limit: int = 4) -> list[str]:
    """用余弦距离（<=>）从向量库里找最相关的知识块"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT content
            FROM fitness_knowledge
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            str(embedding),
            limit,
        )
    return [r["content"] for r in rows]


@app.post("/api/chat")
async def chat(req: ChatRequest):
    # 1. 把问题向量化后检索相关知识片段
    query_vec = await embed_query(req.message)
    knowledge_chunks = await search_knowledge(query_vec)

    # 2. 把检索到的知识块拼成参考资料段落
    knowledge_text = "\n\n---\n\n".join(knowledge_chunks) if knowledge_chunks else "（暂无相关知识）"

    system_prompt = f"""你是一名专业健身教练助手。请根据以下参考资料和用户的训练记录，给出个性化的健身建议。

【参考资料】
{knowledge_text}

【用户最近训练记录】
{req.recent_workouts_text or "（未提供）"}

回答要具体、实用，结合用户实际训练数据给出建议。"""

    # 3. 调 MiniMax chat 生成回答
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            MINIMAX_CHAT_URL,
            headers={"Authorization": f"Bearer {MINIMAX_API_KEY}"},
            json={
                "model": "abab6.5s-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": req.message},
                ],
            },
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"]

    return {"reply": reply}


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

@app.get("/api/debug/pool")
async def debug_pool():
    return {
        "total_connections": pool.get_size(),
        "idle_connections": pool.get_idle_size(),
        "busy_connections": pool.get_size() - pool.get_idle_size(),
        "min_size": pool.get_min_size(),
        "max_size": pool.get_max_size(),
    }