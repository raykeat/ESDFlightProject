<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import SeatSelector from './SeatSelector.vue'
import { usePassengerSession } from '../composables/usePassengerSession'
import { useBookingDraft } from '../composables/useBookingDraft'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()
const { bookingDraft, patchBookingDraft } = useBookingDraft()

const flightID = computed(() => Number.parseInt(route.query.flightID, 10))
const isReturn = computed(() => route.query.isReturn === 'true')
const searchParams = computed(() => ({
  tripType: route.query.tripType || 'one-way',
  departingCountry: route.query.departingCountry || '',
  arrivingCountry: route.query.arrivingCountry || '',
  departureDate: route.query.departureDate || '',
  returnDate: route.query.returnDate || '',
  passengers: Number.parseInt(route.query.passengers, 10) || 1,
}))

const flight = ref(null)
const seats = ref([])
const loading = ref(true)
const error = ref(null)
const selectedSeats = ref([])

const travelers = computed(() => {
  const draftTravelers = bookingDraft.value?.travelers || []

  if (draftTravelers.length) {
    return draftTravelers.map((traveller, index) => ({
      ...traveller,
      displayName: `${traveller.firstName || ''} ${traveller.lastName || ''}`.trim() || `Passenger ${index + 1}`,
    }))
  }

  return Array.from({ length: searchParams.value.passengers }, (_, index) => ({
    id: `passenger-${index + 1}`,
    displayName: index === 0 && currentPassenger.value
      ? `${currentPassenger.value.FirstName || ''} ${currentPassenger.value.LastName || ''}`.trim()
      : `Passenger ${index + 1}`,
    firstName: index === 0 ? (currentPassenger.value?.FirstName || '') : '',
    lastName: index === 0 ? (currentPassenger.value?.LastName || '') : '',
  }))
})

const initialAssignments = computed(() => {
  const assignments = bookingDraft.value?.seatAssignments?.[isReturn.value ? 'return' : 'outbound'] || []
  return Array.from({ length: searchParams.value.passengers }, (_, index) => assignments[index] || '')
})

const totalPrice = computed(() => {
  if (!flight.value) return '0.00'
  const base = Number.parseFloat(flight.value.Price ?? flight.value.price ?? 0)
  return (base * searchParams.value.passengers).toFixed(2)
})

const selectedSeatLabels = computed(() => selectedSeats.value.filter(Boolean))

function formatTime(timeText) {
  if (!timeText) return '--'
  const [hour, minute] = timeText.slice(0, 5).split(':').map(Number)
  const suffix = hour >= 12 ? 'PM' : 'AM'
  const hour12 = hour % 12 || 12
  return `${hour12}:${String(minute).padStart(2, '0')} ${suffix}`
}

function formatDuration(durationText) {
  if (!durationText) return '--'
  const clean = String(durationText).replace('h', '').trim()
  const [hours, minutes = '00'] = clean.split(':')
  return `${Number.parseInt(hours, 10)}h ${String(minutes).padStart(2, '0')}m`
}

