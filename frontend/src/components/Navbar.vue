<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePassengerSession } from '../composables/usePassengerSession'

const route  = useRoute()
const router = useRouter()
const { currentPassenger, clearPassenger } = usePassengerSession()

const profileMenuOpen = ref(false)
const profileMenuRef = ref(null)

// Don't show navbar on staff pages or landing page
const hidden = computed(() =>
  ['/', '/staff', '/staff-flights'].includes(route.path)
)

const displayName = computed(() => {
  const first = currentPassenger.value?.FirstName || ''
  const last = currentPassenger.value?.LastName || ''
  return `${first} ${last}`.trim()
})

// Show auth links (login/signup) only on pages where user may not be logged in
const isAuthPage = computed(() => route.path === '/auth')

// Breadcrumb trail based on current route
const breadcrumbs = computed(() => {
  const crumbs = [{ label: '🏠 Home', path: '/' }]

  if (route.path === '/search-results') {
    crumbs.push({ label: 'Search Results', path: null })
  } else if (route.path === '/flight-detail') {
    crumbs.push({ label: 'Search Results', path: '/search-results', query: route.query })
    crumbs.push({ label: 'Select Seat', path: null })
  } else if (route.path === '/booking-confirmation') {
    crumbs.push({ label: 'Search Results', path: '/search-results', query: route.query })
    crumbs.push({ label: 'Select Seat', path: -1 })
    crumbs.push({ label: 'Confirm Booking', path: null })
  } else if (route.path.startsWith('/booking-success')) {
    crumbs.push({ label: 'Booking Complete', path: null })
  } else if (route.path === '/my-bookings') {
    crumbs.push({ label: 'My Bookings', path: null })
  } else if (route.path === '/profile') {
    crumbs.push({ label: 'Profile', path: null })
  } else if (route.path === '/rebooking-offer') {
    crumbs.push({ label: 'My Bookings', path: '/my-bookings' })
    crumbs.push({ label: 'Rebooking Offer', path: null })
  }

  return crumbs
})

function navigate(crumb) {
  if (!crumb.path) return
  if (crumb.path === -1) { router.back(); return }
  if (crumb.path === '/') { router.push('/'); return }
  if (crumb.query) {
    router.push({ path: crumb.path, query: crumb.query })
  } else {
    router.push(crumb.path)
  }
}

function handleClearPassenger() {
  clearPassenger()
  profileMenuOpen.value = false
  router.push('/')
}

function toggleProfileMenu() {
  profileMenuOpen.value = !profileMenuOpen.value
}

function closeMenuOnOutsideClick(event) {
  if (!profileMenuRef.value?.contains(event.target)) {
    profileMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeMenuOnOutsideClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeMenuOnOutsideClick)
})
</script>

<template>
  <header
    v-if="!hidden"
    class="sticky top-0 z-50 w-full border-b border-black/[0.06] bg-white/75 backdrop-blur-2xl"
  >
    <div class="mx-auto flex h-14 max-w-[1440px] items-center justify-between px-6 md:px-10 xl:px-16">

      <!-- Left: Logo + Breadcrumbs -->
      <nav class="flex min-w-0 items-center gap-1 text-[13px]" aria-label="Breadcrumb">
        <template v-for="(crumb, i) in breadcrumbs" :key="i">
          <!-- Separator (skip for first item) -->
          <span v-if="i > 0" class="mx-1 select-none text-[#c7c7cc]">/</span>

          <!-- Clickable crumb -->
          <button
            v-if="crumb.path"
            @click="navigate(crumb)"
            class="max-w-[160px] truncate rounded-md px-2 py-1 font-semibold transition-colors hover:bg-black/5"
            :class="i === 0 ? 'text-[#1d1d1f]' : 'text-[#6e6e73] hover:text-[#1d1d1f]'"
          >
            {{ crumb.label }}
          </button>

          <!-- Current page (not clickable) -->
          <span
            v-else
            class="max-w-[160px] truncate rounded-md px-2 py-1 font-semibold text-[#e63946]"
          >
            {{ crumb.label }}
          </span>
        </template>
      </nav>

      <!-- Right: User actions -->
      <div class="flex flex-shrink-0 items-center gap-2 text-[13px]">

        <!-- Not on auth page + not logged in -->
        <template v-if="!isAuthPage && !currentPassenger">
          <router-link
            to="/auth"
            class="rounded-full border border-black/10 px-4 py-1.5 font-semibold text-[#1d1d1f] transition-all hover:bg-black/5"
          >
            Log in
          </router-link>
        </template>

        <!-- Logged in -->
        <template v-if="currentPassenger">
          <div ref="profileMenuRef" class="relative">
            <!-- Profile Trigger -->
            <button
              class="flex items-center gap-2 rounded-full border border-black/10 bg-[#f5f5f7] px-3 py-1.5 font-semibold text-[#1d1d1f] transition-all hover:bg-black/5 hover:shadow-sm"
              @click="toggleProfileMenu"
            >
              <div class="flex h-5 w-5 items-center justify-center rounded-full bg-[#1d1d1f] text-[10px] font-bold text-white">
                <svg viewBox="0 0 24 24" class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M20 21a8 8 0 0 0-16 0" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </div>
              <span class="hidden sm:block">{{ displayName }}</span>
              <svg viewBox="0 0 20 20" class="h-3.5 w-3.5 text-[#6e6e73]" fill="currentColor" aria-hidden="true">
                <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z" clip-rule="evenodd" />
              </svg>
            </button>

            <!-- Dropdown -->
            <div
              v-if="profileMenuOpen"
              class="absolute right-0 top-[calc(100%+8px)] w-44 overflow-hidden rounded-2xl border border-black/10 bg-white/95 py-1 shadow-[0_16px_30px_rgba(15,23,42,0.12)]"
            >
              <RouterLink
                to="/profile"
                class="block px-4 py-2.5 text-[11px] font-bold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
                @click="profileMenuOpen = false"
              >
                View Profile
              </RouterLink>
              <RouterLink
                to="/my-bookings"
                class="block px-4 py-2.5 text-[11px] font-bold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
                @click="profileMenuOpen = false"
              >
                My Bookings
              </RouterLink>
              <div class="mx-4 my-1 border-t border-black/8"></div>
              <button
                class="block w-full px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-[0.12em] text-[#6e6e73] transition hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
                @click="handleClearPassenger"
              >
                Log Out
              </button>
            </div>
          </div>
        </template>

      </div>
    </div>
  </header>
</template>
