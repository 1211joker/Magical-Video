import { createRouter, createWebHashHistory } from 'vue-router'
import { studyApi } from '../api/study.js'
import { analysisTaskLink, conversationLink, videoAnalysisLink } from '../studyUi.js'

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
    path: '/qa',
    name: 'qa',
    component: () => import('../views/QAPage.vue'),
  },
  {
    path: '/study',
    name: 'study-library',
    component: () => import('../views/StudyLibraryPage.vue'),
  },
  {
    path: '/study/course/:courseId',
    name: 'study-course',
    component: () => import('../views/StudyCoursePage.vue'),
  },
  {
    path: '/study/video/:videoId',
    name: 'study-video',
    redirect: to => videoAnalysisLink(to.params.videoId),
  },
  {
    path: '/study/wiki/:pageId',
    name: 'study-wiki',
    component: () => import('../views/StudyWikiPage.vue'),
  },
  {
    path: '/study/chat',
    name: 'study-chat',
    redirect: to => ({ name: 'qa', query: to.query }),
  },
  {
    path: '/study/tasks',
    name: 'study-tasks',
    component: null,
    async beforeEnter(to) {
      const id = to.query.task
      if (typeof id !== 'string') return { name: 'analyze', replace: true }
      try {
        const task = await studyApi.task(id)
        if (task.kind === 'question') return { ...conversationLink(task.target.conversation_id), replace: true }
        if (task.kind === 'wiki') {
          return { name: 'study-course', params: { courseId: task.target.course_id }, query: { tab: 'wiki' }, replace: true }
        }
      } catch { /* 解析页负责展示无效或已过期的记录。 */ }
      return { ...analysisTaskLink(id), replace: true }
    },
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
  scrollBehavior(to, from, savedPosition) {
    return savedPosition ?? (to.path === from.path ? false : { top: 0 })
  },
})

export default router
