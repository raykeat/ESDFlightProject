<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()

const loading     = ref(false)
const error       = ref(null)
const sessionUrl  = ref(route.query.sessionUrl || null)  // reuse session if returning from Stripe
const cancelCleanupDone = ref(false)

const isRoundTrip = !!route.query.outboundFlightID

const bookingDetails = ref({
  // The 'flightID' passed from FlightDetail for round-trip is actually the RETURN flight.
  // One-way: main flight. Round-trip: return flight.
  flightID:     parseInt(route.query.flightID),
  seatNumber:   route.query.seatNumber,
  amount:       parseFloat(route.query.amount),
  flightNumber: route.query.flightNumber || 'N/A',

  outboundFlightID:     route.query.outboundFlightID ? parseInt(route.query.outboundFlightID) : null,
  outboundFlightNumber: route.query.outboundFlightNumber || null,
  outboundSeat:         route.query.outboundSeat || null,
  outboundPrice:        route.query.outboundPrice ? parseFloat(route.query.outboundPrice) : null,
})

const totalAmount = computed(() => {
  if (isRoundTrip) {
    return bookingDetails.value.amount + (bookingDetails.value.outboundPrice || 0)
  }
  return bookingDetails.value.amount
})

const displayFlightNumber = computed(() => {
  if (isRoundTrip) {
    return `${bookingDetails.value.outboundFlightNumber} & ${bookingDetails.value.flightNumber}`
  }
  return bookingDetails.value.flightNumber
})

// Preserve search params so Back button returns to correct search results
const searchParams = {
  departingCountry: route.query.departingCountry,
  arrivingCountry:  route.query.arrivingCountry,
  departureDate:    route.query.departureDate,
  returnDate:       route.query.returnDate,
  passengers:       route.query.passengers,
  cabin:            route.query.cabin,
}

function goBack() {
  router.push({ path: '/search-results', query: searchParams })
}

async function cleanupCancelledPendingBooking() {
  if (cancelCleanupDone.value) return
  const bookingID = route.query.bookingID
  if (!bookingID) return

  try {
    await axios.post('http://localhost:3010/api/bookings/cancel-pending', {
      bookingID: Number(bookingID),
      returnBookingID: route.query.returnBookingID ? Number(route.query.returnBookingID) : null,
    })
    cancelCleanupDone.value = true
  } catch (e) {
    console.warn('Pending booking cleanup failed:', e)
  }
}

// ── Confirm booking & redirect to Stripe Checkout ───────────
async function confirmBooking() {
  if (!currentPassenger.value) {
    router.push('/auth')
    return
  }

  loading.value = true
  error.value   = null

  try {
    let finalSessionUrl = sessionUrl.value

    if (!finalSessionUrl) {
      // Step 1: Call Booking Composite to create a pending booking
      const payload = {
        passengerID: currentPassenger.value.passenger_id,
        // Primary flight: Outbound if round-trip, else the single flight
        flightID:    isRoundTrip ? bookingDetails.value.outboundFlightID : bookingDetails.value.flightID,
        seatNumber:  isRoundTrip ? bookingDetails.value.outboundSeat : bookingDetails.value.seatNumber,
        amount:      Number(bookingDetails.value.amount),
        flightNumber: displayFlightNumber.value,
        frontendBaseUrl: window.location.origin
      }

      if (isRoundTrip) {
        payload.returnFlightID   = bookingDetails.value.flightID
        payload.returnSeatNumber = bookingDetails.value.seatNumber
        payload.outboundAmount   = Number(bookingDetails.value.outboundPrice || 0)
        payload.returnAmount     = Number(bookingDetails.value.amount || 0)
      }

      const cancelUrl = new URL('http://localhost:5173/booking-confirmation')
      cancelUrl.searchParams.set('flightID',         bookingDetails.value.flightID)
      cancelUrl.searchParams.set('seatNumber',       bookingDetails.value.seatNumber)
      cancelUrl.searchParams.set('amount',           bookingDetails.value.amount)
      cancelUrl.searchParams.set('flightNumber',     bookingDetails.value.flightNumber)
      if (isRoundTrip) {
        cancelUrl.searchParams.set('outboundFlightID',     bookingDetails.value.outboundFlightID)
        cancelUrl.searchParams.set('outboundFlightNumber', bookingDetails.value.outboundFlightNumber)
        cancelUrl.searchParams.set('outboundSeat',         bookingDetails.value.outboundSeat)
        cancelUrl.searchParams.set('outboundPrice',        bookingDetails.value.outboundPrice)
      }
      cancelUrl.searchParams.set('departingCountry', searchParams.departingCountry || '')
      cancelUrl.searchParams.set('arrivingCountry',  searchParams.arrivingCountry  || '')
      cancelUrl.searchParams.set('departureDate',    searchParams.departureDate    || '')
      cancelUrl.searchParams.set('returnDate',       searchParams.returnDate       || '')
      cancelUrl.searchParams.set('passengers',       searchParams.passengers       || '')
      cancelUrl.searchParams.set('cabin',            searchParams.cabin            || '')
      cancelUrl.searchParams.set('cancelled',        'true')
      cancelUrl.searchParams.set('origin', searchParams.departingCountry || '')
      cancelUrl.searchParams.set('destination', searchParams.arrivingCountry || '')
      cancelUrl.searchParams.set('departureDate', searchParams.departureDate || '')
      payload.cancelUrl = cancelUrl.toString()

      const bookingResponse = await axios.post('http://localhost:3010/api/bookings', payload)

      const { bookingID, returnBookingID } = bookingResponse.data
      console.log(`Booking created with ID ${bookingID}${returnBookingID ? ` and return booking ${returnBookingID}` : ''}.`);

      // Step 2: Booking Composite orchestrates payment session creation
      finalSessionUrl = bookingResponse.data.sessionUrl

      // Store sessionUrl in URL so returning from Stripe reuses same session
      const currentUrl = new URL(window.location.href)
      currentUrl.searchParams.set('sessionUrl', finalSessionUrl)
      window.history.replaceState({}, '', currentUrl.toString())
    }

    // Step 3: Redirect passenger to Stripe's hosted payment page
    window.location.href = finalSessionUrl

  } catch (err) {
    console.error('Booking failed:', err)
    error.value   = err.response?.data?.message || 'Something went wrong. Please try again.'
    loading.value = false
  }
}

