<template>
  <div class="page today-workbench">
    <div class="intro">
      <div>
        <span class="eyebrow">TODAY WORKBENCH</span>
        <h1>今天要做什么</h1>
        <p>{{ data.date || '今日' }} · 固定运营 SOP、广告异常和内容交付任务。</p>
      </div>
      <div class="intro-actions">
        <el-button @click="customDialog = true">新增任务</el-button>
        <el-button @click="refresh">刷新任务</el-button>
        <el-button type="primary" @click="generate">生成今日任务</el-button>
      </div>
    </div>

    <div class="work-summary">
      <div><span>全部任务</span><strong>{{ data.task_summary?.total ?? tasks.length }}</strong></div>
      <div><span>待处理</span><strong>{{ data.task_summary?.pending ?? countBy('pending') }}</strong></div>
      <div><span>进行中</span><strong>{{ data.task_summary?.in_progress ?? countBy('in_progress') }}</strong></div>
      <div><span>已完成</span><strong>{{ data.task_summary?.completed ?? countBy('completed') }}</strong></div>
      <div><span>完成率</span><strong>{{ data.task_summary?.completion_rate ?? 0 }}%</strong></div>
    </div>

    <section class="workspace-panel">
      <div class="section-head">
        <h3>今日任务</h3>
        <div class="task-filters">
          <el-select v-model="statusFilter" clearable placeholder="状态" size="small" @change="refresh">
            <el-option label="待处理" value="pending" /><el-option label="进行中" value="in_progress" /><el-option label="已完成" value="completed" /><el-option label="已跳过" value="skipped" />
          </el-select>
          <el-select v-model="priorityFilter" clearable placeholder="优先级" size="small" @change="refresh">
            <el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" />
          </el-select>
        </div>
      </div>
      <el-table v-loading="loading" :data="tasks" stripe empty-text="今天还没有任务">
        <el-table-column label="时间" width="90"><template #default="scope">{{ dueTime(scope.row.due_at) }}</template></el-table-column>
        <el-table-column label="任务" min-width="240"><template #default="scope"><el-button v-if="scope.row.related_id" link type="primary" @click="openRelated(scope.row)">{{ scope.row.title }}</el-button><span v-else>{{ scope.row.title }}</span></template></el-table-column>
        <el-table-column label="来源" width="100"><template #default="scope">{{ sourceLabel(scope.row.source) }}</template></el-table-column>
        <el-table-column label="优先级" width="90"><template #default="scope"><el-tag :type="priorityType(scope.row.priority)" size="small">{{ priorityLabel(scope.row.priority) }}</el-tag></template></el-table-column>
        <el-table-column label="状态" width="130"><template #default="scope"><el-select :model-value="scope.row.status" size="small" @change="value => updateStatus(scope.row, value)"><el-option label="待处理" value="pending" /><el-option label="进行中" value="in_progress" /><el-option label="已完成" value="completed" /><el-option label="已跳过" value="skipped" /></el-select></template></el-table-column>
        <el-table-column label="说明" min-width="260"><template #default="scope">{{ scope.row.description || '人工完成后更新状态' }}</template></el-table-column>
        <el-table-column label="操作" width="130"><template #default="scope"><el-button v-if="scope.row.source === 'manual'" link @click="editTask(scope.row)">编辑</el-button><el-button link type="danger" @click="removeTask(scope.row)">删除</el-button></template></el-table-column>
      </el-table>
    </section>

    <div class="ops-grid">
      <section class="workspace-panel">
        <div class="section-head"><h3>待处理内容</h3><el-button link type="primary" @click="router.push('/content/mix-projects')">查看方案</el-button></div>
        <div v-for="item in data.content_projects" :key="item.id" class="home-link-row"><span>{{ item.name }}</span><el-button link @click="router.push(`/mix-projects/${item.id}`)">继续编辑</el-button></div>
        <el-empty v-if="!data.content_projects?.length" description="暂无待处理方案" :image-size="50" />
      </section>
      <section class="workspace-panel">
        <div class="section-head"><h3>广告提醒</h3><el-button link type="primary" @click="router.push('/ads')">处理广告</el-button></div>
        <div class="ad-alert-list">
          <div v-for="item in data.ad_alerts" :key="item.id" class="ad-alert-card">
            <div>
              <strong>{{ item.plan_name }}</strong>
              <div class="alert-meta"><span class="status-danger">疑似空烧</span><span>成本 {{ money(item.latest_snapshot?.spend) }}</span><span>SKU 订单 {{ value(item.latest_snapshot?.orders) }}</span></div>
            </div>
            <div class="alert-actions"><el-button link @click="openAd(item.id)">查看广告</el-button><el-button link type="primary" @click="recordAd(item.id)">记录处理</el-button></div>
          </div>
        </div>
        <el-empty v-if="!data.ad_alerts?.length" description="暂无广告提醒" :image-size="50" />
      </section>
    </div>
    <el-dialog v-model="customDialog" title="新增运营任务" width="520px">
      <el-form :model="customForm" label-width="90px">
        <el-form-item label="任务标题"><el-input v-model="customForm.title" placeholder="例如：联系供应商确认库存" /></el-form-item>
        <el-form-item label="优先级"><el-select v-model="customForm.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item>
        <el-form-item label="备注"><el-input v-model="customForm.notes" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="customDialog = false">取消</el-button><el-button type="primary" @click="saveCustomTask">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const tasks = ref<any[]>([])
