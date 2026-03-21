<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()

// ─── Search params from URL ──────────────────────────────
const searchParams = ref({
  tripType: route.query.tripType || 'one-way',
  departingCountry: route.query.departingCountry,
  arrivingCountry: route.query.arrivingCountry,
  departureDate: route.query.departureDate,
  returnDate: route.query.returnDate,
  passengers: parseInt(route.query.passengers) || 1,
})

const isRoundTrip = computed(() => searchParams.value.tripType === 'round-trip')

// ─── Flight data ─────────────────────────────────────────
const outboundFlights = ref([])
const returnFlights = ref([])
const loading = ref(true)
const loadingReturn = ref(false)

// ─── Selection state ─────────────────────────────────────
// step: 'outbound' | 'return' | 'done'
const step = ref(route.query.step || 'outbound')

const selectedOutbound = ref(route.query.outboundFlightID ? {
  flightID:     route.query.outboundFlightID,
  flightNumber: route.query.outboundFlightNumber,
  origin:       route.query.outboundOrigin,
  destination:  route.query.outboundDestination,
  price:        route.query.outboundPrice
} : null)

const selectedOutboundSeat = ref(route.query.outboundSeat || null)
const selectedReturn = ref(null)

// ─── Fetch outbound flights on mount ─────────────────────
onMounted(async () => {
  if (step.value === 'return') {
    loading.value = false
    await fetchReturnFlights()
    return
  }

  loading.value = true
  try {
    const response = await axios.get('http://localhost:3003/flight/available', {
      params: {
        origin: searchParams.value.departingCountry,
        dest: searchParams.value.arrivingCountry,
        dateFrom: searchParams.value.departureDate,
      },
    })
    outboundFlights.value = response.data.map(formatFlight)
  } catch (e) {
    console.error('Error fetching outbound flights:', e)
  } finally {
    loading.value = false
  }
})

// ─── Fetch return flights once outbound seat is chosen ────
async function fetchReturnFlights() {
  loadingReturn.value = true
  try {
    const response = await axios.get('http://localhost:3003/flight/available', {
      params: {
        origin: searchParams.value.arrivingCountry,
        dest: searchParams.value.departingCountry,
        dateFrom: searchParams.value.returnDate,
      },
    })
    returnFlights.value = response.data.map(formatFlight)
  } catch (e) {
    console.error('Error fetching return flights:', e)
  } finally {
    loadingReturn.value = false
  }
}

// ─── Format helpers ──────────────────────────────────────
function formatTime12h(isoString) {
  if (!isoString) return '--'
  const d = new Date(isoString)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true })
}

function formatDuration(d) {
  if (!d) return '--'
  const clean = String(d).replace('h', '').trim()
  const [h, m = '00'] = clean.split(':')
  return `${parseInt(h)}h ${String(m).padStart(2, '0')}m`
}

function formatFlight(f) {
  const [day, month, year] = f.Date.split('/')
  const depDate = new Date(`${year}-${month}-${day}`)

  // Detect overnight: arrival time < departure time means it crossed midnight
  const [depH, depM] = f.DepartureTime.split(':').map(Number)
  const [arrH, arrM] = f.ArrivalTime.split(':').map(Number)
  const isNextDay = arrH * 60 + arrM < depH * 60 + depM

  const arrDate = new Date(depDate)
  if (isNextDay) arrDate.setDate(arrDate.getDate() + 1)

  const fmt = (d) => d.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric', month: 'short' })

  return {
    flightID:      f.FlightID,
    flightNumber:  f.FlightNumber,
    origin:        f.Origin,
    destination:   f.Destination,
    departureTime: `${year}-${month}-${day}T${f.DepartureTime}:00`,
    arrivalTime:   `${year}-${month}-${day}T${f.ArrivalTime}:00`,
    price:         f.Price,
    duration:      f.FlightDuration,
    departureDate: fmt(depDate),
    arrivalDate:   fmt(arrDate),
    isNextDay,
    availableSeats: 30,
    meals:         f.Meals,
    beverages:     f.Beverages,
    wifi:          f.Wifi,
    baggage:       f.Baggage,
  }
}

// ─── User actions ─────────────────────────────────────────
function selectOutbound(flight) {
  selectedOutbound.value = flight
}

function selectReturn(flight) {
  selectedReturn.value = flight
}

