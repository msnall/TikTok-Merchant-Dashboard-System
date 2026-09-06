<template>
  <div class="page">
    <div class="toolbar">
      <el-input v-if="!isAssistant" v-model="query" placeholder="搜索名称、描述或标签" clearable @keyup.enter="load" />
      <el-button v-if="!isAssistant" type="primary" @click="openCreate">新增{{ label }}</el-button>
    </div>

    <template v-if="isAssistant">
      <section class="assistant-panel">
        <div><span class="eyebrow">CONTENT CREATION ASSISTANT</span><h2>从需求到混剪方案</h2><p>选择市场、产品、内容类型和时长，系统根据规则匹配现有脚本、模板与素材。</p></div>
        <div class="assistant-form"><el-input v-model="criteria.market_id" placeholder="市场 ID" /><el-input v-model="criteria.product_id" placeholder="产品 ID" /><el-input v-model="criteria.content_type" placeholder="内容类型，如 pain_point" /><el-input-number v-model="criteria.duration" :min="1" :max="600"/><el-input v-model="criteria.keywords" placeholder="关键词，用逗号分隔"/><el-button type="primary" @click="load">获取推荐</el-button></div>
      </section>
      <div class="recommend-grid">
        <section v-for="section in recommendationSections" :key="section.key" class="recommend-section">
          <div class="section-head"><h3>{{ section.title }}</h3><span class="muted">Top {{ section.limit }}</span></div>
          <div v-if="(recommendations[section.key] || []).length" class="recommend-list">
            <div v-for="item in (recommendations[section.key] || []).slice(0, section.limit)" :key="item.id" class="recommend-item">
              <div class="recommend-main"><strong>{{ item.name || item.title || item.id }}</strong><span class="score">{{ Math.round((item.score || 0) * 100) }}%</span></div>
              <small>{{ (item.reasons || []).join(' · ') || '基础匹配' }}</small>
              <el-button v-if="section.key === 'mix_plans'" size="small" type="primary" plain @click="usePlan(item)">使用此方案</el-button>
            </div>
          </div><el-empty v-else description="暂无匹配结果" :image-size="60" />
        </section>
      </div>
    </template>

    <el-table v-else :data="rows" stripe v-loading="loading" empty-text="暂无数据">
      <el-table-column :label="resource === 'assets' ? '名称' : '标题'"><template #default="scope">{{ scope.row.name || scope.row.title }}</template></el-table-column>
      <el-table-column v-if="resource === 'assets'" prop="asset_type" label="类型"/><el-table-column prop="source_platform" label="来源"/><el-table-column prop="status" label="状态"/>
      <el-table-column label="操作" width="190" fixed="right"><template #default="scope"><el-button link type="primary" @click="showDetail(scope.row)">详情</el-button><el-button link @click="openEdit(scope.row)">编辑</el-button><el-button link type="danger" @click="remove(scope.row)">删除</el-button></template></el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="`${editing ? '编辑' : '新增'}${label}`" width="520px"><el-form :model="form" label-width="80px"><el-form-item label="名称"><el-input v-model="form[titleKey]" /></el-form-item><el-form-item v-if="resource === 'assets'" label="类型"><el-input v-model="form.asset_type" /></el-form-item><el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item></el-form><template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template></el-dialog>
    <el-drawer v-model="detailVisible" title="详情" size="460px"><pre class="detail-json">{{ JSON.stringify(selected, null, 2) }}</pre></el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'; import { useRouter } from 'vue-router'; import axios from 'axios'; import { ElMessage, ElMessageBox } from 'element-plus';
const props = defineProps<{ resource: string }>(); const resource = computed(() => props.resource); const router = useRouter(); const isAssistant = computed(() => resource.value === 'assistant');
const names: Record<string, string> = { assets: '素材', scripts: '口播脚本', templates: '内容模板', 'mix-projects': '混剪方案', videos: '视频作品', assistant: '创作助手' }; const label = computed(() => names[resource.value] || resource.value); const titleKey = computed(() => resource.value === 'scripts' || resource.value === 'videos' ? 'title' : 'name'); const endpoint = computed(() => `/api/${resource.value}`);
const rows = ref<any[]>([]), query = ref(''), loading = ref(false), dialog = ref(false), editing = ref(false), detailVisible = ref(false), selected = ref<any>({}); const form = ref<any>({ name: '', title: '', asset_type: 'demo', description: '' }); const criteria = ref<any>({ market_id: '', product_id: '', content_type: '', duration: 20, keywords: 'sunscreen' }); const recommendations = ref<any>({});
const recommendationSections = [{ key: 'templates', title: '推荐模板', limit: 3 }, { key: 'scripts', title: '推荐脚本', limit: 5 }, { key: 'assets', title: '推荐素材', limit: 10 }, { key: 'mix_plans', title: '推荐混剪方案', limit: 3 }];
const allowedFields: Record<string, string[]> = { assets: ['name', 'asset_type', 'description'], scripts: ['title'], templates: ['name'], videos: ['title'], 'mix-projects': ['name'] };
async function load() { loading.value = true; try { if (isAssistant.value) { const payload = { market_id: criteria.value.market_id ? Number(criteria.value.market_id) : null, product_id: criteria.value.product_id ? Number(criteria.value.product_id) : null, content_type: criteria.value.content_type || null, duration: criteria.value.duration ? Number(criteria.value.duration) : null, keywords: String(criteria.value.keywords || '').split(',').map((word: string) => word.trim()).filter(Boolean) }; recommendations.value = (await axios.post('/api/assistant/recommend', payload)).data; } else rows.value = (await axios.get(endpoint.value, { params: { q: query.value } })).data; } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '加载失败'); } finally { loading.value = false; } }
function usePlan(plan: any) { router.push({ path: '/mix-projects/create', query: { market_id: criteria.value.market_id || '', product_id: criteria.value.product_id || '', script_id: plan.script_id, template_id: plan.template_id, asset_ids: (plan.asset_ids || []).join(','), duration: criteria.value.duration || '' } }); }
function openCreate() { if (resource.value === 'mix-projects') return router.push('/mix-projects/create'); editing.value = false; form.value = { name: '', title: '', asset_type: 'demo', description: '' }; dialog.value = true; } function openEdit(row: any) { if (resource.value === 'mix-projects') return router.push(`/mix-projects/${row.id}`); editing.value = true; form.value = { ...row }; dialog.value = true; } function showDetail(row: any) { if (resource.value === 'mix-projects') return router.push(`/mix-projects/${row.id}`); router.push(`/${resource.value}/${row.id}`); }
async function save() { const fields = allowedFields[resource.value] || []; const payload: Record<string, any> = {}; fields.forEach(key => { if (form.value[key] !== undefined) payload[key] = form.value[key]; }); try { if (editing.value) await axios.put(`${endpoint.value}/${form.value.id}`, payload); else await axios.post(endpoint.value, payload); ElMessage.success('保存成功'); dialog.value = false; await load(); } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '保存失败'); } }
async function remove(row: any) { try { await ElMessageBox.confirm('删除后无法恢复，确定继续吗？', '确认删除', { type: 'warning' }); await axios.delete(`${endpoint.value}/${row.id}`); ElMessage.success('已删除'); await load(); } catch { /* cancelled */ } }
onMounted(load); watch(resource, () => { rows.value = []; query.value = ''; dialog.value = false; load(); });
</script>
