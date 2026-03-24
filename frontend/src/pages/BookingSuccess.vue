<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route  = useRoute()
const router = useRouter()

const bookingID = route.params.bookingID
const sessionID = route.query.session_id   // Stripe appends this to the successUrl
const returnBookingID = route.query.returnBookingID || null

const booking = ref(null)
const returnBooking = ref(null)
const outboundFlight = ref(null)
const returnFlight = ref(null)
const payment = ref(null)
const loading = ref(true)
const error = ref(null)

const isRoundTrip = computed(() => !!returnBooking.value)

const totalPaid = computed(() => {
  const outboundAmount = Number(booking.value?.amount || 0)
  const returnAmount = Number(returnBooking.value?.amount || 0)
  return outboundAmount + returnAmount
})

function formatAmount(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '0.00'
  return amount.toFixed(2)
}

function formatDate(value) {
  if (!value) return '--'
  const [day, month, year] = String(value).split('/')
  if (!day || !month || !year) return String(value)
  return new Date(`${year}-${month}-${day}`).toLocaleDateString('en-US', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function formatTime(value) {
  if (!value) return '--'
  const [hStr, mStr = '00'] = String(value).slice(0, 5).split(':')
  const h = Number(hStr)
  const m = Number(mStr)
  if (!Number.isFinite(h) || !Number.isFinite(m)) return String(value)
  const period = h >= 12 ? 'PM' : 'AM'
  const hour12 = h % 12 || 12
  return `${hour12}:${String(m).padStart(2, '0')} ${period}`
}

async function fetchFlightDetails(flightID) {
  if (!flightID) return null
  try {
    const response = await axios.get(`http://localhost:3003/flight/${flightID}`)
    return response.data
  } catch {
    return null
  }
}

onMounted(async () => {
  try {
    // Step 1: Finalize booking through Booking Composite
    if (!sessionID) {
      throw new Error('Missing payment session id.')
    }

    const finalizePayload = {
      bookingID:        Number(bookingID),
      sessionID,
      flightID:         Number(route.query.flightID),
      seatNumber:       route.query.seatNumber,
      returnBookingID:  route.query.returnBookingID  ? Number(route.query.returnBookingID)  : null,
      returnFlightID:   route.query.returnFlightID   ? Number(route.query.returnFlightID)   : null,
      returnSeatNumber: route.query.returnSeatNumber || null,
      // ── extra fields for notification email ──
      flightNumber:     route.query.flightNumber     || null,
      origin:           route.query.origin           || null,
      destination:      route.query.destination      || null,
      departureDate:    route.query.departureDate     || null,
    }

    const finalizeResponse = await axios.post(
      'http://localhost:3010/api/bookings/finalize',
      finalizePayload
    )
    payment.value = finalizeResponse.data.payment

    // Step 2: Fetch outbound booking details from Booking Composite
    const bookingResponse = await axios.get(
      `http://localhost:3010/api/bookings/${bookingID}`
    )
    booking.value = bookingResponse.data

    // Step 3: Fetch return booking if exists
    if (returnBookingID) {
      const returnBookingResponse = await axios.get(
        `http://localhost:3010/api/bookings/${returnBookingID}`
      )
      returnBooking.value = returnBookingResponse.data
    }

    // Step 4: Fetch flight details for display blocks
    outboundFlight.value = await fetchFlightDetails(booking.value?.flightID)
    if (returnBooking.value?.flightID) {
      returnFlight.value = await fetchFlightDetails(returnBooking.value.flightID)
    }

  } catch (err) {
    console.error('Error confirming booking:', err)
    error.value = err.response?.data?.message || 'Could not confirm your booking. Please contact support.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="min-h-screen bg-[#f5f5f7] py-20">
    <div class="mx-auto max-w-[600px] px-6 md:px-10">

      <!-- Loading -->
      <div v-if="loading" class="flex flex-col items-center justify-center py-20 gap-4">
        <div class="h-12 w-12 animate-spin rounded-full border-4 border-[#e63946] border-t-transparent"></div>
        <p class="text-sm text-[#6e6e73]">Confirming your payment...</p>
      </div>

      <!-- Error -->
      <div
        v-else-if="error"
        class="rounded-[32px] border border-red-200 bg-white p-8 text-center shadow-[0_20px_48px_rgba(0,0,0,0.08)]"
      >
        <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-red-100">
          <svg class="h-10 w-10 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h1 class="text-2xl font-semibold text-[#1d1d1f]">Something went wrong</h1>
        <p class="mt-2 text-sm text-[#6e6e73]">{{ error }}</p>
        <button
          class="mt-8 rounded-2xl bg-[#1d1d1f] px-8 py-3 text-sm font-medium text-white hover:bg-black transition"
          @click="router.push('/')"
        >
          Back to Home
        </button>
      </div>

      <!-- Success -->
      <div
        v-else
        class="rounded-[32px] border border-black/10 bg-white p-8 text-center shadow-[0_20px_48px_rgba(0,0,0,0.08)]"
      >
        <!-- Success icon -->
        <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-green-100">
          <svg class="h-10 w-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>

        <h1 class="text-3xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">Booking Confirmed!</h1>
        <p class="mt-2 text-[#6e6e73]">Your flight has been successfully booked and payment received.</p>

        <!-- Booking summary -->
        <div class="mt-8 rounded-2xl bg-[#f5f5f7] p-6 text-left">
          <div class="space-y-5">
            <div class="flex justify-between">
              <span class="text-[#6e6e73] text-sm">Booking Reference</span>
              <span class="font-mono font-medium text-[#1d1d1f]">#{{ bookingID }}</span>
            </div>

            <div v-if="returnBookingID" class="flex justify-between">
              <span class="text-[#6e6e73] text-sm">Return Booking Ref</span>
              <span class="font-mono font-medium text-[#1d1d1f]">#{{ returnBookingID }}</span>
            </div>

            <!-- Leg 1 -->
            <div v-if="booking" class="rounded-xl border border-black/10 bg-white px-4 py-3">
              <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Flight 1</p>
              <div class="mt-2 grid grid-cols-2 gap-2 text-sm">
                <span class="text-[#6e6e73]">Flight</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ outboundFlight?.FlightNumber || ('#' + booking.flightID) }}</span>
                <span class="text-[#6e6e73]">Route</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ outboundFlight?.Origin || '--' }} → {{ outboundFlight?.Destination || '--' }}</span>
                <span class="text-[#6e6e73]">Date</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ formatDate(outboundFlight?.Date) }}</span>
                <span class="text-[#6e6e73]">Time</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ formatTime(outboundFlight?.DepartureTime) }} - {{ formatTime(outboundFlight?.ArrivalTime) }}</span>
                <span class="text-[#6e6e73]">Seat</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ booking.seatNumber }}</span>
                <span class="text-[#6e6e73]">Fare</span>
                <span class="text-right font-medium text-[#1d1d1f]">${{ formatAmount(booking.amount) }}</span>
              </div>
            </div>

            <!-- Leg 2 -->
            <div v-if="returnBooking" class="rounded-xl border border-black/10 bg-white px-4 py-3">
              <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Flight 2</p>
              <div class="mt-2 grid grid-cols-2 gap-2 text-sm">
                <span class="text-[#6e6e73]">Flight</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ returnFlight?.FlightNumber || ('#' + returnBooking.flightID) }}</span>
                <span class="text-[#6e6e73]">Route</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ returnFlight?.Origin || '--' }} → {{ returnFlight?.Destination || '--' }}</span>
                <span class="text-[#6e6e73]">Date</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ formatDate(returnFlight?.Date) }}</span>
                <span class="text-[#6e6e73]">Time</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ formatTime(returnFlight?.DepartureTime) }} - {{ formatTime(returnFlight?.ArrivalTime) }}</span>
                <span class="text-[#6e6e73]">Seat</span>
                <span class="text-right font-medium text-[#1d1d1f]">{{ returnBooking.seatNumber }}</span>
                <span class="text-[#6e6e73]">Fare</span>
                <span class="text-right font-medium text-[#1d1d1f]">${{ formatAmount(returnBooking.amount) }}</span>
              </div>
            </div>

            <div class="flex justify-between">
              <span class="text-[#6e6e73] text-sm">Status</span>
              <span class="font-medium text-green-600">{{ booking?.status || 'Confirmed' }}</span>
            </div>

            <div class="flex justify-between">
              <span class="text-[#6e6e73] text-sm">Total Amount Paid</span>
              <span class="font-medium text-[#1d1d1f]">${{ formatAmount(totalPaid) }}</span>
            </div>

            <!-- Payment confirmation -->
            <template v-if="payment">
              <div class="border-t border-black/10 pt-3 flex justify-between">
                <span class="text-[#6e6e73] text-sm">Payment Status</span>
                <span class="font-medium text-green-600">{{ payment.status }}</span>
              </div>
            </template>
          </div>
        </div>

        <p class="mt-4 text-xs text-[#6e6e73]">
          A confirmation email has been sent to your registered email address.
        </p>

        <div class="mt-8 flex gap-4">
          <button
            class="flex-1 rounded-2xl border border-black/10 bg-white py-3 text-sm font-medium text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="router.push('/')"
          >
            Back to Home
          </button>
          <button
            class="flex-1 rounded-2xl bg-[#1d1d1f] py-3 text-sm font-medium text-white transition hover:bg-black"
            @click="router.push('/my-bookings')"
          >
            View My Bookings
          </button>
        </div>
      </div>

    </div>
  </main>
</template>