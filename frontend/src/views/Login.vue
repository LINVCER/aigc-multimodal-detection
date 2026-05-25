<template>
  <div class="login-page">
    <div class="animated-bg">
      <div class="gradient-orb orb-1"></div>
      <div class="gradient-orb orb-2"></div>
      <div class="gradient-orb orb-3"></div>
      <div class="grid-overlay"></div>
    </div>

    <div class="login-container">
      <div class="brand-section">
        <div class="brand-content">
          <div class="logo-wrapper">
            <div class="logo-icon">IN</div>
            <h1 class="brand-title">ImageNious</h1>
          </div>
          <p class="brand-subtitle">AI 生成内容检测平台</p>
          <div class="brand-features">
            <div class="feature-item">
              <div class="feature-icon">M</div>
              <span>多模态检测</span>
            </div>
            <div class="feature-item">
              <div class="feature-icon">R</div>
              <span>实时分析</span>
            </div>
            <div class="feature-item">
              <div class="feature-icon">P</div>
              <span>精准报告</span>
            </div>
          </div>
        </div>
      </div>

      <div class="form-section">
        <div class="form-card">
          <div class="form-header">
            <h2 class="form-title">欢迎回来</h2>
            <p class="form-subtitle">登录您的账户以继续</p>
          </div>

          <el-form :model="form" class="login-form" @submit.prevent="handleLogin">
            <div class="input-group">
              <label class="input-label">用户名</label>
              <el-input
                v-model="form.username"
                placeholder="请输入用户名"
                class="custom-input"
              />
            </div>

            <div class="input-group">
              <label class="input-label">密码</label>
              <el-input
                v-model="form.password"
                type="password"
                placeholder="请输入密码"
                show-password
                class="custom-input"
              />
            </div>

            <div class="form-options">
              <el-checkbox v-model="rememberMe" class="remember-checkbox">记住我</el-checkbox>
              <el-button link class="forgot-link" @click="handleForgot">忘记密码？</el-button>
            </div>

            <el-button
              type="primary"
              native-type="submit"
              :loading="loading"
              class="login-button"
            >
              <span v-if="!loading">登录</span>
              <span v-else>登录中...</span>
            </el-button>
          </el-form>

          <div class="form-footer">
            <p class="register-text">
              还没有账号？
              <el-button link class="register-link" @click="showRegister = true">
                立即注册
              </el-button>
            </p>
          </div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="showRegister"
      title="创建账户"
      width="520px"
      class="register-dialog"
      destroy-on-close
    >
      <div class="register-header">
        <p class="register-subtitle">选择适合您的角色，开启AI检测之旅</p>
      </div>
      <el-form :model="regForm" class="register-form">
        <div class="input-group">
          <label class="input-label">用户名</label>
          <el-input v-model="regForm.username" placeholder="请输入用户名" class="custom-input" />
        </div>
        <div class="input-group">
          <label class="input-label">邮箱</label>
          <el-input v-model="regForm.email" placeholder="请输入邮箱" class="custom-input" />
        </div>
        <div class="input-group">
          <label class="input-label">密码</label>
          <el-input v-model="regForm.password" type="password" placeholder="请输入密码（至少6位）" show-password class="custom-input" />
        </div>
        <div class="input-group">
          <label class="input-label">选择角色</label>
          <div class="role-grid">
            <div
              v-for="role in roleOptions"
              :key="role.value"
              class="role-card"
              :class="{ active: regForm.role === role.value }"
              @click="regForm.role = role.value"
            >
              <div class="role-icon" :style="{ background: role.gradient }">
                {{ role.label.charAt(0) }}
              </div>
              <div class="role-info">
                <span class="role-name">{{ role.label }}</span>
                <span class="role-desc">{{ role.description }}</span>
              </div>
              <div class="role-check" v-if="regForm.role === role.value">&#10003;</div>
            </div>
          </div>
        </div>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showRegister = false" class="cancel-button">取消</el-button>
          <el-button type="primary" @click="handleRegister" :loading="regLoading" class="submit-button">
            创建账户
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"
import { ElMessage } from "element-plus"

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const showRegister = ref(false)
const regLoading = ref(false)
const rememberMe = ref(false)

const form = reactive({ username: "", password: "" })
const regForm = reactive({ username: "", email: "", password: "", role: "teacher" })

