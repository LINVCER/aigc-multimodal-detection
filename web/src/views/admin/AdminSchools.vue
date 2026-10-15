<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  adminListSchools, adminSaveSchool, adminSetSchoolStatus, adminImportSchools,
  adminListSeeds, adminSaveSeed, adminRunSeed,
  adminListCandidates, adminMergeCandidate, adminRejectCandidate, adminSyncCandidates,
  type School, type CrawlSeed, type RuleCandidate,
} from '@/api/school'

const tab = ref('schools')

/* ---------- 学校 ---------- */
const schoolQ = ref('')
const schools = ref<School[]>([])
const loadingSchools = ref(false)
async function loadSchools() {
  loadingSchools.value = true
  try { schools.value = await adminListSchools(schoolQ.value || undefined) } finally { loadingSchools.value = false }
}
const schoolDlg = reactive({ open: false, form: {} as Partial<School> })
function newSchool() { schoolDlg.form = { level: 'undergrad' }; schoolDlg.open = true }
function editSchool(s: School) { schoolDlg.form = { ...s }; schoolDlg.open = true }
async function saveSchool() {
  if (!schoolDlg.form.name) { ElMessage.warning('填学校全称'); return }
  await adminSaveSchool(schoolDlg.form); schoolDlg.open = false; ElMessage.success('存好了'); loadSchools()
}
async function toggleSchool(s: School) {
  const next = s.status === 'hidden' ? 'active' : 'hidden'
  await adminSetSchoolStatus(s.id, next); loadSchools()
}
const importDlg = reactive({ open: false, text: '' })
async function doImport() {
  const list = importDlg.text.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
    const [name, shortName, province, level] = l.split(',').map(x => x?.trim())
    return { name, shortName, province, level: level || 'undergrad' }
  }).filter(x => x.name)
  if (!list.length) { ElMessage.warning('每行一所：全称,简称,省份,层次'); return }
  const r = await adminImportSchools(list); importDlg.open = false; importDlg.text = ''
  ElMessage.success(`导入 ${r.imported} 所`); loadSchools()
}

/* ---------- 爬取种子 ---------- */
const seeds = ref<CrawlSeed[]>([])
const loadingSeeds = ref(false)
async function loadSeeds() {
  loadingSeeds.value = true
  try { seeds.value = await adminListSeeds() } finally { loadingSeeds.value = false }
}
const seedDlg = reactive({ open: false, form: {} as Partial<CrawlSeed> })
function newSeed() { seedDlg.form = { adapter: 'generic', enabled: 1 }; seedDlg.open = true }
function editSeed(s: CrawlSeed) { seedDlg.form = { ...s }; seedDlg.open = true }
async function saveSeed() {
  if (!seedDlg.form.entryUrl) { ElMessage.warning('填入口页地址'); return }
  await adminSaveSeed(seedDlg.form); seedDlg.open = false; ElMessage.success('存好了'); loadSeeds()
}
async function runSeed(s: CrawlSeed) {
  const r = await adminRunSeed(s.id)
  ElMessage.success(r.job ? '已投递爬取任务' : '已触发（服务未起时稍后重试）'); loadSeeds()
}

/* ---------- 数据维护（候选审核） ---------- */
const candStatus = ref('pending')
const candidates = ref<RuleCandidate[]>([])
const candTotal = ref(0)
const candPage = ref(1)
const loadingCand = ref(false)
async function loadCandidates() {
  loadingCand.value = true
  try {
    const r = await adminListCandidates({ status: candStatus.value, pageNum: candPage.value, pageSize: 20 })
    candidates.value = r.rows; candTotal.value = r.total
  } finally { loadingCand.value = false }
}
const DEG = { bachelor: '本科', master: '硕士', phd: '博士', unknown: '未知' } as Record<string, string>
const mergeDlg = reactive({ open: false, cand: null as RuleCandidate | null, form: {} as any })
function openMerge(c: RuleCandidate) {
  mergeDlg.cand = c
  mergeDlg.form = {
    schoolId: c.schoolId, college: '', degreeType: c.degreeType === 'unknown' ? 'master' : c.degreeType,
    aiRateLimit: c.metric === 'ai_rate' ? c.limitPct : undefined,
    plagiarismLimit: c.metric === 'plagiarism' ? c.limitPct : undefined,
    platform: c.platform, effectiveYear: c.effectiveYear, sourceUrl: c.sourceUrl,
  }
  mergeDlg.open = true
}
async function doMerge() {
  const f = mergeDlg.form
  if (!f.schoolId) { ElMessage.warning('指定学校 id'); return }
  if (!f.sourceUrl) { ElMessage.warning('必须带原文地址'); return }
  await adminMergeCandidate(mergeDlg.cand!.id, f); mergeDlg.open = false
  ElMessage.success('已发布'); loadCandidates()
}
async function reject(c: RuleCandidate) {
  await ElMessageBox.confirm('驳回这条候选？', '确认', { confirmButtonText: '驳回', cancelButtonText: '算了', confirmButtonClass: 'el-button--danger' })
  await adminRejectCandidate(c.id); ElMessage.success('已驳回'); loadCandidates()
}
const syncing = ref(false)
async function syncCandidates() {
  syncing.value = true
  try { const r = await adminSyncCandidates(); ElMessage.success(`拉取入库 ${r.synced} 条`); candPage.value = 1; loadCandidates() }
  finally { syncing.value = false }
}

