<template>
  <div class="page-shell user-shell">
    <header class="user-header">
      <div class="page-inner user-header__inner">
        <div class="user-brand">
          <span class="user-brand__mark">106</span>
          <div>
            <p class="eyebrow">10666 Recharge</p>
            <h1>{{ pageTitle }}</h1>
          </div>
        </div>
        <div class="user-header__actions">
          <nav class="user-nav" aria-label="导航">
            <RouterLink to="/">
              <span>充值</span>
              <small>卡密充值</small>
            </RouterLink>
            <RouterLink to="/cards">
              <span>卡密查询</span>
              <small>查使用状况</small>
            </RouterLink>
          </nav>
        </div>
      </div>
      <div class="page-inner user-header__meta">
        <div>
          <span>{{ pageEyebrow }}</span>
          <strong>{{ pageDescription }}</strong>
        </div>
      </div>
    </header>
    <main class="user-main page-inner">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

const copy: Record<string, { title: string; eyebrow: string; description: string }> = {
  recharge: { title: '10666 充值', eyebrow: 'Submit', description: '校验卡密、校验 Session，实时查看充值进度' },
  cards: { title: '卡密查询', eyebrow: 'Card Lookup', description: '批量查询卡密使用状况、充值账号与时间' },
};

const current = computed(() => copy[String(route.name || '')] || copy.recharge);
const pageTitle = computed(() => current.value.title);
const pageEyebrow = computed(() => current.value.eyebrow);
const pageDescription = computed(() => current.value.description);
</script>
