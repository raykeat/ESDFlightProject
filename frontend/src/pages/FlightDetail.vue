<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import SeatSelector from './SeatSelector.vue'
import { usePassengerSession } from '../composables/usePassengerSession'

const route  = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()

const flightID         = parseInt(route.query.flightID)
const isReturn         = route.query.isReturn === 'true'
const outboundFlightID = route.query.outboundFlightID || null
const outboundSeat     = route.query.outboundSeat     || null
const searchParams     = {
  tripType:         route.query.tripType         || 'one-way',
  departingCountry: route.query.departingCountry || '',
  arrivingCountry:  route.query.arrivingCountry  || '',
  departureDate:    route.query.departureDate    || '',
  returnDate:       route.query.returnDate       || '',
  passengers:       parseInt(route.query.passengers) || 1,
}

const passengers = searchParams.passengers

// ─── State ────────────────────────────────────────────────
const flight        = ref(null)
const seats         = ref([])
const loading       = ref(true)
const error         = ref(null)
const selectedSeats = ref([])

// ─── Fetch from composite service ─────────────────────────
onMounted(async () => {
  if (!flightID) { error.value = 'No flight ID provided.'; loading.value = false; return }

  const storageKey = `flightSearchComposite:${flightID}`

  try {
    const prefetched = sessionStorage.getItem(storageKey)

    if (prefetched) {
      const parsed = JSON.parse(prefetched)
      flight.value = parsed.flight
      seats.value = Array.isArray(parsed.seats) ? parsed.seats : []
      sessionStorage.removeItem(storageKey)
    }

    if (!flight.value) {
      const res = await axios.get(`http://localhost:5011/flight-search/${flightID}`)
      flight.value = res.data.flight
      seats.value = Array.isArray(res.data.seats) ? res.data.seats : []
    }
  } catch (e) {
    console.error('Flight search composite error:', e)
    error.value = 'Could not load flight details. Please try again.'
  } finally {
    loading.value = false
  }
})

// ─── Seat selection ───────────────────────────────────────
function onSeatSelected(seats) { selectedSeats.value = seats }

// ─── Computed price ───────────────────────────────────────
const totalPrice = computed(() => {
  if (!flight.value) return '0.00'
  const base = parseFloat(flight.value.Price ?? flight.value.price ?? 0)
  return (base * passengers).toFixed(2)
})

// ─── Format helpers ───────────────────────────────────────
// Detect overnight flight (arrival time < departure time → crossed midnight)
const isNextDay = computed(() => {
  if (!flight.value) return false
  const [dh, dm] = (flight.value.DepartureTime ?? '00:00').slice(0, 5).split(':').map(Number)
  const [ah, am] = (flight.value.ArrivalTime   ?? '00:00').slice(0, 5).split(':').map(Number)
  return ah * 60 + am < dh * 60 + dm
})

const arrivalDate = computed(() => {
  if (!flight.value?.Date) return ''
  const [day, month, year] = flight.value.Date.split('/')
  const d = new Date(`${year}-${month}-${day}`)
  if (isNextDay.value) d.setDate(d.getDate() + 1)
  return d.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
})

// "14:30" → "2:30 PM"
function formatTime(t) {
  if (!t) return '--'
  const [h, m] = t.slice(0, 5).split(':').map(Number)
  const period = h >= 12 ? 'PM' : 'AM'
  const h12    = h % 12 || 12
  return `${h12}:${String(m).padStart(2, '0')} ${period}`
}

// "3:00" or "3:00h" → "3h 00m"
function formatDuration(d) {
  if (!d) return '--'
  const clean = String(d).replace('h', '').trim()
  const [h, m = '00'] = clean.split(':')
  return `${parseInt(h)}h ${String(m).padStart(2, '0')}m`
}

// "03/05/2026" → "Sun, May 3, 2026"
function formatDate(d) {
  if (!d) return '--'
  const [day, month, year] = d.split('/')
  return new Date(`${year}-${month}-${day}`).toLocaleDateString('en-US', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
  })
}

// ─── Navigation ───────────────────────────────────────────
function goBack() { router.back() }

function continueToBooking() {
  if (selectedSeats.value.length !== passengers) {
    alert(`Please select ${passengers} seat(s) before continuing.`)
    return
  }
  
  const seatString = selectedSeats.value.join(',')

  if (!currentPassenger.value) {
    router.push({ path: '/auth', query: { redirect: '/flight-detail', flightID, ...searchParams } })
    return
  }

  if (searchParams.tripType === 'round-trip' && !isReturn) {
    // Proceed to return flight selection
    router.push({
      path: '/search-results',
      query: {
        step: 'return',
        outboundFlightID: flightID,
        outboundFlightNumber: flight.value?.FlightNumber,
        outboundOrigin: flight.value?.Origin,
        outboundDestination: flight.value?.Destination,
        outboundPrice: totalPrice.value,
        outboundSeat: seatString,
        ...searchParams,
      }
    })
    return
  }

  // Otherwise, proceed to checkout (one-way or round-trip return flight)
  router.push({
    path: '/booking-confirmation',
    query: {
      flightID,
      flightNumber:         flight.value?.FlightNumber,
      amount:               totalPrice.value,
      seatNumber:           seatString,
      outboundFlightID:     route.query.outboundFlightID || '',
      outboundFlightNumber: route.query.outboundFlightNumber || '',
      outboundSeat:         route.query.outboundSeat     || '',
      outboundPrice:        route.query.outboundPrice    || '',
      ...searchParams,
    }
  })
}
</script>

