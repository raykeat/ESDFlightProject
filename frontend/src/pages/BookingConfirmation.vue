<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'
import { useBookingDraft } from '../composables/useBookingDraft'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()
const { bookingDraft } = useBookingDraft()

const loading = ref(false)
const error = ref(null)
const sessionUrl = ref(route.query.sessionUrl || null)

const isRoundTrip = computed(() => route.query.tripType === 'round-trip' && Boolean(route.query.outboundFlightID))
const draftTravelers = computed(() => bookingDraft.value?.travelers || [])
const outboundSeats = computed(() =>
  ((bookingDraft.value?.seatAssignments?.outbound || []).length
    ? bookingDraft.value.seatAssignments.outbound
    : String(route.query.outboundSeat || '').split(','))
    .map((seat) => seat?.trim?.() || '')
    .filter(Boolean)
)
const returnSeats = computed(() =>
  ((bookingDraft.value?.seatAssignments?.return || []).length
    ? bookingDraft.value.seatAssignments.return
    : String(route.query.seatNumber || '').split(','))
    .map((seat) => seat?.trim?.() || '')
    .filter(Boolean)
)

const bookingDetails = computed(() => ({
  flightID: Number.parseInt(route.query.flightID, 10),
  seatNumber: route.query.seatNumber || returnSeats.value.join(','),
  amount: Number.parseFloat(route.query.amount || 0),
  flightNumber: route.query.flightNumber || bookingDraft.value?.flights?.return?.flightNumber || bookingDraft.value?.flights?.outbound?.flightNumber || 'N/A',
  outboundFlightID: route.query.outboundFlightID ? Number.parseInt(route.query.outboundFlightID, 10) : bookingDraft.value?.flights?.outbound?.flightID || null,
  outboundFlightNumber: route.query.outboundFlightNumber || bookingDraft.value?.flights?.outbound?.flightNumber || null,
  outboundSeat: route.query.outboundSeat || outboundSeats.value.join(','),
  outboundPrice: route.query.outboundPrice ? Number.parseFloat(route.query.outboundPrice) : Number.parseFloat(bookingDraft.value?.flights?.outbound?.price || 0),
}))

const departureAmount = computed(() =>
  Number(bookingDetails.value.outboundPrice || (isRoundTrip.value ? 0 : bookingDetails.value.amount || 0))
)

const returnAmount = computed(() =>
  Number(isRoundTrip.value ? (bookingDetails.value.amount || 0) : 0)
)

const searchParams = {
  departingCountry: route.query.departingCountry || bookingDraft.value?.searchParams?.departingCountry || '',
  arrivingCountry: route.query.arrivingCountry || bookingDraft.value?.searchParams?.arrivingCountry || '',
  departureDate: route.query.departureDate || bookingDraft.value?.searchParams?.departureDate || '',
  returnDate: route.query.returnDate || bookingDraft.value?.searchParams?.returnDate || '',
  passengers: route.query.passengers || bookingDraft.value?.searchParams?.passengers || 1,
}

const totalAmount = computed(() => {
  if (isRoundTrip.value) {
    return departureAmount.value + returnAmount.value
  }

  return departureAmount.value
})

const travelerSummaries = computed(() =>
  draftTravelers.value.map((traveller, index) => ({
    ...traveller,
    displayName: `${traveller.firstName || ''} ${traveller.lastName || ''}`.trim() || `Passenger ${index + 1}`,
    outboundSeat: outboundSeats.value[index] || '--',
    returnSeat: isRoundTrip.value ? (returnSeats.value[index] || '--') : null,
  }))
)

function buildTravelerPayload() {
  return travelerSummaries.value.map((traveller) => ({
    isGuest: !traveller.isPrimary,
    passengerID: traveller.isPrimary ? currentPassenger.value?.passenger_id : null,
    guestFirstName: traveller.isPrimary ? null : traveller.firstName.trim(),
    guestLastName: traveller.isPrimary ? null : traveller.lastName.trim(),
    guestPassportNumber: traveller.isPrimary ? null : traveller.passportNumber.trim(),
    outboundSeatNumber: traveller.outboundSeat !== '--' ? traveller.outboundSeat : null,
    returnSeatNumber: isRoundTrip.value && traveller.returnSeat !== '--' ? traveller.returnSeat : null,
  }))
}

