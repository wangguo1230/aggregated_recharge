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
          <RouterLink v-if="SHOW_GPT" to="/recharge" custom v-slot="{ href, navigate }">
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
              <span class="user-rail__text"><span>{{ t('app.gpt.title') }}</span><small>{{ t('app.gpt.sub') }}</small></span>
            </a>
          </RouterLink>

          <RouterLink to="/claude" custom v-slot="{ href, navigate }">
            <a
              :href="href"
              class="user-rail__item"
              :class="{ 'user-rail__item--active': activeSection === 'claude' }"
              @click="navigate"
            >
              <span class="user-rail__icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 3 L14 10 L21 12 L14 14 L12 21 L10 14 L3 12 L10 10 Z" fill="currentColor" />
                </svg>
              </span>
              <span class="user-rail__text"><span>{{ t('app.claude.title') }}</span><small>{{ t('app.claude.sub') }}</small></span>
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

          <nav v-if="SHOW_GPT && activeSection === 'recharge'" class="user-subnav" :aria-label="t('app.gpt.title')">
            <RouterLink to="/recharge">{{ t('app.subnav.recharge') }}</RouterLink>
            <RouterLink to="/cards">{{ t('app.subnav.cards') }}</RouterLink>
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
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import BrandLogo from './components/BrandLogo.vue';
import { setLocale, type AppLocale } from './i18n';

const route = useRoute();
const { t, locale } = useI18n();

// GPT 充值暂时下线：置 false 隐藏左侧导航与子导航；改回 true 即可恢复。
const SHOW_GPT = false;

function changeLang(lang: AppLocale) {
  setLocale(lang);
}

const PAGE_KEYS = ['recharge', 'cards', 'sms', 'claude'];
const current = computed(() => {
  const name = String(route.name || '');
  const key = PAGE_KEYS.includes(name) ? name : 'recharge';
  return {
    title: t(`app.pages.${key}.title`),
    eyebrow: t(`app.pages.${key}.eyebrow`),
    description: t(`app.pages.${key}.desc`),
  };
});
const pageTitle = computed(() => current.value.title);
const pageEyebrow = computed(() => current.value.eyebrow);
const pageDescription = computed(() => current.value.description);

// 两大区块：GPT 充值（充值 + 卡密查询）/ Claude / 手机接码
const activeSection = computed(() => {
  if (route.name === 'sms') return 'sms';
  if (route.name === 'claude') return 'claude';
  return 'recharge';
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
