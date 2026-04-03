<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import SeatSelector from './SeatSelector.vue'
import { usePassengerSession } from '../composables/usePassengerSession'
import { apiUrl } from '../config/api'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()

const offerID = Number.parseInt(route.query.offerID, 10)

const loading = ref(true)
const submitting = ref(false)
const error = ref(null)
const offer = ref(null)
const newFlight = ref(null)
const seats = ref([])
const groupBookings = ref([])
const selectedSeats = ref([])

const travelers = computed(() =>
  groupBookings.value.map((record, index) => ({
    id: record.bookingID,
    firstName: record.isGuest ? record.guestFirstName : (currentPassenger.value?.FirstName || ''),
    lastName: record.isGuest ? record.guestLastName : (currentPassenger.value?.LastName || ''),
    displayName: record.isGuest
      ? `${record.guestFirstName || ''} ${record.guestLastName || ''}`.trim() || `Passenger ${index + 1}`
      : `${currentPassenger.value?.FirstName || ''} ${currentPassenger.value?.LastName || ''}`.trim() || `Passenger ${index + 1}`,
  }))
)

const totalPrice = computed(() =>
  groupBookings.value.reduce((sum, record) => sum + Number(record.amount || record.amountPaid || 0), 0).toFixed(2)
)

const initialAssignments = computed(() => Array.from({ length: travelers.value.length }, () => ''))

