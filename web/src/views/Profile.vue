<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import ZyIcon from '@/components/ZyIcon.vue'
import FeedbackDialog from '@/components/FeedbackDialog.vue'
import SchoolPicker from '@/components/SchoolPicker.vue'
import { getMyRule, type ResolvedRule } from '@/api/school'

const auth = useAuthStore()
const router = useRouter()

const schoolPickerOpen = ref(false)
const myRule = ref<ResolvedRule | null>(null)
const DEG_CN: Record<string, string> = { bachelor: '本科', master: '硕士', phd: '博士' }
const schoolText = computed(() => {
  const r = myRule.value
  if (!r || !r.schoolName) return ''
  return `${r.schoolName} · ${DEG_CN[r.degreeType || ''] || ''}`
})
const hasRule = computed(() => !!(myRule.value?.resolved && myRule.value?.aiRateLimit != null))
async function loadMyRule() {
  try { myRule.value = await getMyRule() } catch { /* 未登录等，忽略 */ }
}
onMounted(loadMyRule)

const ROLE_CN: Record<string, string> = { STUDENT: '学生', ADMIN: '管理员', USER: '用户' }
const roleText = computed(() => ROLE_CN[auth.user?.role || 'USER'] || auth.user?.role || '用户')

const feedbackOpen = ref(false)
const pwdOpen = ref(false)
const pwd = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const pwdError = computed(() => {
  const p = pwd.value
  if (!p.oldPassword) return '请输入原密码'
  if (p.newPassword.length < 6 || p.newPassword.length > 32) return '新密码长度 6-32 位'
  if (!/[A-Za-z]/.test(p.newPassword) || !/[0-9]/.test(p.newPassword)) return '新密码需同时包含字母和数字'
  if (p.newPassword === p.oldPassword) return '新密码不能与原密码相同'
  if (p.confirmPassword !== p.newPassword) return '两次输入的新密码不一致'
  return ''
})
async function submitPassword() {
  if (pwdError.value) { ElMessage.warning(pwdError.value); return }
  try {
    await auth.changePassword(pwd.value.oldPassword, pwd.value.newPassword, pwd.value.confirmPassword)
    pwdOpen.value = false
    ElMessage.success('密码已修改，请重新登录')
    router.replace('/login')
  } catch { /* 拦截器已 toast */ }
}

const avatarLetter = computed(() => (auth.user?.realName || auth.user?.username || 'U').charAt(0).toUpperCase())

async function logout() {
  try {
    await ElMessageBox.confirm('退出后需要重新登录才能查看报告', '退出登录？', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '再想想',
      confirmButtonClass: 'el-button--danger',
    })
    await auth.logout()
    router.replace('/login')
  } catch { /* 取消 */ }
}
</script>

