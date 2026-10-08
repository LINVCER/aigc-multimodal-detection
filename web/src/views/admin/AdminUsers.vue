<script setup lang="ts">
import { onMounted, ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listAdminUsers, banUser, unbanUser, type AdminUser, type LoginType, type UserStatus,
  listAccounts, getAccountStats, getAccount, updateAccount, setAccountStatus, batchAccountStatus, resetAccountPassword, setAccountRole, createAccount,
  listAdminTasks, type AdminAccount, type AccountRole, type AccountStats, type AdminTask,
} from '@/api/admin'
import { useAuthStore } from '@/stores/auth'

/**
 * 用户管理
 *   平台账号（auth_user）：KPI · 筛选排序 · 多选批量 · 表格 · 详情抽屉（资料编辑 / 角色 / 状态 / 重置密码 / 最近检测）· 导出 CSV
 *   用户画像（user_profile）：原 §3.2 demo，退为次 tab
 */
const auth = useAuthStore()
const router = useRouter()
const tab = ref<'account' | 'profile'>('account')

const ROLE_LABEL: Record<AccountRole, string> = { USER: '普通用户', ADMIN: '管理员', OPS_ADMIN: '运营管理员' }
const ROLE_TAG: Record<AccountRole, '' | 'warning' | 'danger'> = { USER: '', ADMIN: 'warning', OPS_ADMIN: 'danger' }
const isSelf = (a: AdminAccount) => auth.user?.id === a.id