function onTab() {
  if (tab.value === 'schools' && !schools.value.length) loadSchools()
  if (tab.value === 'seeds' && !seeds.value.length) loadSeeds()
  if (tab.value === 'candidates') loadCandidates()
}
onMounted(loadSchools)
</script>

<template>
  <div class="page">
    <el-tabs v-model="tab" @tab-change="onTab">
      <!-- ============ 学校 ============ -->
      <el-tab-pane label="学校" name="schools">
        <div class="bar">
          <el-input v-model="schoolQ" placeholder="搜全称 / 简称 / 别名" clearable style="width: 280px" @keyup.enter="loadSchools" />
          <el-button @click="loadSchools">搜索</el-button>
          <div class="spacer" />
          <el-button @click="importDlg.open = true">批量导入</el-button>
          <el-button type="primary" @click="newSchool">新增学校</el-button>
        </div>
        <el-card>
          <el-table :data="schools" v-loading="loadingSchools">
            <el-table-column prop="name" label="全称" min-width="200" />
            <el-table-column prop="shortName" label="简称" width="110" />
            <el-table-column prop="province" label="省份" width="90" />
            <el-table-column prop="level" label="层次" width="130" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'hidden' ? 'info' : 'success'">{{ row.status === 'hidden' ? '隐藏' : '启用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button link type="primary" @click="editSchool(row)">编辑</el-button>
                <el-button link @click="toggleSchool(row)">{{ row.status === 'hidden' ? '恢复' : '隐藏' }}</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ============ 爬取种子 ============ -->
      <el-tab-pane label="爬取种子" name="seeds">
        <div class="bar">
          <span class="muted">定时批量每 2~5 天刷新；也可对单校「立即爬取」</span>
          <div class="spacer" />
          <el-button type="primary" @click="newSeed">新增种子</el-button>
        </div>
        <el-card>
          <el-table :data="seeds" v-loading="loadingSeeds">
            <el-table-column prop="schoolId" label="学校 id" width="90" />
            <el-table-column prop="entryUrl" label="入口页" min-width="260" show-overflow-tooltip />
            <el-table-column prop="adapter" label="适配器" width="110" />
            <el-table-column label="启用" width="80">
              <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="lastCrawlAt" label="上次爬取" width="160" />
            <el-table-column prop="lastStatus" label="上次结果" min-width="160" show-overflow-tooltip />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button link type="primary" @click="runSeed(row)">立即爬取</el-button>
                <el-button link @click="editSeed(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ============ 数据维护（候选审核） ============ -->
      <el-tab-pane label="数据维护" name="candidates">
        <div class="bar">
          <el-radio-group v-model="candStatus" @change="() => { candPage = 1; loadCandidates() }">
            <el-radio-button value="pending">待审核</el-radio-button>
            <el-radio-button value="merged">已发布</el-radio-button>
            <el-radio-button value="rejected">已驳回</el-radio-button>
          </el-radio-group>
          <span class="muted">按置信度排序；核对原文后再发布</span>
          <div class="spacer" />
          <el-button :loading="syncing" @click="syncCandidates">拉取爬虫候选</el-button>
        </div>
        <el-card>
          <el-table :data="candidates" v-loading="loadingCand">
            <el-table-column label="学校" min-width="130">
              <template #default="{ row }">{{ row.schoolName || ('#' + (row.schoolId ?? '?')) }}</template>
            </el-table-column>
            <el-table-column label="学位" width="80"><template #default="{ row }">{{ DEG[row.degreeType] || row.degreeType }}</template></el-table-column>
            <el-table-column label="指标" width="90"><template #default="{ row }">{{ row.metric === 'ai_rate' ? 'AI 率' : '查重率' }}</template></el-table-column>
            <el-table-column label="红线" width="80"><template #default="{ row }">{{ row.limitPct }}%</template></el-table-column>
            <el-table-column prop="platform" label="平台" width="90" />
            <el-table-column prop="effectiveYear" label="届别" width="80" />
            <el-table-column label="置信" width="80">
              <template #default="{ row }"><el-tag :type="row.confidence >= 80 ? 'success' : row.confidence >= 50 ? 'warning' : 'info'">{{ row.confidence }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="snippet" label="原文片段" min-width="220" show-overflow-tooltip />
            <el-table-column label="原文" width="70">
              <template #default="{ row }"><a :href="row.sourceUrl" target="_blank" class="src">打开</a></template>
            </el-table-column>
            <el-table-column label="操作" width="150" v-if="candStatus === 'pending'">
              <template #default="{ row }">
                <el-button link type="primary" @click="openMerge(row)">合并发布</el-button>
                <el-button link type="danger" @click="reject(row)">驳回</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pager" v-if="candTotal > 20">
            <el-pagination layout="prev, pager, next" :total="candTotal" :page-size="20" v-model:current-page="candPage" @current-change="loadCandidates" />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 学校编辑 -->
    <el-dialog v-model="schoolDlg.open" :title="schoolDlg.form.id ? '编辑学校' : '新增学校'" width="460px">
      <el-form label-width="72px">
        <el-form-item label="全称"><el-input v-model="schoolDlg.form.name" /></el-form-item>
        <el-form-item label="简称"><el-input v-model="schoolDlg.form.shortName" /></el-form-item>
        <el-form-item label="别名"><el-input v-model="schoolDlg.form.aliases" placeholder='JSON 数组，如 ["北航","BUAA"]' /></el-form-item>
        <el-form-item label="省份"><el-input v-model="schoolDlg.form.province" /></el-form-item>
        <el-form-item label="层次">
          <el-select v-model="schoolDlg.form.level" style="width: 100%">
            <el-option label="本科院校" value="undergrad" />
            <el-option label="高职高专" value="vocational" />
            <el-option label="研究生院" value="graduate_school" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="schoolDlg.open = false">取消</el-button><el-button type="primary" @click="saveSchool">保存</el-button></template>
    </el-dialog>

    <!-- 批量导入 -->
    <el-dialog v-model="importDlg.open" title="批量导入学校（手录 50 所）" width="520px">
      <p class="muted">每行一所：<code>全称,简称,省份,层次</code>；层次填 undergrad / vocational / graduate_school</p>
      <el-input v-model="importDlg.text" type="textarea" :rows="10" placeholder="北京航空航天大学,北航,北京,undergrad" />
      <template #footer><el-button @click="importDlg.open = false">取消</el-button><el-button type="primary" @click="doImport">导入</el-button></template>
    </el-dialog>

    <!-- 种子编辑 -->
    <el-dialog v-model="seedDlg.open" :title="seedDlg.form.id ? '编辑种子' : '新增种子'" width="480px">
      <el-form label-width="84px">
        <el-form-item label="学校 id"><el-input v-model.number="seedDlg.form.schoolId" /></el-form-item>
        <el-form-item label="入口页"><el-input v-model="seedDlg.form.entryUrl" placeholder="研究生院通知列表页" /></el-form-item>
        <el-form-item label="适配器"><el-input v-model="seedDlg.form.adapter" placeholder="generic 或 adapters/ 里的名字" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="seedDlg.form.enabled" :active-value="1" :inactive-value="0" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="seedDlg.form.note" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="seedDlg.open = false">取消</el-button><el-button type="primary" @click="saveSeed">保存</el-button></template>
    </el-dialog>

    <!-- 合并发布 -->
    <el-dialog v-model="mergeDlg.open" title="合并发布为学校红线" width="500px">
      <p class="muted">核对原文后发布；原文地址必填，会随规则留痕。</p>
      <el-form label-width="96px">
        <el-form-item label="学校 id"><el-input v-model.number="mergeDlg.form.schoolId" /></el-form-item>
        <el-form-item label="学院"><el-input v-model="mergeDlg.form.college" placeholder="留空=全校" /></el-form-item>
        <el-form-item label="学位">
          <el-select v-model="mergeDlg.form.degreeType" style="width: 100%">
            <el-option label="本科" value="bachelor" /><el-option label="硕士" value="master" /><el-option label="博士" value="phd" />
          </el-select>
        </el-form-item>
        <el-form-item label="AI 率红线"><el-input v-model.number="mergeDlg.form.aiRateLimit" placeholder="%" /></el-form-item>
        <el-form-item label="查重率红线"><el-input v-model.number="mergeDlg.form.plagiarismLimit" placeholder="%" /></el-form-item>
        <el-form-item label="检测平台"><el-input v-model="mergeDlg.form.platform" placeholder="cnki / vip / wanfang / gezida" /></el-form-item>
        <el-form-item label="届别"><el-input v-model.number="mergeDlg.form.effectiveYear" /></el-form-item>
        <el-form-item label="原文地址"><el-input v-model="mergeDlg.form.sourceUrl" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="mergeDlg.open = false">取消</el-button><el-button type="primary" @click="doMerge">发布</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page { padding: 4px 2px; }
.bar { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.spacer { flex: 1; }
.muted { color: var(--label-secondary); font-size: 13px; }
.pager { display: flex; justify-content: flex-end; margin-top: 14px; }
.src { color: var(--ai-700); font-weight: 600; }
code { background: var(--bg-deep); padding: 1px 6px; border-radius: 6px; }
</style>
