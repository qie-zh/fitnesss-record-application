<template>
  <div class="ac-wrap">
    <input
      v-bind="$attrs"
      :value="modelValue"
      @input="onInput"
      @blur="onBlur"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.enter.prevent="confirm(highlighted)"
      @keydown.esc="close"
      autocomplete="off"
    />
    <ul v-if="open && items.length" class="dropdown">
      <li
        v-for="(item, i) in items" :key="i"
        :class="{ hl: i === highlighted }"
        @mousedown.prevent="confirm(i)"
      >
        <span>{{ item.label }}</span>
        <span v-if="item.sub" class="sub">{{ item.sub }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: String,
  items: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'select'])

const open = ref(false)
const highlighted = ref(0)

function onInput(e) {
  emit('update:modelValue', e.target.value)
  open.value = true
  highlighted.value = 0
}

function onBlur() {
  // blur 先于 mousedown 触发；延迟关闭让下拉项的 confirm() 能先执行
  setTimeout(() => { open.value = false }, 150)
}

function move(dir) {
  highlighted.value = Math.max(0, Math.min(props.items.length - 1, highlighted.value + dir))
}

function confirm(i) {
  const item = props.items[i]
  if (!item) return
  emit('update:modelValue', item.label)
  emit('select', item)
  open.value = false
}

function close() {
  open.value = false
}
</script>

<style scoped>
.ac-wrap { position: relative; }

.dropdown {
  position: absolute; top: 100%; left: 0; right: 0;
  background: #fff; border: 1px solid #e0e0e0;
  border-radius: 8px; margin-top: 4px;
  list-style: none; padding: 4px 0;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  z-index: 200;
}

li {
  display: flex; justify-content: space-between; align-items: center;
  padding: 9px 14px; cursor: pointer; font-size: 14px;
}
li.hl, li:hover { background: #f5f5f5; }

.sub { font-size: 12px; color: #aaa; }
</style>
