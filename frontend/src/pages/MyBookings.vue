<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'
// AppNav removed

const router = useRouter()
const { currentPassenger } = usePassengerSession()

const bookings      = ref([])
const offers        = ref([])
const loading       = ref(true)
const error         = ref(null)
const filterStatus  = ref('All')

const STATUS_FILTERS = ['All', 'Confirmed', 'Pending', 'Cancelled', 'Failed']

// ── Mock flight data — replace with Flight Service API call when ready ──
// TODO: replace with axios.get(`http://localhost:XXXX/flights/${flightID}`)
const MOCK_FLIGHTS = {
  201: { flightNumber: 'BA123', origin: 'Singapore (SIN)', destination: 'Bangkok (BKK)', date: '2026-04-15', departureTime: '08:30', arrivalTime: '10:00', duration: '1h 30m' },
  202: { flightNumber: 'BA456', origin: 'Singapore (SIN)', destination: 'Bangkok (BKK)', date: '2026-04-15', departureTime: '14:20', arrivalTime: '15:50', duration: '1h 30m' },
  203: { flightNumber: 'BA789', origin: 'Singapore (SIN)', destination: 'Bangkok (BKK)', date: '2026-04-15', departureTime: '19:45', arrivalTime: '21:15', duration: '1h 30m' },
}

function getFlightDetails(flightID) {
  return MOCK_FLIGHTS[flightID] || null
}

onMounted(async () => {
  if (!currentPassenger.value) { router.push('/auth'); return }
  await loadData()
})

async function loadData() {
  loading.value = true
  error.value   = null
  try {
    const [bookingsRes, offersRes] = await Promise.allSettled([
      axios.get(`http://localhost:3010/api/bookings/passenger/${currentPassenger.value.passenger_id}`),
      axios.get(`http://localhost:5002/offer?passengerID=${currentPassenger.value.passenger_id}&status=Pending Response`)
    ])
    if (bookingsRes.status === 'fulfilled') bookings.value = bookingsRes.value.data
    else error.value = 'Could not load your bookings. Please try again.'
    if (offersRes.status === 'fulfilled') offers.value = offersRes.value.data
  } finally {
    loading.value = false
  }
}

function getPendingOffer(bookingID) {
  return offers.value.find(o => o.bookingID === bookingID && o.status === 'Pending Response')
}

const filteredBookings = computed(() => {
  if (filterStatus.value === 'All') return bookings.value
  return bookings.value.filter(b => {
    if (filterStatus.value === 'Cancelled') return b.status.startsWith('Cancelled')
    return b.status === filterStatus.value
  })
})

function countByStatus(status) {
  if (status === 'All') return bookings.value.length
  if (status === 'Cancelled') return bookings.value.filter(b => b.status.startsWith('Cancelled')).length
  return bookings.value.filter(b => b.status === status).length
}