function validateDraft() {
  if (!currentPassenger.value?.passenger_id) {
    return 'Please sign in before proceeding to payment.'
  }

  if (!travelerSummaries.value.length) {
    return 'We could not find your passenger details. Please go back and fill them in again.'
  }

  for (const traveller of travelerSummaries.value) {
    if (!traveller.firstName?.trim() || !traveller.lastName?.trim() || !traveller.passportNumber?.trim()) {
      return `Passenger details are incomplete for ${traveller.displayName}.`
    }
  }

  return null
}

function goBack() {
  router.push({
    path: '/flight-detail',
    query: {
      flightID: isRoundTrip.value ? bookingDetails.value.flightID : bookingDetails.value.outboundFlightID || bookingDetails.value.flightID,
      isReturn: isRoundTrip.value ? 'true' : 'false',
      tripType: isRoundTrip.value ? 'round-trip' : 'one-way',
      departingCountry: searchParams.departingCountry,
      arrivingCountry: searchParams.arrivingCountry,
      departureDate: searchParams.departureDate,
      returnDate: searchParams.returnDate,
      passengers: searchParams.passengers,
      outboundFlightID: bookingDetails.value.outboundFlightID || '',
      outboundFlightNumber: bookingDetails.value.outboundFlightNumber || '',
      outboundPrice: bookingDetails.value.outboundPrice || '',
      returnFlightID: bookingDetails.value.flightID || '',
      returnFlightNumber: bookingDetails.value.flightNumber || '',
      returnPrice: bookingDetails.value.amount ? (bookingDetails.value.amount / Number(searchParams.passengers || 1)).toFixed(2) : '',
    },
  })
}

async function confirmBooking() {
  error.value = validateDraft()
  if (error.value) return

  loading.value = true

  try {
    let finalSessionUrl = sessionUrl.value

    if (!finalSessionUrl) {
      const payload = {
        passengerID: currentPassenger.value.passenger_id,
        flightID: isRoundTrip.value ? bookingDetails.value.outboundFlightID : bookingDetails.value.flightID,
        seatNumber: isRoundTrip.value ? bookingDetails.value.outboundSeat : bookingDetails.value.seatNumber,
        amount: Number(bookingDetails.value.amount),
        flightNumber: isRoundTrip.value
          ? `${bookingDetails.value.outboundFlightNumber} & ${bookingDetails.value.flightNumber}`
          : bookingDetails.value.flightNumber,
        frontendBaseUrl: window.location.origin,
        travelers: buildTravelerPayload(),
      }

      if (isRoundTrip.value) {
        payload.returnFlightID = bookingDetails.value.flightID
        payload.returnSeatNumber = bookingDetails.value.seatNumber
        payload.outboundAmount = Number(bookingDetails.value.outboundPrice || 0)
        payload.returnAmount = Number(bookingDetails.value.amount || 0)
      }

      const cancelUrl = new URL('http://localhost:5173/booking-confirmation')
      cancelUrl.searchParams.set('flightID', bookingDetails.value.flightID)
      cancelUrl.searchParams.set('seatNumber', bookingDetails.value.seatNumber)
      cancelUrl.searchParams.set('amount', bookingDetails.value.amount)
      cancelUrl.searchParams.set('flightNumber', bookingDetails.value.flightNumber)
      if (isRoundTrip.value) {
        cancelUrl.searchParams.set('outboundFlightID', bookingDetails.value.outboundFlightID)
        cancelUrl.searchParams.set('outboundFlightNumber', bookingDetails.value.outboundFlightNumber)
        cancelUrl.searchParams.set('outboundSeat', bookingDetails.value.outboundSeat)
        cancelUrl.searchParams.set('outboundPrice', bookingDetails.value.outboundPrice)
      }
      cancelUrl.searchParams.set('departingCountry', searchParams.departingCountry)
      cancelUrl.searchParams.set('arrivingCountry', searchParams.arrivingCountry)
      cancelUrl.searchParams.set('departureDate', searchParams.departureDate)
      cancelUrl.searchParams.set('returnDate', searchParams.returnDate)
      cancelUrl.searchParams.set('passengers', searchParams.passengers)
      cancelUrl.searchParams.set('cancelled', 'true')
      payload.cancelUrl = cancelUrl.toString()

      const bookingResponse = await axios.post('http://localhost:3010/api/bookings', payload)
      finalSessionUrl = bookingResponse.data.sessionUrl

      const currentUrl = new URL(window.location.href)
      currentUrl.searchParams.set('sessionUrl', finalSessionUrl)
      if (bookingResponse.data.outboundBookingIDs?.length) {
        currentUrl.searchParams.set('groupBookingIDs', bookingResponse.data.outboundBookingIDs.join(','))
      }
      if (bookingResponse.data.returnBookingIDs?.length) {
        currentUrl.searchParams.set('returnGroupBookingIDs', bookingResponse.data.returnBookingIDs.join(','))
      }
      window.history.replaceState({}, '', currentUrl.toString())
    }

    window.location.href = finalSessionUrl
  } catch (bookingError) {
    console.error('Booking failed:', bookingError)
    error.value = bookingError.response?.data?.message || 'Something went wrong. Please try again.'
    loading.value = false
  }
}

