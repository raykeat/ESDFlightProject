import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../components/LandingPage.vue'
import AuthPage from '../pages/AuthPage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import SearchResults from '../pages/SearchResults.vue' 
import BookingConfirmation from '../pages/BookingConfirmation.vue'  
import BookingSuccess from '../pages/BookingSuccess.vue'

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
    {
      path: '/search-results',
      name: 'search-results',
      component: SearchResults
    },
    {
      path: '/booking-confirmation',
      name: 'booking-confirmation',
      component: BookingConfirmation
    },
    {
      path: '/booking-success/:bookingID',
      name: 'booking-success',
      component: BookingSuccess
    }
  ],
})

export default router
