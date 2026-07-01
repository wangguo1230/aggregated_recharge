import { createRouter, createWebHistory } from 'vue-router';
import GptView from './views/GptView.vue';
import SmsView from './views/SmsView.vue';
import VipGptView from './views/VipGptView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/gpt' },
    { path: '/gpt', name: 'gpt', component: GptView }, // 86GPT（Gift 上游）
    { path: '/vip', name: 'vip', component: VipGptView }, // 74 渠道（zzlokp12）
    { path: '/sms', name: 'sms', component: SmsView },
  ],
});
