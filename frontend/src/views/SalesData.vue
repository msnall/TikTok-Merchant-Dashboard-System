<template>
  <div class="page sales-page">
    <div class="intro sales-intro">
      <div>
        <span class="eyebrow">FILL ASSISTANT</span>
        <h1>销售数据</h1>
        <p>先按 Seller SKU 汇总折后金额，再将同名产品合并展示。</p>
      </div>
      <el-button :disabled="!result" @click="clearResult">清空本次结果</el-button>
    </div>

    <section class="workspace-panel import-panel">
      <div class="import-section">
        <div>
          <span class="step-label">长期配置</span>
          <h3>产品编码</h3>
          <p>{{ mappingText }}</p>
        </div>
        <el-button plain :loading="mappingImporting" @click="mappingInput?.click()">
          {{ mappingImporting ? '正在导入' : '导入 / 更新产品编码' }}
        </el-button>
        <input ref="mappingInput" class="hidden-input" type="file" accept=".xlsx,.xlsm,.csv" @change="importMappings" />
      </div>
      <div class="import-divider"></div>
      <div class="import-section">
        <div>
          <span class="step-label">当天数据</span>
          <h3>全部订单</h3>
          <p>{{ selectedOrder?.name || result?.filename || '尚未选择 CSV 或 Excel 文件' }}</p>
        </div>
        <el-button type="primary" :loading="analyzing" @click="orderInput?.click()">
          {{ analyzing ? '正在汇总' : '导入全部订单' }}
        </el-button>
        <input ref="orderInput" class="hidden-input" type="file" accept=".csv,.xlsx,.xlsm" @change="analyzeOrders" />
      </div>
    </section>

    <template v-if="result">
      <div class="sales-metrics">
        <div><span>订单总行数</span><strong>{{ result.total_rows }}</strong><small>{{ result.valid_rows }} 行参与汇总</small></div>
        <div><span>产品名称</span><strong>{{ result.product_count ?? result.rows.length }}</strong><small>{{ result.sku_count }} 个 SKU 合并统计</small></div>
        <div><span>未匹配 SKU</span><strong>{{ result.unmatched_sku_count }}</strong><small>{{ result.matched_sku_count }} 个已匹配</small></div>
        <div><span>销售金额总计</span><strong>{{ amount(result.total_amount) }}</strong><small>折后小计求和</small></div>
      </div>

      <el-alert
        v-if="result.blank_sku_rows"
        :title="`发现 ${result.blank_sku_rows} 条订单缺少 Seller SKU，已排除`"
        type="warning"
        :closable="false"
        show-icon
        class="sales-alert"
      />
      <el-alert
        v-if="result.unmatched_sku_count"
        :title="`${result.unmatched_sku_count} 个 Seller SKU 未匹配产品名称，销售金额仍保留在结果中`"
        type="warning"
        :closable="false"
        show-icon
        class="sales-alert"
      />

      <section class="workspace-panel result-panel">
        <div class="result-heading">
          <div>
            <span class="step-label">汇总结果</span>
            <h3>销售数据明细</h3>
            <p>{{ result.filename }} · 同名产品已合并，按折后金额降序</p>
          </div>
          <el-button @click="downloadResult">导出销售数据</el-button>
        </div>
        <el-table :data="result.rows" stripe max-height="620" empty-text="暂无销售数据">
          <el-table-column prop="seller_sku" label="Seller SKU" min-width="220" show-overflow-tooltip />
          <el-table-column prop="name" label="名称" min-width="240">
            <template #default="scope">
              <span :class="{ unmatched: !scope.row.matched }">{{ scope.row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="SKU Subtotal After Discount" min-width="230" align="right">
            <template #default="scope"><strong>{{ amount(scope.row.subtotal_after_discount) }}</strong></template>
          </el-table-column>
        </el-table>
      </section>
    </template>

    <section v-else class="empty-workspace sales-empty">
      <div class="empty-mark">CSV</div>
      <h3>等待全部订单</h3>
      <p>导入订单文件后，Seller SKU 销售汇总会显示在这里。</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const STORAGE_KEY = 'fill-assistant:sales-data'

function restoreResult() {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : null
  } catch {
    sessionStorage.removeItem(STORAGE_KEY)
    return null
  }
}

const mappingInput = ref<HTMLInputElement | null>(null)
const orderInput = ref<HTMLInputElement | null>(null)
const selectedOrder = ref<File | null>(null)
const result = ref<any>(restoreResult())
const mappingStatus = ref<any>({ total: 0, updated_at: null })
const mappingImporting = ref(false)
const analyzing = ref(false)

const mappingText = computed(() => {
  if (!mappingStatus.value.total) return '尚未保存产品编码映射'
  return `已保存 ${Number(mappingStatus.value.total).toLocaleString('zh-CN')} 条映射`
})

function amount(value: unknown) {
  return Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function loadMappingStatus() {
  try {
    mappingStatus.value = (await axios.get('/api/fill-assistant/sales/product-codes')).data
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '产品编码状态加载失败')
  }
}

async function importMappings(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const data = new FormData()
  data.append('file', file)
  mappingImporting.value = true
  try {
    const imported = (await axios.post('/api/fill-assistant/sales/product-codes', data)).data
    mappingStatus.value.total = imported.total_saved
    ElMessage.success(`产品编码已保存：新增 ${imported.created}，更新 ${imported.updated}`)
  } catch (error: any) {
    ElMessage.error({ message: error?.response?.data?.detail || '产品编码导入失败', duration: 6000 })
  } finally {
    mappingImporting.value = false
  }
}

async function analyzeOrders(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const data = new FormData()
  data.append('file', file)
  analyzing.value = true
  try {
    const nextResult = (await axios.post('/api/fill-assistant/sales/analyze', data)).data
    selectedOrder.value = file
    result.value = nextResult
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nextResult))
    ElMessage.success(`已汇总 ${nextResult.sku_count} 个 Seller SKU`)
  } catch (error: any) {
    ElMessage.error({ message: error?.response?.data?.detail || '全部订单导入失败', duration: 6000 })
  } finally {
    analyzing.value = false
  }
}

