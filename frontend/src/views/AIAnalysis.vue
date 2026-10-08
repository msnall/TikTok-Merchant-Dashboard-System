<template>
  <div class="page ai-analysis">
    <header class="page-head">
      <div><span class="eyebrow">OPERATIONS ANALYSIS</span><h1>AI运营分析</h1></div>
      <div class="header-actions"><router-link to="/ads/feedback-evaluation">运营闭环</router-link><span class="mode-label">AI辅助 · 人工决策</span></div>
    </header>

    <form class="analysis-form" @submit.prevent="analyze">
      <label>广告计划 ID<el-input v-model="campaignId" placeholder="输入计划 ID" /></label>
      <label>当前运营情况<el-input v-model="report" type="textarea" :rows="3" maxlength="5000" placeholder="例如：A计划消耗8美元，0单，目标ROI 0.8。" /></label>
      <div class="form-actions"><el-button type="primary" native-type="submit" :loading="loading">开始分析</el-button></div>
    </form>
    <div class="open-analysis"><label>继续记录已有分析 <el-input v-model="existingAnalysisId" type="number" :min="1" placeholder="分析记录 ID" /></label><el-button :loading="openingAnalysis" @click="openAnalysis">打开记录</el-button></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <div v-if="result" class="report">
      <section class="judgment-section">
        <div class="section-kicker">01 / 当前判断</div>
        <div class="judgment-head">
          <div><span class="campaign-tag">计划 {{ result.campaign_id || campaignId }}</span><h2>{{ diagnosis.judgment_candidate || decisionTitle(result.decision) }}</h2></div>
          <span class="state-tag">{{ stateTitle(result.state) }}</span>
        </div>
        <p class="judgment-summary">{{ plainSummary }}</p>
        <div class="metric-strip">
          <div><span>当前消耗</span><strong>{{ spendDisplay }}</strong></div>
          <div><span>订单</span><strong>{{ valueDisplay(current.orders) }}</strong></div>
          <div><span>当前 ROI</span><strong>{{ valueDisplay(current.current_roi) }}</strong></div>
          <div><span>目标 ROI</span><strong>{{ valueDisplay(current.target_roi) }}</strong></div>
        </div>
      </section>

      <section class="report-section">
        <div class="section-kicker">02 / 判断原因</div><h2>为什么这样判断</h2>
        <ul v-if="keyFacts.length" class="fact-list"><li v-for="fact in keyFacts" :key="fact">{{ fact }}</li></ul>
        <p v-else class="muted">当前缺少可确认的数据，建议先核对消耗和订单。</p>
        <p v-if="keyLimitation" class="evidence-note">尚不能确认：{{ keyLimitation }}</p>
      </section>

      <section class="report-section">
        <div class="section-kicker">03 / 问题定位</div><h2>可能原因</h2>
        <div v-if="hypotheses.length" class="hypothesis-list">
          <div v-for="item in hypotheses" :key="item.cause" class="hypothesis-row">
            <div><strong>{{ item.cause }}</strong><p v-if="item.supporting_evidence?.length">依据：{{ item.supporting_evidence.join('；') }}</p><p v-if="item.missing_evidence?.length">需要验证：{{ item.missing_evidence.join('、') }}</p></div>
            <span class="confidence-tag">可信度{{ confidenceTitle(item.confidence) }}</span>
          </div>
        </div>
        <p v-else class="muted">现有数据不足以定位原因，不应直接归因于素材或商品。</p>
      </section>

      <section class="report-section advice-section">
        <div class="section-kicker">04 / 运营建议</div><h2>下一步怎么做</h2>
        <p class="advice-copy">{{ advice }}</p>
        <p class="confirmation-note">反馈只记录运营对建议的看法，不代表广告已执行。</p>
        <div v-if="recommendationsLoading" class="muted">正在读取本次分析的建议…</div>
        <div v-else-if="recommendations.length" class="recommendation-list">
          <article v-for="item in recommendations" :key="item.id" class="recommendation-card">
            <div class="recommendation-heading"><div><span class="recommendation-number">建议 {{ item.id }}</span><strong>{{ item.strategy_id ? strategyTitle(item.strategy_id) : '系统建议' }}</strong></div><span class="feedback-state" :class="feedbackClass(item)">{{ feedbackStatus(item) }}</span></div>
            <p>{{ item.recommendation_content }}</p>
            <div v-if="item.status === 'UNREVIEWED'" class="feedback-form">
              <el-radio-group v-model="item.feedback_type" size="small"><el-radio-button label="ACCEPT">接受</el-radio-button><el-radio-button label="REJECT">拒绝</el-radio-button><el-radio-button label="MODIFY">修改</el-radio-button></el-radio-group>
              <el-input v-model="item.operator_note" type="textarea" :rows="2" maxlength="2000" placeholder="填写原因或修改意见" />
              <el-button type="primary" size="small" :disabled="!item.feedback_type" :loading="savingRecommendationId === item.id" @click="submitFeedback(item)">提交反馈</el-button>
              <p v-if="item.feedbackError" class="error-text">{{ item.feedbackError }}</p>
            </div>
            <div v-else class="feedback-record"><span>反馈：{{ feedbackTypeTitle(item.feedback_type) }}</span><span v-if="item.operator_note">备注：{{ item.operator_note }}</span><strong>{{ executionStatusTitle(item.execution_status) }}</strong><small>反馈不会自动创建执行记录。</small>
              <div class="execution-controls">
                <h3>执行情况</h3>
                <p v-if="item.execution" class="saved-record">最近记录：{{ executionStatusTitle(item.execution.execution_status) }} · {{ item.execution.actual_action }}<span v-if="item.execution.execution_source"> · {{ executionSourceTitle(item.execution.execution_source) }}</span></p>
                <p v-else class="muted">尚未记录执行；接受建议不等于已执行。</p>
                <details v-if="item.execution_history?.length > 1" class="execution-history"><summary>查看较早执行与观察记录（{{ item.execution_history.length - 1 }}）</summary><div v-for="record in item.execution_history.slice(1)" :key="record.id" class="saved-record"><strong>{{ executionStatusTitle(record.execution_status) }} · {{ record.actual_action }}</strong><span v-if="record.execution_source">来源：{{ executionSourceTitle(record.execution_source) }}</span><span v-for="observation in record.observations" :key="observation.id">{{ observation.observation_window.start || '日期未提供' }} 至 {{ observation.observation_window.end || '日期未提供' }} · ROI {{ valueDisplay(observation.before_metrics.roi) }} → {{ valueDisplay(observation.after_metrics.roi) }} · 因果关系未知</span></div></details>
                <label>执行状态<el-select v-model="item.execution_input_status" size="small"><el-option label="未知" value="UNKNOWN"/><el-option label="待执行" value="PENDING"/><el-option label="已确认执行" value="CONFIRMED"/><el-option label="执行失败" value="FAILED"/></el-select></label>
                <label>动作描述<el-input v-model="item.execution_action" size="small" placeholder="例如：计划手动调整 ROI 目标"/></label>
                <label>记录来源<el-select v-model="item.execution_source_input" size="small" placeholder="选择来源"><el-option label="人工记录（未核验）" value="operator_input"/><el-option label="人工核验" value="operator_verified"/><el-option label="截图凭证" value="manual_screenshot"/><el-option label="导入记录" value="import"/></el-select></label>
                <label v-if="item.execution_input_status === 'CONFIRMED'">实际执行时间（可选）<el-input v-model="item.execution_time" type="datetime-local" size="small"/></label>
                <label>执行证据<el-input v-model="item.execution_evidence" size="small" placeholder="确认执行或失败时必填"/></label>
                <el-button size="small" :loading="savingExecutionId === item.id" @click="submitExecution(item)">保存执行记录</el-button>
                <p v-if="item.executionError" class="error-text">{{ item.executionError }}</p>
              </div>
              <div v-if="item.execution_id" class="observation-controls">
                <h3>后续结果观察</h3>
                <p v-if="item.execution_status !== 'CONFIRMED'">当前执行未确认，观察记录不能证明该建议已执行。</p>
                <div v-for="observation in item.observations || []" :key="observation.id" class="saved-record">
                  <strong>{{ observation.observation_window.start || '日期未提供' }} 至 {{ observation.observation_window.end || '日期未提供' }}</strong>
                  <span v-for="metric in ['roi', 'orders', 'spend']" :key="metric" v-show="observation.before_metrics[metric] != null || observation.after_metrics[metric] != null">{{ metricTitle(metric) }}：{{ valueDisplay(observation.before_metrics[metric]) }} → {{ valueDisplay(observation.after_metrics[metric]) }}</span>
                  <small>记录来源：{{ observation.data_source === 'manual' ? '人工录入' : '导入' }} · 因果关系：未知</small>
                </div>
                <div class="observation-fields">
                  <label>开始日期<el-input v-model="item.observation_start" type="date" size="small"/></label>
                  <label>结束日期<el-input v-model="item.observation_end" type="date" size="small"/></label>
                  <label v-for="metric in observationInputMetrics" :key="metric.key">观察前{{ metric.label }}<el-input v-model="item.observation_before[metric.key]" type="number" size="small" :min="0" :step="metric.step" placeholder="未记录"/></label>
                  <label v-for="metric in observationInputMetrics" :key="`after-${metric.key}`">观察后{{ metric.label }}<el-input v-model="item.observation_after[metric.key]" type="number" size="small" :min="0" :step="metric.step" placeholder="未记录"/></label>
                </div>
                <el-button size="small" :loading="savingObservationId === item.id" @click="submitObservation(item)">添加观察结果</el-button>
                <p v-if="item.observationError" class="error-text">{{ item.observationError }}</p>
              </div>
            </div>
          </article>
        </div>
        <div v-else-if="diagnosis.judgment_candidate" class="legacy-note"><strong>当前为待验证候选判断</strong><span>尚未生成可逐条反馈的策略建议；先按上方观察方向核对证据。</span></div>
        <div v-else class="legacy-note"><strong>此分析没有逐条建议记录</strong><span>无法确认运营针对哪条建议作出反馈，因此不提供补录入口。</span></div>
        <p v-if="recommendationError" class="error-text">{{ recommendationError }}</p>
      </section>

      <section class="report-section observation-section">
        <div class="section-kicker">05 / 下一轮观察</div><h2>接下来关注什么</h2>
        <div class="observation-content">
          <ul><li v-for="metric in observationMetrics" :key="metric">{{ metricTitle(metric) }}变化</li></ul>
          <div><h3>观察目的</h3><p>{{ observationReason }}</p></div>
        </div>
      </section>

      <details class="audit-details">
        <summary>查看分析依据</summary>
        <div class="audit-grid">
          <div><h3>决策信息</h3><p>分析记录 #{{ result.analysis_id }}</p><p>Decision：{{ result.decision }}</p><p>State：{{ result.state || '未记录' }}</p><p>Confidence：{{ result.confidence || '未评估' }}</p><p>分析模式：{{ result.llm_status || '未记录' }}</p><p v-if="result.llm_model">模型：{{ result.llm_model }}</p></div>
          <div><h3>技术依据</h3><p>Rule：{{ result.rules_used?.join('、') || '无' }}</p><p>Pattern：{{ result.reasoning_result?.pattern_refs?.map((item: any) => item.pattern_id).join('、') || '无' }}</p><p>Strategy：{{ result.strategy_refs?.join('、') || '无' }}</p><p v-for="ref in result.knowledge_refs || []" :key="ref.knowledge_id">{{ ref.rule_id }} · {{ ref.title }} · {{ ref.source_type }} · {{ ref.version }}</p></div>
          <div><h3>历史与状态变化</h3><p v-if="result.historical_comparison?.summary">{{ result.historical_comparison.summary }}</p><p v-for="(value, key) in result.historical_comparison?.delta || {}" :key="key">{{ key }}：{{ value }}</p><p v-if="result.state_transition">{{ result.state_transition.from_state }} → {{ result.state_transition.to_state }}：{{ result.state_transition.trigger }}</p><p v-if="result.observation_plan">{{ result.observation_plan.next_observation_reason }}</p><p v-for="item in history" :key="item.analysis_id">#{{ item.analysis_id }} · {{ item.created_at }} · {{ item.decision }}</p></div>
          <div><h3>策略排序</h3><p>首选：{{ result.strategy_ranking?.primary_strategy || '无' }}</p><p>备选：{{ result.strategy_ranking?.secondary_strategies?.join('、') || '无' }}</p><p v-if="result.strategy_ranking?.ranking_reason">{{ result.strategy_ranking.ranking_reason }}</p><p v-for="item in result.strategy_ranking?.rejected_strategies || []" :key="item.strategy_id">{{ item.strategy_id }}：{{ item.reason }}</p><p v-for="item in result.strategy_impact?.potential_risks || []" :key="item">潜在风险：{{ item }}</p></div>
          <div><h3>原始指标与诊断边界</h3><p v-for="(value, key) in current" :key="key">{{ key }}：{{ value ?? '未提供' }}</p><p v-for="item in diagnosis.diagnostic_limitations || []" :key="item">{{ item }}</p></div>
          <div v-if="result.explanation || result.uncertainties?.length"><h3>解释与不确定性</h3><p v-for="item in result.explanation?.diagnosis || []" :key="item">{{ item }}</p><p v-for="item in result.explanation?.recommendations || []" :key="item">{{ item }}</p><p v-for="item in result.uncertainties || []" :key="item">{{ item }}</p></div>
        </div>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import axios from 'axios'

