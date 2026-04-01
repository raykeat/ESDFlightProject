<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'

const router = useRouter()
const { currentPassenger } = usePassengerSession()

const bookings = ref([])
const offers = ref([])
const payments = ref([])
const flightsById = ref({})

const loading = ref(true)
const error = ref(null)
const filterStatus = ref('All')

const STATUS_FILTERS = ['All', 'Confirmed', 'Pending', 'Cancelled', 'Failed']

onMounted(async () => {
  if (!currentPassenger.value) {
    router.push('/auth')
    return
  }
  await loadData()
})

async function loadData() {
  loading.value = true
  error.value = null

  try {
    const passengerId = currentPassenger.value.passenger_id

    const [bookingsRes, offersRes, paymentsRes] = await Promise.allSettled([
      axios.get(`http://localhost:3010/api/bookings/passenger/${passengerId}`),
      axios.get(`http://localhost:5002/offers?passengerID=${passengerId}`),
      axios.get('http://localhost:5001/payment'),
    ])

    if (bookingsRes.status !== 'fulfilled') {
      error.value = 'Unable to load your bookings right now.'
      return
    }

    bookings.value = Array.isArray(bookingsRes.value.data) ? bookingsRes.value.data : []
    offers.value = offersRes.status === 'fulfilled' && Array.isArray(offersRes.value.data) ? offersRes.value.data : []

    const allPayments = paymentsRes.status === 'fulfilled' && Array.isArray(paymentsRes.value.data)
      ? paymentsRes.value.data
      : []

    payments.value = allPayments.filter(
      (payment) => Number(payment.passengerID) === Number(passengerId)
    )

    await hydrateFlightDetails()
  } catch (e) {
    error.value = 'Unable to load your bookings right now.'
  } finally {
    loading.value = false
  }
}

async function hydrateFlightDetails() {
  const fromBookings = bookings.value
    .map((booking) => Number(booking.flightID))
    .filter((flightID) => Number.isFinite(flightID) && flightID > 0)

  const fromOffers = offers.value.flatMap((offer) => [
    Number(offer.origFlightID),
    Number(offer.newFlightID),
  ]).filter((flightID) => Number.isFinite(flightID) && flightID > 0)

  const uniqueFlightIds = [...new Set([...fromBookings, ...fromOffers])]

  if (!uniqueFlightIds.length) {
    flightsById.value = {}
    return
  }

  const map = {}
  const results = await Promise.allSettled(
    uniqueFlightIds.map((flightID) => axios.get(`http://localhost:3003/flights/${flightID}`))
  )

  results.forEach((result, idx) => {
    if (result.status === 'fulfilled') {
      map[uniqueFlightIds[idx]] = result.value.data
    }
  })

  flightsById.value = map
}

function normalizedStatus(status) {
  return String(status || '').trim()
}

function isCancelled(status) {
  return normalizedStatus(status).toLowerCase().startsWith('cancelled')
}

const filteredBookings = computed(() => {
  if (filterStatus.value === 'All') return bookings.value

  return bookings.value.filter((booking) => {
    const status = normalizedStatus(booking.status)
    if (filterStatus.value === 'Cancelled') return isCancelled(status)
    return status === filterStatus.value
  })
})

function countByStatus(statusFilter) {
  if (statusFilter === 'All') return bookings.value.length

  if (statusFilter === 'Cancelled') {
    return bookings.value.filter((booking) => isCancelled(booking.status)).length
  }

  return bookings.value.filter((booking) => normalizedStatus(booking.status) === statusFilter).length
}

function statusTone(status) {
  const value = normalizedStatus(status)

  if (value === 'Confirmed') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (value === 'Pending') return 'border-amber-200 bg-amber-50 text-amber-700'
  if (value === 'Failed' || value === 'Refund Failed') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (isCancelled(value)) return 'border-slate-200 bg-slate-50 text-slate-600'
  return 'border-slate-200 bg-slate-50 text-slate-600'
}

function getFlight(booking) {
  return flightsById.value[Number(booking.flightID)] || null
}