async function openFlightDetailWithComposite(flight, query) {
  try {
    const response = await axios.get(`http://localhost:5011/flight-search/${flight.flightID}`)
    sessionStorage.setItem(`flightSearchComposite:${flight.flightID}`, JSON.stringify(response.data))
  } catch (e) {
    console.error('Error prefetching flight composite:', e)
  }

  router.push({
    path: '/flight-detail',
    query,
  })
}

// Called when user confirms their outbound flight selection
async function confirmOutbound() {
  const detailQuery = {
    flightID:         selectedOutbound.value.flightID,
    isReturn:         'false',
    tripType:         isRoundTrip.value ? searchParams.value.tripType : 'one-way',
    departingCountry: searchParams.value.departingCountry,
    arrivingCountry:  searchParams.value.arrivingCountry,
    departureDate:    searchParams.value.departureDate,
    returnDate:       searchParams.value.returnDate,
    passengers:       searchParams.value.passengers,
  }

  if (isRoundTrip.value) {
    // For round trip: go to FlightDetail for outbound seat selection first
    await openFlightDetailWithComposite(selectedOutbound.value, detailQuery)
  } else {
    // One-way: go directly to FlightDetail for seat selection
    await openFlightDetailWithComposite(selectedOutbound.value, detailQuery)
  }
}

// Round-trip: after selecting return flight, go to FlightDetail for return seat selection
function proceedToBooking() {
  if (!currentPassenger.value) {
    router.push({ path: '/auth', query: { redirect: '/search-results', ...searchParams.value, step: 'return', outboundFlightID: selectedOutbound.value.flightID, outboundFlightNumber: selectedOutbound.value.flightNumber, outboundOrigin: selectedOutbound.value.origin, outboundDestination: selectedOutbound.value.destination, outboundPrice: selectedOutbound.value.price, outboundSeat: selectedOutboundSeat.value } })
    return
  }

  // Navigate to FlightDetail for the return flight seat selection
  openFlightDetailWithComposite(selectedReturn.value, {
    flightID:             selectedReturn.value.flightID,
    isReturn:             'true',
    outboundFlightID:     selectedOutbound.value.flightID,
    outboundFlightNumber: selectedOutbound.value.flightNumber,
    outboundSeat:         selectedOutboundSeat.value,
    outboundPrice:        selectedOutbound.value.price,
    tripType:             searchParams.value.tripType,
    departingCountry:     searchParams.value.departingCountry,
    arrivingCountry:      searchParams.value.arrivingCountry,
    departureDate:        searchParams.value.departureDate,
    returnDate:           searchParams.value.returnDate,
    passengers:           searchParams.value.passengers,
  })
}
</script>

