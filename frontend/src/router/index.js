import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../components/LandingPage.vue'
import AuthPage from '../pages/AuthPage.vue'
import ProfilePage from '../pages/ProfilePage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: LandingPage,
    },
    {
      path: '/auth',
      name: 'auth',
      component: AuthPage,
    },
    {
      path: '/profile',
      name: 'profile',
      component: ProfilePage,
    },
  ],
})

export default router