<template>
  <main class="relative min-h-screen overflow-hidden" style="background: linear-gradient(135deg, #f8f8fa 0%, #f0f0f5 100%);">
    <div class="pointer-events-none absolute inset-0 z-0">
      <div class="absolute -top-40 -right-40 h-[500px] w-[500px] rounded-full bg-[#e63946]/7 blur-[110px]"></div>
      <div class="absolute -bottom-40 -left-40 h-[420px] w-[420px] rounded-full bg-indigo-400/5 blur-[95px]"></div>
    </div>

    <div class="relative z-10 mx-auto h-[calc(100vh-56px)] max-w-[1520px] px-5 py-3 md:px-8 xl:px-12">
      <div v-if="loading" class="flex h-full flex-col items-center justify-center">
        <div class="relative flex h-14 w-14 items-center justify-center">
          <div class="absolute h-full w-full animate-ping rounded-full border-[3px] border-[#e63946]/20"></div>
          <div class="h-7 w-7 animate-spin rounded-full border-[3px] border-[#e63946] border-t-transparent"></div>
        </div>
        <p class="mt-4 text-xs font-bold uppercase tracking-[0.2em] text-[#6e6e73]">Loading flight…</p>
      </div>

      <div v-else-if="error" class="flex h-full flex-col items-center justify-center text-center">
        <p class="text-base font-semibold text-[#1d1d1f]">{{ error }}</p>
        <button @click="goBack" class="mt-5 rounded-full bg-[#e63946] px-7 py-2.5 text-sm font-bold text-white transition hover:bg-[#d62839]">Go Back</button>
      </div>

      <div v-else class="grid h-full grid-cols-1 gap-4 lg:grid-cols-[420px_1fr] xl:grid-cols-[460px_1fr]">
        <aside class="rounded-[24px] border border-white/80 bg-white/85 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.07)] backdrop-blur-2xl">
          <div class="mb-4 flex items-center justify-between">
            <button
              @click="goBack"
              class="inline-flex items-center gap-1.5 rounded-full border border-black/8 bg-white px-3 py-1.5 text-[11px] font-semibold text-[#1d1d1f] transition hover:bg-[#f8f8fa]"
            >
              <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" d="M15 19l-7-7 7-7"/>
              </svg>
              Back to Results
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
            <span class="text-sm font-semibold text-[#6e6e73]">${{ parseFloat(flight.Price ?? flight.price).toFixed(2) }}</span>
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
            <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Amenities</p>
            <p class="mt-1 text-sm font-semibold text-[#1d1d1f]">
              {{ flight.Baggage || 'Baggage N/A' }} · {{ flight.Meals || 'Meals N/A' }} · {{ flight.Beverages || 'Beverages N/A' }} · {{ flight.Wifi ? 'Wi-Fi Included' : 'No Wi-Fi' }}
            </p>
          </div>

          <div class="mt-4 rounded-2xl border border-[#e63946]/15 bg-gradient-to-br from-[#e63946]/6 to-rose-50 p-3.5">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#e63946]">Selected Seats</p>
                <p class="mt-1 text-lg font-bold text-[#1d1d1f]">{{ selectedSeats.length ? selectedSeats.join(', ') : 'None yet' }}</p>
              </div>
              <div class="text-right">
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Total</p>
                <p class="mt-1 text-2xl font-bold text-[#e63946]">${{ totalPrice }}</p>
              </div>
            </div>
          </div>

          <button
            :disabled="selectedSeats.length !== passengers"
            @click="continueToBooking"
            class="mt-4 w-full rounded-[14px] py-3 text-sm font-bold uppercase tracking-[0.12em] text-white transition-all"
            :class="selectedSeats.length === passengers
              ? 'bg-gradient-to-r from-[#e63946] to-[#f43f5e] shadow-[0_8px_24px_rgba(230,57,70,0.28)] hover:-translate-y-0.5'
              : 'bg-[#d1d1d6] cursor-not-allowed opacity-70'"
          >
            <span v-if="selectedSeats.length !== passengers">Select {{ passengers }} seat(s) to continue</span>
            <span v-else>Continue to Booking · ${{ totalPrice }}</span>
          </button>
        </aside>

        <section class="rounded-[24px] border border-white/80 bg-white/80 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.07)] backdrop-blur-2xl">
          <div class="mb-3">
            <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-[#a1a1a6]">Cabin Map</p>
            <h2 class="text-2xl font-semibold tracking-tight text-[#1d1d1f]">Choose Your Seat</h2>
          </div>
          <div class="h-[calc(100%-52px)]">
            <SeatSelector
              :flightId="flightID"
              :seatsData="seats"
              :maxSeats="passengers"
              @seatSelected="onSeatSelected"
            />
          </div>
        </section>
      </div>
    </div>
  </main>
</template>
