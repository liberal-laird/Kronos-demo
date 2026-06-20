<template>
  <div class="dashboard">
    <div class="controls">
      <StockSelector v-model="symbol" :stocks="stocks" @stocks-updated="refreshStocks" />
      <button class="btn" :disabled="predicting" @click="run">{{ predicting ? 'Predicting&hellip;' : 'Predict' }}</button>
    </div>

    <div v-if="predicting" class="msg warn">Running prediction for {{ symbol }} — ~2&ndash;3 min on CPU&hellip;</div>
    <div v-if="error" class="msg err">{{ error }}</div>

    <!-- latest result -->
    <div v-if="result" class="card">
      <h2>
        {{ result.symbol }} &bull; {{ result.pred_horizon }}d Forecast
        <span class="chip up">{{ pct(result.upside_prob) }}&percnt; up</span>
      </h2>
      <p class="sub">Last close <b>${{ n(result.last_close) }}</b> &nbsp;&bull;&nbsp; {{ ts(result.created_at) }}</p>

      <table>
        <thead><tr><th>Day</th><th>Date</th><th>Mean</th><th>Min</th><th>Max</th></tr></thead>
        <tbody>
          <tr v-for="pt in points" :key="pt.day_index">
            <td>{{ pt.day_index }}</td><td>{{ pt.date }}</td>
            <td class="r">${{ n(pt.mean_close) }}</td>
            <td class="r dim">${{ n(pt.min_close) }}</td>
            <td class="r dim">${{ n(pt.max_close) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="loading" class="msg">Loading&hellip;</div>

    <!-- history -->
    <div class="card">
      <h3>History</h3>
      <table v-if="history.length">
        <thead><tr><th>Symbol</th><th>Status</th><th>Close</th><th>Upside</th><th>Days</th><th>Created</th><th></th></tr></thead>
        <tbody>
          <tr v-for="h in history" :key="h.id">
            <td><b>{{ h.symbol }}</b></td>
            <td><span :class="'s-'+h.status">{{ h.status }}</span></td>
            <td>{{ h.last_close ? '$'+n(h.last_close) : '-' }}</td>
            <td>{{ h.upside_prob != null ? pct(h.upside_prob)+'%' : '-' }}</td>
            <td>{{ h.pred_horizon }}d</td>
            <td class="dim">{{ ts(h.created_at) }}</td>
            <td>
              <button v-if="h.status==='completed' && h.symbol!==symbol" class="lnk" @click="symbol=h.symbol">Load</button>
              <button class="del" @click="del(h.id)">&times;</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="dim" style="text-align:center;padding:24px">No predictions yet.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { fetchStocks, fetchLatestPrediction, createPrediction, fetchPredictions, deletePrediction } from '../api'
import StockSelector from '../components/StockSelector.vue'

const stocks = ref([])
const symbol = ref('AAPL')
const result = ref(null)
const points = ref([])
const history = ref([])
const loading = ref(false)
const predicting = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    stocks.value = await fetchStocks()
    if (stocks.value.length) symbol.value = stocks.value[0]
    await Promise.all([load(), loadHistory()])
  } catch (e) { error.value = 'Init failed: ' + e.message }
})

watch(symbol, () => { result.value = null; load() })

const refreshStocks = async () => { try { stocks.value = await fetchStocks() } catch {} }
const load = async () => {
  loading.value = true; error.value = ''
  try { const d = await fetchLatestPrediction(symbol.value); result.value = d.prediction; points.value = d.prediction_points || [] }
  catch (e) { if (e.response?.status !== 404) error.value = 'Failed: ' + e.message; result.value = null; points.value = [] }
  finally { loading.value = false }
}
const loadHistory = async () => { try { const d = await fetchPredictions(null, 50); history.value = d.items || [] } catch {} }

const run = async () => {
  predicting.value = true; error.value = ''
  try {
    await createPrediction(symbol.value, { pred_horizon: 5 })
    for (let i = 0; i < 120; i++) {
      await new Promise(r => setTimeout(r, 5000))
      try { const d = await fetchLatestPrediction(symbol.value); if (d.prediction?.status === 'completed') { result.value = d.prediction; points.value = d.prediction_points || []; break }
        if (d.prediction?.status === 'failed') throw new Error(d.prediction.error_message || 'failed') } catch (e) { if (e.response?.status !== 404) throw e }
    }
    await loadHistory()
  } catch (e) { error.value = 'Prediction failed: ' + e.message }
  finally { predicting.value = false }
}

const del = async id => { if (!confirm('Delete?')) return; try { await deletePrediction(id); history.value = history.value.filter(p => p.id !== id) } catch (e) { alert('Failed: ' + e.message) } }

const n = v => Number(v || 0).toFixed(2)
const pct = v => (Number(v || 0) * 100).toFixed(0)
const ts = v => v ? new Date(v).toLocaleString() : ''
</script>

<style scoped>
.dashboard { display:flex; flex-direction:column; gap:14px }
.controls { display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:#1a1f26; border:1px solid #2f3336; border-radius:12px }
.btn { padding:8px 22px; background:#1d9bf0; color:#fff; border:none; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; white-space:nowrap }
.btn:disabled { opacity:.5; cursor:not-allowed }
.msg { text-align:center; padding:16px; border-radius:8px; font-size:14px }
.msg.warn { color:#ff9800; background:#1a1f26; border:1px solid #ff980033 }
.msg.err { color:#f44336; background:#1a1f26; border:1px solid #f4433633 }

.card { background:#1a1f26; border:1px solid #2f3336; border-radius:12px; padding:18px 20px }
.card h2 { font-size:17px; display:flex; align-items:center; gap:10px; margin-bottom:4px }
.card h3 { font-size:15px; margin-bottom:10px }
.chip { font-size:12px; padding:2px 10px; border-radius:99px; font-weight:600 }
.chip.up { background:#00c85322; color:#00c853 }
.sub { color:#8b98a5; font-size:13px; margin-bottom:12px }

table { width:100%; border-collapse:collapse }
th, td { padding:7px 10px; text-align:left; border-bottom:1px solid #2f3336; font-size:13px }
th { color:#8b98a5; font-size:11px; text-transform:uppercase }
.r { text-align:right; font-variant-numeric:tabular-nums }
.dim { color:#8b98a5 }

.s-completed { color:#00c853; font-weight:600 }
.s-failed { color:#f44336 }
.s-pending { color:#ff9800 }

.lnk { background:#1d9bf022; color:#1d9bf0; border:none; padding:3px 8px; border-radius:4px; cursor:pointer; font-size:12px; margin-right:4px }
.del { background:none; border:none; color:#f44336; font-size:16px; cursor:pointer; padding:2px 6px }

@media (max-width:640px) { .controls { flex-direction:column; gap:10px; align-items:stretch } }
</style>
