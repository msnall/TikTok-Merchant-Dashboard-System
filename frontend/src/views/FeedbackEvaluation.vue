<template>
  <div class="page feedback-evaluation">
    <header class="page-head"><div><span class="eyebrow">OPERATIONS FEEDBACK</span><h1>运营闭环</h1></div><el-button :loading="loading" @click="loadEvaluation">刷新数据</el-button></header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <div v-if="loading && !evaluation" class="empty-state">正在读取运营反馈数据…</div>
    <div v-else-if="evaluation" class="evaluation-content">
      <div v-if="!evaluation.funnel.generated.count" class="empty-state">暂无真实运营闭环数据</div>
      <template v-else>
        <section class="section-band">
          <div class="section-heading"><div><span class="section-kicker">01 / 建议反馈</span><h2>闭环进度</h2></div><span class="scope-note">按建议统计 · 仅真实运营案例</span></div>
          <div class="funnel"><div v-for="step in funnelSteps" :key="step.key" class="funnel-step"><span>{{ step.label }}</span><strong>{{ evaluation.funnel[step.key].count }}</strong><small>{{ step.key === 'generated' ? '建议总数' : `${evaluation.funnel[step.key].count} / ${evaluation.funnel[step.key].denominator}` }}</small></div></div>
          <p class="definition">每条建议只计一次。反馈和执行取最新记录；确认执行仅表示存在来源与证据记录，不代表广告平台已自动核验。</p>
        </section>
        <section class="section-band detail-grid">
          <div><span class="section-kicker">02 / 执行记录</span><h2>最新执行状态</h2><div class="status-list"><div><span>尚无执行记录</span><strong>{{ evaluation.without_execution_record }}</strong></div><div v-for="status in executionStatuses" :key="status.key"><span>{{ status.label }}</span><strong>{{ evaluation.execution_summary[status.key] }}</strong></div></div><p class="definition">状态分布只描述记录，不是执行成功率。</p></div>
          <div><span class="section-kicker">03 / 观察数据</span><h2>数据完整度</h2><div class="status-list"><div><span>有观察窗口</span><strong>{{ ratio(evaluation.observation_summary.with_window) }}</strong></div><div><span>有前后指标</span><strong>{{ ratio(evaluation.observation_summary.with_paired_metrics) }}</strong></div></div><p class="definition">分母为已接受且最新执行已确认的建议。完整度不是策略效果。</p></div>
        </section>
        <section class="section-band">
          <span class="section-kicker">04 / 事实变化</span><h2>观察到的 ROI 变化</h2><p class="definition">只呈现记录中的前后差值，不推断变化由 AI 建议造成。</p>
          <div v-if="evaluation.observed_changes.length" class="table-wrap"><table><thead><tr><th>建议</th><th>观察窗口</th><th>观察前 ROI</th><th>观察后 ROI</th><th>变化</th><th>因果判断</th></tr></thead><tbody><tr v-for="item in evaluation.observed_changes" :key="item.observation_id"><td>#{{ item.recommendation_id }}</td><td>{{ windowTitle(item.observation_window) }}</td><td>{{ item.roi_before }}</td><td>{{ item.roi_after }}</td><td>{{ signed(item.observed_roi_change) }}</td><td>{{ causalTitle(item.causal_assessment) }}</td></tr></tbody></table></div>
          <p v-else class="empty-inline">暂无同时记录前后 ROI 的已确认执行建议。</p>
        </section>
        <details class="quality-details"><summary>查看数据完整度标签</summary><div class="quality-list"><span>完整 {{ evaluation.data_completeness.HIGH }}</span><span>部分记录 {{ evaluation.data_completeness.MEDIUM }}</span><span>仅有反馈 {{ evaluation.data_completeness.LOW }}</span><span>暂无反馈 {{ evaluation.data_completeness.NONE }}</span></div><p>标签只反映记录是否齐全，不评价建议质量，也不参与推荐。</p></details>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'

