import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../components/LandingPage.vue'
import AuthPage from '../pages/AuthPage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import SearchResults from '../pages/SearchResults.vue' 
import SeatSelector from '../pages/SeatSelector.vue'
import BookingConfirmation from '../pages/BookingConfirmation.vue'  
import BookingSuccess from '../pages/BookingSuccess.vue'
import MyBookings from '../pages/MyBookings.vue'
import RebookingOffer from '../pages/RebookingOffer.vue'
import StaffAuth    from '../pages/StaffAuth.vue'
import StaffFlights from '../pages/StaffFlights.vue'

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
      path: '/flight-details',
      name: 'flight-details',
      component: SeatSelector
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
    },
    {
      path: '/my-bookings',
      name: 'my-bookings',
      component: MyBookings
    },
    {
      path: '/rebooking-offer',
      name: 'rebooking-offer',
      component: RebookingOffer
    },
    {
      path: '/staff/login',
      name: 'staff-login',
      component: StaffAuth
    },
    {
      path: '/staff/flights',
      name: 'staff-flights',
      component: StaffFlights
    }
  ],
})

export default router