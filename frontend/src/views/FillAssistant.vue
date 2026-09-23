<template>
  <div class="page fill-page">
    <div class="intro fill-intro">
      <div>
        <span class="eyebrow">FILL ASSISTANT</span>
        <h1>全域消耗和预估赔付计算</h1>
        <p>导入当天 Product campaign，按产品汇总有效消耗并计算符合条件的预估赔付。</p>
      </div>
      <el-button :disabled="!analysis" @click="clearAnalysis">清空本次结果</el-button>
    </div>

    <section class="workspace-panel import-workspace">
      <div class="import-block primary-import">
        <div>
          <span class="step-label">每日计算</span>
          <h3>Product campaign</h3>
          <p>{{ campaignFile?.name || analysis?.filename || '尚未选择当天报表' }}</p>
        </div>
        <el-button type="primary" :loading="analyzing" @click="campaignInput?.click()">
          {{ analyzing ? '正在计算' : '导入 Product campaign' }}
        </el-button>
        <input ref="campaignInput" class="hidden-input" type="file" accept=".xlsx,.xlsm,.csv" @change="analyzeCampaign" />
      </div>
      <div class="import-divider"></div>
      <div class="import-block">
        <div>
          <span class="step-label">长期配置</span>
          <h3>赔付目标 ROI</h3>
          <p>{{ targetSettings.length }} 项配置，和广告计划中心共用</p>
        </div>
        <div class="config-actions">
          <el-button @click="activeTab = 'settings'">查看配置</el-button>
          <el-button plain :loading="configImporting" @click="configInput?.click()">
            {{ configImporting ? '正在导入' : '重新导入赔付配置' }}
          </el-button>
        </div>
        <input ref="configInput" class="hidden-input" type="file" accept=".xlsx,.xlsm" @change="importConfig" />
      </div>
    </section>

      <div v-if="analysis" class="fill-metrics">
        <div><span>产品数量</span><strong>{{ analysis.product_count }}</strong><small>按产品归集</small></div>
        <div><span>有效计划</span><strong>{{ analysis.effective_rows }}</strong><small>已排除 {{ analysis.zero_cost_rows }} 条零成本</small></div>
        <div><span>全域总消耗</span><strong>{{ money(analysis.total_consumption) }}</strong><small>来自 Product campaign 成本</small></div>
        <div><span>赔付计算</span><strong>{{ analysis.calculated_payout_plans }}</strong><small>{{ analysis.missing_target_roi_plans }} 条待设置目标 ROI</small></div>
      </div>

      <el-tabs v-model="activeTab" class="fill-tabs">
        <el-tab-pane label="计算结果" name="results">
          <template v-if="analysis">
          <section class="workspace-panel result-panel">
            <div class="section-head">
              <div><h3>全域消耗</h3><span class="muted">{{ analysis.filename }} · {{ analysis.total_rows }} 条原始数据</span></div>
              <el-button @click="downloadExport('export-consumption', '全域消耗.xlsx')">导出全域消耗</el-button>
            </div>
            <el-table :data="analysis.products" stripe default-expand-all empty-text="暂无有效成本数据">
              <el-table-column type="expand">
                <template #default="scope">
                  <div class="detail-table-wrap">
                    <el-table :data="scope.row.details" size="small" border>
                      <el-table-column prop="strategy_code" label="编号" width="62" />
                      <el-table-column prop="campaign_name" label="广告计划名称" min-width="250" />
                      <el-table-column prop="orders" label="SKU订单" width="82" align="right" />
                      <el-table-column label="总收入" width="100" align="right"><template #default="item">{{ money(item.row.revenue) }}</template></el-table-column>
                      <el-table-column label="目标ROI" width="92" align="right"><template #default="item">{{ decimal(item.row.target_roi) }}</template></el-table-column>
                      <el-table-column label="赔付ROI" width="92" align="right"><template #default="item">{{ decimal(item.row.payout_roi) }}</template></el-table-column>
                      <el-table-column label="实际消耗" width="105" align="right"><template #default="item">{{ money(item.row.cost) }}</template></el-table-column>
                      <el-table-column label="赔付金额" width="105" align="right">
                        <template #default="item"><span :class="{ pending: item.row.payout_status === 'target_roi_pending' }">{{ payoutValue(item.row) }}</span></template>
                      </el-table-column>
                    </el-table>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="product_name" label="产品" min-width="220" />
              <el-table-column prop="plan_count" label="计划数" width="90" align="right" />
              <el-table-column label="总收入" width="140" align="right"><template #default="scope">{{ money(scope.row.total_revenue) }}</template></el-table-column>
              <el-table-column prop="total_consumption" label="全域总消耗" width="150" align="right" sortable><template #default="scope">{{ money(scope.row.total_consumption) }}</template></el-table-column>
              <el-table-column label="预估赔付" width="150" align="right">
                <template #default="scope"><span :class="{ pending: scope.row.estimated_payout === null }">{{ scope.row.estimated_payout === null ? '待设置目标ROI' : money(scope.row.estimated_payout) }}</span></template>
              </el-table-column>
            </el-table>
          </section>

          <section class="workspace-panel payout-summary">
            <div class="section-head">
              <div><h3>预估赔付</h3><span class="muted">仅 SKU 订单数大于 21 的计划参与计算</span></div>
              <el-button type="primary" @click="downloadExport('export-payout', '预估赔付.xlsx')">导出预估赔付</el-button>
            </div>
            <div class="payout-total">
              <span>可完整计算产品预估赔付</span>
              <strong>{{ money(knownPayoutTotal) }}</strong>
              <small v-if="analysis.missing_target_roi_plans">另有 {{ analysis.missing_target_roi_plans }} 条符合赔付条件的计划待配置 ROI</small>
              <small v-else>全部符合条件的计划均已匹配目标 ROI</small>
            </div>
          </section>
          </template>
          <section v-else class="empty-workspace">
            <div class="empty-mark">XLSX</div>
            <h3>等待 Product campaign</h3>
            <p>选择当天报表后，计算结果会显示在这里。</p>
          </section>
        </el-tab-pane>

        <el-tab-pane :label="`赔付配置 ${targetSettings.length}`" name="settings">
          <section class="workspace-panel settings-panel">
            <div class="section-head">
              <div><h3>产品与编号目标 ROI</h3><span class="muted">此处修改会同步到广告计划中心。</span></div>
              <el-button type="primary" @click="openSetting()">新增配置</el-button>
            </div>
            <el-table :data="targetSettings" stripe empty-text="尚未配置目标 ROI">
              <el-table-column prop="product_name" label="产品" min-width="220" />
              <el-table-column prop="strategy_code" label="编号" width="90" />
              <el-table-column label="目标 ROI" width="140"><template #default="scope">{{ decimal(scope.row.target_roi) }}</template></el-table-column>
              <el-table-column label="操作" width="150" align="right">
                <template #default="scope"><el-button link @click="openSetting(scope.row)">编辑</el-button><el-button link type="danger" @click="removeSetting(scope.row)">删除</el-button></template>
              </el-table-column>
            </el-table>
          </section>
        </el-tab-pane>
      </el-tabs>

    <el-dialog v-model="settingDialog" :title="editingSettingId ? '编辑目标 ROI' : '新增目标 ROI'" width="460px">
      <el-form :model="settingForm" label-width="92px">
        <el-form-item label="产品名称"><el-input v-model="settingForm.product_name" placeholder="例如：微波炉蒸蛋器" /></el-form-item>
        <el-form-item label="计划编号"><el-segmented v-model="settingForm.strategy_code" :options="variantOptions" /></el-form-item>
        <el-form-item label="目标 ROI"><el-input-number v-model="settingForm.target_roi" :min="0.01" :precision="2" :step="0.1" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="settingDialog = false">取消</el-button><el-button type="primary" :loading="settingSaving" @click="saveSetting">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const ANALYSIS_STORAGE_KEY = 'fill-assistant:full-consumption-payout'

