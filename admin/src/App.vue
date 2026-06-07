<template>
  <div class="admin-shell">
    <header class="admin-topbar">
      <span class="admin-topbar__mark">AW</span>
      <div class="admin-topbar__title">
        <strong>卡密映射管理后台</strong>
        <span>AskWhy Recharge Admin</span>
      </div>
      <div class="admin-topbar__spacer"></div>
    </header>
    <main class="admin-main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts"></script>
