<template>
  <div>
    <div v-if="loading" class="state-msg">加载中…</div>
    <div v-else-if="days.length === 0" class="state-msg">暂无记录，点击右上角录入第一条训练</div>

    <div v-for="day in days" :key="day.date" class="day-card">
      <div class="day-header">
        <span class="day-date">{{ formatDate(day.date) }}</span>
        <div class="muscle-tags">
          <span v-for="g in day.muscle_groups" :key="g" class="tag">{{ MUSCLE_LABEL[g] || g }}</span>
        </div>
      </div>
      <div class="exercise-list">
        <div v-for="ex in day.exercises" :key="ex.id" class="exercise-row">
          <span class="ex-name">{{ ex.exercise_name }}</span>
          <span class="ex-detail">{{ formatExercise(ex) }}</span>
          <button class="btn-edit" @click="emit('edit', ex)">编辑</button>
          <button class="btn-del" @click="onDelete(ex)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getRecentWorkouts, deleteWorkout } from '../api.js'
import { MUSCLE_LABEL } from '../constants.js'

const emit = defineEmits(['edit', 'deleted'])

const days = ref([])
const loading = ref(true)

onMounted(async () => {
  const res = await getRecentWorkouts()
  days.value = res.data
  loading.value = false
})

function formatDate(iso) {
  const d = new Date(iso)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

async function onDelete(ex) {
  if (!confirm(`确认删除「${ex.exercise_name}」？`)) return
  await deleteWorkout(ex.id)
  emit('deleted')
}

function formatExercise(ex) {
  if (ex.duration_minutes) return `${ex.duration_minutes} 分钟`
  const parts = []
  if (ex.weight_kg != null) parts.push(`${ex.weight_kg}kg`)
  if (ex.sets) parts.push(`${ex.sets}组`)
  if (ex.reps) parts.push(`${ex.reps}次`)
  return parts.join(' × ')
}
</script>

<style scoped>
.state-msg { text-align: center; color: #999; padding: 48px 0; }

.day-card {
  background: #fff; border-radius: 12px;
  padding: 14px 16px; margin-bottom: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.day-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }

.day-date { font-weight: 700; font-size: 15px; }

.muscle-tags { display: flex; gap: 4px; flex-wrap: wrap; }

.tag {
  padding: 2px 8px; border-radius: 10px;
  background: #f0f0f0; font-size: 12px; color: #555;
}

.exercise-list { display: flex; flex-direction: column; gap: 6px; }

.exercise-row { display: flex; justify-content: space-between; align-items: center; }

.ex-name { font-size: 14px; color: #333; }

.ex-detail { font-size: 13px; color: #888; }

.btn-edit {
  padding: 2px 10px; border-radius: 8px;
  border: 1px solid #e0e0e0; background: #fff;
  font-size: 12px; color: #666; cursor: pointer;
  flex-shrink: 0;
}
.btn-edit:hover { border-color: #ff6b35; color: #ff6b35; }

.btn-del {
  padding: 2px 10px; border-radius: 8px;
  border: 1px solid #e0e0e0; background: #fff;
  font-size: 12px; color: #999; cursor: pointer;
  flex-shrink: 0;
}
.btn-del:hover { border-color: #e53935; color: #e53935; }
</style>
