<template>
  <div class="page workspace">
    <div class="workspace-head">
      <div><span class="eyebrow">MIX PROJECT WORKSPACE</span><h1>{{ isEditing ? '混剪方案详情' : '创建混剪方案' }}</h1></div>
      <div class="workspace-actions"><el-button @click="$router.push('/mix-projects')">返回列表</el-button><el-button type="primary" :loading="saving" @click="saveProject">保存方案</el-button></div>
    </div>

    <el-form :model="form" label-position="top" class="workspace-form">
      <el-form-item label="方案名称"><el-input v-model="form.name" placeholder="例如：Indonesia Sunscreen 20s" /></el-form-item>
      <el-form-item label="市场"><el-select v-model="form.market_id" clearable filterable><el-option v-for="item in markets" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
      <el-form-item label="产品"><el-select v-model="form.product_id" clearable filterable><el-option v-for="item in products" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
      <el-form-item label="目标时长（秒）"><el-input-number v-model="form.target_duration" :min="1" :max="600" /></el-form-item>
      <el-form-item label="口播脚本"><el-select v-model="form.script_id" clearable filterable><el-option v-for="item in scripts" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item>
      <el-form-item label="内容模板"><el-select v-model="form.template_id" clearable filterable><el-option v-for="item in templates" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
    </el-form>

    <section class="workspace-panel">
      <div class="section-head"><h3>时间轴</h3><el-button size="small" @click="addAsset">添加素材</el-button></div>
      <el-table :data="timeline" stripe empty-text="暂无素材，请从右侧添加">
        <el-table-column type="index" label="#" width="55" />
        <el-table-column label="素材" min-width="220"><template #default="scope"><el-select v-model="scope.row.asset_id" filterable><el-option v-for="item in assets" :key="item.id" :label="item.name" :value="item.id" /></el-select></template></el-table-column>
        <el-table-column label="用途" width="150"><template #default="scope"><el-input v-model="scope.row.usage_type" placeholder="hook / demo" /></template></el-table-column>
        <el-table-column label="开始（秒）" width="150"><template #default="scope"><el-input-number v-model="scope.row.start_second" :min="0" :precision="1" /></template></el-table-column>
        <el-table-column label="结束（秒）" width="150"><template #default="scope"><el-input-number v-model="scope.row.end_second" :min="0.1" :precision="1" /></template></el-table-column>
        <el-table-column label="操作" width="90"><template #default="scope"><el-button link type="danger" @click="timeline.splice(scope.$index, 1)">移除</el-button></template></el-table-column>
      </el-table>
      <p class="helper">时间轴会校验开始时间不小于 0、结束时间大于开始时间且不超过目标时长。</p>
    </section>

    <section v-if="isEditing" class="workspace-panel lineage-panel">
      <div class="section-head"><h3>关联成片</h3><el-button size="small" type="primary" @click="createVideo">创建 VideoWork</el-button></div>
      <el-table :data="videos" stripe empty-text="尚未关联成片"><el-table-column prop="title" label="标题"/><el-table-column prop="version" label="版本" width="90"/><el-table-column prop="status" label="状态" width="120"/></el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { ElMessage } from 'element-plus';

const route = useRoute(); const router = useRouter();
const projectId = computed(() => Number(route.params.id) || null); const isEditing = computed(() => Boolean(projectId.value));
const form = ref<any>({ name: '', market_id: null, product_id: null, script_id: null, template_id: null, target_duration: 20, status: 'draft' });
const markets = ref<any[]>([]), products = ref<any[]>([]), scripts = ref<any[]>([]), templates = ref<any[]>([]), assets = ref<any[]>([]), videos = ref<any[]>([]), timeline = ref<any[]>([]), saving = ref(false);

async function load() {
  const [marketResult, productResult, scriptResult, templateResult, assetResult] = await Promise.all([
    axios.get('/api/markets'), axios.get('/api/products'), axios.get('/api/scripts'), axios.get('/api/templates'), axios.get('/api/assets'),
  ]);
  markets.value = marketResult.data; products.value = productResult.data; scripts.value = scriptResult.data; templates.value = templateResult.data; assets.value = assetResult.data;
  if (projectId.value) {
    const project = (await axios.get(`/api/mix-projects/${projectId.value}`)).data; form.value = { ...form.value, ...project }; timeline.value = (project.timeline || []).map((item: any, index: number) => ({ mix_project_id: project.id, asset_id: item.asset.id, order_index: index, start_second: item.start_second ?? index * 3, end_second: item.end_second ?? (index + 1) * 3, usage_type: item.usage_type || '' }));
    videos.value = (await axios.get('/api/videos', { params: { mix_project_id: project.id } })).data;
  } else {
    const query = route.query; form.value.market_id = query.market_id ? Number(query.market_id) : null; form.value.product_id = query.product_id ? Number(query.product_id) : null; form.value.script_id = query.script_id ? Number(query.script_id) : null; form.value.template_id = query.template_id ? Number(query.template_id) : null; form.value.target_duration = query.duration ? Number(query.duration) : 20; form.value.name = query.name || '新建混剪方案';
    const ids = String(query.asset_ids || '').split(',').map(Number).filter(Boolean); timeline.value = ids.map((assetId, index) => ({ asset_id: assetId, order_index: index, start_second: index * 3, end_second: Math.min((index + 1) * 3, form.value.target_duration), usage_type: index === 0 ? 'hook' : 'product' }));
  }
}
function addAsset() { const first = assets.value.find(item => !timeline.value.some(row => row.asset_id === item.id)) || assets.value[0]; if (first) { const start = timeline.value.length ? timeline.value[timeline.value.length - 1].end_second : 0; timeline.value.push({ asset_id: first.id, order_index: timeline.value.length, start_second: start, end_second: Math.min(start + 3, form.value.target_duration), usage_type: 'product' }); } }
async function saveProject() {
  if (!form.value.name?.trim()) return ElMessage.warning('请填写方案名称'); saving.value = true;
  try {
    let id = projectId.value; if (!id) { const created = (await axios.post('/api/mix-projects', form.value)).data; id = created.id; await router.replace(`/mix-projects/${id}`); }
    const entries = timeline.value.map((row, index) => ({ ...row, mix_project_id: id, order_index: index })); await axios.put(`/api/mix-projects/${id}/timeline`, entries); ElMessage.success('方案和时间轴已保存'); await load();
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '保存失败，请检查时间轴'); } finally { saving.value = false; }
}
async function createVideo() { if (!projectId.value) return; try { await axios.post('/api/videos', { title: `${form.value.name} 成片`, mix_project_id: projectId.value, market_id: form.value.market_id, product_id: form.value.product_id, duration: form.value.target_duration }); videos.value = (await axios.get('/api/videos', { params: { mix_project_id: projectId.value } })).data; ElMessage.success('已创建 VideoWork'); } catch { ElMessage.error('创建成片失败'); } }
onMounted(load);
</script>
