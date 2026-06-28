<template>
  <div class="ai-wrap">

    <!-- 历史侧边栏遮罩 -->
    <div v-if="drawerOpen" class="drawer-mask" @click="drawerOpen = false" />

    <!-- 历史侧边栏 -->
    <div :class="['drawer', { open: drawerOpen }]">
      <div class="drawer-header">
        <span class="drawer-title">对话历史</span>
        <button class="btn-new" @click="newSession">+ 新对话</button>
      </div>
      <div class="session-list">
        <div
          v-for="s in sessions" :key="s.id"
          :class="['session-item', { active: s.id === currentSessionId }]"
          @click="selectSession(s.id)"
        >
          <span class="session-title">{{ s.title }}</span>
          <button class="btn-del" @click.stop="deleteSession(s.id)">×</button>
        </div>
        <div v-if="sessions.length === 0" class="session-empty">暂无历史对话</div>
      </div>
    </div>

    <!-- 顶部栏 -->
    <div class="chat-header">
      <button class="btn-history" @click="drawerOpen = true">历史</button>
      <span class="chat-title">{{ currentTitle }}</span>
      <button class="btn-new-top" @click="newSession">+ 新对话</button>
    </div>

    <!-- 消息区 -->
    <div class="messages" ref="msgBox">
      <div v-if="messages.length === 0" class="placeholder">
        发送问题，AI 会结合你的训练记录和健身知识给出建议
      </div>
      <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <div v-if="m.role === 'assistant'" class="bubble md" v-html="renderMd(m.content)" />
        <div v-else class="bubble">{{ m.content }}</div>
      </div>
      <div v-if="loading" class="msg assistant">
        <div class="bubble loading">思考中…</div>
      </div>
    </div>

    <!-- 健身数据选择弹窗 -->
    <div v-if="showWorkoutPicker" class="picker-wrap">
      <div class="picker-header">
        <span>选择训练数据插入</span>
        <button @click="showWorkoutPicker = false">×</button>
      </div>
      <div class="picker-list">
        <div
          v-for="day in recentWorkouts" :key="day.date"
          class="picker-day"
        >
          <div class="picker-day-title">{{ day.date }}（{{ day.muscle_groups.join('/') }}）</div>
          <div
            v-for="ex in day.exercises" :key="ex.id"
            class="picker-ex"
            @click="insertWorkout(day.date, ex)"
          >
            {{ formatExercise(ex) }}
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-bar">
      <button class="btn-plus" @click="showWorkoutPicker = !showWorkoutPicker" title="插入训练数据">+</button>
      <textarea
        v-model="input"
        placeholder="例如：帮我安排下周训练计划"
        rows="2"
        @keydown.enter.exact.prevent="send"
      />
      <button class="btn-send" @click="send" :disabled="loading || !input.trim()">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { getRecentWorkouts, getChatSessions, getChatMessages, deleteChatSession, sendChat } from '../api.js'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

function renderMd(text) {
  return DOMPurify.sanitize(marked.parse(text))
}

const messages = ref([])
const input = ref('')
const loading = ref(false)
const msgBox = ref(null)

const sessions = ref([])
const currentSessionId = ref(null)
const drawerOpen = ref(false)
const showWorkoutPicker = ref(false)
const recentWorkouts = ref([])

const currentTitle = computed(() => {
  if (!currentSessionId.value) return 'AI 建议'
  const s = sessions.value.find(s => s.id === currentSessionId.value)
  return s ? s.title : 'AI 建议'
})

onMounted(async () => {
  const [sessionsRes, workoutsRes] = await Promise.all([
    getChatSessions().catch(() => ({ data: [] })),
    getRecentWorkouts().catch(() => ({ data: [] })),
  ])
  sessions.value = sessionsRes.data
  recentWorkouts.value = workoutsRes.data
})

async function selectSession(id) {
  drawerOpen.value = false
  currentSessionId.value = id
  messages.value = []
  try {
    const res = await getChatMessages(id)
    messages.value = res.data
  } catch {}
  await scrollBottom()
}

function newSession() {
  drawerOpen.value = false
  currentSessionId.value = null
  messages.value = []
  input.value = ''
}

async function deleteSession(id) {
  await deleteChatSession(id).catch(() => {})
  sessions.value = sessions.value.filter(s => s.id !== id)
  if (currentSessionId.value === id) newSession()
}

function formatExercise(ex) {
  if (ex.duration_minutes) return `${ex.exercise_name}：${ex.duration_minutes}分钟`
  const parts = [
    ex.weight_kg != null ? `${ex.weight_kg}kg` : null,
    ex.sets ? `${ex.sets}组` : null,
    ex.reps ? `${ex.reps}次` : null,
  ].filter(Boolean)
  return `${ex.exercise_name}：${parts.join(' × ')}`
}

function insertWorkout(date, ex) {
  input.value += (input.value ? '\n' : '') + `[${date}] ${formatExercise(ex)}`
  showWorkoutPicker.value = false
}

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  await scrollBottom()

  try {
    const res = await sendChat({
      message: text,
      session_id: currentSessionId.value || undefined,
      recent_workouts_text: '',
    })
    messages.value.push({ role: 'assistant', content: res.data.reply })

    // 更新 session_id 和列表
    if (!currentSessionId.value) {
      currentSessionId.value = res.data.session_id
      const listRes = await getChatSessions()
      sessions.value = listRes.data
    } else {
      // 刷新列表顺序（updated_at 变了）
      const listRes = await getChatSessions()
      sessions.value = listRes.data
    }
  } catch {
    messages.value.push({ role: 'assistant', content: '请求失败，请检查网络或 API Key 配置。' })
  } finally {
    loading.value = false
    await scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}
