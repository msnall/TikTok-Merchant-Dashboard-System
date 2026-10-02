<template>
  <div class="page workspace">
    <div class="workspace-head">
      <div><span class="eyebrow">MIX PROJECT WORKSPACE</span><h1>{{ isEditing ? '混剪方案详情' : '创建混剪方案' }}</h1></div>
      <div class="workspace-actions"><el-button @click="$router.push('/mix-projects')">返回列表</el-button><el-button v-if="isEditing" :loading="cloning" @click="cloneProject">克隆方案</el-button><el-button type="primary" :loading="saving" @click="saveProject">保存方案</el-button></div>
    </div>

    <el-form :model="form" label-position="top" class="workspace-form">
      <el-form-item label="方案名称"><el-input v-model="form.name" placeholder="例如：Indonesia Sunscreen 20s" /></el-form-item>
      <el-form-item label="市场"><el-select v-model="form.market_id" clearable filterable><el-option v-for="item in markets" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
      <el-form-item label="产品"><el-select v-model="form.product_id" clearable filterable><el-option v-for="item in products" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
      <el-form-item label="目标时长（秒）"><el-input-number v-model="form.target_duration" :min="1" :max="600" /></el-form-item>
      <el-form-item label="口播脚本"><el-select v-model="form.script_id" clearable filterable @change="applySelectedScript"><el-option v-for="item in scripts" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item>
    </el-form>

    <section v-if="selectedScript" class="workspace-panel project-script-panel">
      <div class="section-head"><div><span class="eyebrow">VOICEOVER SCRIPT</span><h3>{{ selectedScript.title }}</h3></div><audio v-if="selectedScript.audio_path" :src="storageUrl(selectedScript.audio_path)" controls preload="metadata"/></div>
      <div class="project-script-strip"><div v-for="segment in selectedScript.segments || []" :key="segment.id" :class="`role-${segment.role}`"><b>{{ roleLabel(segment.role) }}</b><span>{{ Number(segment.start_second).toFixed(1) }}–{{ Number(segment.end_second).toFixed(1) }} 秒</span><p>{{ segment.spoken_text }}</p></div></div>
    </section>

    <section class="workspace-panel timeline-panel">
      <div class="section-head"><div><h3>执行时间轴</h3><span class="muted">{{ timeline.length }} 段素材 · 点击分段即可预览和下载源文件</span></div><div class="section-actions"><a v-if="projectId" class="download-all" :href="`/api/mix-projects/${projectId}/assets.zip`">下载全部素材</a><el-button size="small" @click="addAsset">添加素材</el-button></div></div>
      <div class="timeline-workspace">
        <div class="timeline-segments">
          <article v-for="(row,index) in timeline" :key="`${row.asset_id}-${index}`" class="timeline-segment" :class="{selected:selectedIndex === index}" @click="selectSegment(index)">
            <div class="segment-heading"><span class="segment-number">{{ String(index + 1).padStart(2,'0') }}</span><div><strong><span class="timeline-role" :class="`role-${row.usage_type}`">{{ roleLabel(row.usage_type) }}</span>{{ row.script_text_snapshot || '未绑定文案' }}</strong><small>成片 {{ timeLabel(row) }} · 素材：{{ assetFor(row.asset_id)?.name || '请选择素材' }}</small></div><span class="file-state" :class="{ready:Boolean(assetFor(row.asset_id)?.file_path)}">{{ assetFor(row.asset_id)?.file_path ? '源文件就绪' : '缺少源文件' }}</span></div>
            <p v-if="segmentFor(row.script_segment_id)?.visual_direction" class="segment-visual-note">画面要求：{{ segmentFor(row.script_segment_id)?.visual_direction }}</p>
            <div class="segment-fields mix-segment-fields" @click.stop><label>匹配素材<el-select v-model="row.asset_id" filterable @change="selectSegment(index)"><el-option v-for="item in assets" :key="item.id" :label="item.name" :value="item.id"/></el-select></label><label>成片开始<el-input-number v-model="row.start_second" :min="0" :precision="1"/></label><label>成片结束<el-input-number v-model="row.end_second" :min="0.1" :precision="1"/></label><label>原素材起点<el-input-number v-model="row.source_start_second" :min="0" :precision="1"/></label><label>原素材终点<el-input-number v-model="row.source_end_second" :min="0.1" :precision="1"/></label></div>
            <div class="segment-actions" @click.stop><el-button link type="primary" @click="selectSegment(index)">预览</el-button><el-button link @click="openAsset(row.asset_id)">素材详情</el-button><a v-if="assetFor(row.asset_id)?.file_path" class="action-link" :href="assetMediaUrl(assetFor(row.asset_id))" :download="downloadName(assetFor(row.asset_id))">下载</a><span v-else class="action-disabled">无法下载</span><span class="action-spacer"></span><el-button link type="danger" @click="removeSegment(index)">移除</el-button></div>
          </article>
          <el-empty v-if="!timeline.length" description="暂无素材，请添加时间轴分段" :image-size="70"/>
          <p class="helper">时间轴会校验开始时间不小于 0、结束时间大于开始时间且不超过目标时长。</p>
        </div>
        <aside class="asset-inspector">
          <template v-if="selectedAsset">
            <div class="inspector-head"><div><span class="eyebrow">SELECTED ASSET</span><h3>第 {{ selectedIndex + 1 }} 段素材</h3></div><span class="file-state" :class="{ready:Boolean(selectedAsset.file_path)}">{{ selectedAsset.file_path ? '可用于剪映' : '未上传' }}</span></div>
            <div class="inspector-media"><img v-if="isImageAsset(selectedAsset)" :src="assetMediaUrl(selectedAsset)" alt="素材预览"/><video v-else-if="isVideoAsset(selectedAsset)" :key="assetMediaUrl(selectedAsset)" :src="assetMediaUrl(selectedAsset)" controls preload="metadata"/><el-empty v-else description="该素材尚未上传源文件" :image-size="60"/></div>
            <h4>{{ selectedAsset.name }}</h4><div class="asset-meta"><span>{{ selectedAsset.asset_type || '未分类' }}</span><span>{{ selectedAsset.duration || 0 }} 秒</span><span>{{ selectedAsset.source_platform || '未知来源' }}</span></div><p class="asset-description">{{ selectedAsset.description || '暂无素材说明' }}</p>
            <div class="inspector-actions"><a v-if="selectedAsset.file_path" class="download-button" :href="assetMediaUrl(selectedAsset)" :download="downloadName(selectedAsset)">下载源文件</a><el-button @click="openAsset(selectedAsset.id)">打开素材详情</el-button><a v-if="selectedAsset.source_url" class="source-link" :href="selectedAsset.source_url" target="_blank" rel="noopener">查看来源</a></div>
          </template><el-empty v-else description="选择一段素材后在这里预览" :image-size="70"/>
        </aside>
      </div>
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
const markets = ref<any[]>([]), products = ref<any[]>([]), scripts = ref<any[]>([]), assets = ref<any[]>([]), videos = ref<any[]>([]), timeline = ref<any[]>([]), saving = ref(false), cloning = ref(false), selectedIndex = ref(0);
const selectedAsset = computed(() => timeline.value[selectedIndex.value] ? assetFor(timeline.value[selectedIndex.value].asset_id) : null);
const selectedScript = computed(() => scripts.value.find(item => item.id === form.value.script_id) || null);