async function downloadResult() {
  if (!result.value) return
  try {
    const response = await axios.post('/api/fill-assistant/sales/export', result.value, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = '销售数据.xlsx'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导出失败')
  }
}

function clearResult() {
  selectedOrder.value = null
  result.value = null
  sessionStorage.removeItem(STORAGE_KEY)
}

onMounted(loadMappingStatus)
</script>

<style scoped>
.sales-page{max-width:1260px}.sales-intro{align-items:center}.sales-intro h1{font-size:34px}.import-panel{display:grid;grid-template-columns:minmax(0,1fr) 1px minmax(0,1fr);padding:0}.import-section{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:24px;min-width:0}.import-section h3{font-size:18px;margin:5px 0}.import-section p,.result-heading p{color:#718184;font-size:13px;margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.import-divider{background:#e3e9ea}.step-label{color:#16856f;font-size:11px;font-weight:700}.hidden-input{display:none}.sales-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}.sales-metrics>div{background:#fff;border:1px solid #e3e9ea;border-radius:7px;padding:18px}.sales-metrics span,.sales-metrics small{display:block;color:#718184;font-size:12px}.sales-metrics strong{display:block;font-size:27px;margin:9px 0 5px;color:#20262e;overflow-wrap:anywhere}.sales-alert{margin-bottom:12px}.result-panel{padding:22px}.result-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;border-bottom:1px solid #e3e9ea;padding-bottom:18px;margin-bottom:4px}.result-heading h3{font-size:20px;margin:5px 0}.unmatched{color:#b56a13;font-weight:600}.sales-empty{min-height:290px}.empty-workspace{border:1px dashed #cdd8d8;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#fff;border-radius:7px;color:#718184}.empty-workspace h3{color:#344246;margin:14px 0 4px}.empty-workspace p{margin:4px}.empty-mark{width:70px;height:52px;display:grid;place-items:center;border:2px solid #8ea5a3;color:#55716f;font-size:12px;font-weight:800}
@media(max-width:900px){.import-panel{grid-template-columns:1fr}.import-divider{height:1px}.sales-metrics{grid-template-columns:repeat(2,1fr)}.sales-intro h1{font-size:28px}}
@media(max-width:620px){.sales-intro,.import-section,.result-heading{display:block}.sales-intro>.el-button,.import-section>.el-button,.result-heading>.el-button{margin-top:14px}.sales-metrics{grid-template-columns:1fr}.result-panel{padding:14px}}
</style>
