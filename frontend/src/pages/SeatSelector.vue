<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref(null)
const flight = ref(null)
const seats = ref([])
const selectedSeatNumber = ref('')

const searchParams = computed(() => ({
  tripType: route.query.tripType || 'one-way',
  departingCountry: route.query.departingCountry,
  arrivingCountry: route.query.arrivingCountry,
  departureDate: route.query.departureDate,
  returnDate: route.query.returnDate,
  passengers: route.query.passengers,
}))

const flightId = computed(() => Number(route.query.flightID || 0))
const fallbackAmount = computed(() => Number(route.query.amount || 0))

const seatRows = computed(() => {
  const rowSet = new Set(
    seats.value.map((seat) => Number(String(seat.SeatNumber).match(/\d+/)?.[0] || 0)).filter(Boolean)
  )
  return Array.from(rowSet).sort((a, b) => a - b)
})

const selectedSeat = computed(() => {
  return seats.value.find((seat) => seat.SeatNumber === selectedSeatNumber.value) || null
})

const basePrice = computed(() => Number(flight.value?.Price || fallbackAmount.value || 0))
const seatSurcharge = computed(() => {
  if (!selectedSeat.value) return 0
  const rowNum = Number(String(selectedSeat.value.SeatNumber).match(/\d+/)?.[0] || 0)
  return rowNum <= 2 ? 50 : 0
})
const totalPrice = computed(() => Number((basePrice.value + seatSurcharge.value).toFixed(2)))

function isSeatAvailable(seat) {
  return String(seat.Status || '').toLowerCase() === 'available'
}

function getSeatClass(seat) {
  if (!isSeatAvailable(seat)) {
    return 'bg-[#e5e5ea] text-[#a1a1a6] shadow-[inset_0_2px_4px_rgba(0,0,0,0.08)] cursor-not-allowed'
  }
  if (seat.SeatNumber === selectedSeatNumber.value) {
    return 'bg-gradient-to-b from-[#f43f5e] to-[#e63946] text-white scale-110 shadow-[0_10px_18px_rgba(230,57,70,0.35),inset_0_1px_1px_rgba(255,255,255,0.4)] ring-2 ring-[#e63946]/35 -translate-y-1 z-20'
  }
  const rowNum = Number(String(seat.SeatNumber).match(/\d+/)?.[0] || 0)
  if (rowNum <= 2) {
    return 'bg-gradient-to-b from-amber-50 to-white border border-amber-200 text-amber-900 shadow-[0_2px_8px_rgba(245,158,11,0.1)] hover:-translate-y-0.5 hover:shadow-[0_6px_14px_rgba(245,158,11,0.18)] hover:border-amber-300'
  }
  return 'bg-white border border-black/10 text-[#1d1d1f] shadow-[0_2px_8px_rgba(0,0,0,0.06)] hover:-translate-y-0.5 hover:shadow-[0_8px_16px_rgba(0,0,0,0.1)] hover:border-[#e63946]/30'
}

function getRowSeats(rowNum, side) {
  const rowSeats = seats.value
    .filter((seat) => Number(String(seat.SeatNumber).match(/\d+/)?.[0] || 0) === rowNum)
    .sort((a, b) => {
      const aCol = String(a.SeatNumber).match(/[A-Za-z]+/)?.[0] || ''
      const bCol = String(b.SeatNumber).match(/[A-Za-z]+/)?.[0] || ''
      return aCol.localeCompare(bCol)
    })

  if (side === 'left') return rowSeats.slice(0, 3)
  return rowSeats.slice(3, 6)
}

function selectSeat(seat) {
  if (!isSeatAvailable(seat)) return
  selectedSeatNumber.value = seat.SeatNumber
}

function goBack() {
  router.push({ path: '/search-results', query: { ...searchParams.value } })
}

function proceedToBooking() {
  if (!selectedSeat.value) return

  router.push({
    path: '/booking-confirmation',
    query: {
      flightID: flight.value?.FlightID || flightId.value,
      flightNumber: flight.value?.FlightNumber || route.query.flightNumber || 'N/A',
      seatNumber: selectedSeat.value.SeatNumber,
      amount: totalPrice.value,
      departingCountry: searchParams.value.departingCountry,
      arrivingCountry: searchParams.value.arrivingCountry,
      departureDate: searchParams.value.departureDate,
      returnDate: searchParams.value.returnDate,
      passengers: searchParams.value.passengers,
      tripType: searchParams.value.tripType,
    }
  })
}

