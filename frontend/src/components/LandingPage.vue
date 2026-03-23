<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { usePassengerSession } from '../composables/usePassengerSession'
import { useRouter } from 'vue-router'

const router = useRouter() 

const booking = ref({
  tripType: 'round-trip',
  departingCountry: '',
  arrivingCountry: '',
  departureDate: '',
  returnDate: '',
  passengers: 1,
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
const datePickerOpen = ref(false)
const datePickerRef = ref(null)
const datePickerMonth = ref(startOfMonth(new Date()))
const activeDateField = ref('departure')

const weekDays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const leftMonth = computed(() => datePickerMonth.value)
const rightMonth = computed(() => addMonths(datePickerMonth.value, 1))
const leftMonthCells = computed(() => buildCalendarCells(leftMonth.value))
const rightMonthCells = computed(() => buildCalendarCells(rightMonth.value))

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function addMonths(date, months) {
  return new Date(date.getFullYear(), date.getMonth() + months, 1)
}

function toISODate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseISODate(value) {
  if (!value) return null
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function buildCalendarCells(monthDate) {
  const firstDay = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
  const daysInMonth = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0).getDate()
  const mondayBasedOffset = (firstDay.getDay() + 6) % 7

  const cells = []
  for (let i = 0; i < mondayBasedOffset; i += 1) {
    cells.push(null)
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push(new Date(monthDate.getFullYear(), monthDate.getMonth(), day))
  }

  while (cells.length % 7 !== 0) {
    cells.push(null)
  }

  return cells
}

function formatMonthYear(date) {
  return new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(date)
}

function formatDateLabel(value) {
  const date = parseISODate(value)
  if (!date) return 'Select date'
  return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(date)
}

function isPastDate(date) {
  if (!date) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date < today
}

function isSameDate(date, value) {
  if (!date || !value) return false
  return toISODate(date) === value
}

function isWithinRange(date) {
  if (!date || !booking.value.departureDate || !booking.value.returnDate) return false
  const current = toISODate(date)
  return current > booking.value.departureDate && current < booking.value.returnDate
}

function selectTravelDate(date) {
  if (!date || isPastDate(date)) return

  const picked = toISODate(date)

  if (booking.value.tripType === 'one-way') {
    booking.value.departureDate = picked
    booking.value.returnDate = ''
    datePickerOpen.value = false
    return
  }

  if (activeDateField.value === 'departure') {
    booking.value.departureDate = picked
    booking.value.returnDate = booking.value.returnDate && booking.value.returnDate >= picked
      ? booking.value.returnDate
      : ''
    activeDateField.value = 'return'
    return
  }

  if (!booking.value.departureDate) {
    booking.value.departureDate = picked
    booking.value.returnDate = ''
    activeDateField.value = 'return'
    return
  }

  if (picked < booking.value.departureDate) {
    booking.value.departureDate = picked
    booking.value.returnDate = ''
    activeDateField.value = 'return'
    return
  }

  booking.value.returnDate = picked
}

function toggleDatePicker(target = 'departure') {
  activeDateField.value = target
  datePickerOpen.value = true
  const baseDate = parseISODate(booking.value.departureDate)
  if (baseDate) {
    datePickerMonth.value = startOfMonth(baseDate)
  }
}

function shiftMonth(step) {
  datePickerMonth.value = addMonths(datePickerMonth.value, step)
}

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
  
  // Validate return date for round trip
  if (booking.value.tripType === 'round-trip' && !booking.value.returnDate) {
    alert('Please select a return date for round trips')
    return
  }

  if (booking.value.tripType === 'round-trip' && booking.value.returnDate < booking.value.departureDate) {
    alert('Return date cannot be earlier than departure date')
    return
  }
  
  // Navigate to search results with query params
  router.push({
    path: '/search-results',
    query: {
      tripType: booking.value.tripType,
      departingCountry: booking.value.departingCountry,
      arrivingCountry: booking.value.arrivingCountry,
      departureDate: booking.value.departureDate,
      returnDate: booking.value.returnDate || '',
      passengers: booking.value.passengers,
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

  const clickedDatePicker = datePickerRef.value?.contains(event.target)
  if (!clickedDatePicker) {
    datePickerOpen.value = false
  }
}

watch(
  () => booking.value.tripType,
  (newType) => {
    if (newType === 'one-way') {
      booking.value.returnDate = ''
      activeDateField.value = 'departure'
    }
  }
)

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
        <!-- Nav removed per request -->

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
            <RouterLink
              to="/my-bookings"
              class="block px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
              @click="profileMenuOpen = false"
            >
              My Bookings
            </RouterLink>
            <div class="mx-4 my-1 border-t border-black/8"></div>
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

      <section id="booking" class="relative z-20 animate__animated animate__fadeInUp animate__delay-1s mt-12 md:mt-16">
        <!-- Outer glow atmosphere -->
        <div class="relative">
          <div class="pointer-events-none absolute -inset-4 rounded-[48px] bg-gradient-to-br from-[#e63946]/10 via-transparent to-[#ff6b6b]/5 blur-2xl"></div>

          <!-- Main card -->
          <div class="relative overflow-visible rounded-[36px] border border-white/40 bg-white/80 shadow-[0_32px_80px_rgba(15,23,42,0.14)] backdrop-blur-3xl">

            <!-- Decorative top gradient strip -->
            <div class="h-1 w-full bg-gradient-to-r from-[#e63946] via-[#ff6b6b] to-[#f43f5e]"></div>

            <div class="p-6 md:p-10">

              <!-- Top row: Title + Trip type toggle -->
              <div class="mb-8 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p class="text-[10px] font-bold uppercase tracking-[0.22em] text-[#e63946]">Blaze Air</p>
                  <h2 class="mt-1 text-2xl font-bold tracking-[-0.025em] text-[#1d1d1f] md:text-3xl">Where to next?</h2>
                </div>

                <div class="rounded-2xl border border-black/8 bg-[#f5f5f7] p-1">
                  <div class="grid grid-cols-2 gap-1">
                    <button
                      type="button"
                      class="inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-[13px] font-semibold transition-all duration-200"
                      :class="booking.tripType === 'one-way' ? 'bg-white text-[#111827] shadow-sm' : 'text-[#6e6e73] hover:text-[#111827]'"
                      @click="booking.tripType = 'one-way'"
                    >
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12h18M15 6l6 6-6 6"/></svg>
                      One-way
                    </button>
                    <button
                      type="button"
                      class="inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-[13px] font-semibold transition-all duration-200"
                      :class="booking.tripType === 'round-trip' ? 'bg-white text-[#111827] shadow-sm' : 'text-[#6e6e73] hover:text-[#111827]'"
                      @click="booking.tripType = 'round-trip'"
                    >
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 7h14m0 0l-4-4m4 4l-4 4M21 17H7m0 0l4-4m-4 4l4 4"/></svg>
                      Return
                    </button>
                  </div>
                </div>
              </div>

              <form @submit.prevent="submitSearch" class="space-y-4">

                <!-- Row 1: From / Swap / To -->
                <div class="flex items-end gap-3">
                  <!-- From -->
                  <div class="flex-1">
                    <label class="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-[#6e6e73]">
                      <svg class="h-3 w-3" fill="currentColor" viewBox="0 0 24 24"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>
                      From
                    </label>
                    <div class="relative">
                      <select
                        v-model="booking.departingCountry"
                        class="w-full appearance-none rounded-2xl border border-black/8 bg-[#f7f7f8] py-4 pl-5 pr-10 text-sm font-semibold text-[#1d1d1f] outline-none transition-all duration-200 focus:border-[#e63946]/50 focus:bg-white focus:shadow-[0_0_0_4px_rgba(230,57,70,0.08)] focus:ring-0"
                      >
                        <option value="" disabled>Select origin city</option>
                        <option>Bangkok</option>
                        <option>Dubai</option>
                        <option>Edinburgh</option>
                        <option>London</option>
                        <option>New York</option>
                        <option>Singapore</option>
                        <option>Tokyo</option>
                      </select>
                      <div class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#6e6e73]">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                      </div>
                    </div>
                  </div>

                  <!-- Swap button -->
                  <button
                    type="button"
                    class="mb-0.5 flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl border border-black/8 bg-white text-[#6e6e73] shadow-sm transition-all duration-300 hover:border-[#e63946]/40 hover:text-[#e63946] hover:shadow-[0_0_20px_rgba(230,57,70,0.15)] hover:rotate-180"
                    @click="[booking.departingCountry, booking.arrivingCountry] = [booking.arrivingCountry, booking.departingCountry]"
                    title="Swap origin and destination"
                  >
                    <svg class="h-4 w-4 transition-transform" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4"/>
                    </svg>
                  </button>

                  <!-- To -->
                  <div class="flex-1">
                    <label class="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-[#6e6e73]">
                      <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                      To
                    </label>
                    <div class="relative">
                      <select
                        v-model="booking.arrivingCountry"
                        class="w-full appearance-none rounded-2xl border border-black/8 bg-[#f7f7f8] py-4 pl-5 pr-10 text-sm font-semibold text-[#1d1d1f] outline-none transition-all duration-200 focus:border-[#e63946]/50 focus:bg-white focus:shadow-[0_0_0_4px_rgba(230,57,70,0.08)] focus:ring-0"
                      >
                        <option value="" disabled>Select destination city</option>
                        <option>Bangkok</option>
                        <option>Dubai</option>
                        <option>Edinburgh</option>
                        <option>London</option>
                        <option>New York</option>
                        <option>Singapore</option>
                        <option>Tokyo</option>
                      </select>
                      <div class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#6e6e73]">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Row 2: Dates + Passengers -->
                <div class="grid gap-4" :class="booking.tripType === 'round-trip' ? 'md:grid-cols-3' : 'md:grid-cols-2'">
                  <div ref="datePickerRef" class="relative" :class="booking.tripType === 'round-trip' ? 'md:col-span-2' : ''">
                    <div class="grid gap-4" :class="booking.tripType === 'round-trip' ? 'md:grid-cols-2' : 'md:grid-cols-1'">
                      <div>
                        <label class="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-[#6e6e73]">
                          <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                          Departure
                        </label>
                        <button
                          type="button"
                          class="w-full rounded-2xl border bg-[#f7f7f8] px-5 py-4 text-left outline-none transition-all duration-200 hover:border-black/20 focus:border-[#e63946]/50 focus:bg-white focus:shadow-[0_0_0_4px_rgba(230,57,70,0.08)]"
                          :class="datePickerOpen && activeDateField === 'departure' ? 'border-[#e63946]/40' : 'border-black/8'"
                          @click="toggleDatePicker('departure')"
                        >
                          <p class="text-sm font-semibold text-[#1d1d1f]">{{ booking.departureDate ? formatDateLabel(booking.departureDate) : 'Select departure date' }}</p>
                          <p class="mt-1 text-xs text-[#6e6e73]">Choose your outbound flight date</p>
                        </button>
                      </div>

                      <div v-if="booking.tripType === 'round-trip'">
                        <label class="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-[#6e6e73]">
                          <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                          Return
                        </label>
                        <button
                          type="button"
                          class="w-full rounded-2xl border bg-[#f7f7f8] px-5 py-4 text-left outline-none transition-all duration-200 hover:border-black/20 focus:border-[#e63946]/50 focus:bg-white focus:shadow-[0_0_0_4px_rgba(230,57,70,0.08)]"
                          :class="datePickerOpen && activeDateField === 'return' ? 'border-[#e63946]/40' : 'border-black/8'"
                          @click="toggleDatePicker('return')"
                        >
                          <p class="text-sm font-semibold text-[#1d1d1f]">{{ booking.returnDate ? formatDateLabel(booking.returnDate) : 'Select return date' }}</p>
                          <p class="mt-1 text-xs text-[#6e6e73]">Choose your inbound flight date</p>
                        </button>
                      </div>
                    </div>

                    <div
                      v-if="datePickerOpen"
                      class="absolute z-50 mt-3 w-full min-w-[320px] rounded-2xl border border-black/10 bg-white p-4 shadow-[0_16px_40px_rgba(15,23,42,0.16)] md:min-w-[680px]"
                    >
                      <div class="mb-4 flex items-center justify-between">
                        <p class="text-xs font-bold uppercase tracking-[0.14em] text-[#6e6e73]">
                          {{ booking.tripType === 'round-trip' ? (activeDateField === 'departure' ? 'Select departure date' : 'Select return date') : 'Select departure date' }}
                        </p>
                        <div class="flex items-center gap-2">
                          <button type="button" class="rounded-lg border border-black/10 px-2.5 py-1 text-sm text-[#374151] transition hover:bg-[#f5f5f7]" @click="shiftMonth(-1)">‹</button>
                          <button type="button" class="rounded-lg border border-black/10 px-2.5 py-1 text-sm text-[#374151] transition hover:bg-[#f5f5f7]" @click="shiftMonth(1)">›</button>
                        </div>
                      </div>

                      <div class="grid gap-4 md:grid-cols-2">
                        <section>
                          <h4 class="mb-2 text-sm font-semibold text-[#111827]">{{ formatMonthYear(leftMonth) }}</h4>
                          <div class="mb-1 grid grid-cols-7 gap-1">
                            <span v-for="day in weekDays" :key="`left-${day}`" class="py-1 text-center text-[10px] font-semibold uppercase tracking-[0.08em] text-[#9ca3af]">{{ day }}</span>
                          </div>
                          <div class="grid grid-cols-7 gap-1">
                            <button
                              v-for="(cell, index) in leftMonthCells"
                              :key="`left-cell-${index}`"
                              type="button"
                              class="h-9 rounded-lg text-sm transition"
                              :class="[
                                !cell ? 'invisible' : '',
                                cell && isPastDate(cell) ? 'cursor-not-allowed text-[#d1d5db]' : 'text-[#1f2937] hover:bg-[#f3f4f6]',
                                cell && isWithinRange(cell) ? 'bg-[#eef2ff]' : '',
                                cell && (isSameDate(cell, booking.departureDate) || isSameDate(cell, booking.returnDate)) ? 'bg-[#e63946] text-white hover:bg-[#e63946]' : ''
                              ]"
                              :disabled="!cell || isPastDate(cell)"
                              @click="selectTravelDate(cell)"
                            >
                              {{ cell ? cell.getDate() : '' }}
                            </button>
                          </div>
                        </section>

                        <section>
                          <h4 class="mb-2 text-sm font-semibold text-[#111827]">{{ formatMonthYear(rightMonth) }}</h4>
                          <div class="mb-1 grid grid-cols-7 gap-1">
                            <span v-for="day in weekDays" :key="`right-${day}`" class="py-1 text-center text-[10px] font-semibold uppercase tracking-[0.08em] text-[#9ca3af]">{{ day }}</span>
                          </div>
                          <div class="grid grid-cols-7 gap-1">
                            <button
                              v-for="(cell, index) in rightMonthCells"
                              :key="`right-cell-${index}`"
                              type="button"
                              class="h-9 rounded-lg text-sm transition"
                              :class="[
                                !cell ? 'invisible' : '',
                                cell && isPastDate(cell) ? 'cursor-not-allowed text-[#d1d5db]' : 'text-[#1f2937] hover:bg-[#f3f4f6]',
                                cell && isWithinRange(cell) ? 'bg-[#eef2ff]' : '',
                                cell && (isSameDate(cell, booking.departureDate) || isSameDate(cell, booking.returnDate)) ? 'bg-[#e63946] text-white hover:bg-[#e63946]' : ''
                              ]"
                              :disabled="!cell || isPastDate(cell)"
                              @click="selectTravelDate(cell)"
                            >
                              {{ cell ? cell.getDate() : '' }}
                            </button>
                          </div>
                        </section>
                      </div>
                    </div>
                  </div>

                  <!-- Passengers -->
                  <div>
                    <label class="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-[#6e6e73]">
                      <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0"/></svg>
                      Passengers
                    </label>
                    <div class="flex items-center overflow-hidden rounded-2xl border border-black/8 bg-[#f7f7f8]">
                      <button
                        type="button"
                        class="px-4 py-4 text-lg font-semibold text-[#6e6e73] transition hover:bg-black/5 hover:text-[#1d1d1f] disabled:opacity-30"
                        :disabled="booking.passengers <= 1"
                        @click="booking.passengers--"
                      >−</button>
                      <span class="flex-1 text-center text-sm font-bold text-[#1d1d1f]">{{ booking.passengers }} {{ booking.passengers === 1 ? 'Passenger' : 'Passengers' }}</span>
                      <button
                        type="button"
                        class="px-4 py-4 text-lg font-semibold text-[#6e6e73] transition hover:bg-black/5 hover:text-[#1d1d1f] disabled:opacity-30"
                        :disabled="booking.passengers >= 12"
                        @click="booking.passengers++"
                      >+</button>
                    </div>
                  </div>
                </div>

                <!-- Search button -->
                <button
                  type="submit"
                  class="group relative mt-2 w-full overflow-hidden rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] py-4 text-sm font-bold uppercase tracking-[0.18em] text-white shadow-[0_8px_30px_rgba(230,57,70,0.35)] transition-all duration-300 hover:shadow-[0_12px_40px_rgba(230,57,70,0.5)] hover:-translate-y-0.5 active:translate-y-0"
                >
                  <!-- Light sweep -->
                  <div class="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 group-hover:translate-x-full"></div>
                  <span class="relative flex items-center justify-center gap-3">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/></svg>
                    Search Flights
                    <svg class="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7"/></svg>
                  </span>
                </button>

              </form>
            </div>
          </div>
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