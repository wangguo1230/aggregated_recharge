import { createRouter, createWebHistory } from 'vue-router';
import AdminView from './views/AdminView.vue';

// 隐蔽入口路径，可用 VITE_ADMIN_PATH 覆盖（默认 /wangguodong）。
const adminPath = import.meta.env.VITE_ADMIN_PATH || '/wangguodong';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: adminPath, name: 'admin', component: AdminView },
    // 其它任何路径都回落到管理入口（独立应用，不暴露其余路由）。
    { path: '/:pathMatch(.*)*', redirect: adminPath },
  ],
});
