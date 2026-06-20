<template>
  <div class="combobox">
    <div class="row">
      <label for="si">Symbol</label>
      <input
        id="si" ref="inp" v-model="q" type="text" placeholder="e.g. AAPL" autocomplete="off"
        @input="onInput" @focus="open=true" @blur="onBlur"
        @keydown.enter="onEnter" @keydown.escape="open=false"
        @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)"
      />
      <button v-if="q" class="clr" @mousedown.prevent="clear">&times;</button>
    </div>
    <ul v-if="open && filtered.length" class="dd">
      <li v-for="(s,i) in filtered" :key="s" :class="{hl:i===idx}" @mousedown.prevent="pick(s)" @mouseenter="idx=i">{{ s }}</li>
      <li v-if="q && !filtered.includes(q.toUpperCase()) && q.length>=2" class="add" @mousedown.prevent="pick(q.toUpperCase())">+ Add "{{ q.toUpperCase() }}"</li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { addStock } from '../api'

const p = defineProps({ stocks:Array, modelValue:String })
const emit = defineEmits(['update:modelValue','stocks-updated'])

const inp = ref(null), q = ref(''), open = ref(false), idx = ref(-1)

const filtered = computed(() => {
  const s = q.value.trim().toUpperCase()
  return s ? p.stocks.filter(x => x.includes(s)) : [...p.stocks]
})

watch(() => p.modelValue, v => { q.value = v || '' })

function onInput() { open.value = true; idx.value = -1 }
function onBlur() { setTimeout(() => open.value = false, 150) }
function move(d) {
  if (!open.value) { open.value = true; return }
  if (filtered.value.length) idx.value = Math.min(filtered.value.length-1, Math.max(0, idx.value+d))
}
function onEnter() {
  const v = q.value.trim().toUpperCase()
  if (!v) return
  if (idx.value >= 0 && idx.value < filtered.value.length) pick(filtered.value[idx.value])
  else pick(v)
}
async function pick(s) {
  s = s.toUpperCase(); open.value = false; q.value = s; emit('update:modelValue', s)
  if (!p.stocks.includes(s)) { try { await addStock(s); emit('stocks-updated') } catch {} }
}
function clear() { q.value = ''; emit('update:modelValue', ''); inp.value?.focus() }
</script>

<style scoped>
.combobox { position:relative; flex:1; max-width:240px }
.row { display:flex; align-items:center; gap:8px }
label { font-size:13px; color:#8b98a5; white-space:nowrap }
input { flex:1; padding:7px 28px 7px 10px; background:#1a1f26; border:1px solid #2f3336; border-radius:8px; color:#e7e9ea; font-size:15px; font-weight:600; outline:none; text-transform:uppercase }
input:focus { border-color:#1d9bf0 }
input::placeholder { text-transform:none; font-weight:400; color:#5c656f }
.clr { position:absolute; right:4px; background:none; border:none; color:#8b98a5; font-size:18px; cursor:pointer; padding:2px 6px }
.clr:hover { color:#e7e9ea }
.dd { position:absolute; top:100%; left:0; right:0; margin-top:4px; background:#1a1f26; border:1px solid #2f3336; border-radius:8px; list-style:none; max-height:200px; overflow-y:auto; z-index:100; padding:4px 0 }
.dd li { padding:7px 10px; cursor:pointer; font-size:13px; color:#e7e9ea }
.dd li.hl { background:#1d9bf033 }
.dd li.add { color:#00c853; border-top:1px solid #2f3336; font-style:italic }
</style>