const roleOptions = [
  { value: "teacher", label: "教师", description: "教学场景使用", gradient: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" },
  { value: "journalist", label: "记者", description: "新闻审核使用", gradient: "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)" },
  { value: "student", label: "学生", description: "学习研究使用", gradient: "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)" },
  { value: "researcher", label: "研究员", description: "学术研究使用", gradient: "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)" },
  { value: "editor", label: "编辑", description: "内容审核使用", gradient: "linear-gradient(135deg, #fa709a 0%, #fee140 100%)" },
  { value: "developer", label: "开发者", description: "技术开发使用", gradient: "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)" }
]

async function handleLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning("请填写用户名和密码")
    return
  }
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success("登录成功")
    router.push("/dashboard")
  } catch {
    ElMessage.error("登录失败，请检查用户名和密码")
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!regForm.username || !regForm.email || !regForm.password) {
    ElMessage.warning("请填写完整信息")
    return
  }
  regLoading.value = true
  try {
    await auth.register(regForm)
    ElMessage.success("注册成功，请登录")
    showRegister.value = false
  } catch {
    ElMessage.error("注册失败")
  } finally {
    regLoading.value = false
  }
}

function handleForgot() {
  ElMessage.info("请联系管理员重置密码")
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: #0a0e27;
}

.animated-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
}

.gradient-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
  animation: float 20s ease-in-out infinite;
}

.orb-1 {
  width: 600px; height: 600px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  top: -200px; left: -200px;
  animation-delay: 0s;
}

.orb-2 {
  width: 500px; height: 500px;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  bottom: -150px; right: -150px;
  animation-delay: -7s;
}

.orb-3 {
  width: 400px; height: 400px;
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  animation-delay: -14s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -30px) scale(1.1); }
  66% { transform: translate(-20px, 20px) scale(0.9); }
}

.grid-overlay {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
}

.login-container {
  display: flex;
  width: 100%;
  max-width: 1200px;
  min-height: 600px;
  position: relative;
  z-index: 1;
  padding: 40px;
  gap: 60px;
}

.brand-section {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-content {
  text-align: center;
  color: white;
}

.logo-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 24px;
}

.logo-icon {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
  font-size: 22px;
  font-weight: 800;
  color: white;
}

.brand-title {
  font-size: 42px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-subtitle {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.7);
  margin: 0 0 48px 0;
  letter-spacing: 2px;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 300px;
  margin: 0 auto;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  transition: all 0.3s ease;
}

.feature-item:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateX(8px);
}

.feature-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
  font-weight: 800;
  color: white;
}

.feature-item span {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.9);
}

.form-section {
  flex: 0 0 440px;
  display: flex;
  align-items: center;
}

.form-card {
  width: 100%;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 24px;
  padding: 48px 40px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(20px);
}

.form-header {
  text-align: center;
  margin-bottom: 32px;
}

.form-title {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 8px 0;
}

.form-subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.input-group {
  margin-bottom: 20px;
}

.input-label {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

:deep(.custom-input .el-input__wrapper) {
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  border: 1px solid #e5e7eb;
  transition: all 0.3s ease;
}

:deep(.custom-input .el-input__wrapper:hover) {
  border-color: #667eea;
}

:deep(.custom-input .el-input__wrapper.is-focus) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

:deep(.remember-checkbox .el-checkbox__label) {
  font-size: 13px;
  color: #6b7280;
}

.forgot-link {
  font-size: 13px;
  color: #667eea;
}

.forgot-link:hover {
  color: #764ba2;
}

.login-button {
  width: 100%;
  height: 48px;
  border-radius: 12px;
  font-size: 17px;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  box-shadow: 0 4px 14px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

.login-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.login-button:active {
  transform: translateY(0);
}

.form-footer {
  text-align: center;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.register-text {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.register-link {
  font-size: 14px;
  color: #667eea;
  font-weight: 600;
}

.register-link:hover {
  color: #764ba2;
}

.register-dialog :deep(.el-dialog__header) {
  text-align: center;
  padding-bottom: 0;
}

.register-dialog :deep(.el-dialog__title) {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
}

.register-header {
  text-align: center;
  margin-bottom: 24px;
}

.register-subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.register-form {
  padding: 0 20px;
}

.role-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.role-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 12px;
  border-radius: 12px;
  border: 2px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  background: white;
}

.role-card:hover {
  border-color: #667eea;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

.role-card.active {
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.05);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
}

.role-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
  font-weight: 800;
  color: white;
}

.role-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.role-info .role-name {
  font-weight: 600;
  color: #1a1a2e;
  font-size: 14px;
}

.role-info .role-desc {
  font-size: 11px;
  color: #6b7280;
}

.role-check {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  background: #667eea;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  font-weight: 700;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 40px;
}

.cancel-button {
  border-radius: 10px;
  padding: 10px 24px;
}

.submit-button {
  border-radius: 10px;
  padding: 10px 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

@media (max-width: 1024px) {
  .login-container {
    flex-direction: column;
    gap: 40px;
    padding: 24px;
  }

  .brand-section {
    order: -1;
  }

  .form-section {
    flex: 1;
    width: 100%;
    max-width: 440px;
    margin: 0 auto;
  }

  .brand-features {
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: center;
  }

  .feature-item {
    flex: 0 0 auto;
  }
}

@media (max-width: 640px) {
  .form-card {
    padding: 32px 24px;
  }

  .brand-title {
    font-size: 32px;
  }
}
</style>