function getOfferForBooking(bookingID) {
  const matches = offers.value.filter((offer) => Number(offer.bookingID) === Number(bookingID))
  if (!matches.length) return null
  return matches.find((offer) => offer.status === 'Pending Response') || matches[0]
}

function hasPendingOffer(bookingID) {
  const offer = getOfferForBooking(bookingID)
  return Boolean(offer && offer.status === 'Pending Response')
}

function getOfferSnapshot(booking) {
  const offer = getOfferForBooking(booking.bookingID)
  if (!offer || offer.status !== 'Pending Response') return null

  const original = flightsById.value[Number(offer.origFlightID)] || getFlight(booking)
  const proposed = flightsById.value[Number(offer.newFlightID)] || null

  return {
    offer,
    original,
    proposed,
    expiryText: getOfferExpiryLabel(offer),
  }
}

function getRefundForBooking(bookingID) {
  return payments.value.find(
    (payment) => Number(payment.bookingID) === Number(bookingID) && String(payment.status).toLowerCase() === 'refunded'
  ) || null
}

function hasRefund(bookingID) {
  return Boolean(getRefundForBooking(bookingID))
}

function getRefundSnapshot(booking) {
  const refund = getRefundForBooking(booking.bookingID)
  if (!refund) return null

  const flight = getFlight(booking)

  return {
    refund,
    flight,
    amount: formatMoney(refund.amount),
    refundID: refund.refundID || 'Processing',
  }
}

function formatMoney(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '0.00'
  return amount.toFixed(2)
}

function formatBookedDate(value) {
  if (!value) return '—'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'

  const day = date.getUTCDate()
  const month = date.toLocaleString('en-SG', { month: 'short', timeZone: 'UTC' })
  const year = date.getUTCFullYear()
  const hours = date.getUTCHours()
  const minutes = String(date.getUTCMinutes()).padStart(2, '0')
  const period = hours >= 12 ? 'PM' : 'AM'
  const h12 = hours % 12 || 12

  return `${day} ${month} ${year}, ${h12}:${minutes} ${period} SGT`
}

function formatFlightDate(flight) {
  if (!flight) return '—'
  return flight.Date || flight.FlightDate || '—'
}

function formatFlightTime(value) {
  if (!value) return '—'
  return String(value).slice(0, 5)
}

function formatOfferExpiry(expiryTime) {
  if (!expiryTime) return null

  const cleaned = String(expiryTime).replace(/ [A-Z]{2,4}$/, '').trim()
  const expiryDate = new Date(cleaned)
  if (Number.isNaN(expiryDate.getTime())) return null

  const diffHours = Math.ceil((expiryDate - new Date()) / 3600000)
  if (diffHours < 0) return 'Offer expired'
  if (diffHours < 24) return `Expires in ${diffHours}h`
  return `Expires in ${Math.ceil(diffHours / 24)} day(s)`
}

function parseSgtDateTime(value) {
  if (!value) return null
  const cleaned = String(value).replace(/ [A-Z]{2,4}$/, '').trim()
  const parsed = new Date(cleaned)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed
}

function getOfferExpiryLabel(offer) {
  if (!offer) return null

  const expiry = parseSgtDateTime(offer.expiryTime)
  const created = parseSgtDateTime(offer.createdTime)

  let effectiveExpiry = expiry
  if (created) {
    const createdPlus24 = new Date(created.getTime() + 24 * 3600000)
    if (!effectiveExpiry || effectiveExpiry.getTime() < createdPlus24.getTime() - 3 * 3600000) {
      effectiveExpiry = createdPlus24
    }
  }

  if (!effectiveExpiry) return null

  const diffHours = Math.ceil((effectiveExpiry - new Date()) / 3600000)
  if (diffHours < 0) return 'Offer expired'
  if (diffHours < 24) return `Expires in ${diffHours}h`
  return `Expires in ${Math.ceil(diffHours / 24)} day(s)`
}

function viewOffer(offer) {
  router.push({
    path: '/rebooking-offer',
    query: { offerID: offer.offerID, bookingID: offer.bookingID }
  })
}

