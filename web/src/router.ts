import { createRouter, createWebHistory } from 'vue-router';
import AskWhyView from './views/AskWhyView.vue';
import CardQueryView from './views/CardQueryView.vue';
import SmsView from './views/SmsView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'recharge', component: AskWhyView },
    { path: '/cards', name: 'cards', component: CardQueryView },
    { path: '/sms', name: 'sms', component: SmsView },
  ],
});
