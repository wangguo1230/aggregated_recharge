<template>
  <div class="page-shell user-shell">
    <div class="user-layout">
      <!-- 左侧主导航：卡密充值 / 手机接码 两大区块 -->
      <aside class="user-sidebar">
        <div class="user-brand">
          <span class="user-brand__mark"><BrandLogo /></span>
          <div>
            <p class="eyebrow">10666 Recharge</p>
            <strong>聚合服务台</strong>
          </div>
        </div>

        <nav class="user-rail" aria-label="主导航">
          <RouterLink to="/" custom v-slot="{ href, navigate }">
            <a
              :href="href"
              class="user-rail__item"
              :class="{ 'user-rail__item--active': activeSection === 'recharge' }"
              @click="navigate"
            >
              <span class="user-rail__icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M13 3 L5 13 H11 L10 21 L19 10 H13 Z" fill="currentColor" />
                </svg>
              </span>
              <span class="user-rail__text"><span>卡密充值</span><small>充值 · 卡密查询</small></span>
            </a>
          </RouterLink>

          <RouterLink to="/sms" custom v-slot="{ href, navigate }">
            <a
              :href="href"
              class="user-rail__item"
              :class="{ 'user-rail__item--active': activeSection === 'sms' }"
              @click="navigate"
            >
              <span class="user-rail__icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <rect x="6.5" y="3" width="11" height="18" rx="2.4" fill="none" stroke="currentColor" stroke-width="2" />
                  <path d="M10 18 H14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                </svg>
              </span>
              <span class="user-rail__text"><span>手机接码</span><small>长期接收短信</small></span>
            </a>
          </RouterLink>
        </nav>
      </aside>

      <!-- 右侧主体：顶部标题 +（卡密充值区块）子导航 + 路由视图 -->
      <div class="user-body">
        <header class="user-topbar">
          <p class="eyebrow">{{ pageEyebrow }}</p>
          <h1>{{ pageTitle }}</h1>
          <p class="user-topbar__desc">{{ pageDescription }}</p>

          <!-- 卡密充值子导航：卡密查询位于充值右侧 -->
          <nav v-if="activeSection === 'recharge'" class="user-subnav" aria-label="卡密充值子导航">
            <RouterLink to="/">充值</RouterLink>
            <RouterLink to="/cards">卡密查询</RouterLink>
          </nav>
        </header>
        <main class="user-main">
          <RouterView />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import BrandLogo from './components/BrandLogo.vue';

const route = useRoute();

const copy: Record<string, { title: string; eyebrow: string; description: string }> = {
  recharge: { title: '充值', eyebrow: 'Submit', description: '校验卡密、校验 Session，实时查看充值进度' },
  cards: { title: '卡密查询', eyebrow: 'Card Lookup', description: '批量查询卡密使用状况、充值账号与时间' },
  sms: { title: '手机接码', eyebrow: 'SMS Receive', description: '输入兑换码获取手机号，长期接收短信验证码' },
};

const current = computed(() => copy[String(route.name || '')] || copy.recharge);
const pageTitle = computed(() => current.value.title);
const pageEyebrow = computed(() => current.value.eyebrow);
const pageDescription = computed(() => current.value.description);

// 两大区块：卡密充值（充值 + 卡密查询）与手机接码；卡密充值内含右侧子 tab。
const activeSection = computed(() => (route.name === 'sms' ? 'sms' : 'recharge'));
</script>
