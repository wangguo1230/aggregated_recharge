import { createI18n } from 'vue-i18n';
import en from './locales/en';
import zh from './locales/zh';

export type AppLocale = 'zh' | 'en';
const STORAGE_KEY = 'recharge:lang';

function detectLocale(): AppLocale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'zh' || saved === 'en') return saved;
  } catch {
    // localStorage 不可用时忽略
  }
  return 'zh'; // 中文优先；用户切换后记忆其选择
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: detectLocale(),
  fallbackLocale: 'zh',
  messages: { zh, en },
});

export function currentLocale(): AppLocale {
  return i18n.global.locale.value as AppLocale;
}

export function setLocale(lang: AppLocale): void {
  i18n.global.locale.value = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // 忽略
  }
  document.documentElement.setAttribute('lang', lang === 'zh' ? 'zh-CN' : 'en');
}
