<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>高校合同智能审阅系统</h2>
      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login">
          <el-form @keyup.enter="onLogin">
            <el-form-item>
              <el-input v-model="identifier" placeholder="用户名 / 邮箱" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="password" type="password" placeholder="密码" show-password />
            </el-form-item>
            <el-button type="primary" style="width: 100%" :loading="loading" @click="onLogin">登 录</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form @keyup.enter="onRegister">
            <el-form-item>
              <el-input v-model="reg.username" placeholder="用户名" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="reg.password" type="password" placeholder="密码" show-password />
            </el-form-item>
            <el-form-item>
              <el-input v-model="reg.displayName" placeholder="姓名（可选）" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="reg.department" placeholder="部门（可选）" />
            </el-form-item>
            <el-button type="primary" style="width: 100%" :loading="loading" @click="onRegister">注 册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const tab = ref('login')
const identifier = ref('')
const password = ref('')
const reg = reactive({ username: '', password: '', displayName: '', department: '' })
const loading = ref(false)

async function onLogin() {
  loading.value = true
  try {
    await auth.login(identifier.value, password.value)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
}

async function onRegister() {
  loading.value = true
  try {
    await auth.register(reg.username, reg.password, reg.displayName, reg.department)
    ElMessage.success('注册成功，请登录')
    tab.value = 'login'
    identifier.value = reg.username
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1d2b45, #2d4a7a); }
.login-card { width: 400px; padding: 12px 20px; }
h2 { text-align: center; color: #1d2b45; margin-bottom: 24px; }
</style>