type Count = { count: number; denominator: number | null }
type Evaluation = {
  funnel: Record<string, Count>
  execution_summary: Record<string, number>
  without_execution_record: number
  observation_summary: Record<string, Count>
  data_completeness: Record<string, number>
  observed_changes: Array<{ recommendation_id: number; observation_id: number; roi_before: number; roi_after: number; observed_roi_change: number; observation_window: Record<string, unknown>; causal_assessment: string }>
}
const evaluation = ref<Evaluation | null>(null)
const loading = ref(false)
const error = ref('')
const funnelSteps = [{ key: 'generated', label: '生成建议' }, { key: 'feedback_received', label: '收到反馈' }, { key: 'accepted', label: '接受建议' }, { key: 'confirmed_execution', label: '确认执行记录' }, { key: 'with_observation', label: '存在观察记录' }]
const executionStatuses = [{ key: 'UNKNOWN', label: '未知' }, { key: 'PENDING', label: '待执行' }, { key: 'CONFIRMED', label: '已确认' }, { key: 'FAILED', label: '执行失败' }]
function ratio(value: Count) { return `${value.count} / ${value.denominator ?? 0}` }
function signed(value: number) { return `${value > 0 ? '+' : ''}${value}` }
function causalTitle(value: string) { return ({ UNKNOWN: '未知', SUPPORTED: '有证据支持', NOT_SUPPORTED: '无证据支持' } as Record<string, string>)[value] || '未知' }
function windowTitle(window: Record<string, unknown>) {
  if (window.start && window.end) return `${window.start} 至 ${window.end}`
  if (window.value && window.unit) return `${window.value} ${window.unit === 'days' ? '天' : window.unit === 'hours' ? '小时' : window.unit === 'weeks' ? '周' : '自定义'}`
  return '未记录'
}
async function loadEvaluation() {
  loading.value = true; error.value = ''
  try { evaluation.value = (await axios.get('/api/ai/feedback/evaluation')).data }
  catch { error.value = '闭环数据读取失败，请检查后端服务并重试' }
  finally { loading.value = false }
}
onMounted(loadEvaluation)
</script>

<style scoped>
.feedback-evaluation{max-width:1100px}.page-head{display:flex;align-items:end;justify-content:space-between;gap:16px;margin:10px 0 22px}.page-head h1{font-size:28px;margin:7px 0 0}.evaluation-content{background:#fff;border:1px solid #e3e9ea;border-radius:7px}.section-band{padding:24px 28px;border-bottom:1px solid #e8eeee}.section-band h2{font-size:17px;margin:5px 0 16px}.section-heading{display:flex;justify-content:space-between;align-items:end;gap:12px}.section-kicker{font-size:11px;font-weight:700;color:#667b7a}.scope-note,.definition{font-size:12px;color:#667477}.definition{line-height:1.6;margin:14px 0 0}.funnel{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid #dce9e3;border-radius:5px;overflow:hidden}.funnel-step{display:grid;gap:5px;min-width:0;padding:17px 15px;border-left:1px solid #dce9e3;background:#f4f9f6}.funnel-step:first-child{border-left:0}.funnel-step span{font-size:12px;color:#536568}.funnel-step strong{font-size:24px;color:#176b59}.funnel-step small{font-size:11px;color:#667477}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:36px}.detail-grid>div{min-width:0}.status-list{display:grid;gap:0;border-top:1px solid #e8eeee}.status-list>div{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid #e8eeee;font-size:13px}.status-list strong{color:#263638}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}th,td{text-align:left;padding:11px 12px;border-bottom:1px solid #e8eeee}th{color:#536568;background:#f7f9f9;font-weight:600}.empty-state{padding:48px 24px;text-align:center;color:#667477;background:#fff;border:1px solid #e3e9ea;border-radius:7px}.evaluation-content .empty-state{border:0}.empty-inline{color:#667477;font-size:13px}.quality-details{padding:18px 28px}.quality-details summary{cursor:pointer;color:#176b59;font-size:13px;font-weight:600}.quality-list{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.quality-list span{padding:6px 9px;background:#edf3f1;border-radius:4px;color:#176b59;font-size:12px}.quality-details p{font-size:12px;color:#667477}@media(max-width:800px){.funnel{grid-template-columns:repeat(2,minmax(0,1fr))}.funnel-step{border-bottom:1px solid #dce9e3}.detail-grid{grid-template-columns:1fr;gap:26px}}@media(max-width:520px){.section-band{padding:18px}.section-heading{align-items:start;flex-direction:column}.funnel-step{padding:12px}.quality-details{padding:18px}}
</style>