const campaignId = ref(''), report = ref(''), loading = ref(false), error = ref('')
const existingAnalysisId = ref(''), openingAnalysis = ref(false)
const result = ref<any>(null), history = ref<any[]>([])
const recommendations = ref<any[]>([]), recommendationsLoading = ref(false), recommendationError = ref('')
const savingRecommendationId = ref<number | null>(null)
const savingExecutionId = ref<number | null>(null), savingObservationId = ref<number | null>(null)
const observationInputMetrics = [{ key: 'roi', label: 'ROI', step: 0.01 }, { key: 'orders', label: '订单', step: 1 }, { key: 'spend', label: '消耗', step: 0.01 }]
const current = computed(() => result.value?.current_analysis || {})
const diagnosis = computed(() => result.value?.diagnosis_result || {})
const hypotheses = computed(() => (diagnosis.value.failure_hypotheses || []).slice(0, 3))
const keyFacts = computed(() => {
  const facts: string[] = []
  if (current.value.spend != null) facts.push(`已产生广告消耗：${spendDisplay.value}`)
  if (current.value.orders != null) facts.push(`当前订单：${current.value.orders} 单`)
  if (current.value.current_roi != null && current.value.target_roi != null) facts.push(`当前 ROI ${current.value.current_roi}，目标 ROI ${current.value.target_roi}`)
  else if (current.value.current_roi != null) facts.push(`当前 ROI：${current.value.current_roi}（目标 ROI 未提供）`)
  if (current.value.ctr != null) facts.push(`CTR：${current.value.ctr}%`)
  if (current.value.official_completion_rate != null) facts.push(`完播率：${current.value.official_completion_rate}%`)
  if (result.value?.decision === 'EMPTY_BURN') facts.push('符合当前空烧判断条件')
  return facts
})
const keyLimitation = computed(() => diagnosis.value.diagnostic_limitations?.[0] || '')
const plainSummary = computed(() => {
  if (result.value?.decision === 'EMPTY_BURN' && current.value.spend != null && current.value.orders === 0) return `计划已消耗 ${spendDisplay.value}，但尚未产生订单。`
  return diagnosis.value.problem_summary || '当前信息不足，请补充关键投放数据后再判断。'
})
const spendDisplay = computed(() => {
  if (current.value.spend == null) return '无法判断'
  const currency = current.value.currency
  return currency === 'USD' ? `$${current.value.spend}` : `${current.value.spend}${currency ? ` ${currency}` : '（币种未确认）'}`
})
const advice = computed(() => {
  const decision = result.value?.decision
  if (decision === 'EMPTY_BURN') return '核对订单与消耗口径，检查素材和商品页表现，再由运营人员评估是否关停重建。'
  if (decision === 'WAIT_OBSERVE') return '暂不调整计划，保留当前投放状态；下一轮比较消耗、订单和 ROI。'
  if (decision === 'INSUFFICIENT_DATA' && diagnosis.value.judgment_candidate === '素材风险候选') return '先核对完整视频指标，测试新素材并对比 CTR 与完播率；尚不能判断 ROI 是否低于目标。'
  if (decision === 'INSUFFICIENT_DATA' && diagnosis.value.judgment_candidate === '首日起量观察候选') return '继续观察订单和 ROI 的稳定性；确认新品及增长趋势后，由运营评估是否小步增加预算。'
  if (decision === 'INSUFFICIENT_DATA') return '先补充缺失的消耗、订单和视频指标，再决定是否调整计划。'
  if (decision === 'SCALE_NEW_PRODUCT') return '核对订单、视频与履约表现后，由运营人员评估是否小步探索预算。'
  if (decision === 'CLOSE_REBUILD' || String(decision).startsWith('CLOSE_REBUILD_')) return '核对视频、转化和 ROI 证据后，由运营人员评估是否重建计划。'
  return '结合当前指标与缺失证据，由运营人员确认下一步测试方向。'
})
const observationMetrics = computed(() => {
  const source = result.value?.operation_report?.next_observation_metrics || result.value?.observation_plan?.metrics_to_compare || []
  return [...new Set(source.length ? source : ['spend', 'orders', 'current_roi'])].slice(0, 5)
})
const observationReason = computed(() => result.value?.decision === 'WAIT_OBSERVE'
  ? '比较下一轮数据，确认当前表现是否持续稳定。'
  : '核对判断是否持续成立，并观察订单与消耗是否同步变化。')