function restoreAnalysis() {
  try {
    const saved = sessionStorage.getItem(ANALYSIS_STORAGE_KEY)
    return saved ? JSON.parse(saved) : null
  } catch {
    sessionStorage.removeItem(ANALYSIS_STORAGE_KEY)
    return null
  }
}

const campaignInput = ref<HTMLInputElement | null>(null)
const configInput = ref<HTMLInputElement | null>(null)
const campaignFile = ref<File | null>(null)
const analysis = ref<any>(restoreAnalysis())
const targetSettings = ref<any[]>([])
const analyzing = ref(false)
const configImporting = ref(false)
const activeTab = ref('results')
const settingDialog = ref(false)
const settingSaving = ref(false)
const editingSettingId = ref<number | null>(null)
const settingForm = ref<any>({ product_name: '', strategy_code: 'A', target_roi: 2 })
const variantOptions = ['A', 'B', 'C', 'D']

const knownPayoutTotal = computed(() => analysis.value?.products.reduce((sum: number, item: any) => sum + (item.estimated_payout ?? 0), 0) ?? 0)
const money = (value: unknown) => `$${Number(value || 0).toFixed(2)}`
const decimal = (value: unknown) => value === null || value === undefined ? '-' : Number(value).toFixed(2)
const payoutValue = (row: any) => row.payout_status === 'target_roi_pending' ? '待设置' : money(row.payout_amount)

async function loadSettings() {
  targetSettings.value = (await axios.get('/api/ads/target-roi-settings')).data
}

async function runAnalysis() {
  if (!campaignFile.value) return
  const data = new FormData()
  data.append('file', campaignFile.value)
  analyzing.value = true
  try {
    analysis.value = (await axios.post('/api/fill-assistant/analyze', data)).data
    sessionStorage.setItem(ANALYSIS_STORAGE_KEY, JSON.stringify(analysis.value))
    activeTab.value = 'results'
    ElMessage.success(`已完成 ${analysis.value.effective_rows} 条有效计划计算`)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'Product campaign 导入失败')
  } finally {
    analyzing.value = false
  }
}

