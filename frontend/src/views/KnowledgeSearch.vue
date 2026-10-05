<template>
  <div class="page knowledge-page">
    <div class="knowledge-heading">
      <div>
        <span class="eyebrow">OPERATIONS KNOWLEDGE</span>
        <h1>运营知识检索</h1>
        <p>检索现有运营经验与规则出处。结果仅供查阅，不会更改广告计划。</p>
      </div>
      <span class="knowledge-version">知识库 V0.1</span>
    </div>

    <form class="knowledge-search" @submit.prevent="search">
      <label for="knowledge-query">业务问题</label>
      <div class="query-row">
        <el-input id="knowledge-query" v-model="query" maxlength="300" clearable
          placeholder="例如：视频正常，但是当前 ROI 低于目标 ROI 怎么办？" />
        <el-button type="primary" native-type="submit" :loading="loading">检索知识</el-button>
      </div>
      <div class="search-options">
        <label>来源
          <el-select v-model="sourceType" aria-label="知识来源">
            <el-option label="全部来源" value="" />
            <el-option label="运营经验" value="operator_experience" />
            <el-option label="平台指标定义" value="official_platform_definition" />
            <el-option label="合成演示" value="synthetic_demo" />
          </el-select>
        </label>
        <label>结果数量
          <el-select v-model="topK" aria-label="结果数量">
            <el-option v-for="count in [3, 5, 10, 20]" :key="count" :label="count + ' 条'" :value="count" />
          </el-select>
        </label>
      </div>
    </form>

    <div class="example-row">
      <span>常见问题</span>
      <button v-for="example in examples" :key="example" type="button" @click="searchExample(example)">{{ example }}</button>
    </div>

    <div v-if="error" class="knowledge-error" role="alert">{{ error }}</div>
    <div v-if="searched" class="result-heading">
      <div><h2>检索结果</h2><span>“{{ submittedQuery }}”</span></div>
      <strong>{{ results.length }} 条</strong>
    </div>
    <div v-if="searched && !results.length && !loading" class="knowledge-empty">没有找到匹配的知识。请更换关键词，或选择“全部来源”。</div>

    <div v-if="results.length" class="knowledge-results">
      <article v-for="item in results" :key="item.knowledge_id" class="knowledge-result">
        <div class="result-top">
          <div class="result-title"><span class="rule-id">{{ item.rule_id }}</span><h3>{{ item.title }}</h3></div>
          <span class="relevance">相关度 {{ Math.round(item.score * 100) }}%</span>
        </div>
        <div class="citation">
          <span>{{ sourceLabel(item.source_type) }}</span><span>版本 {{ item.version }}</span><span>引用 {{ item.rule_id }}</span>
        </div>
        <dl class="rule-facts">
          <div><dt>适用范围</dt><dd>{{ item.business_scope }}</dd></div>
          <div><dt>条件</dt><dd>{{ item.conditions }}</dd></div>
          <div><dt>经验动作</dt><dd>{{ item.action }}</dd></div>
          <div><dt>不确定性</dt><dd>{{ item.uncertainty }}</dd></div>
        </dl>
        <el-collapse class="rule-original"><el-collapse-item title="查看规则原文" :name="item.rule_id"><pre>{{ item.content }}</pre></el-collapse-item></el-collapse>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

type Result = {
  knowledge_id: string; rule_id: string; title: string; source_type: string;
  version: string; content: string; business_scope: string; conditions: string;
  action: string; uncertainty: string; score: number
}

const examples = ['空烧怎么判断？', '视频正常但是 ROI 低怎么办？', '消耗突然增加然后不再消耗怎么办？']
const query = ref('')
const sourceType = ref('')
const topK = ref(5)
const loading = ref(false)
const searched = ref(false)
const submittedQuery = ref('')
const results = ref<Result[]>([])
const error = ref('')
let requestNumber = 0