// Show cancelled message if redirected back from Stripe cancel
const wasCancelled = route.query.cancelled === 'true'

onMounted(async () => {
  if (wasCancelled) {
    await cleanupCancelledPendingBooking()
  }
})
</script>

<template>
  <main class="min-h-screen bg-[#f5f5f7] py-20">
    <div class="mx-auto max-w-[600px] px-6 md:px-10">

      <!-- Header -->
      <div class="mb-8">
        <button
          class="mb-4 flex items-center gap-2 text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition"
          @click="goBack()"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
        <h1 class="text-3xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">Confirm Your Booking</h1>
        <p class="mt-1 text-sm text-[#6e6e73]">Review your details before proceeding to payment</p>
      </div>

      <!-- Cancelled notice -->
      <div
        v-if="wasCancelled"
        class="mb-6 rounded-2xl border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800"
      >
        ⚠️ Payment was cancelled. You can try again below.
      </div>

      <!-- Booking Summary Card -->
      <div class="rounded-[28px] border border-black/10 bg-white p-8 shadow-[0_20px_48px_rgba(0,0,0,0.08)]">
        <h2 class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73] mb-6">Booking Summary</h2>

        <div class="space-y-4">
          <template v-if="!isRoundTrip">
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Flight</span>
              <span class="font-medium text-[#1d1d1f]">{{ bookingDetails.flightNumber }} (#{{ bookingDetails.flightID }})</span>
            </div>
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Seat(s)</span>
              <span class="font-medium text-[#1d1d1f] text-right">{{ bookingDetails.seatNumber.replace(/,/g, ', ') }}</span>
            </div>
          </template>
          <template v-else>
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Departure Flight</span>
              <div class="text-right">
                <span class="block font-medium text-[#1d1d1f]">{{ bookingDetails.outboundFlightNumber }}</span>
                <span class="block text-xs font-medium text-[#6e6e73]">Seat(s) {{ bookingDetails.outboundSeat?.replace(/,/g, ', ') }}</span>
              </div>
            </div>
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Return Flight</span>
              <div class="text-right">
                <span class="block font-medium text-[#1d1d1f]">{{ bookingDetails.flightNumber }}</span>
                <span class="block text-xs font-medium text-[#6e6e73]">Seat(s) {{ bookingDetails.seatNumber?.replace(/,/g, ', ') }}</span>
              </div>
            </div>
          </template>

          <div class="flex justify-between border-b border-black/10 pb-4">
            <span class="text-[#6e6e73]">Passenger</span>
            <span class="font-medium text-[#1d1d1f]">
              {{ currentPassenger?.FirstName }} {{ currentPassenger?.LastName }}
            </span>
          </div>
          <div class="flex justify-between text-lg font-semibold pt-1">
            <span>Total</span>
            <span class="text-[#e63946]">${{ totalAmount.toFixed(2) }}</span>
          </div>
        </div>

        <!-- What happens next -->
        <div class="mt-8 rounded-2xl bg-[#f5f5f7] p-4">
          <p class="text-xs font-semibold uppercase tracking-[0.1em] text-[#6e6e73] mb-3">What happens next</p>
          <div class="space-y-2">
            <div class="flex items-start gap-3">
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#1d1d1f] text-[10px] font-bold text-white">1</span>
              <p class="text-xs text-[#6e6e73]">You'll be redirected to Stripe's secure payment page</p>
            </div>
            <div class="flex items-start gap-3">
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#1d1d1f] text-[10px] font-bold text-white">2</span>
              <p class="text-xs text-[#6e6e73]">Enter your card details on Stripe's hosted page</p>
            </div>
            <div class="flex items-start gap-3">
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#1d1d1f] text-[10px] font-bold text-white">3</span>
              <p class="text-xs text-[#6e6e73]">After payment, you'll be redirected back with your confirmation</p>
            </div>
          </div>
        </div>

        <!-- Error -->
        <div v-if="error" class="mt-6 rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-600">
          {{ error }}
        </div>

        <!-- CTA -->
        <button
          class="mt-8 w-full rounded-2xl bg-[#1d1d1f] py-4 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-black disabled:opacity-50"
          :disabled="loading"
          @click="confirmBooking"
        >
          <span v-if="loading" class="flex items-center justify-center gap-2">
            <span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
            Redirecting to Stripe...
          </span>
          <span v-else>Proceed to Payment · ${{ bookingDetails.amount?.toFixed(2) }}</span>
        </button>

        <p class="mt-4 text-center text-xs text-[#6e6e73]">
          🔒 You'll be redirected to Stripe's secure payment page. We never handle your card details directly.
        </p>
      </div>

    </div>
  </main>
</template>