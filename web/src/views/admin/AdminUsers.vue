<script setup lang="ts">
import { onMounted, ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listAdminUsers, banUser, unbanUser, type AdminUser, type LoginType, type UserStatus,
  listAccounts, setAccountStatus, resetAccountPassword, setAccountRole, createAccount, type AdminAccount, type AccountRole,
} from '@/api/admin'
import { useAuthStore } from '@/stores/auth'

/**
 * 用户管理：两个 tab
 *   平台账号（auth_user）：停用 / 启用、重置密码、改角色、新建 —— 真实登录凭据
 *   用户画像（user_profile）：检测数 / 封禁 —— 原 §3.2 demo 画像
 */
const auth = useAuthStore()
const tab = ref<'account' | 'profile'>('account')

/* ================= 平台账号 ================= */
const ROLE_LABEL: Record<AccountRole, string> = { USER: '普通用户', ADMIN: '管理员', OPS_ADMIN: '运营管理员' }

const af = reactive<{ keyword: string; role: AccountRole | ''; status: 0 | 1 | '' }>({ keyword: '', role: '', status: '' })
const aRows = ref<AdminAccount[]>([])
const aTotal = ref(0)
const aPage = ref(1)
const aSize = ref(20)
const aLoading = ref(false)

async function loadAccounts() {
  aLoading.value = true
  try {
    const resp = await listAccounts({ keyword: af.keyword || undefined, role: af.role || undefined, status: af.status === '' ? undefined : af.status, pageNum: aPage.value, pageSize: aSize.value })
    aRows.value = resp.rows
    aTotal.value = resp.total
  } finally { aLoading.value = false }
}
function searchAccounts() { aPage.value = 1; loadAccounts() }
function resetAccounts() { Object.assign(af, { keyword: '', role: '', status: '' }); searchAccounts() }

const isSelf = (a: AdminAccount) => auth.user?.id === a.id

async function onToggleStatus(a: AdminAccount) {
  const next = a.status === 1 ? 0 : 1
  if (next === 0) {
    await ElMessageBox.confirm(`停用后 ${a.username} 将立即被踢下线且无法登录，确定？`, '停用账号', { type: 'warning', confirmButtonText: '停用', confirmButtonClass: 'el-button--danger' })
  }
  await setAccountStatus(a.id, next)
  ElMessage.success(next === 0 ? '已停用' : '已启用')
  loadAccounts()
}

const tempPwd = ref<{ open: boolean; username: string; password: string; created: boolean }>({ open: false, username: '', password: '', created: false })
async function onResetPassword(a: AdminAccount) {
  await ElMessageBox.confirm(`将为 ${a.username} 生成新的临时密码，旧密码立即失效并踢下线。`, '重置密码', { type: 'warning', confirmButtonText: '重置' })
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
  } catch { /* 取消或失败 */ }
  loadAccounts()
}

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
  loadAccounts()
}

/* ================= 用户画像（demo） ================= */
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
  try {
    const resp = await listAdminUsers({ ...filter, pageNum: pageNum.value, pageSize: pageSize.value })
    rows.value = resp.rows
    total.value = resp.total
  } finally { loading.value = false }
}
function search() { pageNum.value = 1; load() }
function reset() { Object.assign(filter, { loginType: '', status: '', keyword: '', minDetect: undefined, maxDetect: undefined }); search() }
async function onBan(u: AdminUser) {
  await ElMessageBox.confirm(`确定封禁用户 ${u.identity}？`, '封禁确认', { type: 'warning' })
  await banUser(u.id); ElMessage.success('已封禁'); load()
}
async function onUnban(u: AdminUser) { await unbanUser(u.id); ElMessage.success('已解封'); load() }

onMounted(() => { loadAccounts(); load() })
</script>

