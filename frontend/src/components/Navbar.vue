<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route  = useRoute()
const router = useRouter()

// Breadcrumb trail based on current route
const breadcrumbs = computed(() => {
  const crumbs = [{ label: 'Home', path: '/' }]

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
</script>

<template>
  <header
    class="sticky top-0 z-50 w-full border-b border-black/[0.06] bg-white/75 backdrop-blur-2xl"
  >
    <div class="mx-auto flex h-14 max-w-[1440px] items-center px-6 md:px-10 xl:px-16">

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
    </div>
  </header>
</template>
