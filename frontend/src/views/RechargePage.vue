<template>
  <div class="recharge-page">
    <h2 style="text-align:center;margin-bottom:24px">充值中心</h2>

    <el-card style="max-width:500px;margin:0 auto">
      <!-- 收款码 -->
      <div style="text-align:center;margin-bottom:20px">
        <img src="/qrcode_pay.png" alt="收款码" style="width:280px;border-radius:8px;border:1px solid #e2e8f0" />
        <p style="font-size:12px;color:#a0aec0;margin-top:8px">请使用微信扫一扫付款</p>
      </div>

      <el-form label-width="80px">
        <el-form-item label="当前额度">
          <el-tag type="warning" size="large">{{ userStore.user?.quota_remaining || 0 }}</el-tag>
        </el-form-item>

        <el-form-item label="充值额度">
          <el-radio-group v-model="amount" style="display:flex;flex-direction:column;gap:8px">
            <el-radio :value="10" border>10 额度 — ¥10</el-radio>
            <el-radio :value="30" border>30 额度 — ¥30</el-radio>
            <el-radio :value="50" border>50 额度 — ¥50</el-radio>
            <el-radio :value="100" border>100 额度 — ¥100</el-radio>
            <el-radio :value="'custom'" border>
              自定义
              <el-input-number v-model="customAmount" :min="1" :max="99999" size="small" style="margin-left:8px;width:120px" v-if="amount === 'custom'" />
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="实付金额">
          <span style="font-size:22px;font-weight:700;color:#409eff">
            ¥{{ amount === 'custom' ? customAmount : amount }}
          </span>
        </el-form-item>

        <el-form-item>
          <el-button type="success" size="large" style="width:100%" @click="handlePay" :loading="paying">
            我已扫码付款，通知管理员
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 付款记录 -->
      <div style="margin-top:24px">
        <h4 style="margin-bottom:8px">付款记录</h4>
        <div v-if="payments.length === 0" style="color:#a0aec0;font-size:13px;text-align:center;padding:16px">暂无记录</div>
        <div v-for="p in payments" :key="p.id" style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:6px">
          <span>¥{{ p.amount }}</span>
          <el-tag :type="p.status==='confirmed'?'success':p.status==='rejected'?'danger':'warning'" size="small">
            {{ ({pending:'等待确认',confirmed:'已到账',rejected:'已拒绝'} as Record<string,string>)[p.status] }}
          </el-tag>
          <span style="font-size:12px;color:#a0aec0">{{ p.created_at }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import api from "@/api"
import { ElMessage } from "element-plus"
import { useAuthStore } from "@/stores/auth"

const userStore = useAuthStore()
const amount = ref<any>(10)
const customAmount = ref(1)
const paying = ref(false)
const payments = ref<any[]>([])

async function fetchPayments() {
  try {
    const { data } = await api.get("/admin/payments", { params: { status: "pending" } })
    payments.value = (data.items || []).slice(0, 10)
  } catch {}
}

async function handlePay() {
  const finalAmount = amount.value === 'custom' ? customAmount.value : amount.value
  paying.value = true
  try {
    await api.post(`/admin/payment/submit?amount=${finalAmount}`)
    ElMessage.success("付款通知已提交，等待管理员确认到账")
    await fetchPayments()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "提交失败")
  } finally {
    paying.value = false
  }
}

onMounted(fetchPayments)
</script>

<style scoped>
.recharge-page {
  max-width: 600px;
  margin: 0 auto;
  padding: 24px;
}
</style>
