<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'
import { apiUrl } from '../config/api'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()

const bookingID = route.params.bookingID
const sessionID = route.query.session_id
const returnBookingID = route.query.returnBookingID || null
const groupBookingIDs = route.query.groupBookingIDs || ''
const returnGroupBookingIDs = route.query.returnGroupBookingIDs || ''

const booking = ref(null)
const returnBooking = ref(null)
const outboundGroupBookings = ref([])
const returnGroupBookings = ref([])
const outboundFlight = ref(null)
const returnFlight = ref(null)
const payment = ref(null)
const loading = ref(true)
const error = ref(null)

const totalPaid = computed(() => {
  const outboundAmount = outboundGroupBookings.value.reduce((sum, record) => sum + Number(record.amount || 0), 0)
  const returnAmount = returnGroupBookings.value.reduce((sum, record) => sum + Number(record.amount || 0), 0)
  return outboundAmount + returnAmount
})

const outboundFareTotal = computed(() =>
  outboundGroupBookings.value.reduce((sum, record) => sum + Number(record.amount || 0), 0)
)

const returnFareTotal = computed(() =>
  returnGroupBookings.value.reduce((sum, record) => sum + Number(record.amount || 0), 0)
)

function parseIdList(value) {
  return String(value || '')
    .split(',')
    .map((id) => Number(id.trim()))
    .filter((id) => Number.isFinite(id) && id > 0)
}

function travellerName(record) {
  if (!record) return 'Passenger'
  if (record.isGuest) {
    return `${record.guestFirstName || ''} ${record.guestLastName || ''}`.trim() || 'Guest Passenger'
  }
  const first = currentPassenger.value?.FirstName || currentPassenger.value?.firstName || ''
  const last = currentPassenger.value?.LastName || currentPassenger.value?.lastName || ''
  const combined = `${first} ${last}`.trim()
  return combined || 'Primary Passenger'
}

const totalTravellers = computed(() => outboundGroupBookings.value.length || 1)

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
    const response = await axios.get(apiUrl(`/api/flight/${flightID}`))
    return response.data
  } catch {
    return null
  }
}

async function fetchBookingGroup(ids) {
  if (!ids.length) return []

  const results = await Promise.allSettled(
    ids.map((id) => axios.get(apiUrl(`/api/bookings/${id}`)))
  )

  return results
    .filter((result) => result.status === 'fulfilled')
    .map((result) => result.value.data)
}

