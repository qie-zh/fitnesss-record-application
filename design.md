# 健身记录应用 设计文档

---

## 一、现有表结构分析

### 当前 `workout_log` 表 — 无需新增表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer | 主键 |
| date | date | 训练日期 |
| exercise_name | varchar(100) | 动作名，自由文本 + 词联想 |
| weight_kg | numeric(6,2) | 负数表示辅助重量，合理 |
| reps | integer | 次数 |
| sets | integer | 组数 |
| duration_minutes | integer | 有氧时长 |
| notes | text | 备注 |
| muscle_group | varchar(50) | 部位，自由文本 + 词联想 |

### 不需要 exercises 参考表

用户录入时 `exercise_name` 保持自由文本，后端通过以下 SQL 实时返回联想词及其所属部位：

```sql
SELECT DISTINCT ON (exercise_name) exercise_name, muscle_group
FROM workout_log
WHERE exercise_name ILIKE '%<用户输入>%'
ORDER BY exercise_name, date DESC
LIMIT 10;
```

选中已有动作后，`muscle_group` 自动填入（取该动作最近一次记录的部位），用户无需手动选择部位。全新动作才需要手动输入部位，录入后自动进入联想池。

### 历史数据修复建议（可选）

部分 2026-04-16 的记录 `muscle_group` 为空，可手动补全：
```sql
UPDATE workout_log SET muscle_group = 'chest' WHERE date = '2026-04-16' AND exercise_name IN ('史密斯上斜', '史密斯卧推', '器械夹胸');
UPDATE workout_log SET muscle_group = 'arms'  WHERE date = '2026-04-16' AND exercise_name IN ('臂屈伸', '二头弯举');
```

---

## 二、部位分类

| muscle_group 值 | 显示名 |
|---|---|
| chest | 胸 |
| back | 背 |
| shoulders | 肩 |
| biceps | 二头 |
| triceps | 三头 |
| legs | 腿 |
| core | 核心 |
| cardio | 有氧 |

> 手臂细分为 `biceps`（二头）和 `triceps`（三头），录入时词联想也会给出部位建议。

---

## 三、功能模块图

```
┌──────────────────────────────────────────────────────────┐
│                      健身记录应用                         │
├─────────────────┬──────────────────┬─────────────────────┤
│   Dashboard     │    录入模块      │   按部位 + 趋势      │
│                 │                  │                      │
│ · 最近5个训练日 │ · 动作名词联想   │ · 选择部位           │
│   按日期分组    │ · 已有动作自动   │ · 该部位最近10条     │
│   展示所有记录  │   填入部位       │   训练记录           │
│                 │ · 新动作手动     │ · 点击某条记录       │
│                 │   输入部位       │   → 该动作折线图     │
│                 │ · 重量/组数/次数 │   (重量/组数/次数)   │
│                 │ · 有氧填时长     │                      │
└─────────────────┴──────────────────┴─────────────────────┘
```

---

## 四、页面与流程

### 4.1 Dashboard（首页）

```
┌─────────────────────────────────┐
│  最近训练记录       [+ 录入]    │
├─────────────────────────────────┤
│  2026-04-19  [肩]               │
│    绳索侧拉   3.75kg × 5组 × 10次│
│    哑铃推肩   9kg   × 5组 × 15次│
├─────────────────────────────────┤
│  2026-04-18  [背][核心][有氧]   │
│    高位下拉   47kg  × 2组 × 10次│
│    ...                          │
└─────────────────────────────────┘
```

直接展示最近 5 个**有训练记录的日期**（不是自然日），无需跳转。

---

### 4.2 录入流程

```
点击 [+ 录入]
    │
    ▼
填写训练日期（默认今天）
    │
    ▼
输入动作名 → 实时词联想（来自历史记录）
    │
    ├─ 选中已有动作 → 部位自动填入（取该动作最近记录的部位）
    └─ 输入全新动作 → 手动输入部位
    │
    ▼
    ├─ 有氧动作 → 只填时长
    └─ 力量动作 → 填重量 / 组数 / 次数
    │
    ▼
提交 → 成功 → Dashboard 刷新
```