const data = ref<any>({})
const statusFilter = ref<string | undefined>()
const priorityFilter = ref<string | undefined>()
const customDialog = ref(false)
const editingTaskId = ref<number | null>(null)
const customForm = ref<any>({ title: '', priority: 'medium', notes: '', status: 'pending' })
const countBy = (status: string) => tasks.value.filter(item => item.status === status).length
const countPriority = (priority: string) => tasks.value.filter(item => item.priority === priority).length
const dueTime = (value: string | null) => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-'
const sourceLabel = (value: string) => value === 'sop' ? '运营 SOP' : value === 'system' ? '系统提醒' : '手动'
const priorityLabel = (value: string) => value === 'high' ? '高' : value === 'low' ? '低' : '中'
const priorityType = (value: string) => value === 'high' ? 'danger' : value === 'low' ? 'info' : 'warning'
const value = (input: unknown) => input === null || input === undefined ? '-' : String(input)
const money = (input: unknown) => input === null || input === undefined ? '-' : `$${Number(input).toFixed(2)}`
const openAd = (id: number) => router.push({ path: '/ads', query: { plan_id: String(id) } })
const recordAd = (id: number) => router.push({ path: '/operations', query: { ad_plan_id: String(id) } })

async function refresh() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (statusFilter.value) params.status = statusFilter.value
    if (priorityFilter.value) params.priority = priorityFilter.value
    const response = await axios.get('/api/workbench/today', { params })
    data.value = response.data
    tasks.value = response.data.tasks || []
  } finally {
    loading.value = false
  }
}

async function generate() {
  await axios.post('/api/work-tasks/generate')
  await refresh()
  ElMessage.success('今日任务已生成')
}

async function updateStatus(task: any, status: string) {
  try {
    const response = await axios.patch(`/api/work-tasks/${task.id}/status`, { status })
    task.status = response.data.status
    task.completed_at = response.data.completed_at
    await refresh()
    ElMessage.success('任务状态已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '状态保存失败')
  }
}

async function saveCustomTask() {
  if (!customForm.value.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  try {
    const payload = {
      title: customForm.value.title,
      description: customForm.value.notes || null,
      task_type: 'content_task',
      status: customForm.value.status || 'pending',
      priority: customForm.value.priority,
      task_date: data.value.date || new Date().toISOString().slice(0, 10),
      source: 'manual',
      notes: customForm.value.notes || null,
    }
    if (editingTaskId.value) await axios.put(`/api/work-tasks/${editingTaskId.value}`, payload)
    else await axios.post('/api/work-tasks', payload)
    customDialog.value = false
    editingTaskId.value = null
    customForm.value = { title: '', priority: 'medium', notes: '', status: 'pending' }
    await refresh()
    ElMessage.success('任务已创建')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '任务创建失败')
  }
}

function editTask(task: any) {
  editingTaskId.value = task.id
  customForm.value = { title: task.title, priority: task.priority, notes: task.notes || task.description || '', status: task.status }
  customDialog.value = true
}

function openRelated(task: any) {
  if (task.related_type === 'ad_plan') openAd(task.related_id)
  else if (task.related_type === 'mix_project') router.push(`/mix-projects/${task.related_id}`)
  else if (task.related_type === 'video_work') router.push(`/videos/${task.related_id}`)
}

async function removeTask(task: any) {
  try {
    await ElMessageBox.confirm(`确定删除“${task.title}”吗？`, '删除任务', { type: 'warning' })
    await axios.delete(`/api/work-tasks/${task.id}`)
    await refresh()
    ElMessage.success('任务已删除')
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.response?.data?.detail || '删除失败')
  }
}

onMounted(refresh)
</script>