const metricNames: Record<string, string> = { spend: '消耗', orders: '订单', current_roi: 'ROI', roi: 'ROI', ctr: '点击率', cvr: '转化率', official_completion_rate: '完播率', completion_rate: '完播率' }
function metricTitle(metric: string) { return metricNames[metric] || metric }
function valueDisplay(value: unknown) { return value == null ? '无法判断' : String(value) }
function confidenceTitle(value: string) { return ({ LOW: '低', MEDIUM: '中', HIGH: '高' } as Record<string, string>)[value] || '待核对' }
function stateTitle(value: string) { return ({ CLOSED_REBUILD: '重建候选', WAIT_OBSERVE: '继续观察', NEEDS_CONFIRMATION: '待人工确认', INSUFFICIENT_DATA: '数据不足' } as Record<string, string>)[value] || '待判断' }
function decisionTitle(value: string) { return ({ EMPTY_BURN: '空烧风险', WAIT_OBSERVE: '继续观察', INSUFFICIENT_DATA: '证据不足', NEEDS_CONFIRMATION: '需要人工确认', CLOSE_REBUILD: '计划重建候选', CLOSE_REBUILD_KEEP_ROI: '计划重建候选', CLOSE_REBUILD_LOWER_ROI: '计划重建候选', CLOSE_REBUILD_RAISE_ROI: '计划重建候选', SCALE_NEW_PRODUCT: '新品扩量候选' } as Record<string, string>)[value] || '待判断' }
const strategyTitles: Record<string, string> = { S001: '空烧计划重建评估', S002: '少量订单观察', S003: '检查转化并评估 ROI', S004: '检查视频并测试素材', S005: '新品扩量评估', S006: 'ROI 优化评估', S007: '多 ROI 档位测试' }
function strategyTitle(id: string) { return strategyTitles[id] || '运营建议' }
function feedbackTypeTitle(value: string) { return ({ ACCEPT: '已接受', REJECT: '已拒绝', MODIFY: '需要修改' } as Record<string, string>)[value] || '已反馈' }
function feedbackStatus(item: any) { return item.status === 'UNREVIEWED' ? '待反馈' : feedbackTypeTitle(item.feedback_type) }
function feedbackClass(item: any) { return item.status === 'UNREVIEWED' ? 'pending' : 'recorded' }
function executionStatusTitle(value: string) { return ({ UNKNOWN: '执行状态未知', PENDING: '等待执行确认', CONFIRMED: '已确认执行', FAILED: '执行失败' } as Record<string, string>)[value] || '执行状态未知' }
function executionSourceTitle(value: string) { return ({ operator_input: '人工记录', operator_verified: '人工核验', manual_screenshot: '截图凭证', import: '导入记录' } as Record<string, string>)[value] || value }
function numericMetrics(values: Record<string, string>) {
  const metrics: Record<string, number> = {}
  for (const [key, raw] of Object.entries(values)) {
    if (raw.trim() === '') continue
    const value = Number(raw)
    if (!Number.isFinite(value) || value < 0 || (key === 'orders' && !Number.isInteger(value))) throw new Error('请输入有效的非负指标，订单须为整数')
    metrics[key] = value
  }
  return metrics
}

