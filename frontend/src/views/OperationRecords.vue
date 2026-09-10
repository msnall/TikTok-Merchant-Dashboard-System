<template>
  <div class="page">
    <div class="intro">
      <div><span class="eyebrow">OPERATION RECORDS</span><h1>运营记录</h1><p>记录你在 TikTok 后台实际执行的广告操作，不代替平台操作。</p></div>
      <el-button type="primary" @click="openCreate">记录操作</el-button>
    </div>
    <section class="workspace-panel">
      <el-table :data="records" stripe empty-text="暂无运营记录">
        <el-table-column label="广告计划" min-width="200"><template #default="scope">{{ scope.row.ad_plan?.name || scope.row.ad_plan_id }}</template></el-table-column>
        <el-table-column label="操作类型" width="180"><template #default="scope">{{ typeLabel(scope.row.operation_type) }}</template></el-table-column>
        <el-table-column prop="old_target_roi" label="原目标 ROI" width="110" />
        <el-table-column prop="new_target_roi" label="新目标 ROI" width="110" />
        <el-table-column prop="reason" label="原因" />
        <el-table-column prop="operated_at" label="操作时间" width="180" />
        <el-table-column label="操作" width="120"><template #default="scope"><el-button link @click="edit(scope.row)">编辑</el-button><el-button link type="danger" @click="remove(scope.row)">删除</el-button></template></el-table-column>
      </el-table>
    </section>
    <el-dialog v-model="dialog" :title="editingId ? '编辑广告操作' : '记录广告操作'" width="560px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="广告计划"><el-select v-model="form.ad_plan_id" filterable><el-option v-for="item in plans" :key="item.id" :label="item.plan_name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="操作类型"><el-select v-model="form.operation_type"><el-option label="直接关停" value="direct_stop" /><el-option label="重建并修改目标 ROI" value="rebuild_target_roi" /></el-select></el-form-item>
        <div class="form-grid">
          <el-form-item label="原目标 ROI"><el-input-number v-model="form.old_target_roi" :min="0" /></el-form-item>
          <el-form-item label="新目标 ROI"><el-input-number v-model="form.new_target_roi" :min="0" /></el-form-item>
        </div>
        <el-form-item label="原因"><el-input v-model="form.reason" type="textarea" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'

const route = useRoute()
const records = ref<any[]>([])
const plans = ref<any[]>([])
const dialog = ref(false)
const editingId = ref<number | null>(null)
const form = ref<any>({ operation_type: 'direct_stop', old_target_roi: null, new_target_roi: null, reason: '', notes: '' })
const typeLabel = (value: string) => value === 'direct_stop' ? '直接关停' : '重建并修改目标 ROI'
const reset = () => { editingId.value = null; form.value = { operation_type: 'direct_stop', old_target_roi: null, new_target_roi: null, reason: '', notes: '' } }

function openCreate() { reset(); dialog.value = true }
function edit(row: any) { editingId.value = row.id; form.value = { ad_plan_id: row.ad_plan_id, operation_type: row.operation_type, old_target_roi: row.old_target_roi, new_target_roi: row.new_target_roi, reason: row.reason || '', notes: row.notes || '' }; dialog.value = true }
async function load() { [records.value, plans.value] = await Promise.all([(await axios.get('/api/operations')).data, (await axios.get('/api/ads/plans')).data]) }
async function save() { try { if (editingId.value) await axios.put(`/api/operations/${editingId.value}`, form.value); else await axios.post('/api/operations', form.value); ElMessage.success('运营记录已保存'); dialog.value = false; reset(); await load() } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '保存失败') } }
async function remove(row: any) { try { await ElMessageBox.confirm('确定删除这条运营记录吗？', '确认', { type: 'warning' }); await axios.delete(`/api/operations/${row.id}`); await load() } catch { /* cancelled */ } }

onMounted(async () => {
  await load()
  const planId = Number(route.query.ad_plan_id)
  const plan = plans.value.find((item) => item.id === planId)
  if (plan) {
    reset()
    form.value.ad_plan_id = plan.id
    form.value.old_target_roi = plan.target_roi
    dialog.value = true
  }
})
</script>