onMounted(async () => {
  if (!flightId.value) {
    error.value = 'Missing flightID.'
    loading.value = false
    return
  }

  try {
    const response = await axios.get('http://localhost:3011/search/details', {
      params: { FlightID: flightId.value }
    })

    flight.value = response.data
    seats.value = Array.isArray(response.data.Seats) ? response.data.Seats : []
  } catch (err) {
    error.value = err.response?.data?.error || 'Failed to load flight details and seat map.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="min-h-screen bg-[#f5f5f7] py-10">
    <div class="mx-auto max-w-[1400px] px-6 md:px-10">
      <div class="mb-8 flex items-center justify-between">
        <button
          class="group flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm font-medium text-[#1d1d1f] shadow-sm backdrop-blur-md transition hover:bg-white"
          @click="goBack"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Flights
        </button>

        <div class="hidden rounded-full border border-black/10 bg-white/70 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6e6e73] md:block">
          Flight Search Composite View
        </div>
      </div>

      <div v-if="loading" class="flex min-h-[60vh] flex-col items-center justify-center gap-4">
        <div class="h-12 w-12 animate-spin rounded-full border-4 border-[#e63946] border-t-transparent"></div>
        <p class="text-sm text-[#6e6e73]">Loading flight details and cabin map...</p>
      </div>

      <div v-else-if="error" class="rounded-[28px] border border-red-200 bg-white p-10 text-center shadow-[0_20px_48px_rgba(0,0,0,0.08)]">
        <h1 class="text-2xl font-semibold text-[#1d1d1f]">Unable to load this flight</h1>
        <p class="mt-2 text-sm text-[#6e6e73]">{{ error }}</p>
      </div>

      <div v-else class="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
        <section class="rounded-[32px] border border-black/10 bg-white/85 p-8 shadow-[0_24px_52px_rgba(0,0,0,0.08)] backdrop-blur-xl">
          <p class="text-xs font-semibold uppercase tracking-[0.14em] text-[#6e6e73]">Flight Details</p>
          <h1 class="mt-3 text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f]">{{ flight?.FlightNumber }}</h1>

          <div class="mt-8 rounded-2xl border border-black/10 bg-[#f8f8fa] p-5">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-2xl font-bold text-[#1d1d1f]">{{ flight?.DepartureTime }}</p>
                <p class="text-xs uppercase tracking-[0.12em] text-[#6e6e73]">{{ flight?.Origin }}</p>
              </div>
              <div class="px-4 text-[#e63946]">
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
              </div>
              <div class="text-right">
                <p class="text-2xl font-bold text-[#1d1d1f]">{{ flight?.ArrivalTime }}</p>
                <p class="text-xs uppercase tracking-[0.12em] text-[#6e6e73]">{{ flight?.Destination }}</p>
              </div>
            </div>
            <div class="mt-4 text-xs text-[#6e6e73]">Date: {{ flight?.Date }} · Duration: {{ flight?.FlightDuration }}</div>
          </div>

          <div class="mt-6 space-y-3 rounded-2xl border border-black/10 bg-white p-5">
            <div class="flex items-center justify-between text-sm">
              <span class="text-[#6e6e73]">Base Fare</span>
              <span class="font-semibold text-[#1d1d1f]">${{ basePrice.toFixed(2) }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-[#6e6e73]">Seat Premium</span>
              <span class="font-semibold text-[#1d1d1f]">${{ seatSurcharge.toFixed(2) }}</span>
            </div>
            <div class="border-t border-black/10 pt-3">
              <div class="flex items-center justify-between">
                <span class="text-sm font-semibold uppercase tracking-[0.08em] text-[#1d1d1f]">Total</span>
                <span class="text-2xl font-bold text-[#e63946]">${{ totalPrice.toFixed(2) }}</span>
              </div>
            </div>
          </div>

          <div class="mt-6 rounded-2xl border border-black/10 bg-[#f8f8fa] p-5">
            <p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Selected Seat</p>
            <p class="mt-2 text-2xl font-semibold text-[#1d1d1f]">{{ selectedSeatNumber || 'Choose a seat on the map' }}</p>
            <p class="mt-1 text-xs text-[#6e6e73]">Unavailable seats are greyed out. Premium front-row seats have a crown marker.</p>
          </div>

          <button
            class="mt-8 w-full rounded-2xl bg-[#1d1d1f] py-4 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-black disabled:opacity-40 disabled:cursor-not-allowed"
            :disabled="!selectedSeat"
            @click="proceedToBooking"
          >
            Book Selected Seat
          </button>
        </section>

        <section class="rounded-[32px] border border-black/10 bg-white/90 p-8 shadow-[0_24px_52px_rgba(0,0,0,0.08)] backdrop-blur-xl">
          <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
            <h2 class="text-2xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">Cabin Seat Map</h2>
            <div class="flex flex-wrap items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.08em]">
              <span class="inline-flex items-center gap-1.5 text-[#6e6e73]"><span class="h-3 w-3 rounded bg-white border border-black/10"></span>Available</span>
              <span class="inline-flex items-center gap-1.5 text-[#6e6e73]"><span class="h-3 w-3 rounded bg-[#e5e5ea]"></span>Occupied</span>
              <span class="inline-flex items-center gap-1.5 text-[#6e6e73]"><span class="h-3 w-3 rounded bg-gradient-to-b from-[#f43f5e] to-[#e63946]"></span>Selected</span>
              <span class="inline-flex items-center gap-1.5 text-amber-700"><span class="flex h-3 w-3 items-center justify-center rounded bg-amber-100 text-[8px]">👑</span>Premium</span>
            </div>
          </div>

          <div class="relative overflow-x-auto rounded-[44px] border-[10px] border-white bg-gradient-to-b from-[#fbfbfd] to-[#f5f5f7] p-6 shadow-[inset_0_6px_18px_rgba(0,0,0,0.03)]">
            <div class="absolute left-1/2 top-0 h-8 w-24 -translate-x-1/2 -translate-y-1/2 rounded-full border-4 border-white bg-sky-100/50"></div>
            <p class="mb-4 text-center text-[10px] font-bold uppercase tracking-[0.3em] text-[#a1a1a6]">Front</p>

            <div class="relative mx-auto w-fit">
              <div class="absolute bottom-0 left-1/2 top-0 w-10 -translate-x-1/2 bg-[linear-gradient(to_bottom,rgba(0,0,0,0.02)_50%,transparent_50%)] bg-[length:100%_24px]"></div>

              <div
                v-for="row in seatRows"
                :key="row"
                class="relative z-10 mb-3 flex items-center justify-center gap-3"
              >
                <div class="flex gap-2">
                  <button
                    v-for="seat in getRowSeats(row, 'left')"
                    :key="seat.SeatNumber"
                    class="relative flex h-10 w-10 items-center justify-center rounded-[10px] text-[11px] font-bold transition-all duration-300 transform-gpu"
                    :class="getSeatClass(seat)"
                    :disabled="!isSeatAvailable(seat)"
                    @click="selectSeat(seat)"
                  >
                    {{ seat.SeatNumber.match(/[A-Za-z]+/)?.[0] || '' }}
                    <span
                      v-if="Number(String(seat.SeatNumber).match(/\d+/)?.[0] || 0) <= 2 && isSeatAvailable(seat) && seat.SeatNumber !== selectedSeatNumber"
                      class="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-100 border border-amber-200 text-[6px]"
                    >👑</span>
                  </button>
                </div>

                <div class="flex w-10 items-center justify-center">
                  <span class="rounded-full bg-black/5 px-2 py-0.5 text-[9px] font-bold tracking-widest text-[#86868b]">{{ row }}</span>
                </div>

                <div class="flex gap-2">
                  <button
                    v-for="seat in getRowSeats(row, 'right')"
                    :key="seat.SeatNumber"
                    class="relative flex h-10 w-10 items-center justify-center rounded-[10px] text-[11px] font-bold transition-all duration-300 transform-gpu"
                    :class="getSeatClass(seat)"
                    :disabled="!isSeatAvailable(seat)"
                    @click="selectSeat(seat)"
                  >
                    {{ seat.SeatNumber.match(/[A-Za-z]+/)?.[0] || '' }}
                    <span
                      v-if="Number(String(seat.SeatNumber).match(/\d+/)?.[0] || 0) <= 2 && isSeatAvailable(seat) && seat.SeatNumber !== selectedSeatNumber"
                      class="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-100 border border-amber-200 text-[6px]"
                    >👑</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </main>
</template>
