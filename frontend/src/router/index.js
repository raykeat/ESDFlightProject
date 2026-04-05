import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../components/LandingPage.vue'
import AuthPage from '../pages/AuthPage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import SearchResults from '../pages/SearchResults.vue' 
import PassengerDetails from '../pages/PassengerDetails.vue'
import BookingConfirmation from '../pages/BookingConfirmation.vue'  
import BookingSuccess from '../pages/BookingSuccess.vue'
import MyBookings from '../pages/MyBookings.vue'
import RebookingOffer from '../pages/RebookingOffer.vue'
import RebookingSeatSelection from '../pages/RebookingSeatSelection.vue'
import StaffAuth    from '../pages/StaffAuth.vue'
import StaffFlights from '../pages/StaffFlights.vue'
import FlightDetail from '../pages/FlightDetail.vue'
import ConvertMiles from '../pages/ConvertMiles.vue'
import MyVouchers from '../pages/MyVouchers.vue'
import MilesConversionDashboard from '../pages/MilesConversionDashboard.vue'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }

    return { top: 0 }
  },
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
      path: '/passenger-details',
      name: 'passenger-details',
      component: PassengerDetails
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
      path: '/flight-detail',
      name: 'flight-detail',
      component: FlightDetail
    },
    {
      path: '/rebooking-offer',
      name: 'rebooking-offer',
      component: RebookingOffer
    },
    {
      path: '/rebooking-seat-selection',
      name: 'rebooking-seat-selection',
      component: RebookingSeatSelection
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
    },
    {
      path: '/loyalty/convert',
      name: 'loyalty-convert',
      component: ConvertMiles
    },
    {
      path: '/my-vouchers',
      name: 'my-vouchers',
      component: MyVouchers
    },
    {
      path: '/loyalty/history',
      name: 'loyalty-history',
      component: MilesConversionDashboard
    }
  ],
})

export default router
