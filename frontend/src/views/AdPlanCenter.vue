<template>
  <div class="page">
    <div class="intro">
      <div>
        <span class="eyebrow">AD PLAN CENTER</span>
        <h1>广告计划中心</h1>
        <p>以 TikTok 导出数据为依据，识别值得人工检查的计划并记录后续操作。</p>
      </div>
      <div class="intro-actions">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" plain @click="openSetting()">目标 ROI 配置</el-button>
        <label class="upload-button" :class="{ disabled: importing }">
          {{ importing ? '正在导入...' : '导入 Excel' }}
          <input type="file" accept=".xlsx,.xlsm,.csv" :disabled="importing" @change="importFile" />
        </label>
      </div>
    </div>

    <div v-if="importMessage" class="import-message">{{ importMessage }}</div>

    <section class="workspace-panel roi-settings-panel">
      <div class="section-head">
        <div><h3>产品 A/B/C/D 目标 ROI</h3><span class="muted">以后导入任何日期的同产品计划，都会按产品和编号使用相同目标 ROI。</span></div>
        <el-button type="primary" @click="openSetting()">新增配置</el-button>
      </div>
      <el-table :data="targetSettings" stripe empty-text="尚未配置目标 ROI，请先新增产品和编号配置">
        <el-table-column prop="product_name" label="产品" min-width="200" />
        <el-table-column prop="strategy_code" label="编号" width="90" />
        <el-table-column prop="target_roi" label="目标 ROI" width="120"><template #default="scope">{{ number(scope.row.target_roi) }}</template></el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180"><template #default="scope">{{ dateTime(scope.row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" width="130"><template #default="scope"><el-button link @click="openSetting(scope.row)">编辑</el-button><el-button link type="danger" @click="removeSetting(scope.row)">删除</el-button></template></el-table-column>
      </el-table>
    </section>

    <div class="ad-summary">
      <div><span>广告计划</span><strong>{{ plans.length }}</strong></div>
      <div><span>报表期无消耗</span><strong>{{ statusCount('no_spend') }}</strong></div>
      <div><span>消耗探索中</span><strong>{{ statusCount('exploring') }}</strong></div>
      <div><span>空烧</span><strong>{{ statusCount('empty_burn') }}</strong></div>
      <div><span>ROI 低于目标</span><strong>{{ statusCount('low_roi') }}</strong></div>
    </div>

    <section class="workspace-panel ad-plan-panel">
      <div class="ad-toolbar">
        <div class="ad-panel-heading">
          <div>
          <h3>当前广告计划</h3>
          <span class="muted">目标 ROI 按“产品 + A/B/C/D”同步；日期不同不会改变目标值。</span>
          </div>
          <div class="filter-result">
            <span>当前显示</span>
            <strong>{{ filteredPlans.length }}</strong>
            <small>/ {{ plans.length }} 条</small>
          </div>
        </div>
        <div class="ad-filter-row">
          <el-input v-model="keyword" clearable placeholder="搜索计划、产品或 Campaign ID" @keyup.enter="load" />
          <el-select v-model="productFilter" clearable placeholder="全部产品">
            <el-option v-for="item in productOptions" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="variantFilter" clearable placeholder="全部编号">
            <el-option v-for="code in variantOptions" :key="code" :label="code" :value="code" />
          </el-select>
          <el-select v-model="processingFilter" placeholder="全部处理状态">
            <el-option label="全部处理状态" value="all" /><el-option label="待处理" value="pending" /><el-option label="已处理" value="handled" />
          </el-select>
        </div>
        <div class="status-filter-bar">
          <span class="status-filter-label">计划状态</span>
          <el-radio-group v-model="activeStatus" size="small">
            <el-radio-button v-for="item in statusOptions" :key="item.value" :value="item.value">
              <span>{{ item.label }}</span>
              <b>{{ item.value ? statusCount(item.value) : plans.length }}</b>
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <el-table v-loading="loading" :data="filteredPlans" stripe empty-text="暂无符合条件的广告计划" @sort-change="sortPlans">
        <el-table-column prop="plan_name" label="广告计划" min-width="245">
          <template #default="scope">
            <div class="plan-name">{{ scope.row.plan_name }}</div>
            <small class="muted">{{ scope.row.platform_campaign_id || '无 Campaign ID' }}</small>
          </template>
        </el-table-column>
        <el-table-column label="产品" min-width="130">
          <template #default="scope">{{ scope.row.product?.name || scope.row.imported_product_name || '未识别' }}</template>
        </el-table-column>
        <el-table-column label="编号" width="92">
          <template #default="scope">
            <el-select v-model="variantDraft[scope.row.id]" clearable placeholder="-" size="small" @change="saveVariant(scope.row)">
              <el-option v-for="code in variantOptions" :key="code" :label="code" :value="code" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="成本" width="92" align="right">
          <template #default="scope">{{ money(scope.row.latest_snapshot?.spend) }}</template>
        </el-table-column>
        <el-table-column label="实际 ROI" width="94" align="right">
          <template #default="scope">{{ number(scope.row.latest_snapshot?.actual_roi) }}</template>
        </el-table-column>
        <el-table-column label="目标 ROI" width="168">
          <template #default="scope">
            <div class="roi-editor">
              <el-input-number v-model="targetDraft[scope.row.id]" :min="0" :precision="2" :step="0.1" controls-position="right" />
              <el-button link type="primary" :loading="savingIds.includes(scope.row.id)" @click="saveTarget(scope.row)">同步</el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="SKU 订单" width="90" align="right">
          <template #default="scope">{{ value(scope.row.latest_snapshot?.orders) }}</template>
        </el-table-column>
        <el-table-column label="预算" width="92" align="right">
          <template #default="scope">{{ money(scope.row.latest_snapshot?.budget) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="scope"><el-tag :type="statusType(scope.row.current_status)" effect="plain">{{ statusLabel(scope.row.current_status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="建议" min-width="260">
          <template #default="scope"><span class="recommendation">{{ scope.row.latest_snapshot?.recommendation || '暂无最新快照' }}</span></template>
        </el-table-column>
        <el-table-column label="更新时间" width="170" sortable="custom">
          <template #default="scope">{{ dateTime(scope.row.latest_snapshot?.snapshot_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="150">
          <template #default="scope">
            <el-button link @click="showSnapshots(scope.row)">详情</el-button>
            <el-button link type="primary" @click="recordOperation(scope.row)">记录操作</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <div class="ops-grid">
      <section class="workspace-panel">
        <div class="section-head"><h3>最近导入</h3><span class="muted">每次导入保留独立批次和快照</span></div>
        <div v-for="batch in batches.slice(0, 8)" :key="batch.id" class="home-link-row">
          <span>{{ batch.file_name }}</span>
          <small>{{ batch.row_count }} 行 · {{ dateTime(batch.imported_at) }}</small>
        </div>
        <el-empty v-if="!batches.length" description="暂无导入批次" :image-size="50" />
      </section>
      <section class="workspace-panel">
        <div class="section-head"><h3>判断边界</h3></div>
        <div class="rule-list">
          <p><strong>报表期无消耗</strong><span>本次 Excel 中成本 = 0</span></p>
          <p><strong>消耗探索中</strong><span>0 &lt; 成本 ≤ $2 且 SKU 订单数 = 0</span></p>
          <p><strong>疑似空烧</strong><span>成本 &gt; $2 且 SKU 订单数 = 0</span></p>
          <p><strong>ROI 判断</strong><span>有订单后，实际 ROI 与该计划目标 ROI 直接比较</span></p>
          <p><strong>当前预算</strong><span>只展示，不参与状态判断</span></p>
          <p><strong>人工决策</strong><span>系统不自动关停或修改 TikTok 广告</span></p>
        </div>
      </section>
    </div>

    <el-drawer v-model="snapshotDrawer" :title="`${selectedPlan?.plan_name || ''} · 计划详情`" size="min(860px, 94vw)">
      <section v-if="selectedPlan" class="plan-detail-summary">
        <div class="detail-row"><span>产品 / 类型</span><strong>{{ selectedPlan.imported_product_name || selectedPlan.product?.name || '未识别' }} · {{ selectedPlan.strategy_code || '-' }}</strong></div>
        <div class="detail-row"><span>当前状态</span><strong><el-tag :type="statusType(selectedPlan.current_status)" effect="plain">{{ statusLabel(selectedPlan.current_status) }}</el-tag></strong></div>
        <div class="detail-row"><span>成本 / 订单 / 实际 ROI</span><strong>{{ money(selectedPlan.latest_snapshot?.spend) }} · {{ value(selectedPlan.latest_snapshot?.orders) }} · {{ number(selectedPlan.latest_snapshot?.actual_roi) }}</strong></div>
        <div class="detail-row"><span>目标 ROI / 预算</span><strong>{{ number(selectedPlan.target_roi) }} · {{ money(selectedPlan.latest_snapshot?.budget) }}</strong></div>
        <div class="detail-row"><span>判断依据</span><strong>{{ selectedPlan.latest_snapshot?.reason || '暂无最新快照' }}</strong></div>
        <div class="detail-actions"><el-button type="primary" @click="recordOperation(selectedPlan)">记录操作</el-button><span v-if="isHandled(selectedPlan)" class="handled-badge">已记录处理</span><span v-else class="pending-badge">待处理</span></div>
      </section>
      <h3>最近快照</h3>
      <el-table :data="snapshots" stripe empty-text="暂无快照">
        <el-table-column prop="snapshot_at" label="时间" width="170"><template #default="scope">{{ dateTime(scope.row.snapshot_at) }}</template></el-table-column>
        <el-table-column prop="spend" label="成本" width="80" />
        <el-table-column prop="orders" label="订单" width="70" />
        <el-table-column prop="actual_roi" label="实际 ROI" width="90" />
        <el-table-column prop="budget" label="预算" width="80" />
        <el-table-column label="状态" width="120"><template #default="scope">{{ statusLabel(scope.row.status) }}</template></el-table-column>
        <el-table-column prop="reason" label="判断依据" min-width="230" />
        <el-table-column label="成本变化" width="110"><template #default="scope">{{ snapshotDelta(scope.$index, 'spend') }}</template></el-table-column>
      </el-table>
      <h3 class="drawer-section-title">操作记录</h3>
      <div v-for="item in selectedOperations" :key="item.id" class="operation-history-row">
        <div><strong>{{ operationLabel(item.operation_type) }}</strong><span>{{ dateTime(item.operated_at) }}</span></div>
        <p>{{ item.reason || '未填写原因' }}<small v-if="item.notes"> · {{ item.notes }}</small></p>
      </div>
      <el-empty v-if="!selectedOperations.length" description="该计划暂无运营记录" :image-size="50" />
    </el-drawer>

    <el-dialog v-model="settingDialog" :title="editingSettingId ? '编辑目标 ROI 配置' : '新增目标 ROI 配置'" width="480px">
      <el-form :model="settingForm" label-width="100px">
        <el-form-item label="产品名称"><el-input v-model="settingForm.product_name" placeholder="例如：微波炉蒸蛋器" /></el-form-item>
        <el-form-item label="计划编号"><el-segmented v-model="settingForm.strategy_code" :options="variantOptions" /></el-form-item>
        <el-form-item label="目标 ROI"><el-input-number v-model="settingForm.target_roi" :min="0.01" :precision="2" :step="0.1" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="settingDialog = false">取消</el-button><el-button type="primary" :loading="settingSaving" @click="saveSetting">保存配置</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()
