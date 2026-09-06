<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-if="resource !== 'assistant'" v-model="query" placeholder="搜索内容" clearable @keyup.enter="load" />
      <el-button v-if="resource !== 'assistant'" type="primary" @click="openCreate">新增{{ label }}</el-button>
    </div>
    <div v-if="resource === 'assistant'" class="callout assistant-note">
      <span class="eyebrow">规则匹配 + 语义相似度</span><h3>创作助手</h3>
      <p>系统按市场、产品、内容类型、时长和语义相似度推荐现有资产，并说明推荐原因。</p>
      <div class="assistant-form"><el-input v-model="criteria.market_id" placeholder="市场 ID" /><el-input v-model="criteria.product_id" placeholder="产品 ID" /><el-input v-model="criteria.content_type" placeholder="内容类型，如 pain_point" /><el-input v-model="criteria.duration" placeholder="目标时长（秒）" /><el-input v-model="criteria.keywords" placeholder="关键词，用逗号分隔" /></div>
      <el-button type="primary" @click="load">刷新推荐</el-button>
    </div>
    <el-table :data="rows" stripe v-loading="loading">
      <el-table-column prop="name" :label="resource === 'assets' ? '名称' : '标题'"><template #default="scope">{{ scope.row.name || scope.row.title }}</template></el-table-column>
      <el-table-column prop="asset_type" label="类型" />
      <el-table-column prop="source_platform" label="来源" />
      <el-table-column v-if="resource === 'assistant'" prop="score" label="匹配分数"><template #default="scope">{{ Math.round((scope.row.score || 0) * 100) }}%</template></el-table-column>
      <el-table-column v-if="resource === 'assistant'" prop="reasons" label="推荐理由"><template #default="scope">{{ (scope.row.reasons || []).join('、') || '基础匹配' }}</template></el-table-column>
      <el-table-column v-if="resource !== 'assistant'" prop="status" label="状态" />
      <el-table-column v-if="resource !== 'assistant'" label="操作" width="190" fixed="right"><template #default="scope"><el-button link type="primary" @click="showDetail(scope.row)">详情</el-button><el-button link @click="openEdit(scope.row)">编辑</el-button><el-button link type="danger" @click="remove(scope.row)">删除</el-button></template></el-table-column>
    </el-table>
    <el-dialog v-model="dialog" :title="`${editing ? '编辑' : '新增'}${label}`" width="520px">
      <el-form :model="form" label-width="80px"><el-form-item label="名称"><el-input v-model="form[titleKey]" /></el-form-item><el-form-item v-if="resource === 'assets'" label="类型"><el-input v-model="form.asset_type" placeholder="demo、lifestyle…" /></el-form-item><el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
    <el-drawer v-model="detailVisible" title="资产详情" size="460px"><pre class="detail-json">{{ JSON.stringify(selected, null, 2) }}</pre></el-drawer>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'; import axios from 'axios'; import { ElMessage, ElMessageBox } from 'element-plus';
const props = defineProps<{ resource: string }>(); const resource = props.resource;
const names: Record<string, string> = { assets: '素材', scripts: '口播脚本', templates: '内容模板', 'mix-projects': '混剪方案', videos: '视频作品', assistant: '创作助手' };
const label = computed(() => names[resource] || resource); const titleKey = computed(() => resource === 'scripts' || resource === 'videos' ? 'title' : 'name'); const endpoint = computed(() => `/api/${resource}`);
const rows = ref<any[]>([]), query = ref(''), loading = ref(false), dialog = ref(false), editing = ref(false), detailVisible = ref(false), selected = ref<any>({}); const form = ref<any>({ name: '', title: '', asset_type: 'demo', description: '' }); const criteria = ref<any>({ market_id: '', product_id: '', content_type: '', duration: 20, keywords: 'sunscreen' });
async function load() { loading.value = true; try { if (resource === 'assistant') { const payload = { market_id: criteria.value.market_id ? Number(criteria.value.market_id) : null, product_id: criteria.value.product_id ? Number(criteria.value.product_id) : null, content_type: criteria.value.content_type || null, duration: criteria.value.duration ? Number(criteria.value.duration) : null, keywords: String(criteria.value.keywords || '').split(',').map((word: string) => word.trim()).filter(Boolean) }; const result = (await axios.post('/api/assistant/recommend', payload)).data; rows.value = result.assets || []; } else rows.value = (await axios.get(endpoint.value, { params: { q: query.value } })).data; } finally { loading.value = false; } }
function openCreate() { editing.value = false; form.value = { name: '', title: '', asset_type: 'demo', description: '' }; dialog.value = true; } function openEdit(row: any) { editing.value = true; form.value = { ...row }; dialog.value = true; } function showDetail(row: any) { selected.value = row; detailVisible.value = true; }
async function save() { const payload = { ...form.value }; Object.keys(payload).forEach(key => { if (payload[key] === undefined || key === 'id' || typeof payload[key] === 'object') delete payload[key]; }); try { if (editing.value) await axios.put(`${endpoint.value}/${form.value.id}`, payload); else await axios.post(endpoint.value, payload); ElMessage.success('保存成功'); dialog.value = false; await load(); } catch { ElMessage.error('保存失败，请检查字段'); } }
async function remove(row: any) { try { await ElMessageBox.confirm('删除后无法恢复，确定继续吗？', '确认删除', { type: 'warning' }); await axios.delete(`${endpoint.value}/${row.id}`); ElMessage.success('已删除'); await load(); } catch { /* cancelled */ } }
onMounted(load);
</script>
