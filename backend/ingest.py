"""
一次性脚本：解析 /knowledge 目录下的 PDF，分块后向量化存入 pgvector。
运行方式：docker exec fitness-backend python ingest.py
"""

import os
import asyncio
import asyncpg
import httpx
import pdfplumber

DATABASE_URL = os.getenv("DATABASE_URL")
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
KNOWLEDGE_DIR = "/knowledge"

CHUNK_SIZE = 500      # 每块字符数
CHUNK_OVERLAP = 80    # 相邻块重叠字符数，保留上下文衔接


def extract_pdf_text(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        pages = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
    return "\n".join(pages)


def chunk_text(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c.strip() for c in chunks if len(c.strip()) > 50]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """调用 MiniMax embo-01，type=db 表示用于存储端；参数名是 texts，返回字段是 vectors"""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.minimax.chat/v1/embeddings",
            headers={"Authorization": f"Bearer {MINIMAX_API_KEY}"},
            json={"model": "embo-01", "texts": texts, "type": "db"},
        )
        resp.raise_for_status()
        data = resp.json()
        if data["base_resp"]["status_code"] != 0:
            raise RuntimeError(f"MiniMax embedding 错误: {data['base_resp']['status_msg']}")
        return data["vectors"]


async def main():
    conn = await asyncpg.connect(DATABASE_URL)

    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS fitness_knowledge (
            id SERIAL PRIMARY KEY,
            source TEXT,
            chunk_index INT,
            content TEXT,
            embedding vector(1536)
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS fitness_knowledge_emb_idx
        ON fitness_knowledge USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 50)
    """)

    pdf_files = [f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith(".pdf")]
    print(f"找到 {len(pdf_files)} 个 PDF: {pdf_files}")

    for filename in pdf_files:
        path = os.path.join(KNOWLEDGE_DIR, filename)

        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM fitness_knowledge WHERE source=$1", filename
        )
        if existing:
            print(f"[跳过] {filename} 已有 {existing} 条记录")
            continue

        print(f"[解析] {filename} ...")
        text = extract_pdf_text(path)
        chunks = chunk_text(text)
        print(f"  分块数: {len(chunks)}")

        # 每次最多批量 20 条，避免超出 API 限制
        batch_size = 20
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            print(f"  embedding {i}~{i+len(batch)-1} ...")
            embeddings = await embed_texts(batch)
            await conn.executemany(
                """
                INSERT INTO fitness_knowledge (source, chunk_index, content, embedding)
                VALUES ($1, $2, $3, $4::vector)
                """,
                [
                    (filename, i + j, batch[j], str(embeddings[j]))
                    for j in range(len(batch))
                ],
            )

        print(f"  [完成] {filename}，共写入 {len(chunks)} 块")

    await conn.close()
    print("全部完成")


if __name__ == "__main__":
    asyncio.run(main())