<template>
  <div class="page">
    <div class="wrap">
      <header class="page-head">
        <button class="icon-btn" aria-label="返回" @click="router.back()"><ZyIcon name="arrow-left" :size="18" /></button>
        <h1>我的</h1>
      </header>

      <div class="layout">
        <!-- 左栏：身份 + 学校红线（sticky） -->
        <aside class="side">
          <section class="card id-card">
            <div class="avatar">{{ avatarLetter }}</div>
            <div class="id-name">{{ auth.user?.realName || auth.user?.username || '已登录用户' }}</div>
            <div class="id-tags">
              <span class="tag">{{ roleText }}</span>
              <span class="tag ghost">{{ auth.user?.orgName || '教育部合规检测' }}</span>
            </div>
            <div class="id-xiaobai">
              <ZyIcon name="xiaobai-spark" :size="16" />
              <span>论文交给我看，你负责写好它。</span>
            </div>
          </section>

          <section class="card rule-card" :class="{ empty: !hasRule }">
            <div class="rule-head">
              <span class="rule-icon"><ZyIcon name="graduation" :size="18" /></span>
              <span class="rule-title">学校红线</span>
            </div>
            <template v-if="hasRule">
              <div class="rule-school">{{ schoolText }}</div>
              <div class="rule-rate">
                <span class="rule-num">{{ myRule?.aiRateLimit }}</span><span class="rule-unit">%</span>
              </div>
              <div class="rule-desc">AI 率红线，检测按这个数判定达标</div>
              <div class="rule-meta" v-if="myRule?.platform">{{ myRule.platform }}<template v-if="myRule?.effectiveYear"> · {{ myRule.effectiveYear }} 年口径</template></div>
            </template>
            <template v-else>
              <div class="rule-school">还没有设置</div>
              <div class="rule-desc">选了学校，检测就按你学校的红线来判定，不再用通用标准。</div>
            </template>
            <el-button :type="hasRule ? 'default' : 'primary'" size="small" class="rule-btn" @click="schoolPickerOpen = true">
              {{ hasRule ? '换个学校或学位' : '选我的学校' }}
            </el-button>
          </section>
        </aside>

        <!-- 右栏：设置分区 -->
        <main class="content">
          <section class="card sec">
            <div class="sec-title">账户</div>
            <div class="row">
              <span class="row-icon"><ZyIcon name="user" :size="17" /></span>
              <div class="row-text"><span class="row-name">用户名</span><span class="row-sub">{{ auth.user?.username || '—' }}</span></div>
            </div>
            <div class="sep"></div>
            <div class="row clickable" @click="router.push('/dashboard')">
              <span class="row-icon"><ZyIcon name="file-text" :size="17" /></span>
              <div class="row-text"><span class="row-name">历史报告</span><span class="row-sub">检测过的论文都在这里</span></div>
              <ZyIcon class="row-go" name="chevron-right" :size="16" />
            </div>
          </section>

          <section class="card sec">
            <div class="sec-title">安全</div>
            <div class="row clickable" @click="pwdOpen = true">
              <span class="row-icon"><ZyIcon name="shield" :size="17" /></span>
              <div class="row-text"><span class="row-name">修改密码</span><span class="row-sub">改好后所有设备需要重新登录</span></div>
              <span class="row-act">修改</span>
            </div>
          </section>

          <section class="card sec">
            <div class="sec-title">更多</div>
            <div class="row clickable" @click="router.push('/verify')">
              <span class="row-icon"><ZyIcon name="compass" :size="17" /></span>
              <div class="row-text"><span class="row-name">验证报告真伪</span><span class="row-sub">输入报告编号和验证码就能查</span></div>
              <ZyIcon class="row-go" name="chevron-right" :size="16" />
            </div>
            <div class="sep"></div>
            <div class="row clickable" @click="feedbackOpen = true">
              <span class="row-icon"><ZyIcon name="chat" :size="17" /></span>
              <div class="row-text"><span class="row-name">意见反馈</span><span class="row-sub">判错了、有想法，都可以告诉我们</span></div>
              <ZyIcon class="row-go" name="chevron-right" :size="16" />
            </div>
            <div class="sep"></div>
            <div class="row clickable" @click="router.push('/privacy')">
              <span class="row-icon"><ZyIcon name="book" :size="17" /></span>
              <div class="row-text"><span class="row-name">隐私政策</span><span class="row-sub">论文只用于本次检测</span></div>
              <ZyIcon class="row-go" name="chevron-right" :size="16" />
            </div>
          </section>

          <section class="card danger-zone">
            <div class="dz-text">
              <div class="dz-title">退出登录</div>
              <div class="dz-sub">退出后需要重新登录才能查看报告</div>
            </div>
            <el-button type="danger" plain size="small" @click="logout">退出</el-button>
          </section>

          <div class="version">知源 · v0.1.0 · 论文 AIGC 检测课题组</div>
        </main>
      </div>
    </div>

    <FeedbackDialog v-model="feedbackOpen" default-category="suggestion" />
    <SchoolPicker v-model="schoolPickerOpen" @saved="loadMyRule" />

    <el-dialog v-model="pwdOpen" title="修改密码" width="420" align-center destroy-on-close>
      <el-form label-position="top" @submit.prevent="submitPassword">
        <el-form-item label="原密码"><el-input v-model="pwd.oldPassword" type="password" show-password autocomplete="current-password" /></el-form-item>
        <el-form-item label="新密码（6-32 位，含字母和数字）"><el-input v-model="pwd.newPassword" type="password" show-password autocomplete="new-password" /></el-form-item>
        <el-form-item label="确认新密码"><el-input v-model="pwd.confirmPassword" type="password" show-password autocomplete="new-password" /></el-form-item>
        <div class="pwd-hint">修改成功后所有设备需重新登录</div>
      </el-form>
      <template #footer>
        <el-button @click="pwdOpen = false">取消</el-button>
        <el-button type="primary" :loading="auth.loading" :disabled="!!pwdError" @click="submitPassword">改好了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; }
.wrap { max-width: 920px; margin: 0 auto; padding: 24px; }

/* ---- 页头：icon-btn 返回 + 大标题，对齐工作台语言 ---- */
.page-head { display: flex; align-items: center; gap: 14px; margin-bottom: 24px; }
.page-head h1 { font-size: var(--fs-large-title); font-weight: var(--fw-bold); letter-spacing: -0.8px; margin: 0; }
.icon-btn {
  width: 36px; height: 36px; border-radius: var(--radius-btn);
  border: none; background: transparent; color: var(--label-secondary);
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer; transition: background var(--dur-fast), color var(--dur-fast);
}
.icon-btn:hover { background: var(--ai-100); color: var(--ai-700); }
.icon-btn:active { transform: scale(0.96); }

/* ---- 双栏 ---- */
.layout { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 24px; align-items: start; }
.side { position: sticky; top: 24px; display: flex; flex-direction: column; gap: 16px; }

/* ---- 卡片基底：16px 圆角 + 发丝边框 + 轻环境光 ---- */
.card {
  background: var(--system-background);
  border: 1px solid rgba(23, 24, 28, 0.08);
  border-radius: var(--radius-card);
  box-shadow: 0 2px 8px rgba(23, 24, 28, 0.05);
}

