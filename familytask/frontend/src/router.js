import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Signup from './views/Signup.vue'
import TasksView from './views/TasksView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    { path: '/login', component: Login, meta: { guestOnly: true } },
    { path: '/signup', component: Signup, meta: { guestOnly: true } },
    { path: '/tasks', component: TasksView, meta: { requiresAuth: true } },
  ],
})

// Redirige les visiteurs non authentifiés vers l'écran de connexion.
router.beforeEach((to) => {
  const hasToken = Boolean(localStorage.getItem('token'))
  if (to.meta.requiresAuth && !hasToken) return '/login'
  if (to.meta.guestOnly && hasToken) return '/tasks'
  return true
})

export default router