const plans = ref<any[]>([])
const batches = ref<any[]>([])
const targetSettings = ref<any[]>([])
const snapshots = ref<any[]>([])
const selectedPlan = ref<any>(null)
const snapshotDrawer = ref(false)
const selectedOperations = ref<any[]>([])
const operationRecords = ref<any[]>([])
const importMessage = ref('')
const importing = ref(false)
const loading = ref(false)
const activeStatus = ref('')
const keyword = ref('')
const productFilter = ref('')
const variantFilter = ref('')
const processingFilter = ref('all')
const sortKey = ref('')
const sortOrder = ref<'ascending' | 'descending' | null>(null)
const savingIds = ref<number[]>([])
const targetDraft = ref<Record<number, number | null>>({})
const variantDraft = ref<Record<number, 'A' | 'B' | 'C' | 'D' | null>>({})
const settingDialog = ref(false)
const settingSaving = ref(false)
const editingSettingId = ref<number | null>(null)
const settingForm = ref<any>({ product_name: '', strategy_code: 'A', target_roi: 2 })
const variantOptions = ['A', 'B', 'C', 'D']

const statusOptions = [
  { label: '全部', value: '' },
  { label: '无消耗', value: 'no_spend' },
  { label: '探索中', value: 'exploring' },
  { label: '空烧', value: 'empty_burn' },
  { label: 'ROI 低', value: 'low_roi' },
  { label: 'ROI 达标', value: 'roi_reached' },
  { label: '待设目标', value: 'target_roi_pending' },
]

