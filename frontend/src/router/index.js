import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomePage.vue'),
  },
  {
    path: '/analyze',
    name: 'analyze',
    component: () => import('../views/AnalysisPage.vue'),
  },
  {
    path: '/download',
    name: 'download',
    component: () => import('../views/DownloadPage.vue'),
  },
  {
    path: '/issues',
    name: 'issues',
    component: () => import('../views/IssuesPage.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
