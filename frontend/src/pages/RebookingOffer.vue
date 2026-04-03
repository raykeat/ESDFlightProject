<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'
import { apiUrl } from '../config/api'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()

const offerID = parseInt(route.query.offerID)

const offer = ref(null)
const origFlight = ref(null)
const newFlight = ref(null)
const loading = ref(true)
const error = ref(null)
const submitting = ref(false)
const decision = ref(null)
const showConfirm = ref(null)

onMounted(async () => {
  if (!currentPassenger.value) {
    router.push('/auth')
    return
  }

  if (!offerID) {
    error.value = 'Invalid offer link.'
    loading.value = false
    return
  }

  await loadOffer()
})

async function loadOffer() {
  loading.value = true
  error.value = null

  try {
    const offerRes = await axios.get(apiUrl(`/api/offer/${offerID}`))
    offer.value = offerRes.data

    if (offer.value.status !== 'Pending Response') {
      error.value = `This offer has already been ${offer.value.status.toLowerCase()}.`
      return
    }

    const [origRes, newRes] = await Promise.all([
      axios.get(apiUrl(`/api/flight/${offer.value.origFlightID}`)),
      axios.get(apiUrl(`/api/flight/${offer.value.newFlightID}`))
    ])

    const mapFlight = (flight) => {
      const [day, month, year] = flight.Date.split('/')
      return {
        flightID: flight.FlightID,
        flightNumber: flight.FlightNumber,
        origin: flight.Origin,
        destination: flight.Destination,
        date: `${year}-${month}-${day}`,
        departureTime: flight.DepartureTime,
        arrivalTime: flight.ArrivalTime,
        status: flight.Status
      }
    }

    origFlight.value = mapFlight(origRes.data)
    newFlight.value = mapFlight(newRes.data)
  } catch (err) {
    console.error('Error loading offer:', err)
    if (err.response?.status === 404) {
      error.value = 'This offer could not be found. It may have expired or already been responded to.'
    } else {
      error.value = 'Could not load offer details. Please try again.'
    }
  } finally {
    loading.value = false
  }
}

async function acceptOffer() {
  showConfirm.value = null
  router.push({
    path: '/rebooking-seat-selection',
    query: { offerID },
  })
}

async function rejectOffer() {
  submitting.value = true
  showConfirm.value = null

  try {
    await axios.post(apiUrl('/api/rebooking/reject'), {
      offerID
    })

    decision.value = 'rejected'
  } catch (err) {
    console.error('Error rejecting offer:', err)
    error.value = err.response?.data?.message || 'Could not reject offer. Please try again.'
  } finally {
    submitting.value = false
  }
}

