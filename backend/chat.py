from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid
import asyncpg
import httpx
import os
from typing import Optional

router = APIRouter()

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
MINIMAX_EMBED_URL = "https://api.minimax.chat/v1/embeddings"
MINIMAX_CHAT_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"

pool: asyncpg.Pool = None


async def ensure_tables():
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_session (
                id       TEXT PRIMARY KEY,
                title    TEXT NOT NULL DEFAULT '新对话',
                summary  TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_message (
                id         SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    recent_workouts_text: str = ""


@router.get("/api/chat/sessions")
async def list_sessions():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, title, updated_at
            FROM chat_session
            ORDER BY updated_at DESC
            LIMIT 50
        """)
    return [{"id": r["id"], "title": r["title"],
             "updated_at": r["updated_at"].isoformat()} for r in rows]


@router.get("/api/chat/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM chat_session WHERE id=$1", session_id
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Session not found")
        rows = await conn.fetch("""
            SELECT role, content FROM chat_message
            WHERE session_id=$1 ORDER BY id ASC
        """, session_id)
    return [{"role": r["role"], "content": r["content"]} for r in rows]


@router.delete("/api/chat/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str):
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM chat_session WHERE id=$1", session_id
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Session not found")


async def _embed_query(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            MINIMAX_EMBED_URL,
            headers={"Authorization": f"Bearer {MINIMAX_API_KEY}"},
            json={"model": "embo-01", "texts": [text], "type": "query"},
        )
        resp.raise_for_status()
        return resp.json()["vectors"][0]


async def _search_knowledge(embedding: list[float], limit: int = 4) -> list[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT content FROM fitness_knowledge
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """, str(embedding), limit)
    return [r["content"] for r in rows]


async def _call_minimax(messages: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            MINIMAX_CHAT_URL,
            headers={"Authorization": f"Bearer {MINIMAX_API_KEY}"},
            json={"model": "MiniMax-M3", "messages": messages},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _summarize(prev_summary: str, exchange: list[dict]) -> str:
    text = "\n".join(f"{m['role']}: {m['content']}" for m in exchange)
    parts = ["请用简洁的中文（100字以内）总结以下对话要点，保留健身目标、计划、身体状况等关键信息。"]
    if prev_summary:
        parts.append(f"\n已有摘要：{prev_summary}")
    parts.append(f"\n本轮对话：\n{text}")
    return await _call_minimax([
        {"role": "system", "content": "你是对话摘要助手，输出简洁的中文摘要。"},
        {"role": "user", "content": "\n".join(parts)},
    ])


@router.post("/api/chat")
async def chat(req: ChatRequest):
    # 1. 获取或新建 session
    async with pool.acquire() as conn:
        if req.session_id:
            row = await conn.fetchrow(
                "SELECT id, summary FROM chat_session WHERE id=$1", req.session_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = row["id"]
            summary = row["summary"]
        else:
            session_id = str(uuid.uuid4())
            summary = ""
            await conn.execute("INSERT INTO chat_session (id) VALUES ($1)", session_id)

        # 2. 拉取上一轮消息（最后2条），作为 AI 上下文历史 & 摘要素材
        prev_exchange = [dict(r) for r in await conn.fetch("""
            SELECT role, content FROM chat_message
            WHERE session_id=$1 ORDER BY id DESC LIMIT 2
        """, session_id)]
        prev_exchange = list(reversed(prev_exchange))

        total_before = int(await conn.fetchval(
            "SELECT COUNT(*) FROM chat_message WHERE session_id=$1", session_id
        ))

    # 3. RAG 检索
    query_vec = await _embed_query(req.message)
    knowledge_chunks = await _search_knowledge(query_vec)
    knowledge_text = "\n\n---\n\n".join(knowledge_chunks) if knowledge_chunks else "（暂无相关知识）"

    # 4. 构建 system prompt
    system_parts = [
        "你是一名专业健身教练助手。请根据以下参考资料和用户的训练记录，给出个性化的健身建议。回答要具体、实用。",
        f"\n【参考资料】\n{knowledge_text}",
    ]
    if req.recent_workouts_text:
        system_parts.append(f"\n【用户最近训练记录】\n{req.recent_workouts_text}")
    if summary:
        system_parts.append(f"\n【历史对话摘要】\n{summary}")

    ai_messages = [{"role": "system", "content": "\n".join(system_parts)}]
    ai_messages += [{"role": m["role"], "content": m["content"]} for m in prev_exchange]
    ai_messages.append({"role": "user", "content": req.message})

    # 5. 调用 MiniMax
    reply = await _call_minimax(ai_messages)

    # 6. 存储本轮消息，更新 updated_at
    async with pool.acquire() as conn:
        await conn.executemany(
            "INSERT INTO chat_message (session_id, role, content) VALUES ($1,$2,$3)",
            [(session_id, "user", req.message), (session_id, "assistant", reply)],
        )
        await conn.execute(
            "UPDATE chat_session SET updated_at=NOW() WHERE id=$1", session_id
        )

    # 7. 摘要 & title 更新（异步，不阻塞响应）
    exchange_index = total_before // 2  # 本轮是第几轮（0-based）

    if exchange_index == 0:
        # 第1轮结束：摘要本轮对话，前30字作为 title
        title_summary = await _summarize("", [
            {"role": "user", "content": req.message},
            {"role": "assistant", "content": reply},
        ])
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE chat_session SET title=$1 WHERE id=$2",
                title_summary[:30], session_id,
            )
    else:
        # 第2轮及以后：摘要（当前 summary + 上一轮对话）
        new_summary = await _summarize(summary, prev_exchange)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE chat_session SET summary=$1 WHERE id=$2",
                new_summary, session_id,
            )

    return {"reply": reply, "session_id": session_id}
