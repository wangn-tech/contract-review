<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">合同智能审阅</div>
      <el-menu :default-active="route.path" router background-color="#1d2b45" text-color="#cfd8e8" active-text-color="#fff">
        <el-menu-item index="/dashboard">工作台</el-menu-item>
        <el-menu-item index="/contracts">合同管理</el-menu-item>
        <el-menu-item index="/review">智能审阅</el-menu-item>
        <el-menu-item index="/compare">合同比对</el-menu-item>
        <el-menu-item index="/chat">智能问答</el-menu-item>
        <el-menu-item index="/admin">系统配置</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">{{ title }}</span>
        <el-dropdown @command="onCommand">
          <span class="user">{{ auth.user?.display_name || auth.user?.username }}</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const TITLES: Record<string, string> = {
  dashboard: '工作台',
  contracts: '合同管理',
  review: '智能审阅',
  compare: '合同比对',
  chat: '智能问答',
  admin: '系统配置',
}

const title = computed(() => TITLES[route.name as string] || '合同智能审阅')

onMounted(() => {
  if (!auth.user) auth.fetchMe()
})

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #1d2b45; }
.brand { color: #fff; font-size: 18px; font-weight: 600; padding: 20px 16px; }
.aside :deep(.el-menu) { border-right: none; }
.header { display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #e5e7eb; }
.title { font-size: 16px; font-weight: 600; }
.user { cursor: pointer; color: #333; }
.main { background: #f5f7fa; padding: 16px; }
</style>