/* ---- 身份卡：品牌时刻，青→蓝渐变头像 ---- */
.id-card { padding: 24px; text-align: center; }
.avatar {
  width: 56px; height: 56px; border-radius: 50%; margin: 0 auto;
  background: linear-gradient(135deg, var(--ai-500), #3B82F6);
  color: #fff; font-size: 24px; font-weight: var(--fw-semibold);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(15, 118, 110, 0.18);
}
.id-name { margin-top: 14px; font-size: var(--fs-title-3); font-weight: var(--fw-semibold); letter-spacing: -0.3px; }
.id-tags { margin-top: 8px; display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; }
.tag { font-size: var(--fs-caption-1); font-weight: var(--fw-medium); padding: 2px 10px; border-radius: var(--radius-pill); background: var(--ai-100); color: var(--ai-700); }
.tag.ghost { background: var(--bg-deep); color: var(--label-secondary); }
.id-xiaobai { margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(23, 24, 28, 0.08); display: flex; gap: 6px; align-items: flex-start; justify-content: center; color: var(--label-secondary); font-size: var(--fs-footnote); line-height: 1.5; }
.id-xiaobai .zy-icon { color: var(--ai-500); margin-top: 1px; }

/* ---- 学校红线卡：数据感主角 ---- */
.rule-card { padding: 18px 20px 20px; }
.rule-card.empty .rule-icon { background: var(--bg-deep); color: var(--label-secondary); }
.rule-head { display: flex; align-items: center; gap: 8px; }
.rule-icon { width: 32px; height: 32px; border-radius: 10px; background: var(--ai-100); color: var(--ai-700); display: inline-flex; align-items: center; justify-content: center; }
.rule-title { font-weight: var(--fw-semibold); }
.rule-school { margin-top: 14px; font-size: var(--fs-body); font-weight: var(--fw-medium); }
.rule-rate { margin-top: 2px; display: flex; align-items: baseline; gap: 2px; }
.rule-num { font-size: var(--fs-large-title); font-weight: var(--fw-bold); letter-spacing: -1px; color: var(--ai-700); font-variant-numeric: tabular-nums; }
.rule-unit { font-size: var(--fs-subhead); font-weight: var(--fw-semibold); color: var(--ai-700); }
.rule-desc { margin-top: 6px; color: var(--label-secondary); font-size: var(--fs-footnote); line-height: 1.5; }
.rule-meta { margin-top: 8px; color: var(--label-tertiary); font-size: var(--fs-caption-1); }
.rule-btn { margin-top: 14px; width: 100%; }

/* ---- 右栏分区卡 ---- */
.content { display: flex; flex-direction: column; gap: 16px; }
.sec { padding: 8px 0; }
.sec-title { padding: 12px 20px 6px; font-size: var(--fs-caption-1); font-weight: var(--fw-medium); color: var(--label-secondary); letter-spacing: 0.5px; text-transform: uppercase; }
.row { padding: 13px 20px; display: flex; align-items: center; gap: 14px; border-radius: 0 var(--radius-btn) var(--radius-btn) 0; transition: background var(--dur-fast); }
.row.clickable { cursor: pointer; }
.row.clickable:hover { background: var(--ai-100); }
.row-icon { flex: none; width: 36px; height: 36px; border-radius: 12px; background: var(--ai-100); color: var(--ai-700); display: inline-flex; align-items: center; justify-content: center; }
.row.clickable:hover .row-icon { background: var(--system-background); }
.row-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.row-name { font-size: var(--fs-body); font-weight: var(--fw-medium); color: var(--label); }
.row-sub { font-size: var(--fs-footnote); color: var(--label-tertiary); line-height: 1.4; }
.row-go { color: var(--label-tertiary); }
.row.clickable:hover .row-go { color: var(--ai-700); }
.row-act { color: var(--ai-700); font-size: var(--fs-footnote); font-weight: var(--fw-semibold); }
.sep { height: 1px; background: rgba(23, 24, 28, 0.06); margin-left: 70px; }

/* ---- Danger zone：web 惯例的底部危险区 ---- */
.danger-zone { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 20px; border-color: rgba(229, 72, 77, 0.25); }
.dz-title { font-size: var(--fs-body); font-weight: var(--fw-semibold); color: var(--danger); }
.dz-sub { margin-top: 2px; font-size: var(--fs-footnote); color: var(--label-tertiary); }
.version { text-align: center; color: var(--label-tertiary); font-size: var(--fs-caption-1); padding: 4px 0 12px; }

.pwd-hint { font-size: 12px; color: var(--label-tertiary); }

@media (max-width: 860px) {
  .layout { grid-template-columns: 1fr; }
  .side { position: static; }
  .sep { margin-left: 20px; }
  .row { border-radius: 0; }
}
</style>
