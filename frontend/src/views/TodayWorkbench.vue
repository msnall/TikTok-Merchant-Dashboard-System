<template>
  <div class="page today-workbench">
    <div class="intro">
      <div>
        <span class="eyebrow">TODAY WORKBENCH</span>
        <h1>今天要做什么</h1>
        <p>{{ data.date || '今日' }} · 固定运营 SOP、广告异常和内容交付任务。</p>
      </div>
      <div class="intro-actions">
        <el-button @click="refresh">刷新任务</el-button>
        <el-button type="primary" @click="generate">生成今日任务</el-button>
      </div>
    </div>

    <div class="work-summary">
      <div><span>全部任务</span><strong>{{ tasks.length }}</strong></div>
      <div><span>待处理</span><strong>{{ countBy('pending') }}</strong></div>
      <div><span>进行中</span><strong>{{ countBy('in_progress') }}</strong></div>
      <div><span>已完成</span><strong>{{ countBy('completed') }}</strong></div>
      <div><span>高优先级</span><strong>{{ countPriority('high') }}</strong></div>
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
        <el-table-column prop="title" label="任务" min-width="240" />
        <el-table-column label="来源" width="100"><template #default="scope">{{ sourceLabel(scope.row.source) }}</template></el-table-column>
        <el-table-column label="优先级" width="90"><template #default="scope"><el-tag :type="priorityType(scope.row.priority)" size="small">{{ priorityLabel(scope.row.priority) }}</el-tag></template></el-table-column>
        <el-table-column label="状态" width="130"><template #default="scope"><el-select :model-value="scope.row.status" size="small" @change="value => updateStatus(scope.row, value)"><el-option label="待处理" value="pending" /><el-option label="进行中" value="in_progress" /><el-option label="已完成" value="completed" /><el-option label="已跳过" value="skipped" /></el-select></template></el-table-column>
        <el-table-column label="说明" min-width="260"><template #default="scope">{{ scope.row.description || '人工完成后更新状态' }}</template></el-table-column>
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
        <div v-for="item in data.ad_alerts" :key="item.id" class="alert-row"><strong>{{ item.plan_name }}</strong><span>{{ item.current_status }}</span></div>
        <el-empty v-if="!data.ad_alerts?.length" description="暂无广告提醒" :image-size="50" />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const tasks = ref<any[]>([])
const data = ref<any>({})
const statusFilter = ref<string | undefined>()
const priorityFilter = ref<string | undefined>()
const countBy = (status: string) => tasks.value.filter(item => item.status === status).length
const countPriority = (priority: string) => tasks.value.filter(item => item.priority === priority).length
const dueTime = (value: string | null) => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-'
const sourceLabel = (value: string) => value === 'sop' ? '运营 SOP' : value === 'system' ? '系统提醒' : '手动'
const priorityLabel = (value: string) => value === 'high' ? '高' : value === 'low' ? '低' : '中'
const priorityType = (value: string) => value === 'high' ? 'danger' : value === 'low' ? 'info' : 'warning'

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
    ElMessage.success('任务状态已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '状态保存失败')
  }
}

onMounted(refresh)
</script>
