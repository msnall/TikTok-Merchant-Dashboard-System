<template>
  <div class="page affiliate-page">
    <div class="intro affiliate-intro">
      <div>
        <span class="eyebrow">FILL ASSISTANT</span>
        <h1>精选联盟计算</h1>
        <p>导入当天联盟费用表，汇总标准佣金和店铺广告佣金。</p>
      </div>
      <el-button :disabled="!result" @click="clearResult">清空本次结果</el-button>
    </div>

    <section class="workspace-panel affiliate-import">
      <div>
        <span class="step-label">当天数据</span>
        <h3>联盟费用表</h3>
        <p>{{ selectedFile?.name || result?.filename || '尚未选择 CSV 或 Excel 文件' }}</p>
      </div>
      <el-button type="primary" :loading="calculating" @click="fileInput?.click()">
        {{ calculating ? '正在计算' : '导入联盟费用表' }}
      </el-button>
      <input ref="fileInput" class="hidden-input" type="file" accept=".csv,.xlsx,.xlsm" @change="analyzeFile" />
    </section>

    <template v-if="result">
      <section class="workspace-panel affiliate-result">
        <div class="result-heading">
          <div>
            <span class="step-label">计算结果</span>
            <h3>当天精选联盟总费用</h3>
            <p>{{ result.filename }} · {{ result.total_rows }} 条数据 · {{ currencyLabel }}</p>
          </div>
          <el-button @click="downloadResult">导出计算结果</el-button>
        </div>

        <div class="commission-equation">
          <div class="commission-item">
            <span>预计标准佣金付款</span>
            <strong>{{ amount(result.standard_commission_total) }}</strong>
            <small>{{ result.standard_empty_rows }} 个空值按 0 计算</small>
          </div>
          <span class="operator">+</span>
          <div class="commission-item">
            <span>预计店铺广告佣金付款</span>
            <strong>{{ amount(result.store_ad_commission_total) }}</strong>
            <small>{{ result.store_ad_empty_rows }} 个空值按 0 计算</small>
          </div>
          <span class="operator">=</span>
          <div class="commission-item total-item">
            <span>精选联盟总费用</span>
            <strong>{{ amount(result.total_affiliate_fee) }}</strong>
            <small>两项佣金合计</small>
          </div>
        </div>
      </section>
    </template>

    <section v-else class="empty-workspace affiliate-empty">
      <div class="empty-mark">CSV</div>
      <h3>等待联盟费用表</h3>
      <p>导入当天文件后，三个金额会显示在这里。</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const STORAGE_KEY = 'fill-assistant:affiliate-calculation'

function restoreResult() {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : null
  } catch {
    sessionStorage.removeItem(STORAGE_KEY)
    return null
  }
}

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const result = ref<any>(restoreResult())
const calculating = ref(false)
const currencyLabel = computed(() => result.value?.currency || '未提供币种')

function amount(value: unknown) {
  const formatted = Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return result.value?.currency ? `${formatted} ${result.value.currency}` : formatted
}

async function analyzeFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const data = new FormData()
  data.append('file', file)
  calculating.value = true
  try {
    const nextResult = (await axios.post('/api/fill-assistant/affiliate-fees/analyze', data)).data
    selectedFile.value = file
    result.value = nextResult
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nextResult))
    ElMessage.success(`已计算 ${nextResult.total_rows} 条联盟费用数据`)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '联盟费用表导入失败')
  } finally {
    calculating.value = false
  }
}

async function downloadResult() {
  if (!result.value) return
  try {
    const response = await axios.post('/api/fill-assistant/affiliate-fees/export', result.value, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = '精选联盟费用.xlsx'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导出失败')
  }
}

function clearResult() {
  selectedFile.value = null
  result.value = null
  sessionStorage.removeItem(STORAGE_KEY)
}
</script>

<style scoped>
.affiliate-page{max-width:1180px}.affiliate-intro{align-items:center}.affiliate-intro h1{font-size:34px}.affiliate-import{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:24px}.affiliate-import h3{margin:6px 0;font-size:19px}.affiliate-import p,.result-heading p{margin:0;color:#718184;font-size:13px}.step-label{color:#16856f;font-size:11px;font-weight:700}.hidden-input{display:none}.affiliate-result{padding:26px}.result-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;border-bottom:1px solid #e3e9ea;padding-bottom:20px}.result-heading h3{margin:6px 0;font-size:20px}.commission-equation{display:grid;grid-template-columns:minmax(0,1fr) 36px minmax(0,1fr) 36px minmax(0,1.1fr);align-items:stretch;margin-top:24px}.commission-item{padding:22px;background:#f6f8f8;border:1px solid #e3e9ea;min-width:0}.commission-item span,.commission-item small{display:block;color:#718184;font-size:12px}.commission-item strong{display:block;margin:14px 0 8px;font-size:27px;overflow-wrap:anywhere}.total-item{background:#eef5f3;border-color:#cbded9}.total-item strong{color:#167663}.operator{display:grid;place-items:center;color:#748486;font-size:22px;font-weight:600}.affiliate-empty{min-height:300px}.empty-workspace{border:1px dashed #cdd8d8;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#fff;border-radius:7px;color:#718184}.empty-workspace h3{color:#344246;margin:14px 0 4px}.empty-workspace p{margin:4px}.empty-mark{width:70px;height:52px;display:grid;place-items:center;border:2px solid #8ea5a3;color:#55716f;font-size:12px;font-weight:800}
@media(max-width:900px){.commission-equation{grid-template-columns:1fr}.operator{min-height:38px}.affiliate-intro h1{font-size:28px}}
@media(max-width:620px){.affiliate-intro,.affiliate-import,.result-heading{display:block}.affiliate-intro>.el-button,.affiliate-import>.el-button,.result-heading>.el-button{margin-top:14px}.affiliate-result{padding:18px}.commission-item strong{font-size:23px}}
</style>