async function load() {
  const [marketResult, productResult, scriptResult, assetResult] = await Promise.all([
    axios.get('/api/markets'), axios.get('/api/products'), axios.get('/api/scripts'), axios.get('/api/assets'),
  ]);
  markets.value = marketResult.data; products.value = productResult.data; scripts.value = scriptResult.data; assets.value = assetResult.data;
  if (projectId.value) {
    const project = (await axios.get(`/api/mix-projects/${projectId.value}`)).data; form.value = { ...form.value, ...project }; timeline.value = (project.timeline || []).map((item: any, index: number) => ({ mix_project_id: project.id, asset_id: item.asset.id, order_index: index, start_second: item.start_second ?? index * 3, end_second: item.end_second ?? (index + 1) * 3, usage_type: item.usage_type || '', script_segment_id: item.script_segment_id, script_text_snapshot: item.script_text_snapshot || item.script_segment?.spoken_text || '', source_start_second: item.source_start_second ?? 0, source_end_second: item.source_end_second ?? Math.min(item.asset.duration || 3, (item.end_second || 3) - (item.start_second || 0)) }));
    videos.value = (await axios.get('/api/videos', { params: { mix_project_id: project.id } })).data; selectedIndex.value = Math.min(selectedIndex.value, Math.max(timeline.value.length - 1, 0));
  } else {
    const query = route.query; form.value.market_id = query.market_id ? Number(query.market_id) : null; form.value.product_id = query.product_id ? Number(query.product_id) : null; form.value.script_id = query.script_id ? Number(query.script_id) : null; form.value.template_id = null; form.value.target_duration = query.duration ? Number(query.duration) : 20; form.value.name = query.name || '新建混剪方案';
    const ids = String(query.asset_ids || '').split(',').map(Number).filter(Boolean); timeline.value = ids.map((assetId, index) => ({ asset_id: assetId, order_index: index, start_second: index * 3, end_second: Math.min((index + 1) * 3, form.value.target_duration), usage_type: index === 0 ? 'hook' : 'product' }));
  }
}
function addAsset() { const first = assets.value.find(item => !timeline.value.some(row => row.asset_id === item.id)) || assets.value[0]; if (first) { const start = timeline.value.length ? timeline.value[timeline.value.length - 1].end_second : 0; timeline.value.push({ asset_id: first.id, order_index: timeline.value.length, start_second: start, end_second: Math.min(start + 3, form.value.target_duration), usage_type: 'body', script_segment_id: null, script_text_snapshot: '', source_start_second: 0, source_end_second: Math.min(first.duration || 3, 3) }); } }
function assetFor(id: number) { return assets.value.find(item => item.id === id); }
function segmentFor(id: number) { return selectedScript.value?.segments?.find((item: any) => item.id === id); }
function roleLabel(role: string) { return ({hook:'Hook',body:'Body',ending:'Ending',cta:'CTA'} as any)[role] || role || '未设置'; }
function storageUrl(path: string) { return path ? `/storage/${String(path).replaceAll('\\','/')}` : ''; }
function assetMediaUrl(asset: any) { return asset?.file_path ? `/storage/${String(asset.file_path).replaceAll('\\','/')}` : ''; }
function isImageAsset(asset: any) { return /\.(jpg|jpeg|png|webp)$/i.test(assetMediaUrl(asset)); }
function isVideoAsset(asset: any) { return /\.(mp4|mov|webm)$/i.test(assetMediaUrl(asset)); }
function downloadName(asset: any) { const extension = String(asset?.file_path || '').split('.').pop() || 'mp4'; return `${asset?.name || '素材'}.${extension}`; }
function timeLabel(row: any) { return `${Number(row.start_second || 0).toFixed(1)}–${Number(row.end_second || 0).toFixed(1)} 秒`; }
function selectSegment(index: number) { selectedIndex.value = index; }
function openAsset(id: number) { window.open(router.resolve(`/assets/${id}`).href, '_blank', 'noopener'); }
function removeSegment(index: number) { timeline.value.splice(index,1); selectedIndex.value = Math.min(selectedIndex.value, Math.max(timeline.value.length - 1,0)); }
function applySelectedScript() { const script=selectedScript.value;if(!script?.segments?.length)return;form.value.target_duration=script.duration||form.value.target_duration;timeline.value=script.segments.map((segment:any,index:number)=>{const preferred=assets.value.find(asset=>asset.asset_type===segment.recommended_asset_type&&!timeline.value.some(row=>row.asset_id===asset.id))||assets.value.find(asset=>asset.asset_type===segment.recommended_asset_type)||assets.value[index%Math.max(assets.value.length,1)];return{asset_id:preferred?.id,order_index:index,start_second:segment.start_second,end_second:segment.end_second,usage_type:segment.role,script_segment_id:segment.id,script_text_snapshot:segment.spoken_text,source_start_second:0,source_end_second:Math.min(preferred?.duration||segment.end_second-segment.start_second,segment.end_second-segment.start_second)}});selectedIndex.value=0;}
async function saveProject() {
  if (!form.value.name?.trim()) return ElMessage.warning('请填写方案名称');
  if (timeline.value.some(row => !row.asset_id)) return ElMessage.warning('当前脚本有分段未匹配素材，请先选择素材再保存');
  saving.value = true;
  try {
    const projectPayload = { name: form.value.name.trim(), market_id: form.value.market_id || null, product_id: form.value.product_id || null, script_id: form.value.script_id || null, template_id: null, target_duration: form.value.target_duration, status: form.value.status || 'draft', notes: form.value.notes || null };
    let id = projectId.value;
    if (!id) { const created = (await axios.post('/api/mix-projects', projectPayload)).data; id = created.id; await router.replace(`/mix-projects/${id}`); }
    else await axios.put(`/api/mix-projects/${id}`, projectPayload);
    const entries = timeline.value.map((row, index) => ({ ...row, mix_project_id: id, order_index: index })); await axios.put(`/api/mix-projects/${id}/timeline`, entries); ElMessage.success('方案和时间轴已保存'); await load();
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '保存失败，请检查时间轴'); } finally { saving.value = false; }
}
async function createVideo() { if (!projectId.value) return; try { await axios.post('/api/videos', { title: `${form.value.name} 成片`, mix_project_id: projectId.value, market_id: form.value.market_id, product_id: form.value.product_id, duration: form.value.target_duration }); videos.value = (await axios.get('/api/videos', { params: { mix_project_id: projectId.value } })).data; ElMessage.success('已创建 VideoWork'); } catch { ElMessage.error('创建成片失败'); } }
async function cloneProject() { if (!projectId.value) return; cloning.value = true; try { const clone = (await axios.post(`/api/mix-projects/${projectId.value}/clone`)).data; ElMessage.success('方案及时间轴已克隆'); await router.push(`/mix-projects/${clone.id}`); await load(); } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '克隆失败'); } finally { cloning.value = false; } }
onMounted(load);
</script>
