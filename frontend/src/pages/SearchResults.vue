<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'
import { useBookingDraft } from '../composables/useBookingDraft'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()
const { clearBookingDraft } = useBookingDraft()
const RECOMMENDATION_WINDOW_DAYS = 7
const RETURN_RECOMMENDATION_WINDOW_DAYS = 5

const searchParams = ref({
  tripType: route.query.tripType || 'one-way',
  departingCountry: route.query.departingCountry,
  arrivingCountry: route.query.arrivingCountry,
  departureDate: route.query.departureDate,
  returnDate: route.query.returnDate,
  passengers: parseInt(route.query.passengers) || 1,
})

const isRoundTrip = computed(() => searchParams.value.tripType === 'round-trip')
const step = ref(route.query.step || 'outbound')
const outboundFlights = ref([])
const returnFlights = ref([])
const outboundRecommendations = ref([])
const returnRecommendations = ref([])
const loading = ref(true)
const loadingReturn = ref(false)

const selectedOutbound = ref(route.query.outboundFlightID ? {
  flightID: route.query.outboundFlightID,
  flightNumber: route.query.outboundFlightNumber,
  origin: route.query.outboundOrigin,
  destination: route.query.outboundDestination,
  price: route.query.outboundPrice,
} : null)
const selectedReturn = ref(null)

const currentFlights = computed(() => step.value === 'return' ? returnFlights.value : outboundFlights.value)
const currentRecommendations = computed(() => step.value === 'return' ? returnRecommendations.value : outboundRecommendations.value)
const currentSelection = computed(() => step.value === 'return' ? selectedReturn.value : selectedOutbound.value)
const currentRoute = computed(() => ({
  origin: step.value === 'return' ? searchParams.value.arrivingCountry : searchParams.value.departingCountry,
  destination: step.value === 'return' ? searchParams.value.departingCountry : searchParams.value.arrivingCountry,
  date: step.value === 'return' ? searchParams.value.returnDate : searchParams.value.departureDate,
}))
const currentRecommendationMessage = computed(() => {
  if (step.value === 'return') {
    return `We couldn't find a flight on your exact return date, so here are recommended flights within ${RETURN_RECOMMENDATION_WINDOW_DAYS} days before and after your selected return date.`
  }

  return `We couldn't find a flight on your exact departure date, so here are the nearest recommended flights over the next ${RECOMMENDATION_WINDOW_DAYS} days.`
})

onMounted(async () => {
  if (step.value === 'return') {
    loading.value = false
    await fetchReturnFlights()
    return
  }
  await fetchOutboundFlights()
})

watch(
  () => route.query,
  async (query) => {
    searchParams.value = {
      tripType: query.tripType || 'one-way',
      departingCountry: query.departingCountry,
      arrivingCountry: query.arrivingCountry,
      departureDate: query.departureDate,
      returnDate: query.returnDate,
      passengers: parseInt(query.passengers) || 1,
    }

    step.value = query.step || 'outbound'
    selectedOutbound.value = query.outboundFlightID
      ? {
          flightID: query.outboundFlightID,
          flightNumber: query.outboundFlightNumber,
          origin: query.outboundOrigin,
          destination: query.outboundDestination,
          price: query.outboundPrice,
        }
      : null

    selectedReturn.value = null

    if (step.value === 'return') {
      loading.value = false
      await fetchReturnFlights()
      return
    }

    await fetchOutboundFlights()
  }
)

function addDays(dateText, days) {
  const base = new Date(`${dateText}T00:00:00`)
  base.setDate(base.getDate() + days)
  return base.toISOString().slice(0, 10)
}

async function fetchFlights(origin, dest, dateFrom, dateTo) {
  const response = await axios.get('http://localhost:5011/flight-search/available', {
    params: {
      origin,
      dest,
      dateFrom,
      dateTo,
      passengers: searchParams.value.passengers,
    },
  })
  return response.data.map(formatFlight).sort((a, b) => new Date(a.departureTime) - new Date(b.departureTime))
}

function filterOutExactDate(flights, exactDate) {
  return flights.filter((flight) => {
    const departureDate = flight.departureTime.slice(0, 10)
    return departureDate !== exactDate
  })
}

async function fetchOutboundFlights() {
  loading.value = true
  outboundRecommendations.value = []
  try {
    outboundFlights.value = await fetchFlights(searchParams.value.departingCountry, searchParams.value.arrivingCountry, searchParams.value.departureDate, searchParams.value.departureDate)
    if (!outboundFlights.value.length) {
      outboundRecommendations.value = await fetchFlights(searchParams.value.departingCountry, searchParams.value.arrivingCountry, addDays(searchParams.value.departureDate, 1), addDays(searchParams.value.departureDate, RECOMMENDATION_WINDOW_DAYS))
    }
  } catch (e) {
    console.error('Error fetching outbound flights:', e)
  } finally {
    loading.value = false
  }
}

