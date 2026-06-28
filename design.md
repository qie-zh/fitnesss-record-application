# 健身记录应用 设计文档

---

## 一、系统架构

```
用户浏览器 (Vue 3)
    │  HTTP /api/*
    ▼
fitness-frontend  [Nginx · 宿主机 3002 端口]
    │  反向代理 /api → fitness-backend:8000
    ▼
fitness-backend   [FastAPI · Python 3.11]
    │
    ├─ 训练记录 CRUD ──────────→ postgres-rag:5432
    │                              └─ fitness.workout_log
    │
    └─ /api/chat (RAG) ────────→ postgres-rag:5432
                                   └─ fitness.fitness_knowledge (pgvector)
                         └──────→ MiniMax API
                                   ├─ embo-01      (向量化)
                                   └─ abab6.5s-chat (生成)
```

**网络**：所有容器在 `app_default` 网络内互通，仅前端暴露 3002 端口到宿主机。

**知识库入库**（一次性，手动执行）：

```
/mnt/nas/Knowledge/fitness/*.pdf
    │ pdfplumber 提取文本
    ▼
按 500 字分块（80 字重叠）
    │ MiniMax embo-01 (type=db)
    ▼
fitness.fitness_knowledge (pgvector)
```

执行方式：`docker exec fitness-backend python ingest.py`

---

## 二、数据库

### 2.1 `workout_log` — 训练记录

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer | 主键 |
| date | date | 训练日期 |
| exercise_name | varchar(100) | 动作名，自由文本 + 词联想 |
| weight_kg | numeric(6,2) | 负数表示辅助重量 |
| reps | integer | 次数 |
| sets | integer | 组数 |
| duration_minutes | integer | 有氧时长（与 weight/sets/reps 互斥） |
| notes | text | 备注 |
| muscle_group | varchar(50) | 部位，见下表 |

### 2.2 `fitness_knowledge` — RAG 知识库

| 字段 | 类型 | 说明 |
|---|---|---|
| id | serial | 主键 |
| source | text | 来源文件名（如 `15503946.pdf`） |
| chunk_index | int | 在文档中的块序号 |
| content | text | 知识块原文 |
| embedding | vector(1536) | MiniMax embo-01 向量，1536 维 |

索引：`USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)`

### 2.3 部位枚举

| muscle_group | 显示名 |
|---|---|
| chest | 胸 |
| back | 背 |
| shoulders | 肩 |
| biceps | 二头 |
| triceps | 三头 |
| legs | 腿 |
| core | 核心 |
| cardio | 有氧 |

> 动作名词联想通过 `DISTINCT ON (exercise_name) ORDER BY date DESC` 取最近一次记录的 muscle_group，新动作才需要手动选择部位。

---

## 三、功能模块

```
┌──────────────────────────────────────────────────────────────┐
│                        健身记录应用                           │
├──────────────────┬───────────────────┬───────────────────────┤
│   最近记录       │    按部位         │    AI 建议            │
│                  │                   │                       │
│ · 最近5训练日    │ · 部位标签切换    │ · 自然语言对话        │
│   按日期分组     │ · 该部位所有动作  │ · 自动附带最近训练    │
│ · 每条可编辑     │   最新一次数据    │   记录作为上下文      │
│ · 每条可删除     │ · 点击展开折线图  │ · RAG 检索知识库      │
│ · 右上角新建     │   (手风琴效果)    │   生成个性化建议      │
└──────────────────┴───────────────────┴───────────────────────┘
         │                  │                      │
    + 录入 Modal       TrendChart            /api/chat
    (新建/编辑复用)    (ECharts 折线)       (MiniMax)
```

---

## 四、页面与流程

### 4.1 最近记录（Dashboard）

```
┌─────────────────────────────────────────┐
│  最近记录  按部位  AI建议    [+ 录入]   │
├─────────────────────────────────────────┤
│  6月14日  [肩]                          │
│    绳索侧拉  3.75kg × 5组 × 10次  编辑 删除│
│    哑铃推肩  9kg   × 5组 × 15次   编辑 删除│
├─────────────────────────────────────────┤
│  6月13日  [背][核心]                    │
│    高位下拉  47kg × 2组 × 10次    编辑 删除│
└─────────────────────────────────────────┘
```

### 4.2 录入 / 编辑流程（同一个 Modal）

