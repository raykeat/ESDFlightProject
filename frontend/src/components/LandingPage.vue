<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { usePassengerSession } from '../composables/usePassengerSession'
import { useRouter } from 'vue-router'

const router = useRouter() 

const booking = ref({
  departingCountry: '',
  arrivingCountry: '',
  departureDate: '',
  returnDate: '',
  passengers: 1,
  cabin: 'Business',
})

const highlights = [
  {
    title: 'Quiet Cabin Design',
    description: 'Acoustic engineering inspired by private lounges and studio-grade silence.',
  },
  {
    title: 'Curated Arrival Service',
    description: 'Priority exits, concierge transfer options, and city-side fast-track guidance.',
  },
  {
    title: 'Flexible Signature Fare',
    description: 'One fare class with adaptive baggage, seat, and date-change controls built in.',
  },
]

const { currentPassenger, isSignedIn, clearPassenger } = usePassengerSession()
const profileMenuOpen = ref(false)
const profileMenuRef = ref(null)

const displayName = computed(() => {
  const first = currentPassenger.value?.FirstName || ''
  const last = currentPassenger.value?.LastName || ''
  return `${first} ${last}`.trim()
})

function submitSearch() {
  console.log('Search submitted', booking.value)

  // Validate required fields
  if (!booking.value.departingCountry || !booking.value.arrivingCountry || !booking.value.departureDate) {
    alert('Please fill in all required fields')
    return
  }
  
  // Navigate to search results with query params
  router.push({
    path: '/search-results',
    query: {
      departingCountry: booking.value.departingCountry,
      arrivingCountry: booking.value.arrivingCountry,
      departureDate: booking.value.departureDate,
      returnDate: booking.value.returnDate || '',
      passengers: booking.value.passengers,
      cabin: booking.value.cabin
    }
  })
}