<template>
  <main class="relative min-h-screen bg-[#f5f5f7] pb-32">
    <div class="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(circle_at_90%_10%,rgba(230,57,70,0.18),transparent_40%),radial-gradient(circle_at_10%_80%,rgba(29,29,31,0.06),transparent_40%)]" />

    <div class="relative z-10 mx-auto max-w-[1000px] px-6 pt-12 md:px-10 lg:px-12">

      <!-- Header -->
      <div class="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <p class="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-[#e63946] animate__animated animate__fadeInDown">Blaze Select</p>
          <h1 class="text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl animate__animated animate__fadeInUp">
            {{ step === 'return' ? 'Choose Return Flight' : 'Choose Departure Flight' }}
          </h1>
          <p class="mt-4 text-[15px] font-medium text-[#6e6e73] animate__animated animate__fadeInUp animate__delay-1s">
            <span class="font-semibold text-[#1d1d1f]">{{ searchParams.departingCountry }}</span>
            <svg class="mx-2 inline-block h-3 w-3 text-[#e63946]" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
            <span class="font-semibold text-[#1d1d1f]">{{ searchParams.arrivingCountry }}</span>
            <span class="mx-3 text-black/20">•</span>
            {{ new Date(searchParams.departureDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}
            <span v-if="isRoundTrip" class="mx-3 text-black/20">•</span>
            <span v-if="isRoundTrip">Return {{ new Date(searchParams.returnDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}</span>
            <span class="mx-3 text-black/20">•</span>
            {{ searchParams.passengers }} pax
          </p>
        </div>
        <div class="flex items-center gap-3">
          <!-- Back to outbound when on return step -->
          <button
            v-if="step === 'return'"
            class="group flex items-center justify-center rounded-full bg-white/60 p-3 text-[#1d1d1f] shadow-sm backdrop-blur-md transition-all hover:bg-white hover:shadow-md hover:scale-105"
            title="Back to departure selection"
            @click="step = 'outbound'; selectedReturn = null; selectedReturnSeat = ''"
          >
            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" d="M15 19l-7-7 7-7"/></svg>
          </button>
          <RouterLink
            v-else
            to="/"
            class="group flex items-center justify-center rounded-full bg-white/60 p-3 text-[#1d1d1f] shadow-sm backdrop-blur-md transition-all hover:bg-white hover:shadow-md hover:scale-105"
            title="Back to Home"
          >
            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" d="M15 19l-7-7 7-7"/></svg>
          </RouterLink>
          <RouterLink to="/" class="rounded-full bg-white/60 px-6 py-3 text-sm font-semibold text-[#1d1d1f] shadow-sm backdrop-blur-md transition-all hover:bg-white hover:shadow-md hover:-translate-y-0.5">
            Modify Search
          </RouterLink>
        </div>
      </div>

      <!-- Round trip progress indicator -->
      <div v-if="isRoundTrip" class="mb-8 flex items-center gap-3">
        <div class="flex items-center gap-2">
          <div :class="step === 'outbound' ? 'bg-[#e63946] text-white' : 'bg-emerald-500 text-white'" class="h-7 w-7 rounded-full text-[11px] font-bold flex items-center justify-center transition-colors">
            <svg v-if="step !== 'outbound'" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
            <span v-else>1</span>
          </div>
          <span :class="step !== 'outbound' ? 'text-emerald-600' : 'text-[#1d1d1f]'" class="text-sm font-semibold">Departure</span>
        </div>
        <div class="flex-1 h-px bg-black/10 max-w-12"></div>
        <div class="flex items-center gap-2">
          <div :class="step === 'return' ? 'bg-[#e63946] text-white' : 'bg-white/80 text-[#6e6e73] border border-black/10'" class="h-7 w-7 rounded-full text-[11px] font-bold flex items-center justify-center transition-colors">2</div>
          <span :class="step === 'return' ? 'text-[#1d1d1f]' : 'text-[#6e6e73]'" class="text-sm font-semibold transition-colors">Return</span>
        </div>
      </div>

      <!-- Selected outbound summary (shown during Return step) -->
      <div v-if="step === 'return' && selectedOutbound" class="mb-6 rounded-[24px] border border-emerald-200 bg-emerald-50/70 px-6 py-4 backdrop-blur-xl animate__animated animate__fadeIn">
        <p class="mb-1 text-[10px] font-bold uppercase tracking-[0.15em] text-emerald-600">✓ Departure Confirmed</p>
        <div class="flex items-center gap-3 text-sm text-[#1d1d1f]">
          <span class="font-bold">{{ selectedOutbound.flightNumber }}</span>
          <span class="text-[#6e6e73]">{{ selectedOutbound.origin }} → {{ selectedOutbound.destination }}</span>
          <span class="text-[#6e6e73]">•</span>
          <span class="font-semibold">Seat {{ selectedOutboundSeat }}</span>
          <span class="ml-auto font-bold text-emerald-700">${{ selectedOutbound.price }}</span>
        </div>
      </div>

      <!-- ── OUTBOUND STEP ── -->
      <div v-if="step === 'outbound'">
        <!-- Loading -->
        <div v-if="loading" class="flex flex-col items-center justify-center py-32">
          <div class="relative flex h-16 w-16 items-center justify-center">
            <div class="absolute h-full w-full animate-ping rounded-full border-[3px] border-[#e63946]/20"></div>
            <div class="h-8 w-8 animate-spin rounded-full border-[3px] border-[#e63946] border-t-transparent"></div>
          </div>
          <p class="mt-6 text-sm font-semibold uppercase tracking-[0.1em] text-[#6e6e73] animate-pulse">Scanning the skies...</p>
        </div>

        <!-- Outbound flight list -->
        <div v-else class="grid gap-6 animate__animated animate__fadeInUp">
          <article
            v-for="(flight, i) in outboundFlights"
            :key="flight.flightID"
            class="group relative cursor-pointer overflow-hidden rounded-[32px] border border-white/60 bg-white/60 p-1 backdrop-blur-2xl transition-all duration-500 hover:-translate-y-1 hover:bg-white/90 hover:shadow-[0_20px_40px_rgba(0,0,0,0.06)]"
            :class="selectedOutbound?.flightID === flight.flightID ? 'ring-4 ring-[#e63946]/30 shadow-[0_20px_40px_rgba(230,57,70,0.12)] bg-white/95 scale-[1.01]' : ''"
            :style="`animation-delay: ${i * 100}ms`"
            @click="selectOutbound(flight)"
          >
            <div class="p-6 md:p-8">
              <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <!-- Flight path -->
                <div class="flex flex-1 items-center justify-between md:max-w-[65%]">
                  <div class="w-[100px] text-left">
                    <p class="text-2xl font-bold tracking-tight text-[#1d1d1f]">{{ formatTime12h(flight.departureTime) }}</p>
                    <p class="mt-1 text-[13px] font-medium text-[#6e6e73]">{{ flight.origin }}</p>
                  </div>
                  <div class="flex flex-1 flex-col items-center px-3">
                    <div class="mb-2 rounded-full border border-black/5 bg-[#f5f5f7] px-3 py-1 text-[11px] font-bold tracking-[0.15em] text-[#6e6e73] transition-all group-hover:bg-white group-hover:shadow-sm">{{ flight.flightNumber }}</div>
                    <div class="relative w-full">
                      <div class="h-[2px] w-full border-t-2 border-dashed border-[#e63946]/30 transition-colors duration-500 group-hover:border-[#e63946]/60"></div>
                      <div class="absolute right-0 top-1/2 -translate-y-1/2 translate-x-2 text-[#e63946] opacity-70 transition-all duration-500 group-hover:scale-110 group-hover:opacity-100">
                        <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>
                      </div>
                      <div class="absolute left-0 top-1/2 h-2 w-2 -translate-x-1 -translate-y-1/2 rounded-full border-2 border-white bg-[#e63946]/50 shadow-sm transition-colors duration-500 group-hover:bg-[#e63946]"></div>
                    </div>
                    <p class="mt-1.5 text-[11px] font-semibold tracking-wide text-[#a1a1a6]">Direct</p>
                  </div>
                  <div class="w-[100px] text-right">
                    <p class="text-2xl font-bold tracking-tight text-[#1d1d1f]">{{ formatTime12h(flight.arrivalTime) }}</p>
                    <p class="mt-1 text-[13px] font-medium text-[#6e6e73]">{{ flight.destination }}</p>
                  </div>
                </div>
                <div class="hidden h-16 w-px bg-gradient-to-b from-transparent via-black/10 to-transparent md:block"></div>
                <!-- Price -->
                <div class="flex items-center justify-between border-t border-black/5 pt-4 md:w-auto md:flex-col md:items-end md:justify-center md:border-none md:pt-0">
                  <div class="flex items-baseline gap-1">
                    <span class="text-sm font-semibold text-[#6e6e73]">$</span>
                    <span class="text-3xl font-bold tracking-tight text-[#1d1d1f] transition-colors group-hover:text-[#e63946]">{{ flight.price }}</span>
                  </div>
                  <div class="mt-1 flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1">
                    <span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
                    <span class="text-[11px] font-bold tracking-wide text-emerald-700">{{ flight.availableSeats }} seats left</span>
                  </div>
                </div>
              </div>
              <!-- Details strip -->
              <div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-3 border-t border-black/5 pt-4 text-[12px] text-[#6e6e73]">
                <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <span>📅 <span class="font-semibold text-[#1d1d1f]">{{ flight.departureDate }}</span> → <span class="font-semibold text-[#1d1d1f]">{{ flight.arrivalDate }}</span><span v-if="flight.isNextDay" class="ml-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">+1 day</span></span>
                  <span>⏱ {{ formatDuration(flight.duration) }}</span>
                  <span class="rounded-full bg-black/5 px-2.5 py-0.5 font-semibold border border-black/5">✈ Direct</span>
                </div>
                <div class="h-4 w-px bg-black/10 hidden md:block"></div>
                <div class="flex flex-wrap items-center gap-2">
                  <span class="rounded-full border border-black/5 bg-[#f5f5f7] px-2.5 py-0.5 font-medium text-[#1d1d1f]">🧳 {{ flight.baggage }}</span>
                  <span class="rounded-full border border-black/5 bg-[#f5f5f7] px-2.5 py-0.5 font-medium text-[#1d1d1f]">🍱 {{ flight.meals }}</span>
                  <span class="rounded-full border border-black/5 bg-[#f5f5f7] px-2.5 py-0.5 font-medium text-[#1d1d1f]">🥤 {{ flight.beverages }}</span>
                  <span v-if="flight.wifi" class="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 font-semibold text-emerald-700">📶 Free WiFi</span>
                </div>
              </div>
            </div>
            <!-- No seat selector here — seat map is loaded via FlightSearch composite service in Step 2 -->
          </article>
        </div>
      </div>

      <!-- ── RETURN STEP ── -->
      <div v-if="step === 'return'">
        <div v-if="loadingReturn" class="flex flex-col items-center justify-center py-32">
          <div class="relative flex h-16 w-16 items-center justify-center">
            <div class="absolute h-full w-full animate-ping rounded-full border-[3px] border-[#e63946]/20"></div>
            <div class="h-8 w-8 animate-spin rounded-full border-[3px] border-[#e63946] border-t-transparent"></div>
          </div>
          <p class="mt-6 text-sm font-semibold uppercase tracking-[0.1em] text-[#6e6e73] animate-pulse">Finding return flights...</p>
        </div>

        <div v-else class="grid gap-6 animate__animated animate__fadeInUp">
          <article
            v-for="(flight, i) in returnFlights"
            :key="flight.flightID"
            class="group relative cursor-pointer overflow-hidden rounded-[32px] border border-white/60 bg-white/60 p-1 backdrop-blur-2xl transition-all duration-500 hover:-translate-y-1 hover:bg-white/90 hover:shadow-[0_20px_40px_rgba(0,0,0,0.06)]"
            :class="selectedReturn?.flightID === flight.flightID ? 'ring-4 ring-purple-400/40 shadow-[0_20px_40px_rgba(168,85,247,0.12)] bg-white/95 scale-[1.01]' : ''"
            :style="`animation-delay: ${i * 100}ms`"
            @click="selectReturn(flight)"
          >
            <div class="p-6 md:p-8">
              <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div class="flex flex-1 items-center justify-between md:max-w-[65%]">
                  <div class="w-[100px] text-left">
                    <p class="text-2xl font-bold tracking-tight text-[#1d1d1f]">{{ formatTime12h(flight.departureTime) }}</p>
                    <p class="mt-1 text-[13px] font-medium text-[#6e6e73]">{{ flight.origin }}</p>
                  </div>
                  <div class="flex flex-1 flex-col items-center px-3">
                    <div class="mb-2 rounded-full border border-black/5 bg-[#f5f5f7] px-3 py-1 text-[11px] font-bold tracking-[0.15em] text-[#6e6e73] transition-all group-hover:bg-white group-hover:shadow-sm">{{ flight.flightNumber }}</div>
                    <div class="relative w-full">
                      <div class="h-[2px] w-full border-t-2 border-dashed border-purple-400/40 transition-colors duration-500 group-hover:border-purple-400/70"></div>
                      <div class="absolute right-0 top-1/2 -translate-y-1/2 translate-x-2 text-purple-500 opacity-70 transition-all duration-500 group-hover:scale-110 group-hover:opacity-100">
                        <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>
                      </div>
                      <div class="absolute left-0 top-1/2 h-2 w-2 -translate-x-1 -translate-y-1/2 rounded-full border-2 border-white bg-purple-400/50 shadow-sm transition-colors duration-500 group-hover:bg-purple-500"></div>
                    </div>
                    <p class="mt-1.5 text-[11px] font-semibold tracking-wide text-[#a1a1a6]">Direct</p>
                  </div>
                  <div class="w-[100px] text-right">
                    <p class="text-2xl font-bold tracking-tight text-[#1d1d1f]">{{ formatTime12h(flight.arrivalTime) }}</p>
                    <p class="mt-1 text-[13px] font-medium text-[#6e6e73]">{{ flight.destination }}</p>
                  </div>
                </div>
                <div class="hidden h-16 w-px bg-gradient-to-b from-transparent via-black/10 to-transparent md:block"></div>
                <div class="flex items-center justify-between border-t border-black/5 pt-4 md:w-auto md:flex-col md:items-end md:justify-center md:border-none md:pt-0">
                  <div class="flex items-baseline gap-1">
                    <span class="text-sm font-semibold text-[#6e6e73]">$</span>
                    <span class="text-3xl font-bold tracking-tight text-[#1d1d1f] transition-colors group-hover:text-purple-600">{{ flight.price }}</span>
                  </div>
                  <div class="mt-1 flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1">
                    <span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
                    <span class="text-[11px] font-bold tracking-wide text-emerald-700">{{ flight.availableSeats }} seats left</span>
                  </div>
                </div>
              </div>
              <!-- Details strip -->
              <div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-3 border-t border-black/5 pt-4 text-[12px] text-[#6e6e73]">
                <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <span>📅 <span class="font-semibold text-[#1d1d1f]">{{ flight.departureDate }}</span> → <span class="font-semibold text-[#1d1d1f]">{{ flight.arrivalDate }}</span><span v-if="flight.isNextDay" class="ml-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">+1 day</span></span>
                  <span>⏱ {{ formatDuration(flight.duration) }}</span>
                  <span class="rounded-full bg-purple-50 px-2.5 py-0.5 font-semibold text-purple-600 border border-purple-100">✈ Direct</span>
                </div>
                <div class="h-4 w-px bg-black/10 hidden md:block"></div>
                <div class="flex flex-wrap items-center gap-2">
                  <span class="rounded-full border border-black/5 bg-[#f5f5f7] px-2.5 py-0.5 font-medium text-[#1d1d1f]">🧳 {{ flight.baggage }}</span>
                  <span class="rounded-full border border-black/5 bg-[#f5f5f7] px-2.5 py-0.5 font-medium text-[#1d1d1f]">🍱 {{ flight.meals }}</span>
                  <span class="rounded-full border border-black/5 bg-[#f5f5f7] px-2.5 py-0.5 font-medium text-[#1d1d1f]">🥤 {{ flight.beverages }}</span>
                  <span v-if="flight.wifi" class="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 font-semibold text-emerald-700">📶 Free WiFi</span>
                </div>
              </div>
            </div>
            <!-- No seat selector here — seat map is loaded via FlightSearch composite service in Step 2 -->
          </article>
        </div>
      </div>

      <!-- ── STICKY ACTION BUTTON ── -->
      <transition enter-active-class="animate__animated animate__slideInUp animate__faster" leave-active-class="animate__animated animate__slideOutDown animate__faster">

        <!-- Outbound step CTA: confirm outbound seat -->
        <div v-if="step === 'outbound' && selectedOutbound" class="fixed bottom-8 left-0 right-0 z-50 mx-auto flex max-w-[500px] justify-center px-6">
          <div class="w-full rounded-[28px] bg-white/70 p-2 shadow-[0_24px_48px_rgba(0,0,0,0.12)] backdrop-blur-2xl border border-white/80 ring-1 ring-black/5">
            <button
              class="group relative w-full overflow-hidden rounded-[20px] bg-gradient-to-r from-[#e63946] to-[#f43f5e] py-4 text-sm font-bold uppercase tracking-[0.15em] text-white shadow-inner transition-all hover:shadow-[0_8px_20px_rgba(230,57,70,0.3)]"
              @click="confirmOutbound"
            >
              <div class="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-1000 group-hover:translate-x-full"></div>
              <span v-if="isRoundTrip" class="relative z-10 flex items-center justify-center gap-2">
                Select Departure · ${{ selectedOutbound.price }}
                <svg class="h-4 w-4 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7"/></svg>
              </span>
              <span v-else class="relative z-10 flex items-center justify-center gap-2">
                Continue to Booking · ${{ selectedOutbound.price }}
                <svg class="h-4 w-4 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7"/></svg>
              </span>
            </button>
          </div>
        </div>

        <!-- Return step CTA: confirm booking -->
        <div v-else-if="step === 'return' && selectedReturn" class="fixed bottom-8 left-0 right-0 z-50 mx-auto flex max-w-[500px] justify-center px-6">
          <div class="w-full rounded-[28px] bg-white/70 p-2 shadow-[0_24px_48px_rgba(0,0,0,0.12)] backdrop-blur-2xl border border-white/80 ring-1 ring-black/5">
            <button
              class="group relative w-full overflow-hidden rounded-[20px] bg-gradient-to-r from-purple-600 to-purple-500 py-4 text-sm font-bold uppercase tracking-[0.15em] text-white shadow-inner transition-all hover:shadow-[0_8px_20px_rgba(168,85,247,0.3)]"
              @click="proceedToBooking"
            >
              <div class="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-1000 group-hover:translate-x-full"></div>
              <span class="relative z-10 flex items-center justify-center gap-2">
                Confirm Round-Trip · ${{ (parseFloat(selectedOutbound.price) + parseFloat(selectedReturn.price)).toFixed(2) }}
                <svg class="h-4 w-4 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7"/></svg>
              </span>
            </button>
          </div>
        </div>

      </transition>

    </div>
  </main>
</template>