async function analyze() {
  if (!campaignId.value.trim() || !report.value.trim()) { error.value = '请填写广告计划 ID 和当前运营情况'; return }
  loading.value = true; error.value = ''; result.value = null; history.value = []; recommendations.value = []; recommendationError.value = ''
  try {
    const response = await axios.post('/api/ai/analyses', { campaign_id: campaignId.value.trim(), text: report.value.trim() })
    await showAnalysis(response.data)
  } catch { error.value = '分析失败，请检查后端服务并重试' }
  finally { loading.value = false }
}
async function openAnalysis() {
  const id = Number(existingAnalysisId.value)
  if (!Number.isInteger(id) || id < 1) { error.value = '请输入有效的分析记录 ID'; return }
  openingAnalysis.value = true; error.value = ''
  try {
    const response = await axios.get(`/api/ai/analyses/${id}`)
    await showAnalysis(response.data)
  } catch { error.value = '无法打开该分析记录，请核对 ID 和后端服务' }
  finally { openingAnalysis.value = false }
}
async function showAnalysis(analysis: any) {
  result.value = analysis; campaignId.value = analysis.campaign_id || campaignId.value
  await loadRecommendations(analysis.analysis_id)
  try {
    const timeline = await axios.get(`/api/ai/campaigns/${encodeURIComponent(analysis.campaign_id)}/history`)
    history.value = timeline.data.items || []
  } catch { history.value = [] }
}
async function loadRecommendations(analysisId: number) {
  recommendationsLoading.value = true; recommendationError.value = ''
  try {
    const response = await axios.get(`/api/ai/analyses/${analysisId}/recommendations`)
    recommendations.value = response.data.map((item: any) => ({ ...item, feedback_type: item.feedback_type || '', operator_note: item.operator_note || '', feedbackError: '', execution_input_status: item.execution_status || 'UNKNOWN', execution_action: '', execution_source_input: '', execution_time: '', execution_evidence: '', executionError: '', execution_id: item.execution?.id || null, observation_start: '', observation_end: '', observation_before: { roi: '', orders: '', spend: '' }, observation_after: { roi: '', orders: '', spend: '' }, observationError: '' }))
  } catch { recommendationError.value = '建议记录读取失败，请刷新重试' }
  finally { recommendationsLoading.value = false }
}
async function submitFeedback(item: any) {
  if (!item.feedback_type || !result.value) return
  savingRecommendationId.value = item.id; item.feedbackError = ''
  try {
    await axios.post(`/api/ai/recommendations/${item.id}/feedback`, { feedback_type: item.feedback_type, operator_note: item.operator_note.trim() || null })
    await loadRecommendations(result.value.analysis_id)
  } catch (error: any) { item.feedbackError = error?.response?.data?.detail || '反馈提交失败，请重试' }
  finally { savingRecommendationId.value = null }
}
async function submitExecution(item: any) {
  if (!item.execution_action.trim()) { item.executionError = '请填写实际执行动作'; return }
  savingExecutionId.value = item.id; item.executionError = ''
  try {
    const response = await axios.post(`/api/ai/recommendations/${item.id}/execution`, { execution_status: item.execution_input_status || 'UNKNOWN', actual_action: item.execution_action.trim(), execution_source: item.execution_source_input.trim() || null, executed_at: item.execution_input_status === 'CONFIRMED' && item.execution_time ? item.execution_time : null, evidence: item.execution_evidence.trim() || null })
    item.execution_status = response.data.execution_status; item.execution_id = response.data.id
    await loadRecommendations(result.value.analysis_id)
  } catch (error: any) { item.executionError = error?.response?.data?.detail || '执行记录保存失败，请核对来源和证据' }
  finally { savingExecutionId.value = null }
}
async function submitObservation(item: any) {
  if (!item.execution_id) return
  if (!item.observation_start || !item.observation_end) { item.observationError = '请填写观察开始和结束日期'; return }
  if (item.observation_end < item.observation_start) { item.observationError = '结束日期不能早于开始日期'; return }
  let before: Record<string, number>, after: Record<string, number>
  try { before = numericMetrics(item.observation_before); after = numericMetrics(item.observation_after) } catch (error: any) { item.observationError = error.message; return }
  if (!Object.keys(before).length && !Object.keys(after).length) { item.observationError = '请填写至少一项观察指标'; return }
  savingObservationId.value = item.id; item.observationError = ''
  try {
    await axios.post(`/api/ai/executions/${item.execution_id}/observation`, { observation_window: { start: item.observation_start, end: item.observation_end, source: 'operator_input' }, data_source: 'manual', before_metrics: before, after_metrics: after })
    await loadRecommendations(result.value.analysis_id)
  } catch (error: any) { item.observationError = error?.response?.data?.detail || '观察结果保存失败，请检查观察窗口' }
  finally { savingObservationId.value = null }
}
</script>