<template>
  <el-tabs v-model="tab" class="tabs">
    <el-tab-pane label="平台账号" name="account" />
    <el-tab-pane label="用户画像" name="profile" />
  </el-tabs>

  <!-- ================= 平台账号 ================= -->
  <template v-if="tab === 'account'">
    <el-card class="filter-card">
      <div class="filter-row">
        <el-input v-model="af.keyword" placeholder="用户名 / 姓名 / 组织" clearable style="width: 240px" @keyup.enter="searchAccounts" />
        <el-select v-model="af.role" placeholder="角色" clearable style="width: 140px">
          <el-option label="普通用户" value="USER" /><el-option label="管理员" value="ADMIN" /><el-option label="运营管理员" value="OPS_ADMIN" />
        </el-select>
        <el-select v-model="af.status" placeholder="状态" clearable style="width: 120px">
          <el-option label="正常" :value="1" /><el-option label="已停用" :value="0" />
        </el-select>
        <el-button type="primary" @click="searchAccounts">查询</el-button>
        <el-button @click="resetAccounts">重置</el-button>
        <span class="flex-1" />
        <el-button type="primary" plain @click="createOpen = true">＋ 新建账号</el-button>
      </div>
    </el-card>

    <el-card class="table-card">
      <el-table v-loading="aLoading" :data="aRows" empty-text="暂无账号">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="160">
          <template #default="{ row }"><b>{{ row.username }}</b><el-tag v-if="isSelf(row)" size="small" class="self-tag">我</el-tag></template>
        </el-table-column>
        <el-table-column prop="realName" label="姓名" width="120" />
        <el-table-column prop="orgName" label="组织" min-width="140" show-overflow-tooltip />
        <el-table-column label="角色" width="150">
          <template #default="{ row }">
            <el-select :model-value="row.role" size="small" :disabled="isSelf(row)" style="width: 120px" @change="(v: AccountRole) => onChangeRole(row, v)">
              <el-option v-for="(label, k) in ROLE_LABEL" :key="k" :label="label" :value="k" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">{{ row.status === 1 ? '正常' : '已停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="lastLoginAt" label="最近登录" width="170"><template #default="{ row }">{{ row.lastLoginAt || '—' }}</template></el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="170" />
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="onResetPassword(row)">重置密码</el-button>
            <el-button v-if="row.status === 1" size="small" link type="danger" :disabled="isSelf(row)" @click="onToggleStatus(row)">停用</el-button>
            <el-button v-else size="small" link type="success" @click="onToggleStatus(row)">启用</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pager" v-model:current-page="aPage" v-model:page-size="aSize" :total="aTotal" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="loadAccounts" @current-change="loadAccounts" />
    </el-card>

    <el-dialog v-model="createOpen" title="新建账号" width="440" align-center destroy-on-close>
      <el-form label-position="top" @submit.prevent="submitCreate">
        <el-form-item label="用户名（学号 / 工号 / 邮箱）"><el-input v-model="createForm.username" placeholder="2-64 位，字母数字和 _ . @ -" /></el-form-item>
        <el-form-item label="姓名（可选）"><el-input v-model="createForm.realName" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role" style="width: 100%"><el-option v-for="(label, k) in ROLE_LABEL" :key="k" :label="label" :value="k" /></el-select>
        </el-form-item>
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
    <el-card class="filter-card">
      <div class="filter-row">
        <el-select v-model="filter.loginType" placeholder="登录方式" clearable style="width: 130px">
          <el-option label="手机" value="phone" /><el-option label="微信" value="wechat" /><el-option label="邮箱" value="email" />
        </el-select>
        <el-select v-model="filter.status" placeholder="状态" clearable style="width: 130px">
          <el-option label="正常" value="NORMAL" /><el-option label="可疑" value="SUSPICIOUS" /><el-option label="已封禁" value="BANNED" /><el-option label="未激活" value="INACTIVE" />
        </el-select>
        <el-input v-model="filter.keyword" placeholder="账号 / 用户 ID" clearable style="width: 220px" @keyup.enter="search" />
        <el-input-number v-model="filter.minDetect" placeholder="检测数 ≥" :min="0" :controls="false" style="width: 130px" />
        <el-input-number v-model="filter.maxDetect" placeholder="检测数 ≤" :min="0" :controls="false" style="width: 130px" />
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
    </el-card>

    <el-card class="table-card">
      <el-table v-loading="loading" :data="rows" size="default" empty-text="暂无用户">
        <el-table-column prop="id" label="用户 ID" width="100" />
        <el-table-column label="登录方式" width="110"><template #default="{ row }">{{ LOGIN_LABEL[row.loginType as LoginType] || row.loginType }}</template></el-table-column>
        <el-table-column prop="identity" label="账号（脱敏）" min-width="160" />
        <el-table-column prop="detectCount" label="累计检测数" width="110" align="right" />
        <el-table-column prop="lastLoginAt" label="最近登录" width="170" />
        <el-table-column prop="registeredAt" label="注册时间" width="170" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }"><el-tag :type="STATUS_TAG[row.status as UserStatus]?.type" size="small">{{ STATUS_TAG[row.status as UserStatus]?.text || row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status !== 'BANNED'" size="small" type="danger" link @click="onBan(row)">封禁</el-button>
            <el-button v-else size="small" type="primary" link @click="onUnban(row)">解封</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pager" v-model:current-page="pageNum" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="load" @current-change="load" />
    </el-card>
  </template>
</template>

<style scoped>
.tabs { margin-bottom: 8px; }
.filter-card { margin-bottom: 16px; }
.filter-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.flex-1 { flex: 1; }
.table-card :deep(.el-card__body) { padding: 0; }
.pager { justify-content: flex-end; padding: 16px; }
.self-tag { margin-left: 6px; }
.hint { font-size: 12px; color: var(--label-tertiary); line-height: 1.6; }
.muted { color: var(--label-secondary); }
.temp { display: flex; flex-direction: column; gap: 10px; }
.temp-row { display: flex; align-items: center; gap: 12px; }
.temp-pwd { font-size: 20px; letter-spacing: 1px; padding: 4px 10px; border-radius: 8px; background: rgba(120, 120, 128, 0.12); user-select: all; }
</style>
