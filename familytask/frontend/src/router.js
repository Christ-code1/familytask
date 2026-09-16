import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Signup from './views/Signup.vue'
import TasksView from './views/TasksView.vue'
import FamilyView from './views/FamilyView.vue'
import AssistantView from './views/AssistantView.vue'
import { apiFetch } from './api'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    { path: '/login', component: Login, meta: { guestOnly: true } },
    { path: '/signup', component: Signup, meta: { guestOnly: true } },
    { path: '/tasks', component: TasksView, meta: { requiresAuth: true } },
    { path: '/family', component: FamilyView, meta: { requiresAuth: true, adminOnly: true } },
    { path: '/assistant', component: AssistantView, meta: { requiresAuth: true } },
  ],
})

// Redirige les visiteurs non authentifiés vers l'écran de connexion.
router.beforeEach(async (to) => {
  const hasToken = Boolean(localStorage.getItem('token'))
  if (to.meta.requiresAuth && !hasToken) return '/login'
  if (to.meta.guestOnly && hasToken) return '/tasks'
  if (to.meta.adminOnly) {
    const response = await apiFetch('/api/me')
    if (!response.ok || !(await response.json()).is_admin) return '/tasks'
  }
  return true
})

export default router