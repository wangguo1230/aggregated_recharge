import { createRouter, createWebHistory } from 'vue-router';
import AskWhyView from './views/AskWhyView.vue';
import CardQueryView from './views/CardQueryView.vue';
import ClaudeView from './views/ClaudeView.vue';
import SmsView from './views/SmsView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    // GPT 充值暂时隐藏：默认落地到 Claude 充值；GPT 充值/卡密查询保留路由但不在导航暴露。
    { path: '/', redirect: '/claude' },
    { path: '/recharge', name: 'recharge', component: AskWhyView },
    { path: '/cards', name: 'cards', component: CardQueryView },
    { path: '/claude', name: 'claude', component: ClaudeView },
    { path: '/sms', name: 'sms', component: SmsView },
  ],
});
