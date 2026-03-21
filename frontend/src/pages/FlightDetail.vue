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
const loading       = ref(true)
const error         = ref(null)
const selectedSeats = ref([])

// ─── Fetch from composite service ─────────────────────────
onMounted(async () => {
  if (!flightID) { error.value = 'No flight ID provided.'; loading.value = false; return }
  try {
    const res = await axios.get(`http://localhost:5011/flight-search/${flightID}`)
    flight.value = res.data.flight
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

    <!-- Ambient blobs -->
    <div class="pointer-events-none absolute inset-0 z-0">
      <div class="absolute -top-40 -right-40 h-[600px] w-[600px] rounded-full bg-[#e63946]/8 blur-[120px]"></div>
      <div class="absolute -bottom-40 -left-40 h-[500px] w-[500px] rounded-full bg-indigo-400/6 blur-[100px]"></div>
    </div>

    <div class="relative z-10 mx-auto max-w-[1440px] px-6 pt-8 pb-20 md:px-10 xl:px-16">

      <!-- Back button -->
      <button
        @click="goBack"
        class="mb-8 inline-flex items-center gap-2 rounded-full border border-black/8 bg-white/80 px-5 py-2.5 text-sm font-semibold text-[#1d1d1f] shadow-sm backdrop-blur-xl transition-all hover:bg-white hover:shadow-md hover:-translate-x-0.5 active:scale-95"
      >
        <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" d="M15 19l-7-7 7-7"/>
        </svg>
        Back to Results
      </button>

      <!-- ── Loading ── -->
      <div v-if="loading" class="flex flex-col items-center justify-center py-48">
        <div class="relative flex h-16 w-16 items-center justify-center">
          <div class="absolute h-full w-full animate-ping rounded-full border-[3px] border-[#e63946]/20"></div>
          <div class="h-8 w-8 animate-spin rounded-full border-[3px] border-[#e63946] border-t-transparent"></div>
        </div>
        <p class="mt-5 text-xs font-bold uppercase tracking-[0.2em] text-[#6e6e73] animate-pulse">Loading flight…</p>
      </div>

      <!-- ── Error ── -->
      <div v-else-if="error" class="flex flex-col items-center justify-center py-48 text-center">
        <p class="text-5xl mb-4">✈️</p>
        <p class="text-base font-semibold text-[#1d1d1f]">{{ error }}</p>
        <button @click="goBack" class="mt-6 rounded-full bg-[#e63946] px-8 py-3 text-sm font-bold text-white hover:bg-[#d62839] transition-all">Go Back</button>
      </div>

      <!-- ── Main two-column layout ── -->
      <div v-else class="flex flex-col gap-6 lg:flex-row lg:items-start">

        <!-- ════════════════════════════════
             LEFT PANEL — Flight Details
        ════════════════════════════════ -->
        <aside class="w-full lg:w-[400px] xl:w-[440px] lg:flex-shrink-0">
          <div class="sticky top-8 overflow-hidden rounded-[28px] border border-white/80 bg-white/80 shadow-[0_24px_60px_rgba(0,0,0,0.07)] backdrop-blur-2xl">

            <!-- Coloured top strip -->
            <div class="h-1.5 w-full" :class="isReturn ? 'bg-gradient-to-r from-purple-500 to-purple-400' : 'bg-gradient-to-r from-[#e63946] to-[#f43f5e]'"></div>

            <div class="p-8">

              <!-- Label + badge row -->
              <div class="mb-6 flex items-center justify-between">
                <span
                  class="rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-[0.15em]"
                  :class="isReturn ? 'bg-purple-50 text-purple-600' : 'bg-red-50 text-[#e63946]'"
                >
                  {{ isReturn ? '↩ Return Flight' : '↗ Outbound Flight' }}
                </span>
                <div class="flex items-center gap-1.5 rounded-full border border-black/8 bg-[#f5f5f7] px-3 py-1.5">
                  <svg class="h-3.5 w-3.5 text-[#e63946]" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/>
                  </svg>
                  <span class="text-xs font-bold tracking-wide text-[#1d1d1f]">{{ flight.FlightNumber }}</span>
                </div>
              </div>

              <!-- Route display — fixed so long names don't overflow -->
              <div class="mb-6 flex items-center gap-2">
                <!-- Origin -->
                <div class="min-w-0 flex-1">
                  <p class="truncate text-[22px] font-bold leading-tight tracking-tight text-[#1d1d1f]">{{ flight.Origin }}</p>
                </div>
                <!-- Arrow -->
                <div class="flex flex-none flex-col items-center gap-1 px-2">
                  <div class="flex items-center gap-0.5">
                    <div class="h-px w-8 bg-gradient-to-r from-[#e63946]/30 to-[#e63946]/60"></div>
                    <svg class="h-3.5 w-3.5 text-[#e63946]" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/>
                    </svg>
                  </div>
                  <span class="text-[9px] font-semibold uppercase tracking-widest text-[#a1a1a6]">Direct</span>
                </div>
                <!-- Destination -->
                <div class="min-w-0 flex-1 text-right">
                  <p class="truncate text-[22px] font-bold leading-tight tracking-tight text-[#1d1d1f]">{{ flight.Destination }}</p>
                </div>
              </div>

              <!-- Details grid -->
              <div class="mb-6 grid grid-cols-2 gap-3">
                <div class="rounded-2xl bg-[#f5f5f7] p-4">
                  <p class="mb-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Departure</p>
                  <p class="text-sm font-bold text-[#1d1d1f]">{{ formatTime(flight.DepartureTime) }}</p>
                  <p class="mt-0.5 text-[11px] text-[#6e6e73]">{{ formatDate(flight.Date) }}</p>
                </div>
                <div class="rounded-2xl bg-[#f5f5f7] p-4">
                  <p class="mb-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Arrival</p>
                  <div class="flex items-center gap-1.5">
                    <p class="text-sm font-bold text-[#1d1d1f]">{{ formatTime(flight.ArrivalTime) }}</p>
                    <span v-if="isNextDay" class="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">+1</span>
                  </div>
                  <p class="mt-0.5 text-[11px] text-[#6e6e73]">
                    {{ isNextDay ? arrivalDate : formatDate(flight.Date) }}
                  </p>
                </div>
                <div class="rounded-2xl bg-[#f5f5f7] p-4">
                  <p class="mb-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Duration</p>
                  <p class="text-sm font-semibold text-[#1d1d1f]">{{ formatDuration(flight.FlightDuration) }}</p>
                </div>
                <div class="rounded-2xl bg-[#f5f5f7] p-4">
                  <p class="mb-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Status</p>
                  <span class="inline-flex items-center gap-1 text-sm font-semibold text-emerald-600">
                    <span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>{{ flight.Status }}
                  </span>
                </div>
                <div class="col-span-2 rounded-2xl bg-[#f5f5f7] p-4">
                  <p class="mb-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Base Fare</p>
                  <p class="text-sm font-bold text-[#1d1d1f]">${{ parseFloat(flight.Price ?? flight.price).toFixed(2) }}</p>
                </div>
              </div>

              <!-- Amenities -->
              <div class="mb-6 rounded-2xl bg-[#f5f5f7] p-4 text-[#1d1d1f]">
                <p class="mb-3 text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Included Amenities</p>
                <div class="grid grid-cols-2 gap-3 text-xs font-semibold text-[#6e6e73]">
                  <div class="flex items-center gap-2">
                    <span class="text-base">🧳</span><span class="text-[#1d1d1f]">{{ flight.Baggage }} Baggage</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-base">🍱</span><span class="text-[#1d1d1f]">{{ flight.Meals }}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-base">🥤</span><span class="text-[#1d1d1f]">{{ flight.Beverages }}</span>
                  </div>
                  <div v-if="flight.Wifi" class="flex items-center gap-2">
                    <span class="text-base">📶</span><span class="text-emerald-600">Free WiFi</span>
                  </div>
                </div>
              </div>

              <!-- Selected seat pill -->
              <transition
                enter-active-class="transition-all duration-300 ease-out"
                enter-from-class="opacity-0 scale-95"
                enter-to-class="opacity-100 scale-100"
                leave-active-class="transition-all duration-200"
                leave-from-class="opacity-100 scale-100"
                leave-to-class="opacity-0 scale-95"
              >
                <div v-if="selectedSeats.length > 0" class="mb-5 rounded-2xl border border-[#e63946]/15 bg-gradient-to-br from-[#e63946]/6 to-rose-50 p-5">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-[10px] font-bold uppercase tracking-[0.15em] text-[#e63946]">Selected Seats ({{ selectedSeats.length }}/{{ passengers }})</p>
                      <p class="mt-1 text-2xl font-bold text-[#1d1d1f]">{{ selectedSeats.join(', ') }}</p>
                    </div>
                    <div class="text-right">
                      <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Total</p>
                      <p class="mt-1 text-2xl font-bold text-[#e63946]">${{ totalPrice }}</p>
                    </div>
                  </div>
                </div>
              </transition>

              <!-- CTA button -->
              <button
                :disabled="selectedSeats.length !== passengers"
                @click="continueToBooking"
                class="group relative w-full overflow-hidden rounded-[18px] py-4 text-sm font-bold uppercase tracking-[0.12em] text-white transition-all duration-300 active:scale-[0.98]"
                :class="selectedSeats.length === passengers
                  ? 'bg-gradient-to-r from-[#e63946] to-[#f43f5e] shadow-[0_8px_24px_rgba(230,57,70,0.28)] hover:shadow-[0_12px_32px_rgba(230,57,70,0.38)] hover:-translate-y-0.5'
                  : 'bg-[#d1d1d6] cursor-not-allowed opacity-70'"
              >
                <div v-if="selectedSeats.length === passengers" class="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/15 to-transparent transition-transform duration-700 group-hover:translate-x-full"></div>
                <span class="relative z-10 flex items-center justify-center gap-2">
                  <span v-if="selectedSeats.length !== passengers">Select {{ passengers }} seat(s) to continue</span>
                  <template v-else>
                    Continue to Booking · ${{ totalPrice }}
                    <svg class="h-4 w-4 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7"/>
                    </svg>
                  </template>
                </span>
              </button>

            </div>
          </div>
        </aside>

        <!-- ════════════════════════════════
             RIGHT PANEL — Seat Map
        ════════════════════════════════ -->
        <section class="min-w-0 flex-1">
          <div class="rounded-[28px] border border-white/80 bg-white/70 shadow-[0_24px_60px_rgba(0,0,0,0.07)] backdrop-blur-2xl">

            <!-- Header -->
            <div class="border-b border-black/5 px-8 py-6">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-[#a1a1a6]">Cabin Map</p>
                  <h2 class="mt-0.5 text-2xl font-semibold tracking-tight text-[#1d1d1f]">Choose Your Seat</h2>
                </div>
                <!-- Inline legend -->
                <div class="hidden sm:flex items-center gap-5">
                  <div class="flex items-center gap-1.5">
                    <div class="h-3 w-3 rounded bg-white border border-black/10 shadow-sm"></div>
                    <span class="text-[11px] font-semibold text-[#6e6e73]">Available</span>
                  </div>
                  <div class="flex items-center gap-1.5">
                    <div class="h-3 w-3 rounded bg-gradient-to-br from-[#f43f5e] to-[#e63946] shadow-sm"></div>
                    <span class="text-[11px] font-semibold text-[#1d1d1f]">Selected</span>
                  </div>
                  <div class="flex items-center gap-1.5">
                    <div class="h-3 w-3 rounded bg-[#e5e5ea]"></div>
                    <span class="text-[11px] font-semibold text-[#a1a1a6]">Occupied</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Seat selector -->
            <div class="p-6 md:p-10">
              <SeatSelector
                :flightId="flightID"
                :maxSeats="passengers"
                @seatSelected="onSeatSelected"
              />
            </div>

          </div>
        </section>

      </div>
    </div>
  </main>
</template>
