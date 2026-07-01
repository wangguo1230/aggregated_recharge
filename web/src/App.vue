<template>
  <div class="page-shell user-shell">
    <div class="user-layout">
      <!-- 左侧主导航 -->
      <aside class="user-sidebar">
        <div class="user-brand">
          <span class="user-brand__mark"><BrandLogo /></span>
          <div>
            <p class="eyebrow">10666 Recharge</p>
            <strong>{{ t('app.brandName') }}</strong>
          </div>
        </div>

        <nav class="user-rail" :aria-label="t('app.brandName')">
          <RouterLink v-if="SHOW_GPT" to="/gpt" custom v-slot="{ href, navigate }">
            <a
              :href="href"
              class="user-rail__item"
              :class="{ 'user-rail__item--active': activeSection === 'gpt' }"
              @click="navigate"
            >
              <span class="user-rail__icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M13 3 L5 13 H11 L10 21 L19 10 H13 Z" fill="currentColor" />
                </svg>
              </span>
              <span class="user-rail__text"><span>{{ t('app.gpt.title') }}</span><small>{{ t('app.gpt.sub') }}</small></span>
            </a>
          </RouterLink>

          <RouterLink v-if="SHOW_VIP" to="/vip" custom v-slot="{ href, navigate }">
            <a
              :href="href"
              class="user-rail__item"
              :class="{ 'user-rail__item--active': activeSection === 'vip' }"
              @click="navigate"
            >
              <span class="user-rail__icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M4 7 L12 3 L20 7 V12 C20 17 16 20 12 21 C8 20 4 17 4 12 Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
                </svg>
              </span>
              <span class="user-rail__text"><span>{{ t('app.vip.title') }}</span><small>{{ t('app.vip.sub') }}</small></span>
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
              <span class="user-rail__text"><span>{{ t('app.sms.title') }}</span><small>{{ t('app.sms.sub') }}</small></span>
            </a>
          </RouterLink>
        </nav>
      </aside>

      <!-- 右侧主体 -->
      <div class="user-body">
        <header class="user-topbar">
          <div class="lang-switch" role="group" :aria-label="t('lang.label')">
            <button type="button" :class="{ 'is-active': locale === 'zh' }" @click="changeLang('zh')">中文</button>
            <button type="button" :class="{ 'is-active': locale === 'en' }" @click="changeLang('en')">EN</button>
          </div>

          <p class="eyebrow">{{ pageEyebrow }}</p>
          <h1>{{ pageTitle }}</h1>
          <p class="user-topbar__desc">{{ pageDescription }}</p>
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
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import BrandLogo from './components/BrandLogo.vue';
import { setLocale, type AppLocale } from './i18n';

const route = useRoute();
const { t, locale } = useI18n();

// GPT 充值开关：true 显示左侧导航与子导航；false 一键隐藏。
const SHOW_GPT = true;
// 74 充值入口开关：false 暂时关闭（隐藏导航；路由保留但不暴露）。
const SHOW_VIP = false;

function changeLang(lang: AppLocale) {
  setLocale(lang);
}

const PAGE_KEYS = ['gpt', 'vip', 'sms'];
const current = computed(() => {
  const name = String(route.name || '');
  const key = PAGE_KEYS.includes(name) ? name : 'gpt';
  return {
    title: t(`app.pages.${key}.title`),
    eyebrow: t(`app.pages.${key}.eyebrow`),
    description: t(`app.pages.${key}.desc`),
  };
});
const pageTitle = computed(() => current.value.title);
const pageEyebrow = computed(() => current.value.eyebrow);
const pageDescription = computed(() => current.value.description);

// 区块：GPT 充值 / 74 GPT充值 / 手机接码
const activeSection = computed(() => {
  if (route.name === 'sms') return 'sms';
  if (route.name === 'vip') return 'vip';
  return 'gpt';
});
</script>

<style scoped>
.user-topbar {
  position: relative;
}
.lang-switch {
  position: absolute;
  top: 0;
  right: 0;
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  border-radius: 999px;
  background: rgba(40, 103, 122, 0.08);
}
.lang-switch button {
  border: none;
  background: transparent;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: var(--recharge-muted);
  cursor: pointer;
  line-height: 1.4;
}
.lang-switch button.is-active {
  background: #fff;
  color: var(--recharge-blue);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
</style>