function statusStyle(status) {
  if (status === 'Confirmed')              return { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0', dot: '#22c55e' }
  if (status === 'Pending')                return { bg: '#fefce8', color: '#a16207', border: '#fef08a', dot: '#eab308' }
  if (status.startsWith('Cancelled'))      return { bg: '#f9fafb', color: '#6b7280', border: '#e5e7eb', dot: '#9ca3af' }
  if (status === 'Failed')                 return { bg: '#fef2f2', color: '#dc2626', border: '#fecaca', dot: '#ef4444' }
  return                                          { bg: '#f9fafb', color: '#6b7280', border: '#e5e7eb', dot: '#9ca3af' }
}

function formatDate(d) {
  if (!d) return '—'
  // DB stores SGT time but returns it with Z suffix (incorrectly labelled as UTC)
  // So we read the raw time values directly from UTC getters — no conversion needed
  const dt    = new Date(d)
  const day   = dt.getUTCDate()
  const month = dt.toLocaleString('en-SG', { month: 'short', timeZone: 'UTC' })
  const year  = dt.getUTCFullYear()
  const hours = dt.getUTCHours()
  const mins  = String(dt.getUTCMinutes()).padStart(2, '0')
  const ampm  = hours >= 12 ? 'PM' : 'AM'
  const h12   = hours % 12 || 12
  return `${day} ${month} ${year}, ${h12}:${mins} ${ampm} SGT`
}

function formatAmount(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '0.00'
  return amount.toFixed(2)
}

function formatExpiry(expiryStr) {
  if (!expiryStr) return null
  const h = Math.ceil((new Date(expiryStr) - new Date()) / 3600000)
  if (h < 0)  return { text: 'Offer expired', urgent: true }
  if (h < 6)  return { text: `Expires in ${h}h — act now!`, urgent: true }
  if (h < 24) return { text: `Expires in ${h} hours`, urgent: false }
  return { text: `Expires in ${Math.ceil(h/24)} days`, urgent: false }
}

function viewOffer(offer) {
  router.push({ path: '/rebooking-offer', query: { offerID: offer.offerID, bookingID: offer.bookingID } })
}
</script>

<template>
  <div>
  <main style="min-height:100vh; background: radial-gradient(circle at 12% 6%, #ffffff 0%, #f5f5f7 48%, #ececf1 100%); padding: 60px 0 80px;">
    <div style="max-width: 800px; margin: 0 auto; padding: 0 24px;">

      <!-- Header -->
      <div style="display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:36px; flex-wrap:wrap; gap:16px;">
        <div>
          <p style="font-size:11px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:#e63946; margin:0 0 4px;">
            {{ currentPassenger?.FirstName }} {{ currentPassenger?.LastName }}
          </p>
          <h1 style="font-size:42px; font-weight:700; letter-spacing:-0.03em; color:#1d1d1f; margin:0; line-height:1.05;">My Bookings</h1>
          <p style="font-size:14px; color:#6e6e73; margin:6px 0 0;">
            <span v-if="!loading">{{ bookings.length }} booking{{ bookings.length !== 1 ? 's' : '' }} total</span>
            <span v-else>Loading your bookings...</span>
          </p>
        </div>
        <button
          @click="router.push('/')"
          style="display:flex; align-items:center; gap:8px; background:#1d1d1f; color:#fff; border:none; border-radius:100px; padding:12px 22px; font-size:14px; font-weight:600; cursor:pointer; transition:background 0.2s; white-space:nowrap;"
          onmouseover="this.style.background='#000'"
          onmouseout="this.style.background='#1d1d1f'"
        >
          <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M12 4v16m8-8H4"/></svg>
          Book New Flight
        </button>
      </div>

      <!-- Pending offer alert banner -->
      <div v-if="!loading && offers.length > 0"
        style="background:#fff5f5; border:1.5px solid #fecaca; border-radius:20px; padding:20px 24px; margin-bottom:24px; display:flex; align-items:flex-start; gap:16px;">
        <div style="width:40px; height:40px; background:#fee2e2; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
          <svg width="20" height="20" fill="none" stroke="#dc2626" stroke-width="2" viewBox="0 0 24 24">
            <path d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
          </svg>
        </div>
        <div>
          <p style="font-weight:700; color:#1d1d1f; margin:0 0 4px; font-size:15px;">
            Action required — {{ offers.length }} pending rebooking offer{{ offers.length > 1 ? 's' : '' }}
          </p>
          <p style="font-size:13px; color:#6e6e73; margin:0;">
            Your flight was cancelled and we found an alternative. Please scroll down to respond before the offer expires.
          </p>
        </div>
      </div>

      <!-- Loading skeleton -->
      <div v-if="loading" style="display:flex; flex-direction:column; gap:12px;">
        <div v-for="i in 3" :key="i"
          style="height:120px; background:white; border-radius:20px; border:1px solid rgba(0,0,0,0.06); animation: pulse 1.5s ease-in-out infinite;"
        ></div>
        <p style="text-align:center; font-size:13px; color:#6e6e73; margin-top:8px;">Loading your bookings...</p>
      </div>

      <!-- Error state -->
      <div v-else-if="error"
        style="background:white; border:1px solid #fecaca; border-radius:24px; padding:48px 24px; text-align:center;">
        <div style="width:52px; height:52px; background:#fef2f2; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px;">
          <svg width="24" height="24" fill="none" stroke="#ef4444" stroke-width="2" viewBox="0 0 24 24">
            <path d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
          </svg>
        </div>
        <p style="font-weight:700; font-size:16px; color:#1d1d1f; margin:0 0 6px;">Something went wrong</p>
        <p style="font-size:14px; color:#6e6e73; margin:0 0 20px;">{{ error }}</p>
        <button @click="loadData"
          style="background:#1d1d1f; color:white; border:none; border-radius:100px; padding:10px 24px; font-size:14px; font-weight:600; cursor:pointer;">
          Try Again
        </button>
      </div>

      <template v-else>

        <!-- Filter tabs -->
        <div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:20px;">
          <button
            v-for="status in STATUS_FILTERS" :key="status"
            @click="filterStatus = status"
            :style="{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '8px 16px', borderRadius: '100px', fontSize: '13px', fontWeight: '600',
              cursor: 'pointer', transition: 'all 0.15s', border: '1.5px solid',
              background: filterStatus === status ? '#1d1d1f' : 'white',
              color: filterStatus === status ? 'white' : '#6e6e73',
              borderColor: filterStatus === status ? '#1d1d1f' : 'rgba(0,0,0,0.1)',
            }"
          >
            {{ status }}
            <span :style="{
              background: filterStatus === status ? 'rgba(255,255,255,0.2)' : '#f5f5f7',
              color: filterStatus === status ? 'white' : '#6e6e73',
              borderRadius: '100px', padding: '1px 7px', fontSize: '11px', fontWeight: '700'
            }">{{ countByStatus(status) }}</span>
          </button>
        </div>

        <!-- Empty state -->
        <div v-if="filteredBookings.length === 0"
          style="background:white; border:1px solid rgba(0,0,0,0.08); border-radius:28px; padding:64px 24px; text-align:center;">
          <div style="width:64px; height:64px; background:#f5f5f7; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px;">
            <svg width="28" height="28" fill="none" stroke="#6e6e73" stroke-width="1.5" viewBox="0 0 24 24">
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
          </div>
          <p style="font-weight:700; font-size:16px; color:#1d1d1f; margin:0 0 6px;">
            {{ filterStatus === 'All' ? 'No bookings yet' : `No ${filterStatus.toLowerCase()} bookings` }}
          </p>
          <p style="font-size:14px; color:#6e6e73; margin:0 0 20px;">
            {{ filterStatus === 'All' ? 'Your flights will appear here once booked.' : 'Try a different filter above.' }}
          </p>
          <button v-if="filterStatus === 'All'" @click="router.push('/')"
            style="background:#1d1d1f; color:white; border:none; border-radius:100px; padding:10px 24px; font-size:14px; font-weight:600; cursor:pointer;">
            Search Flights
          </button>
          <button v-else @click="filterStatus = 'All'"
            style="background:none; border:none; color:#e63946; font-size:14px; font-weight:600; cursor:pointer; text-decoration:underline;">
            Clear filter
          </button>
        </div>

        <!-- Booking cards -->
        <div v-else style="display:flex; flex-direction:column; gap:12px;">
          <div
            v-for="booking in filteredBookings" :key="booking.bookingID"
            :style="{
              background: 'white',
              border: getPendingOffer(booking.bookingID) ? '2px solid #fca5a5' : '1.5px solid rgba(0,0,0,0.07)',
              borderRadius: '24px',
              overflow: 'hidden',
              transition: 'box-shadow 0.2s, transform 0.2s',
              boxShadow: '0 2px 16px rgba(0,0,0,0.05)',
            }"
            onmouseover="this.style.boxShadow='0 12px 40px rgba(0,0,0,0.1)'; this.style.transform='translateY(-2px)'"
            onmouseout="this.style.boxShadow='0 2px 16px rgba(0,0,0,0.05)'; this.style.transform='translateY(0)'"
          >
            <!-- Coloured top accent bar per status -->
            <div :style="{
              height: '4px',
              background: booking.status === 'Confirmed' ? 'linear-gradient(90deg, #22c55e, #86efac)' :
                          booking.status === 'Pending'   ? 'linear-gradient(90deg, #eab308, #fde047)' :
                          booking.status === 'Failed'    ? 'linear-gradient(90deg, #ef4444, #fca5a5)' :
                          booking.status.startsWith('Cancelled') ? 'linear-gradient(90deg, #9ca3af, #e5e7eb)' :
                          'linear-gradient(90deg, #e63946, #f87171)'
            }"></div>

            <div style="padding: 22px 24px;">

              <!-- Row 1: flight number + status badge -->
              <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:14px;">
                <div style="display:flex; align-items:center; gap:12px;">
                  <!-- Coloured icon matching status -->
                  <div :style="{
                    width: '42px', height: '42px', borderRadius: '14px', flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: booking.status === 'Confirmed' ? '#f0fdf4' :
                                booking.status === 'Pending'   ? '#fefce8' :
                                booking.status === 'Failed'    ? '#fef2f2' : '#f9fafb'
                  }">
                    <svg width="20" height="20" fill="none" stroke-width="1.8" viewBox="0 0 24 24"
                      :stroke="booking.status === 'Confirmed' ? '#22c55e' :
                               booking.status === 'Pending'   ? '#eab308' :
                               booking.status === 'Failed'    ? '#ef4444' : '#9ca3af'">
                      <path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                    </svg>
                  </div>
                  <div>
                    <p style="font-size:16px; font-weight:700; color:#1d1d1f; margin:0 0 2px; letter-spacing:-0.01em;">
                      {{ getFlightDetails(booking.flightID)?.flightNumber || 'Flight #' + booking.flightID }}
                    </p>
                    <div style="display:flex; align-items:center; gap:6px; margin-top:4px; flex-wrap:wrap;">
                      <span style="background:#f5f5f7; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:600; color:#1d1d1f;">
                        Seat {{ booking.seatNumber }}
                      </span>
                      <span style="background:#f5f5f7; border-radius:6px; padding:2px 8px; font-size:11px; font-weight:600; color:#6e6e73; font-family:monospace;">
                        Ref #{{ booking.bookingID }}
                      </span>
                    </div>
                  </div>
                </div>
                <!-- Status badge -->
                <div :style="{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  background: statusStyle(booking.status).bg,
                  color: statusStyle(booking.status).color,
                  border: '1.5px solid ' + statusStyle(booking.status).border,
                  borderRadius: '100px', padding: '5px 14px',
                  fontSize: '12px', fontWeight: '700', whiteSpace: 'nowrap'
                }">
                  <span :style="{ width:'6px', height:'6px', borderRadius:'50%', background: statusStyle(booking.status).dot, flexShrink:0 }"></span>
                  {{ booking.status }}
                </div>
              </div>

              <!-- Row 2: flight route visual -->
              <!-- ⚠️ MOCK DATA — Flight Service Integration Required -->
              <!-- TODO: Replace getFlightDetails() with GET /flights/{flightID} from Flight Service -->
              <div v-if="getFlightDetails(booking.flightID)"
                style="border-radius:14px; padding:16px 18px; margin-bottom:14px; border:1px solid rgba(0,0,0,0.06); background:white; position:relative; overflow:hidden;">
                <!-- Subtle gradient background -->
                <div style="position:absolute; inset:0; background:linear-gradient(135deg, #f0f9ff 0%, #f9fafb 50%, #f0fdf4 100%); opacity:0.6;"></div>
                <div style="position:relative;">
                  <!-- Mock badge -->
                  <div style="display:inline-flex; align-items:center; gap:4px; background:#fff0f0; border:1px solid #fca5a5; border-radius:5px; padding:2px 7px; margin-bottom:12px;">
                    <svg width="9" height="9" fill="#dc2626" viewBox="0 0 20 20"><path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 4a1 1 0 011 1v3a1 1 0 11-2 0V7a1 1 0 011-1zm0 7a1 1 0 100 2 1 1 0 000-2z"/></svg>
                    <span style="font-size:9px; font-weight:700; color:#dc2626; letter-spacing:0.05em;">[ MOCK — Pending Flight Service Integration ]</span>
                  </div>
                  <!-- Route -->
                  <div style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
                    <!-- Origin -->
                    <div style="text-align:left;">
                      <p style="font-size:28px; font-weight:800; color:#1d1d1f; margin:0; letter-spacing:-0.03em; line-height:1;">{{ getFlightDetails(booking.flightID).departureTime }}</p>
                      <p style="font-size:12px; font-weight:700; color:#2563eb; margin:4px 0 0;">{{ getFlightDetails(booking.flightID).origin.split('(')[1]?.replace(')','') || getFlightDetails(booking.flightID).origin.split(' ')[0] }}</p>
                      <p style="font-size:11px; color:#6e6e73; margin:1px 0 0;">{{ getFlightDetails(booking.flightID).origin.split('(')[0].trim() }}</p>
                    </div>
                    <!-- Middle: duration + line -->
                    <div style="flex:1; display:flex; flex-direction:column; align-items:center; gap:4px; padding:0 12px;">
                      <span style="font-size:10px; font-weight:700; color:#6e6e73; background:#f3f4f6; border-radius:100px; padding:2px 8px;">{{ getFlightDetails(booking.flightID).duration }}</span>
                      <div style="width:100%; display:flex; align-items:center; gap:3px;">
                        <div style="width:6px; height:6px; border-radius:50%; border:2px solid #2563eb; flex-shrink:0;"></div>
                        <div style="flex:1; height:1.5px; background:linear-gradient(90deg, #2563eb, #e63946);"></div>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="#e63946"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>
                      </div>
                      <p style="font-size:10px; color:#9ca3af; margin:0; font-weight:500;">{{ getFlightDetails(booking.flightID).date }}</p>
                    </div>
                    <!-- Destination -->
                    <div style="text-align:right;">
                      <p style="font-size:28px; font-weight:800; color:#1d1d1f; margin:0; letter-spacing:-0.03em; line-height:1;">{{ getFlightDetails(booking.flightID).arrivalTime }}</p>
                      <p style="font-size:12px; font-weight:700; color:#e63946; margin:4px 0 0;">{{ getFlightDetails(booking.flightID).destination.split('(')[1]?.replace(')','') || getFlightDetails(booking.flightID).destination.split(' ')[0] }}</p>
                      <p style="font-size:11px; color:#6e6e73; margin:1px 0 0;">{{ getFlightDetails(booking.flightID).destination.split('(')[0].trim() }}</p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Row 3: amount + booked on + action button -->
              <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
                <div style="display:flex; gap:16px; align-items:center;">
                  <div style="padding:8px 14px; background:linear-gradient(135deg, #f0fdf4, #f5f5f7); border:1px solid rgba(34,197,94,0.15); border-radius:10px; text-align:center;">
                    <p style="font-size:9px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#6e6e73; margin:0 0 2px;">Paid</p>
                    <p style="font-size:17px; font-weight:800; color:#1d1d1f; margin:0;">${{ formatAmount(booking.amount) }}</p>
                  </div>
                  <div style="height:36px; width:1px; background:rgba(0,0,0,0.08);"></div>
                  <div>
                    <p style="font-size:9px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#9ca3af; margin:0 0 2px;">Booked</p>
                    <p style="font-size:13px; font-weight:600; color:#1d1d1f; margin:0;">{{ formatDate(booking.createdAt) }}</p>
                  </div>
                </div>

                <!-- Action buttons -->
                <button
                  v-if="getPendingOffer(booking.bookingID)"
                  @click="viewOffer(getPendingOffer(booking.bookingID))"
                  style="display:flex; align-items:center; gap:7px; background:#e63946; color:white; border:none; border-radius:100px; padding:10px 20px; font-size:13px; font-weight:700; cursor:pointer; transition:background 0.2s;"
                  onmouseover="this.style.background='#c81d2a'"
                  onmouseout="this.style.background='#e63946'"
                >
                  <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                  </svg>
                  View Rebooking Offer
                </button>

                <button v-else-if="booking.status === 'Confirmed'" disabled title="Coming soon"
                  style="font-size:12px; color:#9ca3af; background:#f9fafb; border:1px solid #e5e7eb; border-radius:100px; padding:8px 18px; cursor:not-allowed; font-weight:600;">
                  Cancel Booking
                </button>

                <button v-else-if="booking.status === 'Failed'" disabled title="Coming soon"
                  style="font-size:12px; color:#9ca3af; background:#f9fafb; border:1px solid #e5e7eb; border-radius:100px; padding:8px 18px; cursor:not-allowed; font-weight:600;">
                  Retry Payment
                </button>

                <button v-else-if="booking.status === 'Cancelled+Refunded'" disabled title="Coming soon"
                  style="font-size:12px; color:#9ca3af; background:#f9fafb; border:1px solid #e5e7eb; border-radius:100px; padding:8px 18px; cursor:not-allowed; font-weight:600;">
                  View Refund Details
                </button>

                <span v-else-if="booking.status.startsWith('Cancelled') && !booking.status.includes('Refunded')"
                  style="font-size:12px; color:#9ca3af; background:#f9fafb; border:1px solid #e5e7eb; border-radius:100px; padding:7px 14px;">
                  Flight cancelled
                </span>
              </div>

            </div>

            <!-- Offer expiry warning -->
            <div
              v-if="getPendingOffer(booking.bookingID) && formatExpiry(getPendingOffer(booking.bookingID).expiryTime)"
              :style="{
                marginTop: '14px',
                background: formatExpiry(getPendingOffer(booking.bookingID).expiryTime).urgent ? '#fff7ed' : '#fffbeb',
                border: '1px solid ' + (formatExpiry(getPendingOffer(booking.bookingID).expiryTime).urgent ? '#fed7aa' : '#fef08a'),
                borderRadius: '12px', padding: '10px 14px',
                display: 'flex', alignItems: 'center', gap: '8px'
              }"
            >
              <svg width="14" height="14" fill="none" stroke="#d97706" stroke-width="2" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
              </svg>
              <p style="font-size:12px; font-weight:600; color:#92400e; margin:0;">
                {{ formatExpiry(getPendingOffer(booking.bookingID).expiryTime).text }}
              </p>
            </div>

          </div>
        </div>

      </template>

      <!-- Footer -->
      <p style="text-align:center; font-size:12px; color:#6e6e73; margin-top:40px;">
        Need help with a booking? Contact our support team.
      </p>

    </div>
  </main>
  </div>
</template>

<style scoped>
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>