async function fetchReturnFlights() {
  loadingReturn.value = true
  returnRecommendations.value = []
  try {
    returnFlights.value = await fetchFlights(searchParams.value.arrivingCountry, searchParams.value.departingCountry, searchParams.value.returnDate, searchParams.value.returnDate)
    if (!returnFlights.value.length) {
      const nearbyReturnFlights = await fetchFlights(
        searchParams.value.arrivingCountry,
        searchParams.value.departingCountry,
        addDays(searchParams.value.returnDate, -RETURN_RECOMMENDATION_WINDOW_DAYS),
        addDays(searchParams.value.returnDate, RETURN_RECOMMENDATION_WINDOW_DAYS),
      )
      returnRecommendations.value = filterOutExactDate(nearbyReturnFlights, searchParams.value.returnDate)
    }
  } catch (e) {
    console.error('Error fetching return flights:', e)
  } finally {
    loadingReturn.value = false
  }
}

function formatTime12h(isoString) {
  if (!isoString) return '--'
  return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true })
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
  const [depH, depM] = f.DepartureTime.split(':').map(Number)
  const [arrH, arrM] = f.ArrivalTime.split(':').map(Number)
  const isNextDay = arrH * 60 + arrM < depH * 60 + depM
  const arrDate = new Date(depDate)
  if (isNextDay) arrDate.setDate(arrDate.getDate() + 1)
  const fmt = (d) => d.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric', month: 'short' })
  return {
    flightID: f.FlightID,
    flightNumber: f.FlightNumber,
    origin: f.Origin,
    destination: f.Destination,
    departureTime: `${year}-${month}-${day}T${f.DepartureTime}:00`,
    arrivalTime: `${year}-${month}-${day}T${f.ArrivalTime}:00`,
    price: f.Price,
    duration: f.FlightDuration,
    departureDate: fmt(depDate),
    arrivalDate: fmt(arrDate),
    isNextDay,
  }
}

function chooseFlight(flight) {
  if (step.value === 'return') selectedReturn.value = flight
  else selectedOutbound.value = flight
}

function buildPassengerDetailsQuery() {
  return {
    tripType: isRoundTrip.value ? searchParams.value.tripType : 'one-way',
    departingCountry: searchParams.value.departingCountry,
    arrivingCountry: searchParams.value.arrivingCountry,
    departureDate: searchParams.value.departureDate,
    returnDate: searchParams.value.returnDate,
    passengers: searchParams.value.passengers,
    outboundFlightID: selectedOutbound.value?.flightID,
    outboundFlightNumber: selectedOutbound.value?.flightNumber,
    outboundOrigin: selectedOutbound.value?.origin,
    outboundDestination: selectedOutbound.value?.destination,
    outboundPrice: selectedOutbound.value?.price,
    returnFlightID: selectedReturn.value?.flightID || '',
    returnFlightNumber: selectedReturn.value?.flightNumber || '',
    returnOrigin: selectedReturn.value?.origin || '',
    returnDestination: selectedReturn.value?.destination || '',
    returnPrice: selectedReturn.value?.price || '',
  }
}

function redirectToAuthForPassengerDetails() {
  router.push({
    path: '/auth',
    query: {
      redirect: '/passenger-details',
      ...buildPassengerDetailsQuery(),
    },
  })
}

function goToPassengerDetails() {
  clearBookingDraft()
  router.push({
    path: '/passenger-details',
    query: buildPassengerDetailsQuery(),
  })
}

function confirmOutbound() {
  if (!isRoundTrip.value) {
    if (!currentPassenger.value) {
      redirectToAuthForPassengerDetails()
      return
    }

    goToPassengerDetails()
    return
  }

  router.push({
    path: '/search-results',
    query: {
      step: 'return',
      tripType: searchParams.value.tripType,
      departingCountry: searchParams.value.departingCountry,
      arrivingCountry: searchParams.value.arrivingCountry,
      departureDate: searchParams.value.departureDate,
      returnDate: searchParams.value.returnDate,
      passengers: searchParams.value.passengers,
      outboundFlightID: selectedOutbound.value.flightID,
      outboundFlightNumber: selectedOutbound.value.flightNumber,
      outboundOrigin: selectedOutbound.value.origin,
      outboundDestination: selectedOutbound.value.destination,
      outboundPrice: selectedOutbound.value.price,
    },
  })
}