const productOptions = computed(() => Array.from(new Set(plans.value.map((item) => item.imported_product_name || item.product?.name).filter(Boolean))))
const filteredPlans = computed(() => {
  let result = plans.value.filter((item) => {
    const text = keyword.value.trim().toLowerCase()
    const product = item.imported_product_name || item.product?.name || ''
    const matchesKeyword = !text || `${item.plan_name} ${product} ${item.platform_campaign_id || ''}`.toLowerCase().includes(text)
    const matchesProduct = !productFilter.value || product === productFilter.value
    const matchesVariant = !variantFilter.value || item.strategy_code === variantFilter.value
    const matchesStatus = !activeStatus.value || item.current_status === activeStatus.value
    const handled = isHandled(item)
    const matchesProcessing = processingFilter.value === 'all'
      || (item.current_status === 'empty_burn' && (processingFilter.value === 'handled' ? handled : !handled))
    return matchesKeyword && matchesProduct && matchesVariant && matchesStatus && matchesProcessing
  })
  if (sortKey.value) {
    result = [...result].sort((a, b) => {
      const av = sortKey.value === 'updated_at' ? (a.latest_snapshot?.snapshot_at || '') : (a[sortKey.value] ?? 0)
      const bv = sortKey.value === 'updated_at' ? (b.latest_snapshot?.snapshot_at || '') : (b[sortKey.value] ?? 0)
      const comparison = String(av).localeCompare(String(bv), 'zh-CN', { numeric: true })
      return sortOrder.value === 'descending' ? -comparison : comparison
    })
  }
  return result
})

