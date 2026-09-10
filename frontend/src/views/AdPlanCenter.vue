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
        <label class="upload-button" :class="{ disabled: importing }">
          {{ importing ? '正在导入...' : '导入 Excel' }}
          <input type="file" accept=".xlsx,.xlsm,.csv" :disabled="importing" @change="importFile" />
        </label>
      </div>
    </div>

    <div v-if="importMessage" class="import-message">{{ importMessage }}</div>

    <div class="ad-summary">
      <div><span>广告计划</span><strong>{{ plans.length }}</strong></div>
      <div><span>空烧</span><strong>{{ statusCount('empty_burn') }}</strong></div>
      <div><span>ROI 低于目标</span><strong>{{ statusCount('low_roi') }}</strong></div>
      <div><span>ROI 达标</span><strong>{{ statusCount('roi_reached') }}</strong></div>
      <div><span>待设置目标 ROI</span><strong>{{ statusCount('target_roi_pending') }}</strong></div>
    </div>

    <section class="workspace-panel ad-plan-panel">
      <div class="section-head ad-toolbar">
        <div>
          <h3>当前广告计划</h3>
          <span class="muted">目标 ROI 按每条计划独立保存，A/B 计划互不覆盖。</span>
        </div>
        <el-radio-group v-model="activeStatus" size="small">
          <el-radio-button v-for="item in statusOptions" :key="item.value" :value="item.value">
            {{ item.label }} {{ item.value ? statusCount(item.value) : plans.length }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <el-table v-loading="loading" :data="filteredPlans" stripe empty-text="暂无符合条件的广告计划">
        <el-table-column prop="plan_name" label="广告计划" min-width="245">
          <template #default="scope">
            <div class="plan-name">{{ scope.row.plan_name }}</div>
            <small class="muted">{{ scope.row.platform_campaign_id || '无 Campaign ID' }}</small>
          </template>
        </el-table-column>
        <el-table-column label="产品" min-width="130">
          <template #default="scope">{{ scope.row.product?.name || scope.row.imported_product_name || '未识别' }}</template>
        </el-table-column>
        <el-table-column label="A/B" width="92">
          <template #default="scope">
            <el-select v-model="variantDraft[scope.row.id]" clearable placeholder="-" size="small" @change="saveVariant(scope.row)">
              <el-option label="A" value="A" /><el-option label="B" value="B" />
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
              <el-button link type="primary" :loading="savingIds.includes(scope.row.id)" @click="saveTarget(scope.row)">保存</el-button>
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
        <el-table-column label="更新时间" width="170">
          <template #default="scope">{{ dateTime(scope.row.latest_snapshot?.snapshot_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="150">
          <template #default="scope">
            <el-button link @click="showSnapshots(scope.row)">快照</el-button>
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
          <p><strong>24 小时无消耗</strong><span>从系统首次记录计划起计算</span></p>
          <p><strong>疑似空烧</strong><span>成本 &gt; $2 且 SKU 订单数 = 0</span></p>
          <p><strong>ROI 判断</strong><span>实际 ROI 与该计划目标 ROI 直接比较</span></p>
          <p><strong>人工决策</strong><span>系统不自动关停或修改 TikTok 广告</span></p>
        </div>
      </section>
    </div>

    <el-drawer v-model="snapshotDrawer" :title="`${selectedPlan?.plan_name || ''} · 历史快照`" size="min(760px, 92vw)">
      <el-table :data="snapshots" stripe empty-text="暂无快照">
        <el-table-column prop="snapshot_at" label="时间" width="170"><template #default="scope">{{ dateTime(scope.row.snapshot_at) }}</template></el-table-column>
        <el-table-column prop="spend" label="成本" width="80" />
        <el-table-column prop="orders" label="订单" width="70" />
        <el-table-column prop="actual_roi" label="实际 ROI" width="90" />
        <el-table-column prop="budget" label="预算" width="80" />
        <el-table-column label="状态" width="120"><template #default="scope">{{ statusLabel(scope.row.status) }}</template></el-table-column>
        <el-table-column prop="reason" label="判断依据" min-width="230" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const plans = ref<any[]>([])
const batches = ref<any[]>([])
const snapshots = ref<any[]>([])
const selectedPlan = ref<any>(null)
const snapshotDrawer = ref(false)
const importMessage = ref('')
const importing = ref(false)
const loading = ref(false)
const activeStatus = ref('')
const savingIds = ref<number[]>([])
const targetDraft = ref<Record<number, number | null>>({})
const variantDraft = ref<Record<number, 'A' | 'B' | null>>({})

const statusOptions = [
  { label: '全部', value: '' },
  { label: '空烧', value: 'empty_burn' },
  { label: 'ROI 低', value: 'low_roi' },
  { label: 'ROI 达标', value: 'roi_reached' },
  { label: '24h 无消耗', value: 'no_spend' },
  { label: '待设目标', value: 'target_roi_pending' },
  { label: '数据不足', value: 'insufficient_data' },
]

const filteredPlans = computed(() => activeStatus.value
  ? plans.value.filter((item) => item.current_status === activeStatus.value)
  : plans.value)

const statusCount = (status: string) => plans.value.filter((item) => item.current_status === status).length
const value = (input: unknown) => input === null || input === undefined ? '-' : String(input)
const number = (input: unknown) => input === null || input === undefined ? '-' : Number(input).toFixed(2)
const money = (input: unknown) => input === null || input === undefined ? '-' : `$${Number(input).toFixed(2)}`
const dateTime = (input: string | null | undefined) => input ? new Date(input).toLocaleString('zh-CN', { hour12: false }) : '-'
const statusLabel = (status: string) => ({
  empty_burn: '疑似空烧', low_roi: 'ROI 低于目标', roi_reached: 'ROI 达标', no_spend: '24 小时无消耗',
  target_roi_pending: '待设置目标 ROI', insufficient_data: '数据不足', normal: '正常', unknown: '未知',
}[status] || status)
const statusType = (status: string) => status === 'roi_reached' || status === 'normal' ? 'success'
  : status === 'empty_burn' || status === 'no_spend' ? 'danger'
    : status === 'low_roi' ? 'warning' : 'info'

async function load() {
  loading.value = true
  try {
    const [planResult, batchResult] = await Promise.all([
      axios.get('/api/ads/plans'), axios.get('/api/ads/import-batches'),
    ])
    plans.value = planResult.data
    batches.value = batchResult.data
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
    ElMessage.success('目标 ROI 已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '目标 ROI 保存失败')
  } finally {
    savingIds.value = savingIds.value.filter((id) => id !== plan.id)
  }
}

async function showSnapshots(plan: any) {
  selectedPlan.value = plan
  snapshots.value = (await axios.get('/api/ads/snapshots', { params: { ad_plan_id: plan.id } })).data
  snapshotDrawer.value = true
}

async function saveVariant(plan: any) {
  try {
    const result = (await axios.patch(`/api/ads/plans/${plan.id}/variant`, { strategy_code: variantDraft.value[plan.id] || null })).data
    const index = plans.value.findIndex((item) => item.id === plan.id)
    if (index >= 0) plans.value[index] = result
    ElMessage.success('A/B 标记已保存')
  } catch (error: any) {
    variantDraft.value[plan.id] = plan.strategy_code
    ElMessage.error(error?.response?.data?.detail || 'A/B 标记保存失败')
  }
}

function recordOperation(plan: any) {
  router.push({ path: '/operations', query: { ad_plan_id: String(plan.id) } })
}

onMounted(load)
</script>