function formatDate(dateText) {
  if (!dateText) return '--'
  const [day, month, year] = String(dateText).split('/')
  return new Date(`${year}-${month}-${day}`).toLocaleDateString('en-US', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function formatTime(timeText) {
  if (!timeText) return '--'
  const [hour, minute] = String(timeText).slice(0, 5).split(':').map(Number)
  const suffix = hour >= 12 ? 'PM' : 'AM'
  const hour12 = hour % 12 || 12
  return `${hour12}:${String(minute).padStart(2, '0')} ${suffix}`
}

function onSeatSelected(assignments) {
  selectedSeats.value = assignments
}

async function loadContext() {
  loading.value = true
  error.value = null

  try {
    if (!currentPassenger.value) {
      router.push('/auth')
      return
    }

    if (!offerID) {
      throw new Error('Invalid rebooking link.')
    }

    const offerResponse = await axios.get(apiUrl(`/api/offer/${offerID}`))
    offer.value = offerResponse.data

    if (String(offer.value.status) !== 'Pending Response') {
      throw new Error(`This offer has already been ${String(offer.value.status).toLowerCase()}.`)
    }

    const primaryBookingResponse = await axios.get(apiUrl(`/api/bookings/${offer.value.bookingID}`))
    const primaryBooking = primaryBookingResponse.data
    const bookerID = Number(primaryBooking.bookedByPassengerID || primaryBooking.BookedByPassengerID || primaryBooking.passengerID || primaryBooking.PassengerID)
    const createdAt = String(primaryBooking.createdAt || primaryBooking.createdTime || primaryBooking.CreatedTime || '')

    const [allBookingsResponse, newFlightResponse, seatsResponse] = await Promise.all([
      axios.get(apiUrl(`/api/bookings/passenger/${bookerID}`)),
      axios.get(apiUrl(`/api/flight/${offer.value.newFlightID}`)),
      axios.get(apiUrl(`/api/seats/${offer.value.newFlightID}`)),
    ])

    groupBookings.value = (Array.isArray(allBookingsResponse.data) ? allBookingsResponse.data : [])
      .filter((record) => {
        const sameBooker = Number(record.bookedByPassengerID || record.BookedByPassengerID || record.passengerID || record.PassengerID) === bookerID
        const sameCreatedAt = String(record.createdAt || record.createdTime || record.CreatedTime || '') === createdAt
        const sameFlight = Number(record.flightID || record.FlightID) === Number(offer.value.origFlightID)
        return sameBooker && sameCreatedAt && sameFlight
      })
      .sort((a, b) => Number(a.bookingID || a.BookingID) - Number(b.bookingID || b.BookingID))

    if (!groupBookings.value.length) {
      throw new Error('Could not find the affected travellers for this offer.')
    }

    newFlight.value = newFlightResponse.data
    seats.value = Array.isArray(seatsResponse.data) ? seatsResponse.data : []
    selectedSeats.value = Array.from({ length: groupBookings.value.length }, () => '')
  } catch (err) {
    console.error('Error loading rebooking seat selection:', err)
    error.value = err.response?.data?.message || err.message || 'Could not load replacement seat selection.'
  } finally {
    loading.value = false
  }
}

async function confirmRebookingSeats() {
  const everyPassengerSeated = selectedSeats.value.length === travelers.value.length && selectedSeats.value.every(Boolean)
  if (!everyPassengerSeated) {
    error.value = `Please assign ${travelers.value.length} seat(s) before continuing.`
    return
  }

  submitting.value = true
  error.value = null

  try {
    await axios.post(apiUrl('/api/rebooking/accept'), {
      offerID,
      bookingIDs: groupBookings.value.map((record) => Number(record.bookingID || record.BookingID)),
      seatAssignments: selectedSeats.value,
      frontendBaseUrl: window.location.origin,
    })

    router.push('/my-bookings')
  } catch (err) {
    console.error('Error confirming rebooking seats:', err)
    error.value = err.response?.data?.message || 'Could not confirm the new seats. Please try again.'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadContext()
})
</script>

<template>
  <main class="relative min-h-screen overflow-hidden bg-[linear-gradient(135deg,#f8f8fa_0%,#f0f0f5_100%)]">
    <div class="pointer-events-none absolute inset-0 z-0">
      <div class="absolute -right-40 -top-40 h-[500px] w-[500px] rounded-full bg-[#e63946]/7 blur-[110px]"></div>
      <div class="absolute -bottom-40 -left-40 h-[420px] w-[420px] rounded-full bg-[#d4a64c]/8 blur-[95px]"></div>
    </div>

    <div class="relative z-10 mx-auto max-w-[1520px] px-5 py-6 md:px-8 xl:px-12">
      <div class="mb-8 rounded-[28px] bg-white/80 px-6 py-6 shadow-[0_20px_48px_rgba(0,0,0,0.06)] backdrop-blur-2xl">
        <div class="grid grid-cols-3 items-start gap-6">
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#d48710] text-sm font-bold text-white">1</div>
            <div class="min-w-0 flex-1 pt-1">
              <div class="h-1 rounded-full bg-[#d48710]"></div>
              <p class="mt-3 text-sm font-semibold text-[#9a6200]">Review rebooking</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#e63946] text-sm font-bold text-white shadow-[0_10px_18px_rgba(230,57,70,0.22)]">2</div>
            <div class="min-w-0 flex-1 pt-1">
              <div class="h-1 rounded-full bg-[#e63946]"></div>
              <p class="mt-3 text-sm font-semibold text-[#e63946]">Choose your seats</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#eef0f5] text-sm font-bold text-[#7d8594]">3</div>
            <div class="min-w-0 flex-1 pt-1">
              <div class="h-1 rounded-full bg-[#d9dde6]"></div>
              <p class="mt-3 text-sm font-semibold text-[#1d1d1f]">Confirm replacement</p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loading" class="flex min-h-[60vh] flex-col items-center justify-center">
        <div class="relative flex h-14 w-14 items-center justify-center">
          <div class="absolute h-full w-full animate-ping rounded-full border-[3px] border-[#e63946]/20"></div>
          <div class="h-7 w-7 animate-spin rounded-full border-[3px] border-[#e63946] border-t-transparent"></div>
        </div>
        <p class="mt-4 text-xs font-bold uppercase tracking-[0.2em] text-[#6e6e73]">Loading replacement seats...</p>
      </div>

      <div v-else-if="error" class="flex min-h-[60vh] flex-col items-center justify-center text-center">
        <p class="text-base font-semibold text-[#1d1d1f]">{{ error }}</p>
        <button @click="router.push('/my-bookings')" class="mt-5 rounded-full bg-[#e63946] px-7 py-2.5 text-sm font-bold text-white transition hover:bg-[#d62839]">Back to My Bookings</button>
      </div>

      <div v-else class="grid gap-4 lg:grid-cols-[420px_1fr] xl:grid-cols-[460px_1fr]">
        <aside class="relative z-20 rounded-[24px] border border-white/80 bg-white/85 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.07)] backdrop-blur-2xl">
          <div class="mb-4 flex items-center justify-between">
            <button
              @click="router.push({ path: '/rebooking-offer', query: { offerID } })"
              class="inline-flex items-center gap-1.5 rounded-full border border-black/8 bg-white px-3 py-1.5 text-[11px] font-semibold text-[#1d1d1f] transition hover:bg-[#f8f8fa]"
            >
              <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" d="M15 19l-7-7 7-7" />
              </svg>
              Back to offer
            </button>
            <span class="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[#b76b00]">
              Replacement Flight
            </span>
          </div>

          <div class="mb-4 flex items-center justify-between rounded-2xl bg-[#f5f5f7] px-3.5 py-3">
            <span class="text-sm font-bold text-[#1d1d1f]">{{ newFlight?.FlightNumber }}</span>
            <span class="text-sm font-semibold text-[#6e6e73]">${{ totalPrice }}</span>
          </div>

          <div class="mb-4 rounded-2xl bg-[#f5f5f7] p-3.5">
            <div class="flex items-center justify-between gap-2">
              <p class="truncate text-2xl font-bold text-[#1d1d1f]">{{ newFlight?.Origin }}</p>
              <span class="text-xs font-semibold uppercase tracking-[0.14em] text-[#a1a1a6]">Rebooked</span>
              <p class="truncate text-right text-2xl font-bold text-[#1d1d1f]">{{ newFlight?.Destination }}</p>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="rounded-xl bg-[#f5f5f7] p-3">
              <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Departure</p>
              <p class="mt-1 text-base font-bold text-[#1d1d1f]">{{ formatTime(newFlight?.DepartureTime) }}</p>
              <p class="text-[11px] text-[#6e6e73]">{{ formatDate(newFlight?.Date) }}</p>
            </div>
            <div class="rounded-xl bg-[#f5f5f7] p-3">
              <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Arrival</p>
              <p class="mt-1 text-base font-bold text-[#1d1d1f]">{{ formatTime(newFlight?.ArrivalTime) }}</p>
              <p class="text-[11px] text-[#6e6e73]">{{ formatDate(newFlight?.Date) }}</p>
            </div>
          </div>

          <div class="mt-4 rounded-xl border border-black/6 bg-white px-3.5 py-2.5">
            <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#a1a1a6]">Travellers</p>
            <div class="mt-2 space-y-2">
              <div v-for="(traveler, index) in travelers" :key="traveler.id" class="flex items-center justify-between text-sm">
                <span class="font-semibold text-[#1d1d1f]">{{ traveler.displayName }}</span>
                <span class="text-[#6e6e73]">{{ selectedSeats[index] || 'Seat not selected' }}</span>
              </div>
            </div>
          </div>

          <div class="mt-4 rounded-2xl border border-[#d48710]/20 bg-gradient-to-br from-[#fff7ec] to-[#fffaf4] p-3.5">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#b76b00]">Replacement Seats</p>
                <p class="mt-1 text-lg font-bold text-[#1d1d1f]">{{ selectedSeats.filter(Boolean).length ? selectedSeats.filter(Boolean).join(', ') : 'None yet' }}</p>
              </div>
              <div class="text-right">
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Travellers</p>
                <p class="mt-1 text-2xl font-bold text-[#b76b00]">{{ travelers.length }}</p>
              </div>
            </div>
          </div>

          <button
            :disabled="submitting || selectedSeats.length !== travelers.length || selectedSeats.some((seat) => !seat)"
            @click="confirmRebookingSeats"
            class="relative z-30 mt-4 w-full rounded-[14px] py-3 text-sm font-bold uppercase tracking-[0.12em] text-white transition-all"
            :class="submitting || selectedSeats.length !== travelers.length || selectedSeats.some((seat) => !seat)
              ? 'cursor-not-allowed bg-[#d1d1d6] opacity-70'
              : 'bg-gradient-to-r from-[#d48710] to-[#b76b00] shadow-[0_8px_24px_rgba(183,107,0,0.28)] hover:-translate-y-0.5'"
          >
            <span v-if="submitting">Confirming replacement...</span>
            <span v-else-if="selectedSeats.length !== travelers.length || selectedSeats.some((seat) => !seat)">
              Assign {{ travelers.length }} seat(s) to continue
            </span>
            <span v-else>
              Confirm Replacement Seats
            </span>
          </button>
        </aside>

        <section class="relative z-10 rounded-[24px] border border-white/80 bg-white/80 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.07)] backdrop-blur-2xl">
          <div class="mb-3">
            <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-[#a1a1a6]">Replacement Cabin</p>
            <h2 class="text-2xl font-semibold tracking-tight text-[#1d1d1f]">Choose New Seats</h2>
            <p class="mt-2 text-sm text-[#6e6e73]">
              Select the replacement seats you want for this rebooked flight. Once confirmed, these seats will be saved and no one else can book them.
            </p>
          </div>
          <div class="h-[calc(100%-72px)]">
            <SeatSelector
              :flightId="offer?.newFlightID"
              :seatsData="seats"
              :maxSeats="travelers.length"
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
