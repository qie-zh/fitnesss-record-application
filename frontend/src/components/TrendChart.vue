<template>
  <div class="chart-wrap">
    <div v-if="loading" class="chart-msg">加载中…</div>
    <div v-else-if="series[0].data.length === 0" class="chart-msg">暂无数据</div>
    <VChart v-else class="chart" :option="option" autoresize />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getTrend } from '../api.js'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({ exercise: String })

const data = ref([])
const loading = ref(true)

onMounted(async () => {
  const res = await getTrend(props.exercise)
  data.value = res.data
  loading.value = false
})

const noWeight   = computed(() => data.value.every(d => d.max_weight_kg == null))
const isCardio   = computed(() => noWeight.value && data.value.some(d => d.total_duration != null))
const isBodyweight = computed(() => noWeight.value && !isCardio.value)

const dates = computed(() => data.value.map(d => d.date))

const series = computed(() => {
  if (isCardio.value) {
    return [{
      name: '时长(分钟)', type: 'line', smooth: true,
      data: data.value.map(d => d.total_duration),
      itemStyle: { color: '#ff6b35' },
    }]
  }
  if (isBodyweight.value) {
    return [
      {
        name: '总组数', type: 'line', smooth: true,
        data: data.value.map(d => d.total_sets),
        itemStyle: { color: '#4a90e2' },
      },
      {
        name: '最大次数', type: 'line', smooth: true,
        data: data.value.map(d => d.max_reps),
        itemStyle: { color: '#7ed321' },
      },
    ]
  }
  return [
    {
      name: '最大重量(kg)', type: 'line', smooth: true,
      data: data.value.map(d => d.max_weight_kg),
      itemStyle: { color: '#ff6b35' },
    },
    {
      name: '总组数', type: 'line', smooth: true,
      data: data.value.map(d => d.total_sets),
      itemStyle: { color: '#4a90e2' },
      yAxisIndex: 1,
    },
    {
      name: '最大次数', type: 'line', smooth: true,
      data: data.value.map(d => d.max_reps),
      itemStyle: { color: '#7ed321' },
      yAxisIndex: 1,
    },
  ]
})

const option = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { bottom: 0, textStyle: { fontSize: 12 } },
  grid: { top: 12, left: 40, right: 40, bottom: 40 },
  xAxis: { type: 'category', data: dates.value, axisLabel: { fontSize: 11 } },
  yAxis: (!isBodyweight.value && !isCardio.value)
    ? [
        { type: 'value', name: 'kg', nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 } },
        { type: 'value', name: '次/组', nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 } },
      ]
    : [{ type: 'value', axisLabel: { fontSize: 11 } }],
  series: series.value,
}))
</script>

<style scoped>
.chart-wrap {
  margin-top: 8px; border-radius: 12px;
  background: #fff; padding: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.chart { height: 220px; width: 100%; }
.chart-msg { text-align: center; color: #aaa; padding: 32px 0; font-size: 13px; }
</style>