---

### 4.3 按部位查看 + 折线图（合并流程）

```
进入「按部位」页
    │
    ▼
顶部选择部位标签（胸 / 背 / 肩 / 二头 / 三头 / 腿 / 核心 / 有氧）
    │
    ▼
展示该部位最近 10 条训练记录
（每条显示：日期 · 动作名 · 重量×组×次）
    │
    ▼
点击某条记录中的动作名
    │
    ▼
底部展开（或弹出）该动作的折线图（X轴=日期）
    ├─ 最大重量 kg
    ├─ 总组数
    └─ 单组最大次数
```

---

## 五、API 接口设计

### Base URL: `/api`

---

### 5.1 词联想

#### `GET /api/suggest/exercise?q=高位`
动作名联想，同时返回该动作对应的部位（用于自动填入）

**Response**
```json
[
  { "exercise_name": "高位下拉", "muscle_group": "back" },
  { "exercise_name": "高位绳索飞鸟", "muscle_group": "chest" }
]
```

> 取消独立的部位联想接口，部位通过动作联想一并返回，全新动作时前端直接显示部位输入框。

---

### 5.2 训练记录

#### `GET /api/workouts/recent`
最近 5 个训练日的记录（Dashboard 用）

**Response**
```json
[
  {
    "date": "2026-04-19",
    "muscle_groups": ["shoulders"],
    "exercises": [
      { "id": 44, "exercise_name": "绳索侧拉", "weight_kg": 3.75, "sets": 5, "reps": 10, "duration_minutes": null },
      { "id": 45, "exercise_name": "哑铃推肩", "weight_kg": 9.00, "sets": 5, "reps": 15, "duration_minutes": null }
    ]
  }
]
```

---

#### `GET /api/workouts/by-muscle?group=back`
按部位查看最近 10 条训练记录（扁平列表，不按日期分组）

**Query Params**
| 参数 | 必填 | 说明 |
|---|---|---|
| group | ✅ | 如 `back` / `biceps` / `triceps` |

**Response**
```json
[
  { "id": 37, "date": "2026-04-18", "exercise_name": "高位下拉", "weight_kg": 47, "sets": 2, "reps": 10, "duration_minutes": null },
  { "id": 38, "date": "2026-04-18", "exercise_name": "高位下拉", "weight_kg": 40, "sets": 2, "reps": 10, "duration_minutes": null }
]
```

---

#### `GET /api/workouts/trend?exercise=高位下拉`
某动作历史趋势（折线图数据，点击记录后调用）

**Response**
```json
[
  { "date": "2026-04-18", "max_weight_kg": 47.0, "total_sets": 4, "max_reps": 10 },
  { "date": "2026-03-10", "max_weight_kg": 43.0, "total_sets": 3, "max_reps": 10 }
]
```

---

#### `POST /api/workouts`
录入一条训练记录

**Request Body**
```json
{
  "date": "2026-06-11",
  "exercise_name": "高位下拉",
  "muscle_group": "back",
  "weight_kg": 50,
  "sets": 3,
  "reps": 10,
  "duration_minutes": null,
  "notes": ""
}
```

> `muscle_group` 在前端由词联想自动填入，后端仍作为必填字段存储，保证数据完整。

**Response** `201`
```json
{ "id": 46, "date": "2026-06-11", "exercise_name": "高位下拉", ... }
```

---

## 六、技术栈

| 层 | 选择 | 说明 |
|---|---|---|
| 前端 | Vue 3 + Vite | 轻量，适合小应用 |
| 图表 | ECharts | 折线图支持好 |
| 后端 | FastAPI (Python) | 接 PostgreSQL 方便 |
| 数据库 | 现有 PostgreSQL `fitness` 库 | 无需改表结构 |
| 部署 | docker-compose 新增服务 | 加到现有 compose 文件 |

---

> 确认设计后开始实现
