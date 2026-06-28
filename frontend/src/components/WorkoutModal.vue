<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <h2>{{ workout ? '编辑训练' : '录入训练' }}</h2>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <form @submit.prevent="submit" class="form">
        <label>日期</label>
        <input type="date" v-model="form.date" required />

        <label>动作</label>
        <AutoComplete
          v-model="form.exercise_name"
          :items="suggestions"
          class="form-input"
          placeholder="输入动作名…"
          @input.native="fetchSuggestions"
          @update:modelValue="fetchSuggestions"
          @select="onSelectExercise"
          required
        />

        <template v-if="form.exercise_name && !autoFilledMuscle">
          <label>部位</label>
          <select v-model="form.muscle_group" required>
            <option value="">请选择</option>
            <option v-for="g in MUSCLE_GROUPS" :key="g" :value="g">{{ MUSCLE_LABEL[g] }}</option>
          </select>
        </template>

        <template v-else-if="autoFilledMuscle">
          <label>部位</label>
          <div class="auto-filled">{{ MUSCLE_LABEL[form.muscle_group] || form.muscle_group }}</div>
        </template>

        <template v-if="form.muscle_group === 'cardio'">
          <label>时长（分钟）</label>
          <input type="number" v-model.number="form.duration_minutes" min="1" required />
        </template>

        <template v-else-if="form.muscle_group">
          <label>重量（kg）</label>
          <input type="number" v-model.number="form.weight_kg" step="0.25" placeholder="辅助器械可填负数" />

          <label>组数</label>
          <input type="number" v-model.number="form.sets" min="1" required />

          <label>次数</label>
          <input type="number" v-model.number="form.reps" min="1" required />
        </template>

        <label>备注</label>
        <input type="text" v-model="form.notes" placeholder="可选" />

        <button type="submit" class="btn-submit" :disabled="saving">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import AutoComplete from './AutoComplete.vue'
import { suggestExercise, createWorkout, updateWorkout } from '../api.js'
import { MUSCLE_LABEL, MUSCLE_GROUPS } from '../constants.js'

const props = defineProps({ workout: { type: Object, default: null } })
const emit = defineEmits(['close', 'saved'])

const today = new Date().toISOString().slice(0, 10)
const form = reactive(props.workout ? { ...props.workout } : {
  date: today,
  exercise_name: '',
  muscle_group: '',
  weight_kg: null,
  sets: null,
  reps: null,
  duration_minutes: null,
  notes: '',
})

const suggestions = ref([])
// 从联想词选中后置 true，将部位显示为只读标签，防止误触下拉框
const autoFilledMuscle = ref(false)
const saving = ref(false)

let debounceTimer = null
async function fetchSuggestions(val) {
  const q = typeof val === 'string' ? val : form.exercise_name
  if (!q) { suggestions.value = []; return }
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(async () => {
    const res = await suggestExercise(q)
    suggestions.value = res.data.map(d => ({
      label: d.exercise_name,
      sub: MUSCLE_LABEL[d.muscle_group] || d.muscle_group,
      muscle_group: d.muscle_group,
    }))
  }, 200)
}

function onSelectExercise(item) {
  if (item.muscle_group) {
    form.muscle_group = item.muscle_group
    autoFilledMuscle.value = true
  } else {
    autoFilledMuscle.value = false
  }
}

async function submit() {
  saving.value = true
  try {
    if (props.workout?.id) {
      await updateWorkout(props.workout.id, { ...form })
    } else {
      await createWorkout({ ...form })
    }
    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0; z-index: 300;
  background: rgba(0,0,0,0.45);
  display: flex; align-items: flex-end; justify-content: center;
}

.modal {
  background: #fff; border-radius: 20px 20px 0 0;
  width: 100%; max-width: 680px;
  padding: 20px 20px 40px;
  max-height: 90vh; overflow-y: auto;
}

.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}

h2 { font-size: 18px; }

.close-btn {
  background: none; border: none;
  font-size: 18px; color: #999; cursor: pointer;
}

.form { display: flex; flex-direction: column; gap: 8px; }

label { font-size: 13px; color: #666; margin-top: 4px; }

input, select {
  padding: 10px 12px; border: 1px solid #e0e0e0;
  border-radius: 8px; font-size: 15px;
  outline: none; width: 100%;
}
input:focus, select:focus { border-color: #ff6b35; }

.form-input input {
  padding: 10px 12px; border: 1px solid #e0e0e0;
  border-radius: 8px; font-size: 15px;
  outline: none; width: 100%;
}
.form-input input:focus { border-color: #ff6b35; }

.auto-filled {
  padding: 10px 12px; background: #f5f5f5;
  border-radius: 8px; font-size: 15px; color: #555;
}

.btn-submit {
  margin-top: 12px; padding: 14px;
  background: #ff6b35; color: #fff;
  border: none; border-radius: 10px;
  font-size: 16px; font-weight: 600;
  cursor: pointer;
}
.btn-submit:disabled { opacity: 0.6; }
</style>