function outcomeForBooking(booking) {
  const offer = getOfferForBooking(booking.bookingID)
  const refund = getRefundForBooking(booking.bookingID)

  if (offer && offer.status === 'Pending Response') {
    return {
      kind: 'action',
      title: 'Flight cancelled - action required',
      detail: getOfferExpiryLabel(offer) || 'Review and respond to your rebooking offer.',
      buttonLabel: 'Review Offer',
      buttonAction: () => viewOffer(offer),
    }
  }

  if (offer && offer.status && offer.status !== 'Pending Response') {
    return {
      kind: 'info',
      title: `Offer status: ${offer.status}`,
      detail: 'Your rebooking offer has already been processed.',
    }
  }

  if (refund) {
    return {
      kind: 'info',
      title: 'Refund completed',
      detail: `Refunded amount: $${formatMoney(refund.amount)}${refund.refundID ? ` · Ref ${refund.refundID}` : ''}`,
    }
  }

  if (normalizedStatus(booking.status) === 'Refund Failed') {
    return {
      kind: 'warning',
      title: 'Refund processing issue',
      detail: 'Please contact support for manual assistance.',
    }
  }

  return {
    kind: 'info',
    title: 'Compensation processing',
    detail: 'We are finalizing your rebooking/refund outcome. Please check back shortly.',
  }
}

function hasDisruption(booking) {
  return isCancelled(booking.status) || normalizedStatus(booking.status) === 'Refund Failed' || hasPendingOffer(booking.bookingID)
}
</script>