function handleLogout() {
  clearPassenger()
  profileMenuOpen.value = false
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
  <main class="relative overflow-hidden pb-20">
    <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_90%_8%,rgba(230,57,70,0.16),transparent_34%),radial-gradient(circle_at_12%_82%,rgba(255,255,255,0.7),transparent_40%)]" />

    <section class="relative mx-auto max-w-[1240px] px-6 pt-6 md:px-10 lg:px-16">
      <header class="animate__animated animate__fadeInDown sticky top-4 z-20 flex items-center justify-between rounded-[28px] border border-black/5 bg-white/75 px-5 py-3 backdrop-blur-xl md:px-7">
        <span class="text-sm font-semibold tracking-[0.18em] text-[#1d1d1f]">BLAZE AIR</span>
        <nav class="hidden items-center gap-8 text-sm font-medium text-[#6e6e73] md:flex">
          <a href="#experience" class="transition-colors duration-300 hover:text-[#1d1d1f]">Experience</a>
          <a href="#booking" class="transition-colors duration-300 hover:text-[#1d1d1f]">Book</a>
          <a href="#fleet" class="transition-colors duration-300 hover:text-[#1d1d1f]">Fleet</a>
        </nav>

        <RouterLink
          v-if="!isSignedIn"
          to="/auth"
          class="rounded-full border border-[#e63946]/40 bg-white/80 px-5 py-2 text-xs font-semibold tracking-[0.12em] text-[#1d1d1f] transition-all duration-300 hover:border-[#e63946] hover:shadow-[0_0_24px_rgba(230,57,70,0.3)]"
        >
          Sign In
        </RouterLink>

        <div v-else ref="profileMenuRef" class="relative">
          <button
            class="flex items-center gap-2 rounded-full border border-black/10 bg-white/85 px-3 py-1.5"
            @click="toggleProfileMenu"
          >
            <span class="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#1d1d1f] text-white">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M20 21a8 8 0 0 0-16 0" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </span>
            <span class="text-xs font-semibold tracking-[0.08em] text-[#1d1d1f]">{{ displayName }}</span>
            <svg viewBox="0 0 20 20" class="h-4 w-4 text-[#6e6e73]" fill="currentColor" aria-hidden="true">
              <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z" clip-rule="evenodd" />
            </svg>
          </button>

          <div
            v-if="profileMenuOpen"
            class="absolute right-0 mt-2 w-44 overflow-hidden rounded-2xl border border-black/10 bg-white/95 py-1 shadow-[0_16px_30px_rgba(15,23,42,0.12)]"
          >
            <RouterLink
              to="/profile"
              class="block px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
              @click="profileMenuOpen = false"
            >
              View Profile
            </RouterLink>
            <button
              class="block w-full px-4 py-2 text-left text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73] transition hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
              @click="handleLogout"
            >
              Log Out
            </button>
          </div>
        </div>
      </header>

      <section class="animate__animated animate__fadeInUp pt-14 text-center md:pt-20">
        <p class="text-xs font-semibold uppercase tracking-[0.24em] text-[#6e6e73]">New Generation Air Travel</p>
        <h1 class="mx-auto mt-4 max-w-4xl text-5xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-7xl lg:text-8xl">
          Fly the world with cinematic calm.
        </h1>
        <p class="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-[#6e6e73] md:text-lg">
          Blaze Air blends precision routing with refined onboard design for travelers who value simplicity, speed, and a quieter way to move.
        </p>
      </section>

      <section id="booking" class="animate__animated animate__fadeInUp animate__delay-1s mt-12 md:mt-16">
        <div class="rounded-[34px] border border-black/5 bg-white/85 p-5 shadow-[0_22px_52px_rgba(15,23,42,0.08)] backdrop-blur-2xl md:p-8">
          <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h2 class="text-2xl font-semibold tracking-[-0.02em] text-[#1d1d1f] md:text-3xl">Search flights</h2>
            <span class="rounded-full border border-[#e63946]/20 bg-[#e63946]/6 px-4 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-[#e63946]">
              Fast Booking
            </span>
          </div>

          <form class="grid gap-4 md:grid-cols-2 lg:grid-cols-6" @submit.prevent="submitSearch">
            <label class="lg:col-span-1">
              <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Departing Country</span>
              <input
                v-model="booking.departingCountry"
                type="text"
                placeholder="United States"
                class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
              />
            </label>

            <label class="lg:col-span-1">
              <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Arriving Country</span>
              <input
                v-model="booking.arrivingCountry"
                type="text"
                placeholder="Japan"
                class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
              />
            </label>

            <label class="lg:col-span-1">
              <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Departure Date</span>
              <input
                v-model="booking.departureDate"
                type="date"
                class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
              />
            </label>

            <label class="lg:col-span-1">
              <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Return Date</span>
              <input
                v-model="booking.returnDate"
                type="date"
                class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
              />
            </label>

            <label class="lg:col-span-1">
              <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">No. Pax</span>
              <input
                v-model.number="booking.passengers"
                min="1"
                max="12"
                type="number"
                class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
              />
            </label>

            <label class="lg:col-span-1">
              <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Cabin</span>
              <select
                v-model="booking.cabin"
                class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
              >
                <option>Economy</option>
                <option>Premium Economy</option>
                <option>Business</option>
                <option>First</option>
              </select>
            </label>

            <button
              type="submit"
              class="md:col-span-2 lg:col-span-6 mt-2 w-full rounded-2xl bg-[#1d1d1f] px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-black hover:shadow-[0_8px_24px_rgba(29,29,31,0.35)]"
            >
              Search Flights
            </button>
          </form>
        </div>
      </section>

      <section id="experience" class="animate__animated animate__fadeInUp animate__delay-3s mt-14 grid gap-5 md:grid-cols-3">
        <article
          v-for="item in highlights"
          :key="item.title"
          class="rounded-[28px] border border-black/6 bg-white/80 p-6 shadow-[0_18px_36px_rgba(15,23,42,0.06)] backdrop-blur"
        >
          <p class="text-xs font-semibold uppercase tracking-[0.15em] text-[#e63946]">Blaze Standard</p>
          <h3 class="mt-3 text-2xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">{{ item.title }}</h3>
          <p class="mt-3 text-sm leading-relaxed text-[#6e6e73]">{{ item.description }}</p>
        </article>
      </section>
    </section>
  </main>
</template>