function formatDate(dateText) {
  if (!dateText) return '--'
  const [day, month, year] = dateText.split('/')
  return new Date(`${year}-${month}-${day}`).toLocaleDateString('en-US', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

const isNextDay = computed(() => {
  if (!flight.value) return false
  const [departureHour, departureMinute] = (flight.value.DepartureTime ?? '00:00').slice(0, 5).split(':').map(Number)
  const [arrivalHour, arrivalMinute] = (flight.value.ArrivalTime ?? '00:00').slice(0, 5).split(':').map(Number)
  return arrivalHour * 60 + arrivalMinute < departureHour * 60 + departureMinute
})

const arrivalDate = computed(() => {
  if (!flight.value?.Date) return ''
  const [day, month, year] = flight.value.Date.split('/')
  const arrival = new Date(`${year}-${month}-${day}`)
  if (isNextDay.value) arrival.setDate(arrival.getDate() + 1)
  return arrival.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
})

function onSeatSelected(assignments) {
  selectedSeats.value = assignments
}

function goBack() {
  if (isReturn.value) {
    router.push({
      path: '/flight-detail',
      query: {
        ...route.query,
        flightID: route.query.outboundFlightID,
        isReturn: 'false',
      },
    })
    return
  }

  router.push({
    path: '/passenger-details',
    query: {
      tripType: searchParams.value.tripType,
      departingCountry: searchParams.value.departingCountry,
      arrivingCountry: searchParams.value.arrivingCountry,
      departureDate: searchParams.value.departureDate,
      returnDate: searchParams.value.returnDate,
      passengers: searchParams.value.passengers,
      outboundFlightID: route.query.outboundFlightID || route.query.flightID,
      outboundFlightNumber: route.query.outboundFlightNumber || '',
      outboundOrigin: route.query.outboundOrigin || searchParams.value.departingCountry,
      outboundDestination: route.query.outboundDestination || searchParams.value.arrivingCountry,
      outboundPrice: route.query.outboundPrice || '',
      returnFlightID: route.query.returnFlightID || '',
      returnFlightNumber: route.query.returnFlightNumber || '',
      returnOrigin: route.query.returnOrigin || '',
      returnDestination: route.query.returnDestination || '',
      returnPrice: route.query.returnPrice || '',
    },
  })
}

function persistSeatAssignments() {
  patchBookingDraft({
    seatAssignments: {
      ...(bookingDraft.value?.seatAssignments || { outbound: [], return: [] }),
      [isReturn.value ? 'return' : 'outbound']: [...selectedSeats.value],
    },
  })
}

function continueToBooking() {
  const everyPassengerSeated = selectedSeats.value.length === searchParams.value.passengers && selectedSeats.value.every(Boolean)
  if (!everyPassengerSeated) {
    alert(`Please assign ${searchParams.value.passengers} seat(s) before continuing.`)
    return
  }

  if (!currentPassenger.value) {
    router.push({ path: '/auth', query: { redirect: '/passenger-details', ...route.query } })
    return
  }

  persistSeatAssignments()

  if (searchParams.value.tripType === 'round-trip' && !isReturn.value) {
    router.push({
      path: '/flight-detail',
      query: {
        ...route.query,
        flightID: route.query.returnFlightID,
        isReturn: 'true',
      },
    })
    return
  }

  router.push({
    path: '/booking-confirmation',
    query: {
      flightID: flightID.value,
      flightNumber: flight.value?.FlightNumber || route.query.returnFlightNumber || route.query.outboundFlightNumber || '',
      amount: totalPrice.value,
      seatNumber: selectedSeats.value.join(','),
      outboundFlightID: route.query.outboundFlightID || '',
      outboundFlightNumber: route.query.outboundFlightNumber || '',
      outboundSeat: (bookingDraft.value?.seatAssignments?.outbound || []).join(','),
      outboundPrice: route.query.outboundPrice
        ? (Number.parseFloat(route.query.outboundPrice) * searchParams.value.passengers).toFixed(2)
        : '',
      tripType: searchParams.value.tripType,
      departingCountry: searchParams.value.departingCountry,
      arrivingCountry: searchParams.value.arrivingCountry,
      departureDate: searchParams.value.departureDate,
      returnDate: searchParams.value.returnDate,
      passengers: searchParams.value.passengers,
    },
  })
}

async function loadFlightDetail() {
  if (!flightID.value) {
    error.value = 'No flight ID provided.'
    loading.value = false
    return
  }

  loading.value = true
  error.value = null
  flight.value = null
  seats.value = []

  const storageKey = `flightSearchComposite:${flightID.value}`

  try {
    const prefetched = sessionStorage.getItem(storageKey)

    if (prefetched) {
      const parsed = JSON.parse(prefetched)
      flight.value = parsed.flight
      seats.value = Array.isArray(parsed.seats) ? parsed.seats : []
      sessionStorage.removeItem(storageKey)
    }

    if (!flight.value) {
      const compositeResponse = await axios.get(`http://localhost:5011/flight-search/${flightID.value}`)
      flight.value = compositeResponse.data.flight
      seats.value = Array.isArray(compositeResponse.data.seats) ? compositeResponse.data.seats : []
    }

    selectedSeats.value = [...initialAssignments.value]
  } catch (fetchError) {
    console.error('Flight search composite error:', fetchError)
    error.value = 'Could not load flight details. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadFlightDetail()
})

watch(
  () => route.query,
  async () => {
    await loadFlightDetail()
  }
)
</script>

<template>
  <main class="relative min-h-screen overflow-hidden bg-[linear-gradient(135deg,#f8f8fa_0%,#f0f0f5_100%)]">
    <div class="pointer-events-none absolute inset-0 z-0">
      <div class="absolute -right-40 -top-40 h-[500px] w-[500px] rounded-full bg-[#e63946]/7 blur-[110px]"></div>
      <div class="absolute -bottom-40 -left-40 h-[420px] w-[420px] rounded-full bg-indigo-400/5 blur-[95px]"></div>
    </div>

    <div class="relative z-10 mx-auto max-w-[1520px] px-5 py-6 md:px-8 xl:px-12">
      <div class="mb-8 rounded-[28px] bg-white/80 px-6 py-6 shadow-[0_20px_48px_rgba(0,0,0,0.06)] backdrop-blur-2xl">
        <div class="grid grid-cols-3 items-start gap-6">
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-sm font-bold text-white">✓</div>
            <div class="min-w-0 flex-1 pt-1">
              <div class="h-1 rounded-full bg-emerald-500"></div>
              <p class="mt-3 text-sm font-semibold text-emerald-600">Fill in your info</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#e63946] text-sm font-bold text-white shadow-[0_10px_18px_rgba(230,57,70,0.22)]">2</div>
            <div class="min-w-0 flex-1 pt-1">
              <div class="h-1 rounded-full bg-[#e63946]"></div>
              <p class="mt-3 text-sm font-semibold text-[#e63946]">Choose your seat</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#eef0f5] text-sm font-bold text-[#7d8594]">3</div>
            <div class="min-w-0 flex-1 pt-1">
              <div class="h-1 rounded-full bg-[#d9dde6]"></div>
              <p class="mt-3 text-sm font-semibold text-[#1d1d1f]">Finalise your payment</p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loading" class="flex min-h-[60vh] flex-col items-center justify-center">
        <div class="relative flex h-14 w-14 items-center justify-center">
          <div class="absolute h-full w-full animate-ping rounded-full border-[3px] border-[#e63946]/20"></div>
          <div class="h-7 w-7 animate-spin rounded-full border-[3px] border-[#e63946] border-t-transparent"></div>
        </div>
        <p class="mt-4 text-xs font-bold uppercase tracking-[0.2em] text-[#6e6e73]">Loading flight...</p>
      </div>

      <div v-else-if="error" class="flex min-h-[60vh] flex-col items-center justify-center text-center">
        <p class="text-base font-semibold text-[#1d1d1f]">{{ error }}</p>
        <button @click="goBack" class="mt-5 rounded-full bg-[#e63946] px-7 py-2.5 text-sm font-bold text-white transition hover:bg-[#d62839]">Go Back</button>
      </div>

      <div v-else class="grid gap-4 lg:grid-cols-[420px_1fr] xl:grid-cols-[460px_1fr]">
        <aside class="relative z-20 rounded-[24px] border border-white/80 bg-white/85 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.07)] backdrop-blur-2xl">
          <div class="mb-4 flex items-center justify-between">
            <button
              @click="goBack"
              class="inline-flex items-center gap-1.5 rounded-full border border-black/8 bg-white px-3 py-1.5 text-[11px] font-semibold text-[#1d1d1f] transition hover:bg-[#f8f8fa]"
            >
              <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" d="M15 19l-7-7 7-7" />
              </svg>
              {{ isReturn ? 'Back to Departure Seats' : 'Back' }}
            </button>
            <span
              class="rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em]"
              :class="isReturn ? 'bg-purple-50 text-purple-600' : 'bg-red-50 text-[#e63946]'"
            >
              {{ isReturn ? 'Return Flight' : 'Outbound Flight' }}
            </span>
          </div>

          <div class="mb-4 flex items-center justify-between rounded-2xl bg-[#f5f5f7] px-3.5 py-3">
            <span class="text-sm font-bold text-[#1d1d1f]">{{ flight.FlightNumber }}</span>
            <span class="text-sm font-semibold text-[#6e6e73]">${{ Number.parseFloat(flight.Price ?? flight.price ?? 0).toFixed(2) }}</span>
          </div>

          <div class="mb-4 rounded-2xl bg-[#f5f5f7] p-3.5">
            <div class="flex items-center justify-between gap-2">
              <p class="truncate text-2xl font-bold text-[#1d1d1f]">{{ flight.Origin }}</p>
              <span class="text-xs font-semibold uppercase tracking-[0.14em] text-[#a1a1a6]">Direct</span>
              <p class="truncate text-right text-2xl font-bold text-[#1d1d1f]">{{ flight.Destination }}</p>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="rounded-xl bg-[#f5f5f7] p-3">
              <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Departure</p>
              <p class="mt-1 text-base font-bold text-[#1d1d1f]">{{ formatTime(flight.DepartureTime) }}</p>
              <p class="text-[11px] text-[#6e6e73]">{{ formatDate(flight.Date) }}</p>
            </div>
            <div class="rounded-xl bg-[#f5f5f7] p-3">
              <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Arrival</p>
              <p class="mt-1 text-base font-bold text-[#1d1d1f]">{{ formatTime(flight.ArrivalTime) }}</p>
              <p class="text-[11px] text-[#6e6e73]">{{ isNextDay ? arrivalDate : formatDate(flight.Date) }}</p>
            </div>
            <div class="rounded-xl bg-[#f5f5f7] p-3">
              <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Duration</p>
              <p class="mt-1 text-base font-semibold text-[#1d1d1f]">{{ formatDuration(flight.FlightDuration) }}</p>
            </div>
            <div class="rounded-xl bg-[#f5f5f7] p-3">
              <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Status</p>
              <p class="mt-1 text-base font-semibold text-emerald-600">{{ flight.Status }}</p>
            </div>
          </div>

          <div class="mt-4 rounded-xl border border-black/6 bg-white px-3.5 py-2.5">
            <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Passengers</p>
            <div class="mt-2 space-y-2">
              <div v-for="(traveler, index) in travelers" :key="traveler.id" class="flex items-center justify-between text-sm">
                <span class="font-semibold text-[#1d1d1f]">{{ traveler.displayName }}</span>
                <span class="text-[#6e6e73]">{{ selectedSeats[index] || 'Seat not selected' }}</span>
              </div>
            </div>
          </div>

          <div class="mt-4 rounded-2xl border border-[#e63946]/15 bg-gradient-to-br from-[#e63946]/6 to-rose-50 p-3.5">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#e63946]">Assigned Seats</p>
                <p class="mt-1 text-lg font-bold text-[#1d1d1f]">{{ selectedSeatLabels.length ? selectedSeatLabels.join(', ') : 'None yet' }}</p>
              </div>
              <div class="text-right">
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Total</p>
                <p class="mt-1 text-2xl font-bold text-[#e63946]">${{ totalPrice }}</p>
              </div>
            </div>
          </div>

          <button
            :disabled="selectedSeatLabels.length !== searchParams.passengers || selectedSeats.some((seat) => !seat)"
            @click="continueToBooking"
            class="relative z-30 mt-4 w-full rounded-[14px] py-3 text-sm font-bold uppercase tracking-[0.12em] text-white transition-all"
            :class="selectedSeatLabels.length === searchParams.passengers && !selectedSeats.some((seat) => !seat)
              ? 'bg-gradient-to-r from-[#e63946] to-[#f43f5e] shadow-[0_8px_24px_rgba(230,57,70,0.28)] hover:-translate-y-0.5'
              : 'cursor-not-allowed bg-[#d1d1d6] opacity-70'"
          >
            <span v-if="selectedSeatLabels.length !== searchParams.passengers || selectedSeats.some((seat) => !seat)">
              Assign {{ searchParams.passengers }} seat(s) to continue
            </span>
            <span v-else>
              {{ isReturn ? `Continue to Payment · $${totalPrice}` : searchParams.tripType === 'round-trip' ? 'Continue to Return Seats' : `Continue to Booking · $${totalPrice}` }}
            </span>
          </button>
        </aside>

        <section class="relative z-10 rounded-[24px] border border-white/80 bg-white/80 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.07)] backdrop-blur-2xl">
          <div class="mb-3">
            <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-[#a1a1a6]">Cabin Map</p>
            <h2 class="text-2xl font-semibold tracking-tight text-[#1d1d1f]">Choose Your Seat</h2>
          </div>
          <div class="h-[calc(100%-52px)]">
            <SeatSelector
              :flightId="flightID"
              :seatsData="seats"
              :maxSeats="searchParams.passengers"
              :travelers="travelers"
              :initialAssignments="initialAssignments"
              @seatSelected="onSeatSelected"
            />
          </div>
        </section>
      </div>
    </div>
  </main>
</template>
