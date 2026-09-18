<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listAdminUsers, banUser, unbanUser, type AdminUser, type LoginType, type UserStatus } from '@/api/admin'

const filter = reactive<{
  loginType: LoginType | ''
  status: UserStatus | ''
  keyword: string
  minDetect?: number
  maxDetect?: number
}>({ loginType: '', status: '', keyword: '' })

const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(20)
const rows = ref<AdminUser[]>([])
const loading = ref(false)

const LOGIN_LABEL: Record<LoginType, string> = { phone: '📱 手机', wechat: '💚 微信', email: '📧 邮箱' }
const STATUS_TAG: Record<UserStatus, { text: string; type: 'success' | 'danger' | 'warning' | 'info' }> = {
  NORMAL:     { text: '正常',   type: 'success' },
  BANNED:     { text: '已封禁', type: 'danger'  },
  INACTIVE:   { text: '未激活', type: 'info'    },
  SUSPICIOUS: { text: '可疑',   type: 'warning' },
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
function reset() {
  Object.assign(filter, { loginType: '', status: '', keyword: '', minDetect: undefined, maxDetect: undefined })
  search()
}

async function onBan(u: AdminUser) {
  await ElMessageBox.confirm(`确定封禁用户 ${u.identity}？`, '封禁确认', { type: 'warning' })
  await banUser(u.id)
  ElMessage.success('已封禁')
  load()
}
async function onUnban(u: AdminUser) {
  await unbanUser(u.id)
  ElMessage.success('已解封')
  load()
}

onMounted(load)
</script>

<template>
  <el-card class="filter-card">
    <div class="filter-row">
      <el-select v-model="filter.loginType" placeholder="登录方式" clearable style="width: 130px">
        <el-option label="手机" value="phone" />
        <el-option label="微信" value="wechat" />
        <el-option label="邮箱" value="email" />
      </el-select>
      <el-select v-model="filter.status" placeholder="状态" clearable style="width: 130px">
        <el-option label="正常" value="NORMAL" />
        <el-option label="可疑" value="SUSPICIOUS" />
        <el-option label="已封禁" value="BANNED" />
        <el-option label="未激活" value="INACTIVE" />
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
      <el-table-column label="登录方式" width="110">
        <template #default="{ row }">{{ LOGIN_LABEL[row.loginType as LoginType] || row.loginType }}</template>
      </el-table-column>
      <el-table-column prop="identity" label="账号（脱敏）" min-width="160" />
      <el-table-column prop="detectCount" label="累计检测数" width="110" align="right" />
      <el-table-column prop="lastLoginAt" label="最近登录" width="170" />
      <el-table-column prop="registeredAt" label="注册时间" width="170" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="STATUS_TAG[row.status as UserStatus]?.type" size="small">
            {{ STATUS_TAG[row.status as UserStatus]?.text || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status !== 'BANNED'" size="small" type="danger" link @click="onBan(row)">封禁</el-button>
          <el-button v-else size="small" type="primary" link @click="onUnban(row)">解封</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      v-model:current-page="pageNum"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      @size-change="load"
      @current-change="load"
    />
  </el-card>
</template>

<style scoped>
.filter-card { margin-bottom: 16px; }
.filter-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.table-card :deep(.el-card__body) { padding: 0; }
.pager { justify-content: flex-end; padding: 16px; }
</style>