<template>
  <main class="min-h-screen bg-[radial-gradient(circle_at_10%_5%,#ffffff_0%,#f3f4f8_48%,#e9ecf2_100%)] pb-20 pt-8">
    <section class="mx-auto max-w-[1240px] px-6 md:px-10 lg:px-16">
      <div class="mb-10 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p class="mb-1 text-xs font-bold uppercase tracking-[0.14em] text-[#e63946]">
            {{ currentPassenger?.FirstName }} {{ currentPassenger?.LastName }}
          </p>
          <h1 class="text-4xl font-bold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">My Bookings</h1>
          <p class="mt-2 text-sm text-[#6e6e73]">
            <span v-if="!loading">{{ bookings.length }} booking{{ bookings.length !== 1 ? 's' : '' }} total</span>
            <span v-else>Loading your trips...</span>
          </p>
        </div>

        <button
          @click="router.push('/')"
          class="inline-flex items-center gap-2 rounded-full bg-[#1d1d1f] px-5 py-3 text-sm font-semibold text-white transition hover:bg-black"
        >
          <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path d="M12 4v16m8-8H4"/>
          </svg>
          Book New Flight
        </button>
      </div>

      <div class="mb-7 flex flex-wrap gap-2">
        <button
          v-for="status in STATUS_FILTERS"
          :key="status"
          @click="filterStatus = status"
          class="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition-all"
          :class="filterStatus === status
            ? 'border-[#1d1d1f] bg-[#1d1d1f] text-white shadow-[0_6px_20px_rgba(29,29,31,0.2)]'
            : 'border-black/10 bg-white text-[#6e6e73] hover:border-black/20 hover:text-[#1d1d1f]'"
        >
          {{ status }}
          <span
            class="rounded-full px-2 py-0.5 text-xs"
            :class="filterStatus === status ? 'bg-white/20 text-white' : 'bg-[#f5f5f7] text-[#6e6e73]'"
          >
            {{ countByStatus(status) }}
          </span>
        </button>
      </div>

      <div v-if="loading" class="space-y-3">
        <div v-for="i in 3" :key="i" class="h-28 animate-pulse rounded-2xl border border-black/5 bg-white"></div>
      </div>

      <div v-else-if="error" class="rounded-2xl border border-rose-200 bg-white p-8 text-center">
        <p class="text-base font-semibold text-[#1d1d1f]">{{ error }}</p>
        <button @click="loadData" class="mt-4 rounded-full bg-[#1d1d1f] px-5 py-2 text-sm font-semibold text-white">Try Again</button>
      </div>

      <div v-else-if="filteredBookings.length === 0" class="rounded-2xl border border-black/10 bg-white p-10 text-center">
        <p class="text-lg font-semibold text-[#1d1d1f]">
          {{ filterStatus === 'All' ? 'No bookings yet' : `No ${filterStatus.toLowerCase()} bookings` }}
        </p>
        <p class="mt-2 text-sm text-[#6e6e73]">Your upcoming and historical trips will show here.</p>
      </div>

      <div v-else class="space-y-5">
        <article
          v-for="booking in filteredBookings"
          :key="booking.bookingID"
          class="overflow-hidden rounded-3xl border border-black/10 bg-white shadow-[0_8px_28px_rgba(15,23,42,0.06)]"
        >
          <div class="h-1.5" :class="hasPendingOffer(booking.bookingID) ? 'bg-amber-300' : hasRefund(booking.bookingID) ? 'bg-rose-500' : normalizedStatus(booking.status) === 'Confirmed' ? 'bg-emerald-400' : normalizedStatus(booking.status) === 'Pending' ? 'bg-amber-300' : isCancelled(booking.status) ? 'bg-slate-300' : 'bg-rose-300'"></div>

          <div class="p-6">
            <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p class="text-xl font-bold text-[#1d1d1f]">
                  {{ getFlight(booking)?.FlightNumber || 'Flight details unavailable' }}
                </p>
                <p class="mt-1 text-sm text-[#6e6e73]">
                  {{ getFlight(booking)?.Origin || '—' }} → {{ getFlight(booking)?.Destination || '—' }}
                </p>
                <p class="mt-2 inline-flex rounded-full bg-[#f4f4f6] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#656b78]">
                  Booking #{{ booking.bookingID }}
                </p>
              </div>

              <span class="rounded-full border px-3 py-1 text-xs font-bold" :class="hasPendingOffer(booking.bookingID) ? 'border-rose-200 bg-rose-50 text-rose-700' : hasRefund(booking.bookingID) ? 'border-slate-300 bg-slate-50 text-slate-700' : statusTone(booking.status)">
                {{ hasPendingOffer(booking.bookingID) ? 'Action Required' : hasRefund(booking.bookingID) ? 'Refunded' : normalizedStatus(booking.status) }}
              </span>
            </div>

            <div
              v-if="getOfferSnapshot(booking)"
              class="mb-5 rounded-2xl border border-rose-200 bg-rose-50/50 p-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
                <div>
                  <p class="text-sm font-bold uppercase tracking-[0.12em] text-rose-700">Flight Cancelled</p>
                  <p class="mt-1 text-xs text-[#6e6e73]">{{ getOfferSnapshot(booking).expiryText || 'Offer available' }}</p>
                </div>
                <button
                  @click="viewOffer(getOfferSnapshot(booking).offer)"
                  class="rounded-full bg-amber-600 px-5 py-2 text-xs font-bold uppercase tracking-[0.1em] text-white transition hover:bg-amber-700"
                >
                  Review Offer
                </button>
              </div>

              <div class="flex items-stretch gap-2">
                <div class="flex-1 rounded-lg border border-rose-200 bg-white p-3">
                  <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-rose-600">Cancelled</p>
                  <p class="mt-2 text-sm font-semibold text-[#1d1d1f]">{{ getOfferSnapshot(booking).original?.FlightNumber || 'N/A' }}</p>
                  <p class="text-xs text-[#6e6e73] mt-1">{{ formatFlightDate(getOfferSnapshot(booking).original) }} · {{ formatFlightTime(getOfferSnapshot(booking).original?.DepartureTime) }}</p>
                </div>

                <div class="flex items-center justify-center text-[#9ca3af] px-2">
                  <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </div>

                <div class="flex-1 rounded-lg border border-emerald-200 bg-emerald-50/70 p-3">
                  <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-emerald-700">Proposed</p>
                  <p class="mt-2 text-sm font-semibold text-[#1d1d1f]">{{ getOfferSnapshot(booking).proposed?.FlightNumber || 'N/A' }}</p>
                  <p class="text-xs text-[#6e6e73] mt-1">{{ formatFlightDate(getOfferSnapshot(booking).proposed) }} · {{ formatFlightTime(getOfferSnapshot(booking).proposed?.DepartureTime) }}</p>
                </div>
              </div>
            </div>

            <div
              v-else-if="getRefundSnapshot(booking)"
              class="mb-5 rounded-2xl border border-rose-200 bg-gradient-to-br from-red-50 to-rose-50 p-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-sm font-bold uppercase tracking-[0.12em] text-rose-700">Flight Cancelled</p>
                <p class="rounded-full border border-rose-200 bg-white px-3 py-1 text-xs font-semibold text-rose-700">
                  Refunded
                </p>
              </div>

              <p class="mt-2 text-sm text-[#1d1d1f] font-semibold">Your flight has been cancelled and your payment has been fully refunded.</p>

              <div class="mt-4 grid gap-3 md:grid-cols-2">
                <div class="rounded-xl border border-rose-200 bg-white/80 p-3">
                  <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-rose-600">Cancelled Flight</p>
                  <p class="mt-1 text-sm font-semibold text-[#1d1d1f]">{{ getRefundSnapshot(booking).flight?.FlightNumber || 'N/A' }}</p>
                  <p class="text-xs text-[#6e6e73]">{{ formatFlightDate(getRefundSnapshot(booking).flight) }} · {{ formatFlightTime(getRefundSnapshot(booking).flight?.DepartureTime) }}</p>
                </div>
                <div class="rounded-xl border border-rose-200 bg-white/80 p-3">
                  <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-rose-600">Refund Amount</p>
                  <p class="mt-1 text-2xl font-bold text-rose-700">${{ getRefundSnapshot(booking).amount }}</p>
                  <p class="text-xs text-[#6e6e73] mt-2">Ref {{ getRefundSnapshot(booking).refundID }}</p>
                </div>
              </div>

              <p class="mt-3 text-xs text-[#6e6e73]">
                The refund was processed to your original payment method. Please allow 3-5 business days for the funds to appear in your account.
              </p>
            </div>

            <div v-if="!getOfferSnapshot(booking) && !getRefundSnapshot(booking)" class="grid gap-3 rounded-2xl border border-black/6 bg-[#fafafa] p-4 md:grid-cols-4">
              <div>
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#9ca3af]">Departure Date</p>
                <p class="mt-1 text-sm font-semibold text-[#1d1d1f]">{{ formatFlightDate(getFlight(booking)) }}</p>
              </div>
              <div>
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#9ca3af]">Departure Time</p>
                <p class="mt-1 text-sm font-semibold text-[#1d1d1f]">{{ formatFlightTime(getFlight(booking)?.DepartureTime) }}</p>
              </div>
              <div>
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#9ca3af]">Seat</p>
                <p class="mt-1 text-sm font-semibold text-[#1d1d1f]">{{ booking.seatNumber || '—' }}</p>
              </div>
              <div>
                <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#9ca3af]">Paid</p>
                <p class="mt-1 text-sm font-semibold text-[#1d1d1f]">${{ formatMoney(booking.amount) }}</p>
              </div>
            </div>

            <p class="mt-4 text-xs text-[#6e6e73]">Booked on {{ formatBookedDate(booking.createdAt) }}</p>

            <div
              v-if="hasDisruption(booking) && !hasPendingOffer(booking.bookingID) && !hasRefund(booking.bookingID)"
              class="mt-4 rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
            >
              <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#e63946]">Disruption Outcome</p>
              <p class="mt-1 text-sm font-semibold text-[#1d1d1f]">{{ outcomeForBooking(booking).title }}</p>
              <p class="mt-1 text-xs text-[#6e6e73]">{{ outcomeForBooking(booking).detail }}</p>
            </div>
          </div>
        </article>
      </div>

      <p class="mt-10 text-center text-xs text-[#6e6e73]">Need help with your booking? Contact support.</p>
    </section>
  </main>
</template>