<style scoped>
.ai-analysis{max-width:1080px}.page-head{display:flex;justify-content:space-between;align-items:end;gap:16px;margin:10px 0 22px}.page-head h1{font-size:28px;margin:7px 0 0}.mode-label{font-size:12px;color:#27624e;background:#e8f3ec;padding:7px 10px;border-radius:4px}.analysis-form{display:grid;grid-template-columns:minmax(180px,280px) minmax(0,1fr) auto;gap:14px;align-items:end;padding:18px;background:#fff;border:1px solid #e3e9ea;border-radius:7px;margin-bottom:18px}.analysis-form label{display:grid;gap:7px;font-size:12px;font-weight:600;color:#536568}.form-actions{padding-bottom:1px}.report{background:#fff;border:1px solid #e3e9ea;border-radius:7px;overflow:hidden}.report section{padding:20px 26px;border-bottom:1px solid #e8eeee}.report h2{font-size:17px;margin:5px 0 14px}.report h3{font-size:12px;margin:0 0 8px;color:#536568}.report p,.report li{font-size:13px;line-height:1.6}.section-kicker{font-size:11px;font-weight:700;color:#667b7a}.judgment-section{background:#f0f7f4;border-left:4px solid #16856f}.judgment-head{display:flex;justify-content:space-between;align-items:center;gap:16px}.judgment-head h2{font-size:22px;margin:7px 0 0}.campaign-tag{font-size:12px;color:#536568}.state-tag{flex:none;background:#fff;color:#176b59;font-size:12px;padding:6px 9px;border-radius:4px}.judgment-summary{font-size:15px!important;margin:14px 0 18px}.metric-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid #dce9e3;padding-top:15px}.metric-strip>div{min-width:0;padding:0 16px;border-left:1px solid #dce9e3}.metric-strip>div:first-child{padding-left:0;border-left:0}.metric-strip span,.metric-strip strong{display:block}.metric-strip span{font-size:11px;color:#607675}.metric-strip strong{font-size:18px;margin-top:5px;overflow-wrap:anywhere}.fact-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 24px;list-style:none;padding:0;margin:0}.fact-list li{position:relative;padding-left:20px}.fact-list li:before{content:'✓';position:absolute;left:0;color:#16856f;font-weight:700}.evidence-note{color:#8b6025;margin:13px 0 0}.hypothesis-row{display:flex;justify-content:space-between;gap:18px;padding:10px 0;border-top:1px solid #edf1f2}.hypothesis-row:first-child{border-top:0;padding-top:0}.hypothesis-row strong{font-size:13px}.hypothesis-row p{color:#667477;margin:4px 0 0}.confidence-tag{align-self:start;flex:none;font-size:11px;color:#8b6025;background:#fff6df;padding:4px 7px;border-radius:4px}.advice-section{background:#fcfdfc}.advice-copy{font-size:15px!important;font-weight:600;max-width:760px;margin:0 0 12px}.confirmation-note{color:#8b6025;font-size:12px!important;margin:0}.recommendation-list{display:grid;gap:10px;margin-top:16px}.recommendation-card{padding:16px;border:1px solid #e3e9ea;border-radius:5px;background:#fff}.recommendation-heading{display:flex;justify-content:space-between;align-items:center;gap:12px}.recommendation-heading>div{display:flex;align-items:center;gap:10px;min-width:0}.recommendation-heading strong{font-size:14px}.recommendation-number{font-size:11px;color:#667477;white-space:nowrap}.feedback-state{font-size:11px;padding:4px 7px;border-radius:4px;white-space:nowrap}.feedback-state.pending{color:#8b6025;background:#fff6df}.feedback-state.recorded{color:#176b59;background:#e8f3ec}.recommendation-card>p{margin:10px 0;color:#263638}.feedback-form{display:grid;justify-items:start;gap:9px;border-top:1px solid #edf1f2;margin-top:12px;padding-top:12px}.feedback-form .el-textarea{width:100%}.feedback-record{display:grid;gap:6px;margin-top:12px;padding-top:11px;border-top:1px solid #edf1f2;font-size:12px;color:#536568}.feedback-record strong{color:#8b6025}.feedback-record small{color:#718184}.legacy-note{display:grid;gap:5px;margin-top:14px;padding:12px;background:#f5f7f8;color:#536568;font-size:12px}.legacy-note span{color:#718184}.error-text{color:#a63d2f;font-size:12px!important}.observation-content{display:grid;grid-template-columns:1fr 1fr;gap:24px}.observation-content ul{display:flex;flex-wrap:wrap;gap:8px;list-style:none;margin:0;padding:0}.observation-content li{padding:5px 9px;background:#edf3f1;color:#176b59;border-radius:4px}.observation-content p{margin:0;color:#667477}.muted{color:#667477}.audit-details{padding:0 26px}.audit-details summary{cursor:pointer;padding:16px 0;color:#176b59;font-size:13px;font-weight:600}.audit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 28px;border-top:1px solid #e8eeee;padding:5px 0 24px}.audit-grid h3{margin-top:18px}.audit-grid p{font-size:12px;color:#667477;line-height:1.5;margin:5px 0;overflow-wrap:anywhere}@media(max-width:850px){.analysis-form{grid-template-columns:1fr}.form-actions{justify-self:end}}@media(max-width:620px){.page-head{align-items:flex-start;flex-direction:column}.report section{padding:18px}.metric-strip{grid-template-columns:repeat(2,minmax(0,1fr));row-gap:14px}.metric-strip>div:nth-child(3){padding-left:0;border-left:0}.fact-list,.observation-content,.audit-grid{grid-template-columns:1fr}.hypothesis-row{flex-direction:column;gap:5px}.confidence-tag{align-self:start}.recommendation-heading{align-items:flex-start}.recommendation-heading>div{align-items:flex-start;flex-direction:column;gap:4px}.audit-details{padding:0 18px}}
.execution-controls,.observation-controls{display:grid;gap:9px;margin-top:10px;padding:12px;background:#f7f9f9;border:1px solid #e8eeee}.execution-controls h3,.observation-controls h3{margin:0}.execution-controls label,.observation-fields label{display:grid;gap:5px;min-width:0;font-size:12px;color:#536568}.execution-controls .el-select,.execution-controls .el-input,.observation-fields .el-input{width:100%}.execution-controls .el-button,.observation-controls .el-button{justify-self:start}.observation-fields{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}.saved-record{display:grid;gap:4px;padding:9px 10px;background:#fff;border:1px solid #e3e9ea;font-size:12px!important;color:#536568!important;overflow-wrap:anywhere}.saved-record strong{font-size:12px;color:#263638}.saved-record small{color:#718184}.observation-controls p{margin:0;color:#8b6025}@media(max-width:700px){.observation-fields{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:420px){.observation-fields{grid-template-columns:1fr}}
.open-analysis{display:flex;align-items:end;gap:10px;margin:-5px 0 18px}.open-analysis label{display:grid;gap:5px;width:210px;font-size:12px;color:#536568}@media(max-width:420px){.open-analysis{align-items:stretch;flex-direction:column}.open-analysis label{width:100%}}
.execution-history summary{cursor:pointer;color:#176b59;font-size:12px}.execution-history .saved-record{margin-top:8px}
.header-actions{display:flex;align-items:center;gap:14px}.header-actions a{font-size:13px;color:#176b59;text-decoration:none}.header-actions a:hover{text-decoration:underline}@media(max-width:520px){.header-actions{flex-wrap:wrap}}
</style>
