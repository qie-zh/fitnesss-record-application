<template>
  <div>
    <div class="muscle-tabs">
      <button
        v-for="g in MUSCLE_GROUPS" :key="g"
        :class="['mtab', { active: selected === g }]"
        @click="select(g)"
      >{{ MUSCLE_LABEL[g] }}</button>
    </div>

    <div v-if="loading" class="state-msg">加载中…</div>
    <div v-else-if="exercises.length === 0" class="state-msg">该部位暂无记录</div>

    <div v-else class="exercise-list">
      <template v-for="ex in exercises" :key="ex.exercise_name">
        <div
          :class="['ex-row', { active: activeExercise === ex.exercise_name }]"
          @click="toggleChart(ex.exercise_name)"
        >
          <div class="ex-left">
            <span class="ex-name">{{ ex.exercise_name }}</span>
            <span class="ex-sessions">共 {{ ex.total_sessions }} 次训练</span>
          </div>
          <div class="ex-right">
            <span class="ex-detail">{{ formatExercise(ex) }}</span>
            <span class="ex-date">{{ formatDate(ex.latest_date) }}</span>
          </div>
        </div>

        <TrendChart
          v-if="activeExercise === ex.exercise_name"
          :exercise="ex.exercise_name"
          :key="ex.exercise_name"
          class="chart-inline"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getByMuscle } from '../api.js'
import { MUSCLE_LABEL, MUSCLE_GROUPS } from '../constants.js'
import TrendChart from '../components/TrendChart.vue'

const selected = ref('back')
const exercises = ref([])
const loading = ref(false)
const activeExercise = ref(null)

async function select(g) {
  selected.value = g
  activeExercise.value = null
  loading.value = true
  const res = await getByMuscle(g)
  exercises.value = res.data
  loading.value = false
}

function toggleChart(name) {
  activeExercise.value = activeExercise.value === name ? null : name
}

function formatDate(iso) {
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function formatExercise(ex) {
  if (ex.latest_duration) return `${ex.latest_duration} 分钟`
  const parts = []
  if (ex.latest_weight_kg != null) parts.push(`${ex.latest_weight_kg}kg`)
  if (ex.latest_sets) parts.push(`${ex.latest_sets}组`)
  if (ex.latest_reps) parts.push(`${ex.latest_reps}次`)
  return parts.join(' × ')
}

onMounted(() => select('back'))
</script>

<style scoped>
.state-msg { text-align: center; color: #999; padding: 48px 0; }

.muscle-tabs {
  display: flex; gap: 6px; flex-wrap: wrap;
  margin-bottom: 14px;
}

.mtab {
  padding: 6px 14px; border-radius: 20px;
  border: 1px solid #ddd; background: #fff;
  font-size: 13px; color: #555; cursor: pointer;
  transition: all 0.15s;
}
.mtab.active { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }

.exercise-list { display: flex; flex-direction: column; gap: 2px; }

.ex-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 13px 16px; background: #fff; border-radius: 10px;
  cursor: pointer; transition: background 0.15s;
}
.ex-row:hover { background: #fafafa; }
.ex-row.active { background: #fff8f5; border-left: 3px solid #ff6b35; }

.ex-left { display: flex; flex-direction: column; gap: 3px; }

.ex-name { font-size: 15px; font-weight: 500; }

.ex-sessions { font-size: 12px; color: #aaa; }

.ex-right { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }

.ex-detail { font-size: 14px; color: #333; }

.ex-date { font-size: 12px; color: #aaa; }

.chart-inline { margin-bottom: 4px; }
</style>