function formatDate(dateValue) {
  if (!dateValue) return '--'
  const cleaned = String(dateValue).replace(/ [A-Z]{2,4}$/, '').trim()
  return new Date(cleaned).toLocaleDateString('en-SG', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}

function getAirportCode(place) {
  if (!place) return '---'
  return String(place)
    .split(/[\s-]+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 3)
    .toUpperCase()
}

function passengerName() {
  const first = currentPassenger.value?.FirstName || currentPassenger.value?.firstName || ''
  const last = currentPassenger.value?.LastName || currentPassenger.value?.lastName || ''
  return `${first} ${last}`.trim() || 'Passenger'
}

function routeLabel(flight) {
  if (!flight) return '--'
  return `${flight.origin} to ${flight.destination}`
}

function formatExpiry(expiryStr) {
  if (!expiryStr) return null

  const cleaned = expiryStr.replace(/ [A-Z]{2,4}$/, '').trim()
  const hours = Math.ceil((new Date(cleaned) - new Date()) / 3600000)

  if (isNaN(hours)) return null
  if (hours < 0) return { text: 'Expired', urgent: true }
  if (hours < 6) return { text: `Expires in ${hours}h - act now!`, urgent: true }
  if (hours < 24) return { text: `Expires in ${hours} hours`, urgent: false }
  return { text: `Expires in ${Math.ceil(hours / 24)} days`, urgent: false }
}
</script>

<template>
  <main style="min-height:100vh; background:radial-gradient(circle at 88% 10%, rgba(239,68,68,0.15), transparent 22%), radial-gradient(circle at 10% 18%, rgba(255,255,255,0.95), transparent 28%), linear-gradient(180deg, #fbfbfd 0%, #f7f4f4 46%, #f2eeee 100%); padding: 52px 0 84px;">
    <div style="max-width:1080px; margin:0 auto; padding:0 24px;">
      <button
        @click="router.push('/my-bookings')"
        style="display:flex; align-items:center; gap:6px; background:none; border:none; color:#6e6e73; font-size:14px; font-weight:500; cursor:pointer; margin-bottom:28px; padding:0;"
      >
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path d="M15 19l-7-7 7-7"/>
        </svg>
        Back to My Bookings
      </button>

      <div v-if="loading" style="display:flex; flex-direction:column; align-items:center; gap:16px; padding:80px 0;">
        <div style="width:48px; height:48px; border:4px solid #f5f5f7; border-top-color:#e63946; border-radius:50%; animation:spin 0.8s linear infinite;"></div>
        <p style="font-size:14px; color:#6e6e73;">Loading your offer...</p>
      </div>

      <div
        v-else-if="error && !decision"
        style="background:white; border:1px solid #fecaca; border-radius:24px; padding:48px 32px; text-align:center; box-shadow:0 24px 48px rgba(17,24,39,0.08);"
      >
        <div style="width:56px; height:56px; background:#fef2f2; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px;">
          <svg width="26" height="26" fill="none" stroke="#ef4444" stroke-width="2" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 8v4m0 4h.01"/>
          </svg>
        </div>
        <p style="font-weight:700; font-size:17px; color:#1d1d1f; margin:0 0 8px;">{{ error }}</p>
        <button
          @click="router.push('/my-bookings')"
          style="margin-top:16px; background:linear-gradient(135deg, #ef4444 0%, #f43f5e 100%); color:white; border:none; border-radius:100px; padding:10px 24px; font-size:14px; font-weight:600; cursor:pointer;"
        >
          Back to My Bookings
        </button>
      </div>

      <div
        v-else-if="decision === 'accepted'"
        style="background:white; border:1px solid rgba(230,57,70,0.12); border-radius:32px; padding:56px 32px; text-align:center; box-shadow:0 30px 70px rgba(17,24,39,0.08);"
      >
        <div style="width:72px; height:72px; background:linear-gradient(135deg, #ecfdf3 0%, #d1fae5 100%); border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 20px;">
          <svg width="36" height="36" fill="none" stroke="#16a34a" stroke-width="2.5" viewBox="0 0 24 24">
            <path d="M5 13l4 4L19 7"/>
          </svg>
        </div>
        <h1 style="font-size:30px; font-weight:700; color:#1d1d1f; margin:0 0 10px; letter-spacing:-0.02em;">Rebooking Confirmed!</h1>
        <p style="font-size:15px; color:#6e6e73; margin:0 0 28px; line-height:1.6;">
          You've been rebooked onto <strong style="color:#1d1d1f;">Flight {{ newFlight?.flightNumber }}</strong> on {{ formatDate(newFlight?.date) }}.
          A confirmation email has been sent to you.
        </p>
        <div style="background:linear-gradient(180deg, #fffefe 0%, #f8fbf9 100%); border:1px solid #d1fae5; border-radius:18px; padding:16px 20px; margin-bottom:28px; display:inline-block; min-width:280px;">
          <p style="font-size:12px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#15803d; margin:0 0 4px;">New Flight</p>
          <p style="font-size:18px; font-weight:700; color:#1d1d1f; margin:0;">{{ newFlight?.flightNumber }} - {{ newFlight?.departureTime }} to {{ newFlight?.arrivalTime }}</p>
          <p style="font-size:13px; color:#6e6e73; margin:4px 0 0;">{{ routeLabel(newFlight) }}</p>
        </div>
        <br>
        <button
          @click="router.push('/my-bookings')"
          style="background:linear-gradient(135deg, #ef4444 0%, #f43f5e 100%); color:white; border:none; border-radius:100px; padding:12px 32px; font-size:14px; font-weight:600; cursor:pointer; box-shadow:0 12px 24px rgba(239,68,68,0.24);"
        >
          View My Bookings
        </button>
      </div>

      <div
        v-else-if="decision === 'rejected'"
        style="background:white; border:1px solid rgba(230,57,70,0.12); border-radius:32px; padding:56px 32px; text-align:center; box-shadow:0 30px 70px rgba(17,24,39,0.08);"
      >
        <div style="width:72px; height:72px; background:#f9fafb; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 20px;">
          <svg width="36" height="36" fill="none" stroke="#6b7280" stroke-width="2" viewBox="0 0 24 24">
            <path d="M9 14l2-2 2 2M15 10l-2 2-2-2M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/>
          </svg>
        </div>
        <h1 style="font-size:30px; font-weight:700; color:#1d1d1f; margin:0 0 10px; letter-spacing:-0.02em;">Offer Rejected</h1>
        <p style="font-size:15px; color:#6e6e73; margin:0 0 28px; line-height:1.6;">
          Your original booking has been cancelled and a <strong style="color:#1d1d1f;">full refund</strong> has been initiated.
          Please allow 5-10 business days for the refund to appear.
        </p>
        <button
          @click="router.push('/my-bookings')"
          style="background:linear-gradient(135deg, #ef4444 0%, #f43f5e 100%); color:white; border:none; border-radius:100px; padding:12px 32px; font-size:14px; font-weight:600; cursor:pointer; box-shadow:0 12px 24px rgba(239,68,68,0.24);"
        >
          View My Bookings
        </button>
      </div>

      <section
        v-else-if="offer && origFlight && newFlight"
        style="background:white; border:1px solid rgba(15,23,42,0.06); border-radius:34px; overflow:hidden; box-shadow:0 30px 70px rgba(17,24,39,0.08);"
      >
        <div style="padding:34px 34px 24px; background:radial-gradient(circle at top right, rgba(239,68,68,0.12), transparent 22%), linear-gradient(180deg, #ffffff 0%, #fff8f8 100%); border-bottom:1px solid rgba(15,23,42,0.06);">
          <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:18px; flex-wrap:wrap; margin-bottom:22px;">
            <div>
              <p style="font-size:11px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:#ef4444; margin:0 0 8px;">Blaze Assist</p>
              <h1 style="font-size:40px; font-weight:700; letter-spacing:-0.03em; color:#111827; margin:0 0 10px;">Review Your Flight Change</h1>
              <p style="font-size:15px; color:#6b7280; margin:0; max-width:640px; line-height:1.7;">
                Your original flight was disrupted. We found a replacement option for the same journey and held it for you temporarily.
              </p>
            </div>

            <div
              v-if="offer.expiryTime && formatExpiry(offer.expiryTime)"
              :style="{
                background: formatExpiry(offer.expiryTime).urgent ? '#fff1f2' : '#fff7ed',
                border: '1px solid ' + (formatExpiry(offer.expiryTime).urgent ? '#fecdd3' : '#fed7aa'),
                borderRadius: '999px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px'
              }"
            >
              <svg width="16" height="16" fill="none" stroke="#ea580c" stroke-width="2" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 6v6l4 2"/>
              </svg>
              <p style="font-size:13px; font-weight:700; color:#9a3412; margin:0;">
                {{ formatExpiry(offer.expiryTime).text }}
              </p>
            </div>
          </div>

          <div style="display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px;">
            <div style="background:#fff; border:1px solid rgba(15,23,42,0.06); border-radius:18px; padding:16px 18px;">
              <p style="font-size:10px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#9ca3af; margin:0 0 6px;">Offer Reference</p>
              <p style="font-size:18px; font-weight:700; color:#111827; margin:0;">#{{ offer.offerID }}</p>
            </div>
            <div style="background:#fff; border:1px solid rgba(15,23,42,0.06); border-radius:18px; padding:16px 18px;">
              <p style="font-size:10px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#9ca3af; margin:0 0 6px;">Booking</p>
              <p style="font-size:18px; font-weight:700; color:#111827; margin:0;">#{{ offer.bookingID }}</p>
            </div>
            <div style="background:#fff; border:1px solid rgba(15,23,42,0.06); border-radius:18px; padding:16px 18px;">
              <p style="font-size:10px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#9ca3af; margin:0 0 6px;">Passenger</p>
              <p style="font-size:18px; font-weight:700; color:#111827; margin:0;">{{ passengerName() }}</p>
            </div>
            <div style="background:#fff; border:1px solid rgba(15,23,42,0.06); border-radius:18px; padding:16px 18px;">
              <p style="font-size:10px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#9ca3af; margin:0 0 6px;">Affected Route</p>
              <p style="font-size:18px; font-weight:700; color:#111827; margin:0;">{{ routeLabel(origFlight) }}</p>
            </div>
          </div>
        </div>

        <div style="padding:28px 34px 34px;">
          <div style="margin-bottom:18px; background:linear-gradient(135deg, #fff9ee 0%, #fff3dc 100%); border:1px solid #f4d6a6; border-radius:20px; padding:16px 18px; display:flex; align-items:flex-start; gap:12px;">
            <div style="width:36px; height:36px; border-radius:12px; background:#fff7e8; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
              <svg width="18" height="18" fill="none" stroke="#b76b00" stroke-width="2" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 7v5l3 3"/>
              </svg>
            </div>
            <div>
              <p style="font-size:12px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#9a6200; margin:0 0 4px;">Replacement Search Window</p>
              <p style="font-size:14px; color:#7a5a20; margin:0; line-height:1.7;">
                Blaze Air searched for the next suitable flight on the same route within <strong>2 days</strong> of your cancelled departure, and only offered an option that can fit your full booking.
              </p>
            </div>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:18px;">
            <div style="background:linear-gradient(180deg, #fffdfd 0%, #fff4f4 100%); border:1px solid #f9c9cf; border-radius:24px; padding:24px; box-shadow:0 16px 34px rgba(230,57,70,0.06);">
              <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:18px;">
                <div>
                  <p style="font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#9ca3af; margin:0 0 6px;">Cancelled Flight</p>
                  <h2 style="font-size:28px; font-weight:700; color:#111827; margin:0;">{{ origFlight.flightNumber }}</h2>
                </div>
                <span style="background:#fff1f2; color:#e11d48; border:1px solid #fecdd3; border-radius:999px; padding:8px 14px; font-size:12px; font-weight:700;">Cancelled</span>
              </div>

              <div style="background:white; border:1px solid rgba(15,23,42,0.06); border-radius:18px; padding:18px; margin-bottom:14px;">
                <p style="font-size:15px; font-weight:700; color:#111827; margin:0 0 4px;">{{ routeLabel(origFlight) }}</p>
                <p style="font-size:13px; color:#6b7280; margin:0;">{{ formatDate(origFlight.date) }}</p>
              </div>

              <div style="display:grid; grid-template-columns:1fr auto 1fr; gap:12px; align-items:center;">
                <div>
                  <p style="font-size:28px; font-weight:700; color:#111827; margin:0;">{{ origFlight.departureTime }}</p>
                  <p style="font-size:15px; font-weight:600; color:#374151; margin:4px 0 0;">{{ origFlight.origin }}</p>
                </div>
                <div style="width:92px; display:flex; align-items:center; justify-content:center;">
                  <svg width="92" height="18" viewBox="0 0 92 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M4 9H36" stroke="#f0b7be" stroke-width="1.6" stroke-linecap="round"/>
                    <path d="M56 9H88" stroke="#f0b7be" stroke-width="1.6" stroke-linecap="round"/>
                    <path d="M42 5L50 9L42 13" stroke="#e98a94" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
                <div style="text-align:right;">
                  <p style="font-size:28px; font-weight:700; color:#111827; margin:0;">{{ origFlight.arrivalTime }}</p>
                  <p style="font-size:15px; font-weight:600; color:#374151; margin:4px 0 0;">{{ origFlight.destination }}</p>
                </div>
              </div>
            </div>

            <div style="background:linear-gradient(180deg, #fffef9 0%, #fff7ec 100%); border:1px solid #f4d6a6; box-shadow:0 18px 36px rgba(206,140,37,0.10); border-radius:24px; padding:24px;">
              <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:18px;">
                <div>
                  <p style="font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#9ca3af; margin:0 0 6px;">Proposed Flight</p>
                  <h2 style="font-size:28px; font-weight:700; color:#111827; margin:0;">{{ newFlight.flightNumber }}</h2>
                </div>
                <span style="background:#fff7e8; color:#b76b00; border:1px solid #f4d6a6; border-radius:999px; padding:8px 14px; font-size:12px; font-weight:700;">Ready to Confirm</span>
              </div>

              <div style="background:white; border:1px solid rgba(15,23,42,0.06); border-radius:18px; padding:18px; margin-bottom:14px;">
                <p style="font-size:15px; font-weight:700; color:#111827; margin:0 0 4px;">{{ routeLabel(newFlight) }}</p>
                <p style="font-size:13px; color:#6b7280; margin:0;">{{ formatDate(newFlight.date) }}</p>
              </div>

              <div style="display:grid; grid-template-columns:1fr auto 1fr; gap:12px; align-items:center; margin-bottom:16px;">
                <div>
                  <p style="font-size:28px; font-weight:700; color:#111827; margin:0;">{{ newFlight.departureTime }}</p>
                  <p style="font-size:15px; font-weight:600; color:#374151; margin:4px 0 0;">{{ newFlight.origin }}</p>
                </div>
                <div style="width:92px; display:flex; align-items:center; justify-content:center;">
                  <svg width="92" height="18" viewBox="0 0 92 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M4 9H34" stroke="#efc787" stroke-width="1.8" stroke-linecap="round"/>
                    <path d="M58 9H88" stroke="#efc787" stroke-width="1.8" stroke-linecap="round"/>
                    <path d="M39 9H50" stroke="#ce8c25" stroke-width="1.8" stroke-linecap="round"/>
                    <path d="M46 5L54 9L46 13" stroke="#ce8c25" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
                <div style="text-align:right;">
                  <p style="font-size:28px; font-weight:700; color:#111827; margin:0;">{{ newFlight.arrivalTime }}</p>
                  <p style="font-size:15px; font-weight:600; color:#374151; margin:4px 0 0;">{{ newFlight.destination }}</p>
                </div>
              </div>

              <div style="background:linear-gradient(135deg, #fffaf0 0%, #fff3dc 100%); border:1px solid #f4d6a6; border-radius:16px; padding:14px 16px;">
                <p style="font-size:12px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#b76b00; margin:0 0 6px;">Fare Protection</p>
                <p style="font-size:13px; color:#8a5a10; margin:0; line-height:1.6;">
                  No additional charge. Any fare difference is absorbed by Blaze Air.
                </p>
              </div>
            </div>
          </div>

          <div style="display:grid; grid-template-columns:1.05fr 0.95fr; gap:18px;">
            <div style="background:linear-gradient(180deg, #ffffff 0%, #fffbfb 100%); border:1px solid rgba(15,23,42,0.06); border-radius:24px; padding:24px;">
              <p style="font-size:12px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#9ca3af; margin:0 0 16px;">What happens next</p>
              <div style="display:grid; gap:14px;">
                <div style="padding:18px; background:linear-gradient(180deg, #fff8f8 0%, #fff1f2 100%); border:1px solid #fecdd3; border-radius:18px;">
                  <p style="font-size:16px; font-weight:700; color:#c81e45; margin:0 0 8px;">Reject and get refunded</p>
                  <p style="font-size:13px; color:#9f1239; margin:0; line-height:1.7;">Your original booking will be cancelled and the full amount will be returned to your original payment method within 5-10 business days.</p>
                </div>
                <div style="padding:18px; background:linear-gradient(180deg, #fffdf7 0%, #fff6e8 100%); border:1px solid #f4d6a6; border-radius:18px;">
                  <p style="font-size:16px; font-weight:700; color:#9a6200; margin:0 0 8px;">Accept the replacement flight</p>
                  <p style="font-size:13px; color:#7a4d00; margin:0; line-height:1.7;">We'll confirm you on the proposed flight, keep your itinerary active, and send an updated booking confirmation by email.</p>
                </div>
              </div>
            </div>

            <div style="background:linear-gradient(180deg, #ffffff 0%, #fff9f7 100%); border:1px solid rgba(239,68,68,0.10); border-radius:24px; padding:24px; box-shadow:0 18px 36px rgba(17,24,39,0.05);">
              <p style="font-size:12px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#9ca3af; margin:0 0 14px;">Decision</p>
              <h3 style="font-size:24px; font-weight:700; color:#111827; margin:0 0 10px;">Choose what Blaze Air should do next</h3>
              <p style="font-size:14px; color:#6b7280; margin:0 0 20px; line-height:1.7;">
                Review the route, date, departure time, and destination carefully before responding. No extra payment is needed if you accept this change.
              </p>

              <div
                v-if="error"
                style="background:#fef2f2; border:1px solid #fecaca; border-radius:14px; padding:14px 18px; margin-bottom:16px; font-size:13px; color:#dc2626;"
              >
                {{ error }}
              </div>

              <div style="display:grid; gap:12px;">
                <button
                  @click="showConfirm = 'accept'"
                  :disabled="submitting"
                  style="padding:16px; border-radius:16px; border:none; background:linear-gradient(135deg, #d48710 0%, #b76b00 100%); font-size:15px; font-weight:700; color:white; cursor:pointer; box-shadow:0 12px 24px rgba(183,107,0,0.20);"
                >
                  <span v-if="submitting" style="display:flex; align-items:center; justify-content:center; gap:8px;">
                    <span style="width:16px; height:16px; border:2px solid rgba(255,255,255,0.3); border-top-color:white; border-radius:50%; animation:spin 0.8s linear infinite; display:inline-block;"></span>
                    Processing...
                  </span>
                  <span v-else>Accept Rebooking</span>
                </button>
                <button
                  @click="showConfirm = 'reject'"
                  :disabled="submitting"
                  style="padding:16px; border-radius:16px; border:1.5px solid #fecdd3; background:linear-gradient(180deg, #fffdfd 0%, #fff6f7 100%); font-size:15px; font-weight:700; color:#d72660; cursor:pointer;"
                >
                  Reject and Get Refund
                </button>
              </div>

              <p style="font-size:12px; color:#6b7280; margin:16px 0 0; line-height:1.7;">
                By accepting, you agree to the replacement flight above. By rejecting, your booking will move to refund processing.
              </p>
            </div>
          </div>
        </div>
      </section>

      <div
        v-if="showConfirm"
        style="position:fixed; inset:0; background:rgba(0,0,0,0.5); backdrop-filter:blur(4px); display:flex; align-items:center; justify-content:center; z-index:100; padding:24px;"
      >
        <div style="background:white; border-radius:28px; padding:36px 32px; max-width:400px; width:100%; text-align:center; box-shadow:0 32px 64px rgba(0,0,0,0.2);">
          <template v-if="showConfirm === 'accept'">
            <div style="width:56px; height:56px; background:#fff1f2; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px;">
              <svg width="26" height="26" fill="none" stroke="#ef4444" stroke-width="2.5" viewBox="0 0 24 24">
                <path d="M5 13l4 4L19 7"/>
              </svg>
            </div>
            <h2 style="font-size:20px; font-weight:700; color:#1d1d1f; margin:0 0 8px;">Confirm Acceptance</h2>
            <p style="font-size:14px; color:#6e6e73; margin:0 0 24px; line-height:1.6;">
              You'll be rebooked onto <strong style="color:#1d1d1f;">{{ newFlight?.flightNumber }}</strong> on {{ formatDate(newFlight?.date) }} with no extra fare.
            </p>
            <div style="display:flex; gap:10px;">
              <button
                @click="showConfirm = null"
                style="flex:1; padding:12px; border-radius:12px; border:1.5px solid rgba(0,0,0,0.12); background:white; font-size:14px; font-weight:600; color:#6e6e73; cursor:pointer;"
              >
                Go Back
              </button>
              <button
                @click="acceptOffer"
                style="flex:1; padding:12px; border-radius:12px; border:none; background:linear-gradient(135deg, #ef4444 0%, #f43f5e 100%); font-size:14px; font-weight:600; color:white; cursor:pointer;"
              >
                Yes, Accept
              </button>
            </div>
          </template>

          <template v-else-if="showConfirm === 'reject'">
            <div style="width:56px; height:56px; background:#fef2f2; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px;">
              <svg width="26" height="26" fill="none" stroke="#ef4444" stroke-width="2" viewBox="0 0 24 24">
                <path d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
              </svg>
            </div>
            <h2 style="font-size:20px; font-weight:700; color:#1d1d1f; margin:0 0 8px;">Confirm Rejection</h2>
            <p style="font-size:14px; color:#6e6e73; margin:0 0 24px; line-height:1.6;">
              Your booking will be <strong style="color:#1d1d1f;">cancelled</strong> and you'll receive a <strong style="color:#1d1d1f;">full refund</strong> within 5-10 business days.
            </p>
            <div style="display:flex; gap:10px;">
              <button
                @click="showConfirm = null"
                style="flex:1; padding:12px; border-radius:12px; border:1.5px solid rgba(0,0,0,0.12); background:white; font-size:14px; font-weight:600; color:#6e6e73; cursor:pointer;"
              >
                Go Back
              </button>
              <button
                @click="rejectOffer"
                style="flex:1; padding:12px; border-radius:12px; border:none; background:#e63946; font-size:14px; font-weight:600; color:white; cursor:pointer;"
              >
                Yes, Get Refund
              </button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 960px) {
  [style*='grid-template-columns:repeat(4, minmax(0, 1fr))'],
  [style*='grid-template-columns:1fr 1fr'],
  [style*='grid-template-columns:1.05fr 0.95fr'] {
    grid-template-columns: 1fr !important;
  }
}
</style>