const statusCount = (status: string) => plans.value.filter((item) => item.current_status === status).length
const value = (input: unknown) => input === null || input === undefined ? '-' : String(input)
const number = (input: unknown) => input === null || input === undefined ? '-' : Number(input).toFixed(2)
const money = (input: unknown) => input === null || input === undefined ? '-' : `$${Number(input).toFixed(2)}`
const dateTime = (input: string | null | undefined) => input ? new Date(input).toLocaleString('zh-CN', { hour12: false }) : '-'
const statusLabel = (status: string) => ({
  empty_burn: '疑似空烧', exploring: '消耗探索中', low_roi: 'ROI 低于目标', roi_reached: 'ROI 达标', no_spend: '报表期无消耗',
  target_roi_pending: '待设置目标 ROI', normal: '正常', unknown: '未知',
}[status] || status)
const statusType = (status: string) => status === 'roi_reached' || status === 'normal' ? 'success'
  : status === 'empty_burn' || status === 'no_spend' ? 'danger'
    : status === 'low_roi' ? 'warning' : 'info'
const operationLabel = (value: string) => value === 'direct_stop' ? '直接关停' : '重建并修改目标 ROI'
const isHandled = (plan: any) => {
  const operations = plan.operations || operationRecords.value.filter((item) => item.ad_plan_id === plan.id)
  const latestOperation = operations.slice().sort((a: any, b: any) => new Date(b.operated_at).getTime() - new Date(a.operated_at).getTime())[0]
  if (!latestOperation) return false
  const snapshotAt = plan.latest_snapshot?.snapshot_at
  return !snapshotAt || new Date(latestOperation.operated_at).getTime() >= new Date(snapshotAt).getTime()
}
const sortPlans = ({ prop, order }: any) => { sortKey.value = prop || ''; sortOrder.value = order }
const snapshotDelta = (index: number, key: string) => {
  if (index >= snapshots.value.length - 1) return '-'
  const current = Number(snapshots.value[index]?.[key] || 0)
  const previous = Number(snapshots.value[index + 1]?.[key] || 0)
  const delta = current - previous
  return `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}`
}