const wasCancelled = route.query.cancelled === 'true'
</script>

<template>
  <main class="relative min-h-screen overflow-hidden bg-[#f5f5f7] pb-20">
    <div class="pointer-events-none absolute inset-0">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_90%_12%,rgba(230,57,70,0.16),transparent_32%),radial-gradient(circle_at_8%_78%,rgba(29,29,31,0.05),transparent_30%)]"></div>
    </div>
    <div class="relative mx-auto max-w-[1400px] px-6 py-10">
      <div class="mx-auto max-w-[760px] px-6 md:px-10">
      <div class="mb-10 rounded-[34px] border border-white/80 bg-white/80 px-8 py-8 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur-2xl">
        <div class="grid grid-cols-3 items-start gap-6">
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-sm font-bold text-white shadow-[0_10px_18px_rgba(16,185,129,0.18)]">✓</div>
            <div class="min-w-0 flex-1 pt-1">
              <div class="h-1 rounded-full bg-emerald-500"></div>
              <p class="mt-3 text-sm font-semibold text-emerald-600">Fill in your info</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-sm font-bold text-white shadow-[0_10px_18px_rgba(16,185,129,0.18)]">✓</div>
            <div class="min-w-0 flex-1 pt-1">
              <div class="h-1 rounded-full bg-emerald-500"></div>
              <p class="mt-3 text-sm font-semibold text-emerald-600">Choose your seat</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#e63946] text-sm font-bold text-white shadow-[0_10px_18px_rgba(230,57,70,0.22)]">3</div>
            <div class="min-w-0 flex-1 pt-1">
              <div class="h-1 rounded-full bg-[#e63946]"></div>
              <p class="mt-3 text-sm font-semibold text-[#e63946]">Finalise your payment</p>
            </div>
          </div>
        </div>
      </div>

      <div class="hidden mb-8 grid gap-4 rounded-[28px] bg-white px-6 py-6 shadow-[0_20px_48px_rgba(0,0,0,0.08)] md:grid-cols-3">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500 text-white">✓</div>
          <p class="text-sm font-semibold text-emerald-600">Fill in your info</p>
        </div>
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500 text-white">✓</div>
          <p class="text-sm font-semibold text-emerald-600">Choose your seat</p>
        </div>
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-full bg-[#e63946] text-white">3</div>
          <p class="text-sm font-semibold text-[#e63946]">Finalise your payment</p>
        </div>
      </div>

      <div class="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 class="text-3xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">Confirm Your Booking</h1>
          <p class="mt-1 text-sm text-[#6e6e73]">Review your passengers and assigned seats before proceeding to payment.</p>
        </div>

        <button
          class="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-black/8 bg-white px-3 py-1.5 text-[11px] font-semibold text-[#1d1d1f] transition hover:bg-[#f8f8fa]"
          @click="goBack"
        >
          <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Seats
        </button>
      </div>

      <div v-if="wasCancelled" class="mb-6 rounded-2xl border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
        Payment was cancelled. Your seats are still reserved for up to 5 minutes, so you can continue payment below.
      </div>

      <div class="rounded-[28px] border border-black/10 bg-white p-8 shadow-[0_20px_48px_rgba(0,0,0,0.08)]">
        <h2 class="mb-6 text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Booking Summary</h2>

        <div class="space-y-4">
          <template v-if="!isRoundTrip">
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Departure Flight</span>
              <span class="font-medium text-[#1d1d1f]">{{ bookingDetails.flightNumber }} (#{{ bookingDetails.flightID }})</span>
            </div>
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Departure Fare</span>
              <span class="font-medium text-[#1d1d1f]">${{ departureAmount.toFixed(2) }}</span>
            </div>
          </template>
          <template v-else>
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Departure Flight</span>
              <span class="font-medium text-[#1d1d1f]">{{ bookingDetails.outboundFlightNumber }}</span>
            </div>
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Departure Fare</span>
              <span class="font-medium text-[#1d1d1f]">${{ departureAmount.toFixed(2) }}</span>
            </div>
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Return Flight</span>
              <span class="font-medium text-[#1d1d1f]">{{ bookingDetails.flightNumber }}</span>
            </div>
            <div class="flex justify-between border-b border-black/10 pb-4">
              <span class="text-[#6e6e73]">Return Fare</span>
              <span class="font-medium text-[#1d1d1f]">${{ returnAmount.toFixed(2) }}</span>
            </div>
          </template>

          <div class="flex justify-between text-lg font-semibold pt-1">
            <span>Total</span>
            <span class="text-[#e63946]">${{ totalAmount.toFixed(2) }}</span>
          </div>
        </div>

        <div class="mt-8 rounded-2xl border border-black/8 bg-[#fafafa] p-5">
          <div class="mb-4">
            <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Passengers</p>
            <p class="mt-1 text-sm text-[#6e6e73]">Each seat assignment is now tied to a named traveller.</p>
          </div>

          <div class="space-y-4">
            <div
              v-for="traveller in travelerSummaries"
              :key="traveller.id"
              class="rounded-2xl border border-black/8 bg-white p-4"
            >
              <div class="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p class="text-base font-semibold text-[#1d1d1f]">{{ traveller.displayName }}</p>
                  <p class="mt-1 text-sm text-[#6e6e73]">
                    Passport {{ traveller.passportNumber }}
                    <span v-if="traveller.isPrimary" class="ml-2 rounded-full bg-[#f5f5f7] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Primary</span>
                  </p>
                </div>
                <div class="text-right text-sm">
                  <p class="font-semibold text-[#1d1d1f]">Departure seat: {{ traveller.outboundSeat }}</p>
                  <p v-if="isRoundTrip" class="mt-1 font-semibold text-[#1d1d1f]">Return seat: {{ traveller.returnSeat }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="mt-8 rounded-2xl bg-[#f5f5f7] p-4">
          <p class="mb-3 text-xs font-semibold uppercase tracking-[0.1em] text-[#6e6e73]">What happens next</p>
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

        <div v-if="error" class="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600">
          {{ error }}
        </div>

        <button
          class="mt-8 w-full rounded-2xl bg-[#1d1d1f] py-4 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-black disabled:opacity-50"
          :disabled="loading"
          @click="confirmBooking"
        >
          <span v-if="loading" class="flex items-center justify-center gap-2">
            <span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
            Redirecting to Stripe...
          </span>
          <span v-else>Proceed to Payment · ${{ totalAmount.toFixed(2) }}</span>
        </button>

        <p class="mt-4 text-center text-xs text-[#6e6e73]">
          You'll be redirected to Stripe's secure payment page. We never handle your card details directly.
        </p>
      </div>
    </div>
    </div>
  </main>
</template>