```
点击 [+ 录入] → editingWorkout = null → 新建模式
点击 [编辑]   → editingWorkout = 该条记录 → 编辑模式
    │
    ▼
WorkoutModal 根据是否有 workout.id 决定调用 POST 还是 PUT
    │
    ├─ 填写日期（默认今天）
    ├─ 输入动作名 → 实时词联想
    │   ├─ 选中已有动作 → muscle_group 自动填入（只读标签）
    │   └─ 全新动作 → 显示部位下拉框
    ├─ 有氧 → 只填时长
    └─ 力量 → 填重量 / 组数 / 次数
    │
    ▼
保存 → 列表刷新
```

### 4.3 按部位 + 折线图

```
选择部位标签
    │
    ▼
展示该部位所有动作（最新一次数据 + 累计训练次数）
    │
    ▼
点击某动作行 → 展开折线图（再次点击折叠）
    ├─ 力量：最大重量(kg) / 总组数 / 最大次数  [双 Y 轴]
    └─ 有氧：总时长(分钟)                      [单 Y 轴]
```

### 4.4 AI 建议（RAG 对话）

```
进入页面 → 拉取最近训练记录并格式化为文本（缓存）
    │
用户发送问题
    │
    ▼
POST /api/chat { message, recent_workouts_text }
    │
    ├─ 1. 问题 → embo-01 (type=query) → 查询向量
    ├─ 2. pgvector <=> 余弦检索 Top 4 知识块
    ├─ 3. 拼 Prompt：系统角色 + 知识块 + 训练记录 + 问题
    └─ 4. abab6.5s-chat 生成回答
    │
    ▼
气泡样式展示对话，Enter 发送，支持多轮
```

---

## 五、API 接口

### Base URL: `/api`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/suggest/exercise?q=` | 动作名词联想（含 muscle_group） |
| GET | `/workouts/recent` | 最近 5 训练日记录 |
| GET | `/workouts/by-muscle?group=` | 按部位查所有动作最新数据 |
| GET | `/workouts/trend?exercise=` | 某动作历史趋势（折线图） |
| POST | `/workouts` | 新建训练记录 |
| PUT | `/workouts/{id}` | 编辑训练记录 |
| DELETE | `/workouts/{id}` | 删除训练记录 |
| POST | `/chat` | AI 建议（RAG + MiniMax） |

### POST `/chat` 详情

**Request**
```json
{
  "message": "帮我安排下周训练计划",
  "recent_workouts_text": "2026-06-14（肩）\n  - 绳索侧拉：3.75kg × 5组 × 10次\n..."
}
```

**Response**
```json
{ "reply": "根据你最近的训练情况..." }
```

---

## 六、技术栈

| 层 | 选择 | 说明 |
|---|---|---|
| 前端框架 | Vue 3 + Vite | 轻量，组合式 API |
| 图表 | ECharts + vue-echarts | 折线图，双 Y 轴 |
| HTTP 客户端 | Axios | 统一封装在 api.js |
| 后端 | FastAPI (Python 3.11) | 异步，类型注解 |
| 数据库驱动 | asyncpg | 异步 PostgreSQL |
| HTTP 客户端（后端） | httpx | 异步调用 MiniMax API |
| PDF 解析 | pdfplumber | 中文 PDF 提取 |
| 数据库 | PostgreSQL 16 + pgvector | 现有容器 `postgres-rag` |
| AI API | MiniMax | embo-01 embedding + abab6.5s-chat |
| 部署 | docker-compose | app_default 网络 |
| 静态服务 | Nginx | 前端 + /api 反向代理 |

---

## 七、文件结构

```
fitness/
├── .env                    # MINIMAX_API_KEY（不提交 git）
├── .gitignore
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt    # fastapi uvicorn asyncpg httpx pdfplumber
│   ├── main.py             # FastAPI 路由
│   └── ingest.py           # 知识库入库脚本（手动执行一次）
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── vite.config.js
    └── src/
        ├── api.js           # Axios 封装
        ├── constants.js     # 部位枚举
        ├── App.vue          # 顶部导航 + Tab 切换
        ├── views/
        │   ├── DashboardView.vue  # 最近记录
        │   ├── MuscleView.vue     # 按部位
        │   └── AiView.vue         # AI 建议
        └── components/
            ├── WorkoutModal.vue   # 新建/编辑 Modal
            ├── AutoComplete.vue   # 动作名词联想下拉
            └── TrendChart.vue     # ECharts 折线图
```