async function load() {
  loading.value = true
  try {
    const [planResult, batchResult, settingResult, operationResult] = await Promise.all([
      axios.get('/api/ads/plans'), axios.get('/api/ads/import-batches'), axios.get('/api/ads/target-roi-settings'), axios.get('/api/operations'),
    ])
    plans.value = planResult.data
    batches.value = batchResult.data
    targetSettings.value = settingResult.data
    operationRecords.value = operationResult.data
    targetDraft.value = Object.fromEntries(plans.value.map((item) => [item.id, item.target_roi]))
    variantDraft.value = Object.fromEntries(plans.value.map((item) => [item.id, item.strategy_code]))
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '广告数据加载失败')
  } finally {
    loading.value = false
  }
}

async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const data = new FormData()
  data.append('file', file)
  importing.value = true
  try {
    const result = (await axios.post('/api/ads/import', data)).data
    importMessage.value = `已导入 ${result.batch.row_count} 行，生成 ${result.snapshots} 条历史快照`
    ElMessage.success('广告数据导入成功')
    await load()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
    input.value = ''
  }
}

async function saveTarget(plan: any) {
  savingIds.value.push(plan.id)
  try {
    const result = (await axios.patch(`/api/ads/plans/${plan.id}/target-roi`, { target_roi: targetDraft.value[plan.id] })).data
    const index = plans.value.findIndex((item) => item.id === plan.id)
    if (index >= 0) plans.value[index] = result
    targetDraft.value[plan.id] = result.target_roi
    await load()
    ElMessage.success('该产品同编号的目标 ROI 已同步')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '目标 ROI 保存失败')
  } finally {
    savingIds.value = savingIds.value.filter((id) => id !== plan.id)
  }
}

async function showSnapshots(plan: any) {
  selectedPlan.value = plan
  const [snapshotResult, operationResult] = await Promise.all([
    axios.get('/api/ads/snapshots', { params: { ad_plan_id: plan.id } }),
    axios.get('/api/operations', { params: { ad_plan_id: plan.id } }),
  ])
  snapshots.value = snapshotResult.data
  selectedOperations.value = operationResult.data
  snapshotDrawer.value = true
}

async function saveVariant(plan: any) {
  try {
    const result = (await axios.patch(`/api/ads/plans/${plan.id}/variant`, { strategy_code: variantDraft.value[plan.id] || null })).data
    const index = plans.value.findIndex((item) => item.id === plan.id)
    if (index >= 0) plans.value[index] = result
    ElMessage.success('计划编号已保存')
  } catch (error: any) {
    variantDraft.value[plan.id] = plan.strategy_code
    ElMessage.error(error?.response?.data?.detail || '计划编号保存失败')
  }
}

function recordOperation(plan: any) {
  router.push({ path: '/operations', query: { ad_plan_id: String(plan.id) } })
}

function openSetting(setting?: any) {
  editingSettingId.value = setting?.id || null
  settingForm.value = setting
    ? { product_name: setting.product_name, strategy_code: setting.strategy_code, target_roi: setting.target_roi }
    : { product_name: '', strategy_code: 'A', target_roi: 2 }
  settingDialog.value = true
}

async function saveSetting() {
  if (!settingForm.value.product_name.trim()) {
    ElMessage.warning('请填写产品名称')
    return
  }
  settingSaving.value = true
  try {
    if (editingSettingId.value) await axios.put(`/api/ads/target-roi-settings/${editingSettingId.value}`, settingForm.value)
    else await axios.post('/api/ads/target-roi-settings', settingForm.value)
    ElMessage.success('目标 ROI 配置已保存并同步到已有计划')
    settingDialog.value = false
    await load()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '目标 ROI 配置保存失败')
  } finally {
    settingSaving.value = false
  }
}

async function removeSetting(setting: any) {
  try {
    await ElMessageBox.confirm(`确定删除“${setting.product_name} · ${setting.strategy_code}”的目标 ROI 配置吗？`, '确认删除', { type: 'warning' })
    await axios.delete(`/api/ads/target-roi-settings/${setting.id}`)
    ElMessage.success('配置已删除')
    await load()
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.response?.data?.detail || '删除失败')
  }
}

onMounted(async () => {
  await load()
  const planId = Number(route.query.plan_id)
  const plan = plans.value.find((item) => item.id === planId)
  if (plan) await showSnapshots(plan)
})
</script>