async function analyzeCampaign(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  campaignFile.value = file
  await runAnalysis()
}

async function importConfig(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const data = new FormData()
  data.append('file', file)
  configImporting.value = true
  try {
    const result = (await axios.post('/api/fill-assistant/import-payout-config', data)).data
    await loadSettings()
    await runAnalysis()
    ElMessage.success(`已导入 ${result.imported} 项目标 ROI 配置`)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '赔付配置导入失败')
  } finally {
    configImporting.value = false
  }
}

async function downloadExport(endpoint: string, filename: string) {
  if (!analysis.value) return
  try {
    const response = await axios.post(`/api/fill-assistant/${endpoint}`, analysis.value, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url; link.download = filename; link.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导出失败')
  }
}

function clearAnalysis() {
  campaignFile.value = null
  analysis.value = null
  sessionStorage.removeItem(ANALYSIS_STORAGE_KEY)
  activeTab.value = 'results'
}

function openSetting(setting?: any) {
  editingSettingId.value = setting?.id || null
  settingForm.value = setting
    ? { product_name: setting.product_name, strategy_code: setting.strategy_code, target_roi: setting.target_roi }
    : { product_name: '', strategy_code: 'A', target_roi: 2 }
  settingDialog.value = true
}

async function saveSetting() {
  if (!settingForm.value.product_name.trim()) return ElMessage.warning('请填写产品名称')
  settingSaving.value = true
  try {
    if (editingSettingId.value) await axios.put(`/api/ads/target-roi-settings/${editingSettingId.value}`, settingForm.value)
    else await axios.post('/api/ads/target-roi-settings', settingForm.value)
    settingDialog.value = false
    await loadSettings(); await runAnalysis()
    ElMessage.success('目标 ROI 已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '目标 ROI 保存失败')
  } finally {
    settingSaving.value = false
  }
}

async function removeSetting(setting: any) {
  try {
    await ElMessageBox.confirm(`确定删除“${setting.product_name} · ${setting.strategy_code}”吗？`, '删除配置', { type: 'warning' })
    await axios.delete(`/api/ads/target-roi-settings/${setting.id}`)
    await loadSettings(); await runAnalysis()
    ElMessage.success('配置已删除')
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.response?.data?.detail || '删除失败')
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.fill-page{max-width:1320px}.fill-intro{align-items:center}.fill-intro h1{font-size:34px}.import-workspace{display:grid;grid-template-columns:minmax(0,1fr) 1px minmax(0,1fr);gap:24px;padding:0}.import-block{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:24px;min-width:0}.import-block h3{font-size:17px;margin:5px 0}.import-block p{color:#718184;font-size:13px;margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:420px}.config-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.step-label{color:#16856f;font-size:11px;font-weight:700;text-transform:uppercase}.import-divider{background:#e3e9ea}.hidden-input{display:none}.fill-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}.fill-metrics>div{background:#fff;border:1px solid #e3e9ea;border-radius:7px;padding:18px}.fill-metrics span,.fill-metrics small{display:block;color:#718184;font-size:12px}.fill-metrics strong{display:block;font-size:27px;margin:9px 0 5px;color:#20262e}.fill-tabs{margin-top:4px}.result-panel,.settings-panel{padding:22px}.detail-table-wrap{padding:12px 24px;background:#f6f8f8}.pending{color:#b56a13;font-weight:600}.payout-summary{display:flex;align-items:center;justify-content:space-between}.payout-summary .section-head{margin:0;min-width:360px}.payout-total{text-align:right}.payout-total span,.payout-total small{display:block;color:#718184;font-size:12px}.payout-total strong{display:block;font-size:30px;margin:6px 0;color:#16856f}.empty-workspace{min-height:280px;border:1px dashed #cdd8d8;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#fff;border-radius:7px;color:#718184}.empty-workspace h3{color:#344246;margin:14px 0 4px}.empty-workspace p{margin:4px}.empty-mark{width:70px;height:52px;display:grid;place-items:center;border:2px solid #8ea5a3;color:#55716f;font-size:12px;font-weight:800}
@media(max-width:900px){.import-workspace{grid-template-columns:1fr}.import-divider{height:1px}.fill-metrics{grid-template-columns:repeat(2,1fr)}.payout-summary{display:block}.payout-total{text-align:left;margin-top:18px}.import-block{align-items:flex-start;flex-direction:column}.fill-intro h1{font-size:28px}}
@media(max-width:560px){.fill-metrics{grid-template-columns:1fr}.fill-intro{display:block}.fill-intro>.el-button{margin-top:14px}.result-panel{padding:14px}.detail-table-wrap{padding:8px}}
</style>