</script>

<style scoped>
.ai-wrap {
  display: flex; flex-direction: column;
  height: calc(100vh - 52px);
  position: relative;
}

/* 侧边栏 */
.drawer-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 200;
}
.drawer {
  position: fixed; top: 0; left: -280px; width: 280px; height: 100vh;
  background: #fff; z-index: 201; transition: left 0.25s ease;
  display: flex; flex-direction: column;
  box-shadow: 2px 0 12px rgba(0,0,0,0.15);
}
.drawer.open { left: 0; }

.drawer-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px; border-bottom: 1px solid #e8e8e8;
}
.drawer-title { font-weight: 600; font-size: 15px; }
.btn-new {
  padding: 5px 12px; background: #ff6b35; color: #fff;
  border: none; border-radius: 16px; font-size: 13px; cursor: pointer;
}

.session-list { flex: 1; overflow-y: auto; padding: 8px 0; }
.session-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; cursor: pointer; transition: background 0.1s;
}
.session-item:hover { background: #f5f5f5; }
.session-item.active { background: #fff3ef; }
.session-title {
  flex: 1; font-size: 14px; color: #1a1a1a;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.btn-del {
  color: #bbb; background: none; border: none;
  font-size: 18px; cursor: pointer; padding: 0 4px; line-height: 1;
}
.btn-del:hover { color: #ff4444; }
.session-empty { padding: 24px 16px; text-align: center; color: #bbb; font-size: 13px; }

/* 顶部栏 */
.chat-header {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 0 6px; border-bottom: 1px solid #e8e8e8;
}
.btn-history {
  padding: 5px 12px; background: #f0f0f0; color: #555;
  border: none; border-radius: 16px; font-size: 13px; cursor: pointer;
}
.chat-title {
  flex: 1; font-size: 14px; font-weight: 500; color: #555;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.btn-new-top {
  padding: 5px 12px; background: #f0f0f0; color: #555;
  border: none; border-radius: 16px; font-size: 13px; cursor: pointer;
  white-space: nowrap;
}

/* 消息区 */
.messages {
  flex: 1; overflow-y: auto;
  padding: 12px 0; display: flex; flex-direction: column; gap: 10px;
}
.placeholder {
  text-align: center; color: #bbb; font-size: 13px; padding: 40px 16px;
}
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble {
  max-width: 85%; padding: 10px 14px;
  border-radius: 16px; font-size: 14px; line-height: 1.6;
  white-space: pre-wrap;
}
.msg.user .bubble { background: #ff6b35; color: #fff; border-bottom-right-radius: 4px; }
.msg.assistant .bubble {
  background: #fff; color: #1a1a1a; border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.loading { color: #aaa; font-style: italic; }

/* markdown 内容样式 */
.bubble.md :deep(p) { margin: 0 0 8px; }
.bubble.md :deep(p:last-child) { margin-bottom: 0; }
.bubble.md :deep(ul), .bubble.md :deep(ol) { padding-left: 18px; margin: 4px 0 8px; }
.bubble.md :deep(li) { margin-bottom: 3px; }
.bubble.md :deep(strong) { font-weight: 600; }
.bubble.md :deep(code) {
  background: #f0f0f0; padding: 1px 5px;
  border-radius: 4px; font-size: 13px; font-family: monospace;
}
.bubble.md :deep(pre) {
  background: #f0f0f0; padding: 10px 12px;
  border-radius: 8px; overflow-x: auto; margin: 6px 0;
}
.bubble.md :deep(pre code) { background: none; padding: 0; }
.bubble.md :deep(h1), .bubble.md :deep(h2), .bubble.md :deep(h3) {
  font-size: 15px; font-weight: 600; margin: 8px 0 4px;
}
.bubble.md :deep(blockquote) {
  border-left: 3px solid #ff6b35; padding-left: 10px;
  margin: 6px 0; color: #666;
}

/* 健身数据选择弹窗 */
.picker-wrap {
  background: #fff; border-top: 1px solid #e8e8e8;
  max-height: 220px; overflow-y: auto;
}
.picker-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px; font-size: 13px; font-weight: 500; color: #555;
  border-bottom: 1px solid #f0f0f0;
}
.picker-header button {
  background: none; border: none; font-size: 18px; cursor: pointer; color: #999;
}
.picker-day { padding: 6px 12px; }
.picker-day-title { font-size: 12px; color: #999; margin-bottom: 4px; }
.picker-ex {
  font-size: 13px; color: #1a1a1a; padding: 5px 8px;
  border-radius: 8px; cursor: pointer; transition: background 0.1s;
}
.picker-ex:hover { background: #fff3ef; color: #ff6b35; }

/* 输入区 */
.input-bar {
  display: flex; gap: 8px; align-items: flex-end;
  padding: 10px 0 0; border-top: 1px solid #e8e8e8;
}
.btn-plus {
  width: 36px; height: 36px; border-radius: 50%;
  background: #f0f0f0; color: #555; border: none;
  font-size: 20px; cursor: pointer; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.btn-plus:hover { background: #ff6b35; color: #fff; }
textarea {
  flex: 1; resize: none;
  padding: 10px 12px; border: 1px solid #e0e0e0;
  border-radius: 12px; font-size: 14px;
  outline: none; font-family: inherit;
}
textarea:focus { border-color: #ff6b35; }
.btn-send {
  padding: 10px 18px;
  background: #ff6b35; color: #fff;
  border: none; border-radius: 12px;
  font-size: 14px; font-weight: 600; cursor: pointer;
  white-space: nowrap;
}
.btn-send:disabled { opacity: 0.5; cursor: default; }
</style>