function sourceLabel(value: string) {
  return ({ operator_experience: '运营经验', official_platform_definition: '平台指标定义', synthetic_demo: '合成演示' } as Record<string, string>)[value] || value
}

async function search() {
  const text = query.value.trim()
  if (!text) { error.value = '请输入业务问题'; return }
  const currentRequest = ++requestNumber
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.post('/api/ai/knowledge/search', {
      query: text, top_k: topK.value, source_type: sourceType.value || null,
    })
    if (currentRequest !== requestNumber) return
    results.value = data.results
    submittedQuery.value = text
    searched.value = true
  } catch {
    if (currentRequest !== requestNumber) return
    error.value = '检索失败，请检查服务是否正在运行后重试。'
  } finally {
    if (currentRequest === requestNumber) loading.value = false
  }
}

function searchExample(example: string) { query.value = example; search() }
</script>

<style scoped>
.knowledge-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin:10px 0 24px}.knowledge-heading h1{font-size:28px;margin:8px 0}.knowledge-heading p{color:#667477;margin:0;line-height:1.6}.knowledge-version{white-space:nowrap;padding:7px 10px;background:#e8efec;color:#36584d;font-size:12px;border-radius:4px}.knowledge-search{padding:22px;background:#fff;border:1px solid #dfe7e7;border-radius:7px}.knowledge-search>label,.search-options label{display:grid;gap:8px;font-size:12px;font-weight:600;color:#536568}.query-row{display:flex;gap:10px;margin-top:9px}.query-row .el-input{flex:1}.query-row .el-button{min-width:110px}.search-options{display:flex;gap:14px;margin-top:17px}.search-options .el-select{width:180px}.example-row{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:16px 0 26px}.example-row span{font-size:12px;color:#718184;margin-right:4px}.example-row button{padding:7px 10px;border:1px solid #dce5e4;border-radius:5px;background:#fff;color:#385654;cursor:pointer;font-size:12px}.example-row button:hover{border-color:#16856f;color:#116b59}.result-heading{display:flex;align-items:end;justify-content:space-between;gap:10px;border-bottom:1px solid #dfe7e7;padding-bottom:12px;margin-bottom:13px}.result-heading div{min-width:0}.result-heading h2{font-size:18px;margin:0 0 5px}.result-heading span{color:#718184;font-size:12px;overflow-wrap:anywhere}.result-heading strong{color:#385654;font-size:13px;white-space:nowrap}.knowledge-results{display:grid;gap:12px}.knowledge-result{padding:18px 20px;background:#fff;border:1px solid #dfe7e7;border-radius:7px}.result-top,.result-title,.citation{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.result-top{justify-content:space-between}.result-title h3{margin:0;font-size:16px}.rule-id{font-size:12px;font-weight:700;color:#176b59;background:#e9f6f1;padding:4px 7px;border-radius:4px}.relevance{font-size:12px;color:#536568}.citation{gap:14px;color:#718184;font-size:11px;margin:10px 0 15px}.rule-facts{display:grid;grid-template-columns:1fr 1fr;gap:10px 20px;margin:0 0 12px}.rule-facts div{min-width:0}.rule-facts dt{font-size:11px;color:#718184;margin-bottom:4px}.rule-facts dd{margin:0;font-size:13px;line-height:1.55;overflow-wrap:anywhere}.rule-original pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;font-size:12px;line-height:1.7;color:#536568}.knowledge-empty,.knowledge-error{padding:20px;background:#fff;border:1px solid #dfe7e7;border-radius:7px;color:#667477}.knowledge-error{margin-bottom:15px;color:#a63d2f;background:#fff8f6;border-color:#f0d7d1}
@media(max-width:700px){.knowledge-heading{align-items:flex-start;flex-direction:column}.query-row{flex-direction:column}.query-row .el-button{width:100%}.search-options{flex-wrap:wrap}.search-options label{flex:1;min-width:130px}.search-options .el-select{width:100%}.rule-facts{grid-template-columns:1fr}.knowledge-result{padding:15px}}
</style>