onMounted(async () => {
  try {
    if (!sessionID) {
      throw new Error('Missing payment session id.')
    }

    const finalizePayload = {
      bookingID: Number(bookingID),
      groupBookingIDs,
      sessionID,
      flightID: Number(route.query.flightID),
      seatNumber: route.query.seatNumber,
      returnBookingID: route.query.returnBookingID ? Number(route.query.returnBookingID) : null,
      returnGroupBookingIDs,
      returnFlightID: route.query.returnFlightID ? Number(route.query.returnFlightID) : null,
      returnSeatNumber: route.query.returnSeatNumber || null,
      flightNumber: route.query.flightNumber || null,
      origin: route.query.origin || null,
      destination: route.query.destination || null,
      departureDate: route.query.departureDate || null,
    }

    const finalizeResponse = await axios.post(
      apiUrl('/api/bookings/finalize'),
      finalizePayload
    )
    payment.value = finalizeResponse.data.payment

    const outboundIds = parseIdList(groupBookingIDs)
    const returnIds = parseIdList(returnGroupBookingIDs)

    if (!outboundIds.length) outboundIds.push(Number(bookingID))
    if (!returnIds.length && returnBookingID) returnIds.push(Number(returnBookingID))

    outboundGroupBookings.value = await fetchBookingGroup(outboundIds)
    returnGroupBookings.value = await fetchBookingGroup(returnIds)

    booking.value = outboundGroupBookings.value[0] || null
    returnBooking.value = returnGroupBookings.value[0] || null

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
  <main class="relative min-h-screen overflow-hidden bg-[#f5f5f7] py-16">
    <div class="pointer-events-none absolute inset-0">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_88%_10%,rgba(230,57,70,0.16),transparent_32%),radial-gradient(circle_at_10%_85%,rgba(29,29,31,0.05),transparent_30%)]"></div>
    </div>

    <div class="relative mx-auto max-w-[1100px] px-6 md:px-10">
      <div v-if="loading" class="flex flex-col items-center justify-center gap-4 py-24">
        <div class="h-12 w-12 animate-spin rounded-full border-4 border-[#e63946] border-t-transparent"></div>
        <p class="text-sm text-[#6e6e73]">Confirming your payment...</p>
      </div>

      <div
        v-else-if="error"
        class="mx-auto max-w-[620px] rounded-[32px] border border-red-200 bg-white/90 p-8 text-center shadow-[0_20px_48px_rgba(0,0,0,0.08)] backdrop-blur-xl"
      >
        <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-red-100">
          <svg class="h-10 w-10 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h1 class="text-2xl font-semibold text-[#1d1d1f]">Something went wrong</h1>
        <p class="mt-2 text-sm text-[#6e6e73]">{{ error }}</p>
        <button
          class="mt-8 rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-8 py-3 text-sm font-semibold text-white shadow-[0_14px_28px_rgba(230,57,70,0.22)] transition hover:brightness-105"
          @click="router.push('/')"
        >
          Back to Home
        </button>
      </div>

      <div
        v-else
        class="rounded-[36px] border border-white/80 bg-white/85 p-6 shadow-[0_28px_70px_rgba(15,23,42,0.10)] backdrop-blur-2xl md:p-8"
      >
        <div class="mx-auto mb-8 max-w-[780px] text-center">
          <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-[#fff1f2] shadow-[0_10px_24px_rgba(230,57,70,0.14)]">
            <svg class="h-10 w-10 text-[#e63946]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
            </svg>
          </div>

          <p class="text-[11px] font-bold uppercase tracking-[0.18em] text-[#e63946]">Booking Complete</p>
          <h1 class="mt-3 text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">You're all set.</h1>
          <p class="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-[#6e6e73]">
            Payment has been received and your itinerary is confirmed for {{ totalTravellers }} passenger<span v-if="totalTravellers !== 1">s</span>.
          </p>
        </div>

        <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
          <section class="rounded-[30px] border border-black/8 bg-white p-6 text-left shadow-[0_16px_36px_rgba(15,23,42,0.05)]">
            <div class="flex flex-wrap items-start justify-between gap-4 border-b border-black/8 pb-5">
              <div>
                <p class="text-[11px] font-bold uppercase tracking-[0.16em] text-[#e63946]">Reference</p>
                <p class="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#1d1d1f]">#{{ bookingID }}</p>
                <p v-if="returnBookingID" class="mt-2 text-sm text-[#6e6e73]">Return reference #{{ returnBookingID }}</p>
              </div>
              <div class="flex flex-wrap gap-2">
                <span class="rounded-full bg-[#ecfdf3] px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">
                  {{ booking?.status || 'Confirmed' }}
                </span>
                <span v-if="payment" class="rounded-full bg-[#fff6ea] px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#c26b13]">
                  Payment {{ payment.status }}
                </span>
              </div>
            </div>

            <div v-if="outboundGroupBookings.length" class="mt-6 rounded-[24px] border border-black/8 bg-[#fcfcfd] p-5">
              <div class="mb-4 flex items-center justify-between gap-3">
                <div>
                  <p class="text-[11px] font-bold uppercase tracking-[0.16em] text-[#6e6e73]">Travellers</p>
                  <p class="mt-1 text-sm text-[#6e6e73]">Seats are confirmed exactly as selected during checkout.</p>
                </div>
                <p class="text-sm font-semibold text-[#1d1d1f]">{{ totalTravellers }} passenger<span v-if="totalTravellers !== 1">s</span></p>
              </div>

              <div class="space-y-3">
                <div
                  v-for="traveller in outboundGroupBookings"
                  :key="traveller.bookingID"
                  class="flex items-start justify-between gap-4 rounded-2xl border border-black/8 bg-white px-4 py-3"
                >
                  <div>
                    <p class="font-semibold text-[#1d1d1f]">{{ travellerName(traveller) }}</p>
                    <p v-if="traveller.isGuest" class="mt-1 text-xs text-[#6e6e73]">Passport {{ traveller.guestPassportNumber || '--' }}</p>
                    <p v-else class="mt-1 text-xs text-[#6e6e73]">Primary booking passenger</p>
                  </div>
                  <div class="text-right">
                    <p class="text-[11px] font-bold uppercase tracking-[0.14em] text-[#6e6e73]">Seat</p>
                    <p class="mt-1 text-base font-semibold text-[#e63946]">{{ traveller.seatNumber || '--' }}</p>
                  </div>
                </div>
              </div>
            </div>

            <div class="mt-6 space-y-5">
              <article v-if="booking" class="overflow-hidden rounded-[24px] border border-black/8 bg-white">
                <div class="border-b border-black/8 bg-gradient-to-r from-[#fff1f2] to-[#fff8f8] px-5 py-4">
                  <p class="text-[11px] font-bold uppercase tracking-[0.16em] text-[#e63946]">Flight 1</p>
                  <div class="mt-2 flex flex-wrap items-center gap-3">
                    <span class="text-xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">{{ outboundFlight?.Origin || '--' }}</span>
                    <span class="text-[#e63946]">→</span>
                    <span class="text-xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">{{ outboundFlight?.Destination || '--' }}</span>
                  </div>
                </div>

                <div class="grid gap-4 px-5 py-5 md:grid-cols-2">
                  <div class="space-y-3 text-sm">
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Flight</span>
                      <span class="font-medium text-[#1d1d1f]">{{ outboundFlight?.FlightNumber || ('#' + booking.flightID) }}</span>
                    </div>
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Date</span>
                      <span class="font-medium text-[#1d1d1f]">{{ formatDate(outboundFlight?.Date) }}</span>
                    </div>
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Time</span>
                      <span class="font-medium text-[#1d1d1f]">{{ formatTime(outboundFlight?.DepartureTime) }} - {{ formatTime(outboundFlight?.ArrivalTime) }}</span>
                    </div>
                  </div>
                  <div class="space-y-3 text-sm">
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Seats</span>
                      <span class="font-medium text-[#1d1d1f]">{{ outboundGroupBookings.map((record) => record.seatNumber).join(', ') }}</span>
                    </div>
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Fare</span>
                      <span class="font-medium text-[#1d1d1f]">${{ formatAmount(outboundFareTotal) }}</span>
                    </div>
                  </div>
                </div>
              </article>

              <article v-if="returnBooking" class="overflow-hidden rounded-[24px] border border-black/8 bg-white">
                <div class="border-b border-black/8 bg-gradient-to-r from-[#fff1f2] to-[#fff8f8] px-5 py-4">
                  <p class="text-[11px] font-bold uppercase tracking-[0.16em] text-[#e63946]">Flight 2</p>
                  <div class="mt-2 flex flex-wrap items-center gap-3">
                    <span class="text-xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">{{ returnFlight?.Origin || '--' }}</span>
                    <span class="text-[#e63946]">→</span>
                    <span class="text-xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">{{ returnFlight?.Destination || '--' }}</span>
                  </div>
                </div>

                <div class="grid gap-4 px-5 py-5 md:grid-cols-2">
                  <div class="space-y-3 text-sm">
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Flight</span>
                      <span class="font-medium text-[#1d1d1f]">{{ returnFlight?.FlightNumber || ('#' + returnBooking.flightID) }}</span>
                    </div>
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Date</span>
                      <span class="font-medium text-[#1d1d1f]">{{ formatDate(returnFlight?.Date) }}</span>
                    </div>
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Time</span>
                      <span class="font-medium text-[#1d1d1f]">{{ formatTime(returnFlight?.DepartureTime) }} - {{ formatTime(returnFlight?.ArrivalTime) }}</span>
                    </div>
                  </div>
                  <div class="space-y-3 text-sm">
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Seats</span>
                      <span class="font-medium text-[#1d1d1f]">{{ returnGroupBookings.map((record) => record.seatNumber).join(', ') }}</span>
                    </div>
                    <div class="flex justify-between gap-4">
                      <span class="text-[#6e6e73]">Fare</span>
                      <span class="font-medium text-[#1d1d1f]">${{ formatAmount(returnFareTotal) }}</span>
                    </div>
                  </div>
                </div>
              </article>
            </div>

            <div class="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-[24px] border border-black/8 bg-[#fcfcfd] px-5 py-4">
              <div>
                <p class="text-[11px] font-bold uppercase tracking-[0.16em] text-[#6e6e73]">Confirmation</p>
                <p class="mt-1 text-sm text-[#6e6e73]">A confirmation email has been sent to your registered email address.</p>
              </div>
              <p class="text-2xl font-semibold tracking-[-0.03em] text-[#e63946]">${{ formatAmount(totalPaid) }}</p>
            </div>
          </section>

          <aside class="space-y-5">
            <div class="rounded-[30px] border border-black/8 bg-white p-6 text-left shadow-[0_16px_36px_rgba(15,23,42,0.05)]">
              <p class="text-[11px] font-bold uppercase tracking-[0.16em] text-[#e63946]">Payment Summary</p>
              <div class="mt-4 space-y-4 text-sm">
                <div class="flex justify-between gap-4">
                  <span class="text-[#6e6e73]">Booking status</span>
                  <span class="font-medium text-emerald-600">{{ booking?.status || 'Confirmed' }}</span>
                </div>
                <div v-if="payment" class="flex justify-between gap-4">
                  <span class="text-[#6e6e73]">Payment</span>
                  <span class="font-medium text-emerald-600">{{ payment.status }}</span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-[#6e6e73]">Passengers</span>
                  <span class="font-medium text-[#1d1d1f]">{{ totalTravellers }}</span>
                </div>
                <div class="border-t border-black/8 pt-4">
                  <div class="flex items-end justify-between gap-4">
                    <span class="text-sm font-semibold text-[#1d1d1f]">Total Paid</span>
                    <span class="text-3xl font-semibold tracking-[-0.03em] text-[#e63946]">${{ formatAmount(totalPaid) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-[30px] border border-black/8 bg-white p-6 text-left shadow-[0_16px_36px_rgba(15,23,42,0.05)]">
              <p class="text-[11px] font-bold uppercase tracking-[0.16em] text-[#6e6e73]">Next Steps</p>
              <div class="mt-4 space-y-3 text-sm text-[#6e6e73]">
                <p>Check your email for the booking summary and confirmation details.</p>
                <p>View your itinerary and any future changes from My Bookings.</p>
                <p>Keep your passport details ready for check-in and airport verification.</p>
              </div>
            </div>
          </aside>
        </div>

        <div class="mt-8 flex flex-col gap-4 md:flex-row">
          <button
            class="flex-1 rounded-2xl border border-black/10 bg-white py-3.5 text-sm font-semibold text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="router.push('/')"
          >
            Back to Home
          </button>
          <button
            class="flex-1 rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] py-3.5 text-sm font-semibold text-white shadow-[0_14px_28px_rgba(230,57,70,0.22)] transition hover:brightness-105"
            @click="router.push('/my-bookings')"
          >
            View My Bookings
          </button>
        </div>
      </div>
    </div>
  </main>
</template>
