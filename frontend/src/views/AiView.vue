<template>
  <div class="ai-wrap">
    <!-- 对话历史区 -->
    <div class="messages" ref="msgBox">
      <div v-if="messages.length === 0" class="placeholder">
        发送问题，AI 会结合你的训练记录和健身资料给出建议
      </div>
      <div
        v-for="(m, i) in messages" :key="i"
        :class="['msg', m.role]"
      >
        <div class="bubble">{{ m.content }}</div>
      </div>
      <div v-if="loading" class="msg assistant">
        <div class="bubble loading">思考中…</div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-bar">
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
import { ref, nextTick, onMounted } from 'vue'
import { getRecentWorkouts } from '../api.js'
import axios from 'axios'

const messages = ref([])
const input = ref('')
const loading = ref(false)
const msgBox = ref(null)

// 缓存最近训练记录文本，首次打开时拉取一次
let recentWorkoutsText = ''

onMounted(async () => {
  try {
    const res = await getRecentWorkouts()
    // 把结构化训练数据转成易读的文本，让 LLM 更好理解
    recentWorkoutsText = res.data.map(day => {
      const exList = day.exercises.map(ex => {
        if (ex.duration_minutes) return `  - ${ex.exercise_name}：${ex.duration_minutes}分钟`
        const detail = [
          ex.weight_kg != null ? `${ex.weight_kg}kg` : null,
          ex.sets ? `${ex.sets}组` : null,
          ex.reps ? `${ex.reps}次` : null,
        ].filter(Boolean).join(' × ')
        return `  - ${ex.exercise_name}：${detail}`
      }).join('\n')
      return `${day.date}（${day.muscle_groups.join('/')}）\n${exList}`
    }).join('\n\n')
  } catch {
    recentWorkoutsText = ''
  }
})

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  await scrollBottom()

  try {
    const res = await axios.post('/api/chat', {
      message: text,
      recent_workouts_text: recentWorkoutsText,
    })
    messages.value.push({ role: 'assistant', content: res.data.reply })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '请求失败，请检查 API Key 配置。' })
  } finally {
    loading.value = false
    await scrollBottom()
  }
}

// 每次新消息后滚到底部
async function scrollBottom() {
  await nextTick()
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}
</script>

<style scoped>
.ai-wrap {
  display: flex; flex-direction: column;
  height: calc(100vh - 52px);  /* 减去顶部导航高度 */
}

.messages {
  flex: 1; overflow-y: auto;
  padding: 12px 0; display: flex; flex-direction: column; gap: 10px;
}

.placeholder {
  text-align: center; color: #bbb;
  font-size: 13px; padding: 40px 16px;
}

.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }

.bubble {
  max-width: 85%; padding: 10px 14px;
  border-radius: 16px; font-size: 14px; line-height: 1.6;
  white-space: pre-wrap;  /* 保留 AI 回答中的换行格式 */
}
.msg.user .bubble { background: #ff6b35; color: #fff; border-bottom-right-radius: 4px; }
.msg.assistant .bubble { background: #fff; color: #1a1a1a; border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

.loading { color: #aaa; font-style: italic; }

.input-bar {
  display: flex; gap: 8px; align-items: flex-end;
  padding: 10px 0 0;
  border-top: 1px solid #e8e8e8;
}

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