/* ---------- 工具 ---------- */
function relTime(s?: string | null) {
  if (!s) return '从未'
  const t = Date.parse(String(s).replace(' ', 'T'))
  if (Number.isNaN(t)) return s
  const d = Date.now() - t
  const m = Math.floor(d / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  const day = Math.floor(h / 24)
  if (day < 30) return `${day} 天前`
  return String(s).slice(0, 10)
}
const fmt = (s?: string | null) => (s ? String(s).replace('T', ' ').slice(0, 16) : '—')
const initial = (a: AdminAccount) => (a.realName || a.username || '?').charAt(0).toUpperCase()
const AVATAR_COLORS = ['#007AFF', '#5856D6', '#AF52DE', '#FF2D55', '#FF9500', '#34C759', '#5AC8FA', '#0D9488']
const avatarColor = (a: AdminAccount) => AVATAR_COLORS[a.id % AVATAR_COLORS.length]

/* ---------- KPI ---------- */
const stats = ref<AccountStats | null>(null)
async function loadStats() { try { stats.value = await getAccountStats() } catch { stats.value = null } }

/* ---------- 列表 ---------- */
const af = reactive<{ keyword: string; role: AccountRole | ''; status: 0 | 1 | ''; sortBy: string; sortOrder: 'asc' | 'desc' }>({ keyword: '', role: '', status: '', sortBy: '', sortOrder: 'desc' })
const aRows = ref<AdminAccount[]>([])
const aTotal = ref(0)
const aPage = ref(1)
const aSize = ref(20)
const aLoading = ref(false)
const selected = ref<AdminAccount[]>([])

async function loadAccounts() {
  aLoading.value = true
  try {
    const resp = await listAccounts({
      keyword: af.keyword || undefined, role: af.role || undefined, status: af.status === '' ? undefined : af.status,
      sortBy: af.sortBy || undefined, sortOrder: af.sortOrder, pageNum: aPage.value, pageSize: aSize.value,
    })
    aRows.value = resp.rows
    aTotal.value = resp.total
  } finally { aLoading.value = false }
}
function searchAccounts() { aPage.value = 1; loadAccounts() }
function resetAccounts() { Object.assign(af, { keyword: '', role: '', status: '', sortBy: '', sortOrder: 'desc' }); searchAccounts() }
function onSortChange({ prop, order }: { prop: string; order: 'ascending' | 'descending' | null }) {
  af.sortBy = order ? prop : ''
  af.sortOrder = order === 'ascending' ? 'asc' : 'desc'
  loadAccounts()
}
function quickFilter(status: 0 | 1 | '') { af.status = status; af.role = ''; searchAccounts() }
function refreshAll() { loadStats(); loadAccounts() }

/* ---------- 单个操作 ---------- */
async function onToggleStatus(a: AdminAccount) {
  const next = a.status === 1 ? 0 : 1
  if (next === 0) {
    try { await ElMessageBox.confirm(`停用后 ${a.username} 将立即被踢下线且无法登录。`, '停用账号', { type: 'warning', confirmButtonText: '停用', confirmButtonClass: 'el-button--danger' }) } catch { return }
  }
  await setAccountStatus(a.id, next)
  ElMessage.success(next === 0 ? '已停用' : '已启用')
  if (drawer.account?.id === a.id) drawer.account.status = next
  refreshAll()
}

const tempPwd = ref<{ open: boolean; username: string; password: string; created: boolean }>({ open: false, username: '', password: '', created: false })
async function onResetPassword(a: AdminAccount) {
  try { await ElMessageBox.confirm(`将为 ${a.username} 生成新的临时密码，旧密码立即失效并踢下线。`, '重置密码', { type: 'warning', confirmButtonText: '重置' }) } catch { return }
  const r = await resetAccountPassword(a.id)
  tempPwd.value = { open: true, username: a.username, password: r.tempPassword, created: false }
}
async function copyTemp() {
  try { await navigator.clipboard.writeText(`账号 ${tempPwd.value.username}  临时密码 ${tempPwd.value.password}`); ElMessage.success('已复制') } catch { ElMessage.warning('复制失败，请手动选择') }
}

async function onChangeRole(a: AdminAccount, role: AccountRole) {
  if (role === a.role) return
  try {
    await ElMessageBox.confirm(`把 ${a.username} 的角色改为「${ROLE_LABEL[role]}」？对方需重新登录生效。`, '修改角色', { type: 'warning' })
    await setAccountRole(a.id, role)
    ElMessage.success('角色已更新')
    if (drawer.account?.id === a.id) drawer.account.role = role
  } catch { /* 取消或失败 */ }
  refreshAll()
}

/* ---------- 批量 ---------- */
const batchable = computed(() => selected.value.filter((a) => !isSelf(a)))
async function onBatch(status: 0 | 1) {
  const ids = batchable.value.filter((a) => a.status !== status).map((a) => a.id)
  if (!ids.length) { ElMessage.info('所选账号无需变更'); return }
  try {
    await ElMessageBox.confirm(`${status === 0 ? '停用' : '启用'} ${ids.length} 个账号？${status === 0 ? '停用后立即踢下线。' : ''}`, '批量操作', { type: 'warning', confirmButtonClass: status === 0 ? 'el-button--danger' : '' })
  } catch { return }
  const r = await batchAccountStatus(ids, status)
  ElMessage.success(`已更新 ${r.updated} 个账号`)
  selected.value = []
  refreshAll()
}

/* ---------- 导出 ---------- */
function exportCsv() {
  if (!aRows.value.length) { ElMessage.info('当前没有数据'); return }
  const head = ['ID', '用户名', '姓名', '组织', '角色', '状态', '检测数', '最近检测', '最近登录', '创建时间']
  const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const lines = aRows.value.map((a) => [a.id, a.username, a.realName, a.orgName, ROLE_LABEL[a.role] || a.role, a.status === 1 ? '正常' : '已停用', a.detectCount, fmt(a.lastDetectAt), fmt(a.lastLoginAt), fmt(a.createdAt)].map(esc).join(','))
  const blob = new Blob(['﻿' + [head.map(esc).join(','), ...lines].join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `accounts-${new Date().toISOString().slice(0, 10)}.csv`; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/* ---------- 新建 ---------- */
const createOpen = ref(false)
const createForm = reactive<{ username: string; realName: string; role: AccountRole; orgName: string }>({ username: '', realName: '', role: 'USER', orgName: '' })
const createError = computed(() => {
  if (!createForm.username.trim()) return '请输入用户名'
  if (!/^[A-Za-z0-9_.@-]{2,64}$/.test(createForm.username.trim())) return '用户名只能包含字母、数字、_ . @ -，2-64 位'
  return ''
})
async function submitCreate() {
  if (createError.value) { ElMessage.warning(createError.value); return }
  const r = await createAccount({ username: createForm.username.trim(), realName: createForm.realName.trim() || undefined, role: createForm.role, orgName: createForm.orgName.trim() || undefined })
  createOpen.value = false
  tempPwd.value = { open: true, username: createForm.username.trim(), password: r.tempPassword, created: true }
  Object.assign(createForm, { username: '', realName: '', role: 'USER', orgName: '' })
  refreshAll()
}

/* ---------- 详情抽屉 ---------- */
const drawer = reactive<{ open: boolean; loading: boolean; account: AdminAccount | null; tasks: AdminTask[]; taskTotal: number; editing: boolean; form: { realName: string; orgName: string }; saving: boolean }>({
  open: false, loading: false, account: null, tasks: [], taskTotal: 0, editing: false, form: { realName: '', orgName: '' }, saving: false,
})
async function openDetail(a: AdminAccount) {
  drawer.open = true
  drawer.loading = true
  drawer.editing = false
  drawer.account = a
  try {
    const [acc, tasks] = await Promise.all([getAccount(a.id), listAdminTasks({ userId: a.id, pageSize: 8 })])
    drawer.account = acc
    drawer.tasks = tasks.rows
    drawer.taskTotal = tasks.total
  } catch { drawer.tasks = []; drawer.taskTotal = 0 } finally { drawer.loading = false }
}
function startEdit() {
  if (!drawer.account) return
  drawer.form = { realName: drawer.account.realName || '', orgName: drawer.account.orgName || '' }
  drawer.editing = true
}
async function saveEdit() {
  if (!drawer.account) return
  drawer.saving = true
  try {
    await updateAccount(drawer.account.id, { realName: drawer.form.realName.trim(), orgName: drawer.form.orgName.trim() })
    drawer.account.realName = drawer.form.realName.trim()
    drawer.account.orgName = drawer.form.orgName.trim() || null
    drawer.editing = false
    ElMessage.success('已保存')
    loadAccounts()
  } finally { drawer.saving = false }
}
const taskStatus: Record<string, { t: string; type: 'success' | 'warning' | 'danger' | 'info' }> = { DONE: { t: '完成', type: 'success' }, RUNNING: { t: '检测中', type: 'warning' }, PENDING: { t: '排队', type: 'info' }, FAILED: { t: '失败', type: 'danger' } }

/* ---------- 用户画像（demo） ---------- */
const filter = reactive<{ loginType: LoginType | ''; status: UserStatus | ''; keyword: string; minDetect?: number; maxDetect?: number }>({ loginType: '', status: '', keyword: '' })
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(20)
const rows = ref<AdminUser[]>([])
const loading = ref(false)
const LOGIN_LABEL: Record<LoginType, string> = { phone: '📱 手机', wechat: '💚 微信', email: '📧 邮箱' }
const STATUS_TAG: Record<UserStatus, { text: string; type: 'success' | 'danger' | 'warning' | 'info' }> = {
  NORMAL: { text: '正常', type: 'success' }, BANNED: { text: '已封禁', type: 'danger' }, INACTIVE: { text: '未激活', type: 'info' }, SUSPICIOUS: { text: '可疑', type: 'warning' },
}
async function load() {
  loading.value = true
  try { const resp = await listAdminUsers({ ...filter, pageNum: pageNum.value, pageSize: pageSize.value }); rows.value = resp.rows; total.value = resp.total } finally { loading.value = false }
}
function search() { pageNum.value = 1; load() }
function reset() { Object.assign(filter, { loginType: '', status: '', keyword: '', minDetect: undefined, maxDetect: undefined }); search() }
async function onBan(u: AdminUser) { await ElMessageBox.confirm(`确定封禁用户 ${u.identity}？`, '封禁确认', { type: 'warning' }); await banUser(u.id); ElMessage.success('已封禁'); load() }
async function onUnban(u: AdminUser) { await unbanUser(u.id); ElMessage.success('已解封'); load() }

onMounted(() => { refreshAll(); load() })
</script>

<template>
  <div class="page-head">
    <div>
      <div class="page-title">用户管理</div>
      <div class="page-sub">平台账号的登录凭据、角色与状态；用户画像为运营侧 demo 数据</div>
    </div>
    <el-radio-group v-model="tab" size="default">
      <el-radio-button value="account">平台账号</el-radio-button>
      <el-radio-button value="profile">用户画像</el-radio-button>
    </el-radio-group>
  </div>

  <!-- ================= 平台账号 ================= -->
  <template v-if="tab === 'account'">
    <div class="kpi-row">
      <el-card class="kpi" :class="{ on: af.status === '' }" body-style="padding: 16px 18px" @click="quickFilter('')"><div class="kpi-label">账号总数</div><div class="kpi-value">{{ stats?.total ?? '—' }}</div><div class="kpi-foot" v-if="stats">{{ ROLE_LABEL.USER }} {{ stats.byRole.USER || 0 }} · {{ ROLE_LABEL.ADMIN }} {{ stats.byRole.ADMIN || 0 }} · {{ ROLE_LABEL.OPS_ADMIN }} {{ stats.byRole.OPS_ADMIN || 0 }}</div></el-card>
      <el-card class="kpi" :class="{ on: af.status === 1 }" body-style="padding: 16px 18px" @click="quickFilter(1)"><div class="kpi-label">正常</div><div class="kpi-value ok">{{ stats?.active ?? '—' }}</div><div class="kpi-foot">点击筛选</div></el-card>
      <el-card class="kpi" :class="{ on: af.status === 0 }" body-style="padding: 16px 18px" @click="quickFilter(0)"><div class="kpi-label">已停用</div><div class="kpi-value" :class="{ bad: (stats?.disabled || 0) > 0 }">{{ stats?.disabled ?? '—' }}</div><div class="kpi-foot">点击筛选</div></el-card>
      <el-card class="kpi static" body-style="padding: 16px 18px"><div class="kpi-label">今日新增</div><div class="kpi-value">{{ stats?.todayNew ?? '—' }}</div><div class="kpi-foot">含注册与管理员新建</div></el-card>
      <el-card class="kpi static" body-style="padding: 16px 18px"><div class="kpi-label">7 日活跃</div><div class="kpi-value">{{ stats?.active7d ?? '—' }}</div><div class="kpi-foot" v-if="stats && stats.total">占 {{ Math.round((stats.active7d / stats.total) * 100) }}%</div></el-card>
    </div>

    <el-card class="filter-card" body-style="padding: 14px 18px">
      <div class="filter-row">
        <el-input v-model="af.keyword" placeholder="搜索用户名 / 姓名 / 组织" clearable prefix-icon="Search" style="width: 260px" @keyup.enter="searchAccounts" @clear="searchAccounts" />
        <el-select v-model="af.role" placeholder="全部角色" clearable style="width: 140px" @change="searchAccounts">
          <el-option v-for="(label, k) in ROLE_LABEL" :key="k" :label="label" :value="k" />
        </el-select>
        <el-select v-model="af.status" placeholder="全部状态" clearable style="width: 120px" @change="searchAccounts">
          <el-option label="正常" :value="1" /><el-option label="已停用" :value="0" />
        </el-select>
        <el-button @click="resetAccounts">重置</el-button>
        <span class="flex-1" />
        <el-button :disabled="!aRows.length" @click="exportCsv">导出 CSV</el-button>
        <el-button type="primary" @click="createOpen = true">＋ 新建账号</el-button>
      </div>
      <transition name="fade">
        <div v-if="selected.length" class="batch-bar">
          <span>已选 {{ selected.length }} 个<template v-if="selected.length !== batchable.length">（不含自己）</template></span>
          <el-button size="small" type="success" plain @click="onBatch(1)">批量启用</el-button>
          <el-button size="small" type="danger" plain @click="onBatch(0)">批量停用</el-button>
          <el-button size="small" link @click="selected = []">取消选择</el-button>
        </div>
      </transition>
    </el-card>

    <el-card class="table-card" body-style="padding: 0">
      <el-table v-loading="aLoading" :data="aRows" row-key="id" @selection-change="(v: AdminAccount[]) => (selected = v)" @sort-change="onSortChange">
        <template #empty>
          <div class="empty"><div class="empty-title">没有符合条件的账号</div><div class="empty-sub">换个筛选条件，或点右上角新建账号</div></div>
        </template>
        <el-table-column type="selection" width="44" :selectable="(row: AdminAccount) => !isSelf(row)" />
        <el-table-column label="账号" min-width="240" prop="username" sortable="custom">
          <template #default="{ row }">
            <div class="who" @click="openDetail(row)">
              <span class="avatar" :style="{ background: avatarColor(row) }">{{ initial(row) }}</span>
              <div class="who-main">
                <div class="who-name">{{ row.realName || row.username }}<el-tag v-if="isSelf(row)" size="small" effect="plain" class="self-tag">我</el-tag></div>
                <div class="who-sub">{{ row.username }}<template v-if="row.orgName"> · {{ row.orgName }}</template></div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="150">
          <template #default="{ row }">
            <el-select :model-value="row.role" size="small" :disabled="isSelf(row)" style="width: 124px" @change="(v: AccountRole) => onChangeRole(row, v)">
              <el-option v-for="(label, k) in ROLE_LABEL" :key="k" :label="label" :value="k" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="检测" width="110" align="right">
          <template #default="{ row }">
            <a class="num" :class="{ zero: !row.detectCount }" @click="openDetail(row)">{{ row.detectCount || 0 }}</a>
            <div class="cell-sub" v-if="row.lastDetectAt">{{ relTime(row.lastDetectAt) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" width="150" prop="lastLoginAt" sortable="custom">
          <template #default="{ row }"><el-tooltip :content="fmt(row.lastLoginAt)" placement="top" :disabled="!row.lastLoginAt"><span :class="{ muted: !row.lastLoginAt }">{{ relTime(row.lastLoginAt) }}</span></el-tooltip></template>
        </el-table-column>
        <el-table-column label="创建时间" width="150" prop="createdAt" sortable="custom">
          <template #default="{ row }"><span class="muted">{{ fmt(row.createdAt) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-switch :model-value="row.status === 1" :disabled="isSelf(row)" inline-prompt active-text="正常" inactive-text="停用" style="--el-switch-on-color: var(--el-color-success)" @change="onToggleStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button size="small" link @click="onResetPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager-row">
        <span class="muted small">共 {{ aTotal }} 个账号</span>
        <el-pagination v-model:current-page="aPage" v-model:page-size="aSize" :total="aTotal" :page-sizes="[10, 20, 50, 100]" layout="sizes, prev, pager, next" @size-change="loadAccounts" @current-change="loadAccounts" />
      </div>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawer.open" size="460px" :with-header="false" destroy-on-close>
      <div v-if="drawer.account" class="dr">
        <div class="dr-head">
          <span class="avatar lg" :style="{ background: avatarColor(drawer.account) }">{{ initial(drawer.account) }}</span>
          <div class="dr-title">
            <div class="dr-name">{{ drawer.account.realName || drawer.account.username }}</div>
            <div class="dr-sub">{{ drawer.account.username }} · #{{ drawer.account.id }}</div>
          </div>
          <el-tag :type="drawer.account.status === 1 ? 'success' : 'danger'" effect="light">{{ drawer.account.status === 1 ? '正常' : '已停用' }}</el-tag>
        </div>

        <div class="dr-sec">
          <div class="dr-sec-head"><span>资料</span><el-button v-if="!drawer.editing" link type="primary" size="small" @click="startEdit">编辑</el-button></div>
          <template v-if="drawer.editing">
            <el-form label-position="top" size="default" @submit.prevent="saveEdit">
              <el-form-item label="姓名"><el-input v-model="drawer.form.realName" maxlength="64" /></el-form-item>
              <el-form-item label="组织 / 学校"><el-input v-model="drawer.form.orgName" maxlength="128" /></el-form-item>
              <div class="dr-edit-actions"><el-button size="small" @click="drawer.editing = false">取消</el-button><el-button size="small" type="primary" :loading="drawer.saving" @click="saveEdit">保存</el-button></div>
            </el-form>
          </template>
          <dl v-else class="kv">
            <dt>姓名</dt><dd>{{ drawer.account.realName || '—' }}</dd>
            <dt>组织</dt><dd>{{ drawer.account.orgName || '—' }}</dd>
            <dt>角色</dt><dd><el-tag size="small" :type="ROLE_TAG[drawer.account.role] || 'info'" effect="plain">{{ ROLE_LABEL[drawer.account.role] || drawer.account.role }}</el-tag></dd>
            <dt>创建</dt><dd>{{ fmt(drawer.account.createdAt) }}</dd>
            <dt>最近登录</dt><dd>{{ fmt(drawer.account.lastLoginAt) }} <span class="muted small">{{ relTime(drawer.account.lastLoginAt) }}</span></dd>
            <dt>累计检测</dt><dd>{{ drawer.account.detectCount || 0 }} 次<span v-if="drawer.account.lastDetectAt" class="muted small"> · 最近 {{ relTime(drawer.account.lastDetectAt) }}</span></dd>
          </dl>
        </div>

        <div class="dr-sec">
          <div class="dr-sec-head"><span>操作</span></div>
          <div class="dr-actions">
            <el-select :model-value="drawer.account.role" size="default" :disabled="isSelf(drawer.account)" style="width: 150px" @change="(v: AccountRole) => onChangeRole(drawer.account!, v)">
              <el-option v-for="(label, k) in ROLE_LABEL" :key="k" :label="label" :value="k" />
            </el-select>
            <el-button @click="onResetPassword(drawer.account)">重置密码</el-button>
            <el-button v-if="drawer.account.status === 1" type="danger" plain :disabled="isSelf(drawer.account)" @click="onToggleStatus(drawer.account)">停用账号</el-button>
            <el-button v-else type="success" plain @click="onToggleStatus(drawer.account)">启用账号</el-button>
          </div>
          <div class="muted small" style="margin-top: 8px">停用、重置密码、改角色都会让对方所有设备下线。</div>
        </div>

        <div class="dr-sec">
          <div class="dr-sec-head"><span>最近检测</span><span class="muted small">{{ drawer.taskTotal }} 条</span></div>
          <div v-if="drawer.loading" class="muted small">加载中…</div>
          <div v-else-if="!drawer.tasks.length" class="muted small">还没有检测记录</div>
          <div v-for="t in drawer.tasks" :key="t.id" class="task" @click="router.push(`/task/${t.id}`)">
            <div class="task-main">
              <div class="task-title">{{ t.paperTitle || '未命名' }}</div>
              <div class="task-sub">{{ fmt(t.createdAt) }} · 红线 {{ t.threshold }}%</div>
            </div>
            <b v-if="t.aiRate != null" class="task-rate" :class="t.aiRate <= t.threshold ? 'ok' : 'bad'">{{ t.aiRate.toFixed(1) }}%</b>
            <el-tag v-else size="small" :type="taskStatus[t.status]?.type || 'info'">{{ taskStatus[t.status]?.t || t.status }}</el-tag>
          </div>
          <el-button v-if="drawer.taskTotal > drawer.tasks.length" link type="primary" size="small" @click="router.push({ path: '/admin/tasks', query: { userId: drawer.account.id } })">查看全部 {{ drawer.taskTotal }} 条 ›</el-button>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="createOpen" title="新建账号" width="440" align-center destroy-on-close>
      <el-form label-position="top" @submit.prevent="submitCreate">
        <el-form-item label="用户名（学号 / 工号 / 邮箱）"><el-input v-model="createForm.username" placeholder="2-64 位，字母数字和 _ . @ -" /></el-form-item>
        <el-form-item label="姓名（可选）"><el-input v-model="createForm.realName" /></el-form-item>
        <el-form-item label="角色"><el-select v-model="createForm.role" style="width: 100%"><el-option v-for="(label, k) in ROLE_LABEL" :key="k" :label="label" :value="k" /></el-select></el-form-item>
        <el-form-item label="组织 / 学校（可选）"><el-input v-model="createForm.orgName" /></el-form-item>
        <div class="hint">密码由系统生成临时密码，创建后只显示一次，请复制给用户并提醒登录后修改。</div>
      </el-form>
      <template #footer>
        <el-button round @click="createOpen = false">取消</el-button>
        <el-button type="primary" round :disabled="!!createError" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tempPwd.open" :title="tempPwd.created ? '账号已创建' : '密码已重置'" width="420" align-center>
      <div class="temp">
        <div class="temp-row"><span class="muted">账号</span><b>{{ tempPwd.username }}</b></div>
        <div class="temp-row"><span class="muted">临时密码</span><code class="temp-pwd">{{ tempPwd.password }}</code></div>
        <div class="hint">只显示这一次。请通过安全渠道告知用户，并提醒其登录后在「我的 → 修改密码」里改掉。</div>
      </div>
      <template #footer>
        <el-button round @click="tempPwd.open = false">关闭</el-button>
        <el-button type="primary" round @click="copyTemp">复制账号与密码</el-button>
      </template>
    </el-dialog>
  </template>

  <!-- ================= 用户画像（demo） ================= -->
  <template v-else>
    <el-alert type="info" :closable="false" show-icon class="demo-alert" title="用户画像来自 user_profile 示例数据，封禁只影响画像状态，不影响登录；账号停用请到「平台账号」。" />
    <el-card class="filter-card" body-style="padding: 14px 18px">
      <div class="filter-row">
        <el-select v-model="filter.loginType" placeholder="登录方式" clearable style="width: 130px"><el-option label="手机" value="phone" /><el-option label="微信" value="wechat" /><el-option label="邮箱" value="email" /></el-select>
        <el-select v-model="filter.status" placeholder="状态" clearable style="width: 130px"><el-option label="正常" value="NORMAL" /><el-option label="可疑" value="SUSPICIOUS" /><el-option label="已封禁" value="BANNED" /><el-option label="未激活" value="INACTIVE" /></el-select>
        <el-input v-model="filter.keyword" placeholder="账号 / 用户 ID" clearable style="width: 220px" @keyup.enter="search" />
        <el-input-number v-model="filter.minDetect" placeholder="检测数 ≥" :min="0" :controls="false" style="width: 130px" />
        <el-input-number v-model="filter.maxDetect" placeholder="检测数 ≤" :min="0" :controls="false" style="width: 130px" />
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
    </el-card>
    <el-card class="table-card" body-style="padding: 0">
      <el-table v-loading="loading" :data="rows" empty-text="暂无用户">
        <el-table-column prop="id" label="用户 ID" width="100" />
        <el-table-column label="登录方式" width="110"><template #default="{ row }">{{ LOGIN_LABEL[row.loginType as LoginType] || row.loginType }}</template></el-table-column>
        <el-table-column prop="identity" label="账号（脱敏）" min-width="160" />
        <el-table-column prop="detectCount" label="累计检测数" width="110" align="right" />
        <el-table-column prop="lastLoginAt" label="最近登录" width="170" />
        <el-table-column prop="registeredAt" label="注册时间" width="170" />
        <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="STATUS_TAG[row.status as UserStatus]?.type" size="small">{{ STATUS_TAG[row.status as UserStatus]?.text || row.status }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status !== 'BANNED'" size="small" type="danger" link @click="onBan(row)">封禁</el-button>
            <el-button v-else size="small" type="primary" link @click="onUnban(row)">解封</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager-row"><span class="muted small">共 {{ total }} 人</span><el-pagination v-model:current-page="pageNum" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="sizes, prev, pager, next" @size-change="load" @current-change="load" /></div>
    </el-card>
  </template>
</template>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.page-title { font-size: 22px; font-weight: 700; letter-spacing: -0.4px; }
.page-sub { font-size: 13px; color: var(--label-secondary); margin-top: 4px; }

.kpi-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 14px; }
.kpi { cursor: pointer; border: 1px solid transparent; transition: border-color .15s, transform .15s; }
.kpi:hover:not(.static) { transform: translateY(-1px); }
.kpi.on { border-color: var(--system-blue); }
.kpi.static { cursor: default; }
.kpi-label { font-size: 12px; color: var(--label-secondary); }
.kpi-value { font-size: 28px; font-weight: 700; letter-spacing: -0.6px; margin-top: 4px; font-variant-numeric: tabular-nums; }
.kpi-value.ok { color: #1B7F3E; } .kpi-value.bad { color: #C62A22; }
.kpi-foot { font-size: 11px; color: var(--label-tertiary); margin-top: 6px; min-height: 14px; }

.filter-card { margin-bottom: 12px; }
.filter-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.flex-1 { flex: 1; }
.batch-bar { display: flex; align-items: center; gap: 10px; margin-top: 12px; padding: 8px 12px; border-radius: 10px; background: rgba(0, 122, 255, 0.07); font-size: 13px; }
.fade-enter-active, .fade-leave-active { transition: opacity .15s; } .fade-enter-from, .fade-leave-to { opacity: 0; }

.table-card :deep(.el-table) { --el-table-header-bg-color: #FAFBFC; }
.who { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.avatar { width: 34px; height: 34px; border-radius: 50%; color: #fff; font-weight: 600; display: inline-flex; align-items: center; justify-content: center; flex: none; font-size: 14px; }
.avatar.lg { width: 48px; height: 48px; font-size: 20px; }
.who-main { min-width: 0; }
.who-name { font-weight: 600; display: flex; align-items: center; gap: 6px; }
.who-sub { font-size: 12px; color: var(--label-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.self-tag { height: 18px; line-height: 16px; padding: 0 5px; }
.num { font-weight: 600; cursor: pointer; color: var(--system-blue); font-variant-numeric: tabular-nums; } .num.zero { color: var(--label-tertiary); font-weight: 400; }
.cell-sub { font-size: 11px; color: var(--label-tertiary); }
.muted { color: var(--label-secondary); } .small { font-size: 12px; }
.empty { padding: 36px 0; } .empty-title { font-weight: 600; color: var(--label); } .empty-sub { font-size: 12px; color: var(--label-tertiary); margin-top: 4px; }
.pager-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; }

.dr { display: flex; flex-direction: column; gap: 20px; }
.dr-head { display: flex; align-items: center; gap: 14px; }
.dr-title { flex: 1; min-width: 0; }
.dr-name { font-size: 18px; font-weight: 700; }
.dr-sub { font-size: 12px; color: var(--label-secondary); }
.dr-sec { padding-top: 16px; border-top: 1px solid var(--label-quaternary); }
.dr-sec-head { display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-weight: 600; color: var(--label-secondary); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 10px; }
.kv { display: grid; grid-template-columns: 72px 1fr; gap: 8px 12px; margin: 0; font-size: 14px; }
.kv dt { color: var(--label-secondary); } .kv dd { margin: 0; }
.dr-edit-actions { display: flex; justify-content: flex-end; gap: 8px; }
.dr-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.task { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--label-quaternary); cursor: pointer; } .task:last-of-type { border-bottom: none; }
.task:hover .task-title { color: var(--system-blue); }
.task-main { flex: 1; min-width: 0; }
.task-title { font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-sub { font-size: 12px; color: var(--label-tertiary); }
.task-rate { font-variant-numeric: tabular-nums; } .task-rate.ok { color: #1B7F3E; } .task-rate.bad { color: #C62A22; }

.hint { font-size: 12px; color: var(--label-tertiary); line-height: 1.6; }
.temp { display: flex; flex-direction: column; gap: 10px; }
.temp-row { display: flex; align-items: center; gap: 12px; }
.temp-pwd { font-size: 20px; letter-spacing: 1px; padding: 4px 10px; border-radius: 8px; background: rgba(120, 120, 128, 0.12); user-select: all; }
.demo-alert { margin-bottom: 12px; }
@media (max-width: 1100px) { .kpi-row { grid-template-columns: repeat(3, 1fr); } }
</style>
