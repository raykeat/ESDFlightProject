<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Navbar from './components/Navbar.vue'
import AppNav from './components/AppNav.vue'

const route = useRoute()

const isStaffRoute = computed(() => route.path.startsWith('/staff'))
const isLandingRoute = computed(() => route.path === '/')
const bookingFlowRoutes = ['search-results', 'flight-detail', 'booking-confirmation', 'booking-success']

const showBookingNavbar = computed(() => bookingFlowRoutes.includes(route.name))
const showDefaultNavbar = computed(() => !isStaffRoute.value && !isLandingRoute.value && !showBookingNavbar.value)
</script>

<template>
  <Navbar v-if="showBookingNavbar" />
  <AppNav v-else-if="showDefaultNavbar" />
  <router-view />
</template>