function proceedToBooking() {
  if (!currentPassenger.value) {
    redirectToAuthForPassengerDetails()
    return
  }

  goToPassengerDetails()
}
</script>

<template>
  <main class="relative min-h-screen bg-[#f5f5f7] pb-32">
    <div class="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(circle_at_90%_10%,rgba(230,57,70,0.18),transparent_40%),radial-gradient(circle_at_10%_80%,rgba(29,29,31,0.06),transparent_40%)]" />
    <div class="relative z-10 mx-auto max-w-[1000px] px-6 pt-12 md:px-10 lg:px-12">
      <div class="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <p class="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-[#e63946]">Blaze Select</p>
          <h1 class="text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">{{ step === 'return' ? 'Choose Return Flight' : 'Choose Departure Flight' }}</h1>
          <p class="mt-4 text-[15px] font-medium text-[#6e6e73]">
            <span class="font-semibold text-[#1d1d1f]">{{ searchParams.departingCountry }}</span>
            <span class="mx-3 text-black/20">•</span>
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
          <button v-if="step === 'return'" class="rounded-full bg-white/60 p-3 text-[#1d1d1f] shadow-sm backdrop-blur-md transition-all hover:bg-white hover:shadow-md" @click="step = 'outbound'; selectedReturn = null">
            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" d="M15 19l-7-7 7-7"/></svg>
          </button>
          <RouterLink v-else to="/" class="rounded-full bg-white/60 p-3 text-[#1d1d1f] shadow-sm backdrop-blur-md transition-all hover:bg-white hover:shadow-md">
            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" d="M15 19l-7-7 7-7"/></svg>
          </RouterLink>
          <RouterLink to="/" class="rounded-full bg-white/60 px-6 py-3 text-sm font-semibold text-[#1d1d1f] shadow-sm backdrop-blur-md transition-all hover:bg-white hover:shadow-md">Modify Search</RouterLink>
        </div>
      </div>

      <div v-if="isRoundTrip" class="mb-8 flex items-center gap-3">
        <div class="flex items-center gap-2"><div :class="step === 'outbound' ? 'bg-[#e63946] text-white' : 'bg-emerald-500 text-white'" class="h-7 w-7 rounded-full text-[11px] font-bold flex items-center justify-center">1</div><span class="text-sm font-semibold">Departure</span></div>
        <div class="flex-1 h-px bg-black/10 max-w-12"></div>
        <div class="flex items-center gap-2"><div :class="step === 'return' ? 'bg-[#e63946] text-white' : 'bg-white/80 text-[#6e6e73] border border-black/10'" class="h-7 w-7 rounded-full text-[11px] font-bold flex items-center justify-center">2</div><span class="text-sm font-semibold">Return</span></div>
      </div>

      <div v-if="step === 'return' && selectedOutbound" class="mb-6 rounded-[24px] border border-emerald-200 bg-emerald-50/70 px-6 py-4">
        <p class="mb-1 text-[10px] font-bold uppercase tracking-[0.15em] text-emerald-600">Departure Confirmed</p>
        <div class="flex items-center gap-3 text-sm text-[#1d1d1f]">
          <span class="font-bold">{{ selectedOutbound.flightNumber }}</span>
          <span class="text-[#6e6e73]">{{ selectedOutbound.origin }} → {{ selectedOutbound.destination }}</span>
          <span class="ml-auto font-bold text-emerald-700">${{ selectedOutbound.price }}</span>
        </div>
      </div>

      <div v-if="step === 'outbound' ? loading : loadingReturn" class="flex flex-col items-center justify-center py-32">
        <div class="relative flex h-16 w-16 items-center justify-center">
          <div class="absolute h-full w-full animate-ping rounded-full border-[3px] border-[#e63946]/20"></div>
          <div class="h-8 w-8 animate-spin rounded-full border-[3px] border-[#e63946] border-t-transparent"></div>
        </div>
        <p class="mt-6 text-sm font-semibold uppercase tracking-[0.1em] text-[#6e6e73] animate-pulse">{{ step === 'return' ? 'Finding return flights...' : 'Scanning the skies...' }}</p>
      </div>

      <div v-else-if="currentFlights.length" class="grid gap-6">
        <article v-for="(flight, i) in currentFlights" :key="flight.flightID" class="group relative cursor-pointer overflow-hidden rounded-[32px] border border-white/60 bg-white/60 p-1 backdrop-blur-2xl transition-all duration-500 hover:-translate-y-1 hover:bg-white/90 hover:shadow-[0_20px_40px_rgba(0,0,0,0.06)]" :class="currentSelection?.flightID === flight.flightID ? (step === 'return' ? 'ring-4 ring-purple-400/40 shadow-[0_20px_40px_rgba(168,85,247,0.12)] bg-white/95 scale-[1.01]' : 'ring-4 ring-[#e63946]/30 shadow-[0_20px_40px_rgba(230,57,70,0.12)] bg-white/95 scale-[1.01]') : ''" :style="`animation-delay: ${i * 100}ms`" @click="chooseFlight(flight)">
          <div class="p-6 md:p-8">
            <div class="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div class="flex-1">
                <p class="text-[12px] font-semibold text-[#1d1d1f]">Non-stop • {{ formatDuration(flight.duration) }}</p>
                <div class="mt-4 grid grid-cols-[auto_1fr_auto] items-center gap-4">
                  <div><p class="text-3xl font-semibold tracking-[-0.03em] text-[#1d1d1f]">{{ formatTime12h(flight.departureTime) }}</p><p class="mt-1 text-[14px] font-semibold text-[#1d1d1f]">{{ flight.origin }}</p><p class="text-[12px] text-[#6e6e73]">{{ flight.departureDate }}</p></div>
                  <div class="relative"><div class="h-[2px] w-full border-t-2 border-dashed border-black/20"></div><p class="mt-2 text-center text-[12px] font-semibold uppercase tracking-[0.08em] text-[#6e6e73]">{{ flight.flightNumber }}</p></div>
                  <div class="text-right"><p class="text-3xl font-semibold tracking-[-0.03em] text-[#1d1d1f]">{{ formatTime12h(flight.arrivalTime) }}<span v-if="flight.isNextDay" class="ml-1 align-top text-xs font-semibold text-amber-600">+1</span></p><p class="mt-1 text-[14px] font-semibold text-[#1d1d1f]">{{ flight.destination }}</p><p class="text-[12px] text-[#6e6e73]">{{ flight.arrivalDate }}</p></div>
                </div>
              </div>
              <div class="hidden self-stretch w-px bg-black/10 md:block"></div>
              <div class="border-t border-black/5 pt-4 md:min-w-[180px] md:border-none md:pt-0 md:pl-6">
                <p class="text-[12px] font-medium text-[#6e6e73]">From</p>
                <div class="mt-0.5 flex items-baseline gap-1"><span class="text-sm font-semibold text-[#6e6e73]">$</span><span class="text-3xl font-bold tracking-tight text-[#1d1d1f]">{{ flight.price }}</span></div>
                <button type="button" class="mt-4 w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition" :class="step === 'return' ? 'bg-purple-600 hover:bg-purple-700' : 'bg-[#e63946] hover:bg-[#d62f3c]'" @click.stop="chooseFlight(flight)">Select</button>
              </div>
            </div>
          </div>
        </article>
      </div>

      <div v-else class="space-y-6">
        <section class="rounded-[28px] border border-white/60 bg-white/70 p-6 shadow-[0_16px_36px_rgba(15,23,42,0.05)] backdrop-blur-xl">
          <p class="text-[11px] font-bold uppercase tracking-[0.16em] text-[#e63946]">No Exact Match</p>
          <h2 class="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#1d1d1f]">We couldn't find the exact flight you searched for.</h2>
          <p class="mt-3 max-w-2xl text-sm text-[#6e6e73]">
            We checked {{ currentRoute.origin }} to {{ currentRoute.destination }} on
            {{ new Date(currentRoute.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}.
          </p>
          <p class="mt-2 max-w-2xl text-sm font-medium text-[#1d1d1f]">
            {{ currentRecommendationMessage }}
          </p>
        </section>

        <div v-if="currentRecommendations.length" class="grid gap-6">
          <article v-for="(flight, i) in currentRecommendations" :key="`rec-${flight.flightID}`" class="group relative cursor-pointer overflow-hidden rounded-[32px] border border-white/60 bg-white/60 p-1 backdrop-blur-2xl transition-all duration-500 hover:-translate-y-1 hover:bg-white/90 hover:shadow-[0_20px_40px_rgba(0,0,0,0.06)]" :class="currentSelection?.flightID === flight.flightID ? (step === 'return' ? 'ring-4 ring-purple-400/40 shadow-[0_20px_40px_rgba(168,85,247,0.12)] bg-white/95 scale-[1.01]' : 'ring-4 ring-[#e63946]/30 shadow-[0_20px_40px_rgba(230,57,70,0.12)] bg-white/95 scale-[1.01]') : ''" :style="`animation-delay: ${i * 100}ms`" @click="chooseFlight(flight)">
            <div class="p-6 md:p-8">
              <div class="mb-4 inline-flex rounded-full bg-[#fff1f2] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[#e63946]">Suggested Alternative</div>
              <div class="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                <div class="flex-1">
                  <p class="text-[12px] font-semibold text-[#1d1d1f]">Non-stop • {{ formatDuration(flight.duration) }}</p>
                  <div class="mt-4 grid grid-cols-[auto_1fr_auto] items-center gap-4">
                    <div><p class="text-3xl font-semibold tracking-[-0.03em] text-[#1d1d1f]">{{ formatTime12h(flight.departureTime) }}</p><p class="mt-1 text-[14px] font-semibold text-[#1d1d1f]">{{ flight.origin }}</p><p class="text-[12px] text-[#6e6e73]">{{ flight.departureDate }}</p></div>
                    <div class="relative"><div class="h-[2px] w-full border-t-2 border-dashed border-black/20"></div><p class="mt-2 text-center text-[12px] font-semibold uppercase tracking-[0.08em] text-[#6e6e73]">{{ flight.flightNumber }}</p></div>
                    <div class="text-right"><p class="text-3xl font-semibold tracking-[-0.03em] text-[#1d1d1f]">{{ formatTime12h(flight.arrivalTime) }}<span v-if="flight.isNextDay" class="ml-1 align-top text-xs font-semibold text-amber-600">+1</span></p><p class="mt-1 text-[14px] font-semibold text-[#1d1d1f]">{{ flight.destination }}</p><p class="text-[12px] text-[#6e6e73]">{{ flight.arrivalDate }}</p></div>
                  </div>
                </div>
                <div class="hidden self-stretch w-px bg-black/10 md:block"></div>
                <div class="border-t border-black/5 pt-4 md:min-w-[180px] md:border-none md:pt-0 md:pl-6">
                  <p class="text-[12px] font-medium text-[#6e6e73]">From</p>
                  <div class="mt-0.5 flex items-baseline gap-1"><span class="text-sm font-semibold text-[#6e6e73]">$</span><span class="text-3xl font-bold tracking-tight text-[#1d1d1f]">{{ flight.price }}</span></div>
                  <button type="button" class="mt-4 w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition" :class="step === 'return' ? 'bg-purple-600 hover:bg-purple-700' : 'bg-[#e63946] hover:bg-[#d62f3c]'" @click.stop="chooseFlight(flight)">Select This Flight</button>
                </div>
              </div>
            </div>
          </article>
        </div>

        <section v-else class="rounded-[28px] border border-black/10 bg-white/80 p-8 text-center shadow-[0_16px_36px_rgba(15,23,42,0.05)]">
          <h3 class="text-xl font-semibold text-[#1d1d1f]">No nearby {{ step === 'return' ? 'return flights' : 'departures' }} found either.</h3>
          <p class="mt-3 text-sm text-[#6e6e73]">Try another route or change your date to see more flights.</p>
        </section>
      </div>

      <transition enter-active-class="animate__animated animate__slideInUp animate__faster" leave-active-class="animate__animated animate__slideOutDown animate__faster">
        <div v-if="step === 'outbound' && selectedOutbound" class="fixed bottom-8 left-0 right-0 z-50 mx-auto flex max-w-[500px] justify-center px-6">
          <div class="w-full rounded-[28px] bg-white/70 p-2 shadow-[0_24px_48px_rgba(0,0,0,0.12)] backdrop-blur-2xl border border-white/80 ring-1 ring-black/5">
            <button class="w-full rounded-[20px] bg-gradient-to-r from-[#e63946] to-[#f43f5e] py-4 text-sm font-bold uppercase tracking-[0.15em] text-white" @click="confirmOutbound">{{ isRoundTrip ? `Select Departure · $${selectedOutbound.price}` : `Continue to Booking · $${selectedOutbound.price}` }}</button>
          </div>
        </div>
        <div v-else-if="step === 'return' && selectedReturn" class="fixed bottom-8 left-0 right-0 z-50 mx-auto flex max-w-[500px] justify-center px-6">
          <div class="w-full rounded-[28px] bg-white/70 p-2 shadow-[0_24px_48px_rgba(0,0,0,0.12)] backdrop-blur-2xl border border-white/80 ring-1 ring-black/5">
            <button class="w-full rounded-[20px] bg-gradient-to-r from-purple-600 to-purple-500 py-4 text-sm font-bold uppercase tracking-[0.15em] text-white" @click="proceedToBooking">Confirm Round-Trip · ${{ (parseFloat(selectedOutbound.price) + parseFloat(selectedReturn.price)).toFixed(2) }}</button>
          </div>
        </div>
      </transition>
    </div>
  </main>
</template>
