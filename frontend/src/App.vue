<template>
  <div class="app">
    <header class="header">
      <nav class="tabs">
        <button :class="['tab', { active: page === 'dashboard' }]" @click="page = 'dashboard'">最近记录</button>
        <button :class="['tab', { active: page === 'muscle' }]" @click="page = 'muscle'">按部位</button>
      </nav>
      <button class="btn-add" @click="showModal = true">+ 录入</button>
    </header>

    <main class="main">
      <DashboardView v-if="page === 'dashboard'" :key="refreshKey" />
      <MuscleView v-else :key="refreshKey" />
    </main>

    <WorkoutModal v-if="showModal" @close="showModal = false" @saved="onSaved" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import DashboardView from './views/DashboardView.vue'
import MuscleView from './views/MuscleView.vue'
import WorkoutModal from './components/WorkoutModal.vue'

const page = ref('dashboard')
const showModal = ref(false)
const refreshKey = ref(0)

function onSaved() {
  showModal.value = false
  refreshKey.value++
}
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f5f5f5;
  color: #1a1a1a;
}

.app { display: flex; flex-direction: column; min-height: 100vh; }

.header {
  position: sticky; top: 0; z-index: 100;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  height: 52px;
}

.tabs { display: flex; gap: 4px; }

.tab {
  padding: 6px 16px;
  border: none; border-radius: 20px;
  background: transparent; cursor: pointer;
  font-size: 14px; color: #666;
  transition: all 0.15s;
}
.tab.active { background: #1a1a1a; color: #fff; }

.btn-add {
  padding: 7px 16px;
  background: #ff6b35; color: #fff;
  border: none; border-radius: 20px;
  font-size: 14px; font-weight: 600;
  cursor: pointer;
}

.main { flex: 1; padding: 16px; max-width: 680px; margin: 0 auto; width: 100%; }
</style>
