<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'
import AppNav from '../components/AppNav.vue'

const route  = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()

const offerID   = parseInt(route.query.offerID)
const bookingID = parseInt(route.query.bookingID)

const offer        = ref(null)
const origFlight   = ref(null)
const newFlight    = ref(null)
const passenger    = ref(null)
const couponCode   = ref(null)   // fetched from Coupon Service using offer.couponID
const loading      = ref(true)
const error        = ref(null)
const submitting   = ref(false)
const decision     = ref(null)   // 'accepted' | 'rejected'
const showConfirm  = ref(null)   // 'accept' | 'reject' — confirmation modal

onMounted(async () => {
  if (!currentPassenger.value) { router.push('/auth'); return }
  if (!offerID) { error.value = 'Invalid offer link.'; loading.value = false; return }
  await loadOffer()
})

async function loadOffer() {
  loading.value = true
  error.value   = null
  try {
    // Step 1: Load offer details from Offer Service
    const offerRes = await axios.get(`http://localhost:5002/offer/${offerID}`)
    offer.value = offerRes.data

    // Step 2: Fetch coupon code from Coupon Service if offer has a coupon
    // TODO: Replace port with actual Coupon Service port when available
    if (offer.value.couponID) {
      try {
        const couponRes = await axios.get()
        couponCode.value = couponRes.data.couponCode
      } catch {
        // Coupon Service not yet built — fail silently, coupon section just won't show
        console.warn('Coupon Service unavailable — coupon code not displayed')
      }
    }

    // Check offer is still actionable
    if (offer.value.status !== 'Pending Response') {
      error.value = `This offer has already been ${offer.value.status.toLowerCase()}.`
      return
    }

    // Step 2: Load flight details (mock until Flight Service is ready)
    // TODO: Replace with actual Flight Service calls when available
    // const [origRes, newRes] = await Promise.all([
    //   axios.get(`http://localhost:XXXX/flights/${offer.value.origFlightID}`),
    //   axios.get(`http://localhost:XXXX/flights/${offer.value.newFlightID}`)
    // ])
    // origFlight.value = origRes.data
    // newFlight.value  = newRes.data

    // Mock flight data for now
    origFlight.value = {
      flightID:      offer.value.origFlightID,
      flightNumber:  'SQ123',
      origin:        'Singapore (SIN)',
      destination:   'Tokyo (NRT)',
      date:          '2026-03-20',
      departureTime: '08:30',
      arrivalTime:   '16:30',
      status:        'Cancelled'
    }
    newFlight.value = {
      flightID:      offer.value.newFlightID,
      flightNumber:  'SQ125',
      origin:        'Singapore (SIN)',
      destination:   'Tokyo (NRT)',
      date:          '2026-03-21',
      departureTime: '10:00',
      arrivalTime:   '18:00',
      status:        'Available'
    }

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

// ── Accept offer — Scenario 3 Path A ────────────────────────
async function acceptOffer() {
  submitting.value = true
  showConfirm.value = null
  try {
    // Calls Rebooking Composite (Scenario 3) — not yet built
    // TODO: Replace with actual Rebooking Composite call
    // await axios.post('http://localhost:XXXX/api/rebooking/respond', {
    //   offerID,
    //   bookingID,
    //   decision: 'Accepted',
    //   passengerID: currentPassenger.value.passenger_id
    // })

    // For now: directly update Offer Service status
    await axios.put(`http://localhost:5002/offer/${offerID}`, {
      status: 'Accepted'
    })

    decision.value = 'accepted'
  } catch (err) {
    console.error('Error accepting offer:', err)
    error.value = err.response?.data?.message || 'Could not accept offer. Please try again.'
  } finally {
    submitting.value = false
  }
}

// ── Reject offer — Scenario 3 Path B ────────────────────────
async function rejectOffer() {
  submitting.value = true
  showConfirm.value = null
  try {
    // Calls Rebooking Composite (Scenario 3) — not yet built
    // TODO: Replace with actual Rebooking Composite call
    // await axios.post('http://localhost:XXXX/api/rebooking/respond', {
    //   offerID,
    //   bookingID,
    //   decision: 'Rejected',
    //   passengerID: currentPassenger.value.passenger_id
    // })

    // For now: directly update Offer Service status
    await axios.put(`http://localhost:5002/offer/${offerID}`, {
      status: 'Rejected'
    })

    decision.value = 'rejected'
  } catch (err) {
    console.error('Error rejecting offer:', err)
    error.value = err.response?.data?.message || 'Could not reject offer. Please try again.'
  } finally {
    submitting.value = false
  }
}

function formatDate(d) {
  if (!d) return '—'
  const cleaned = String(d).replace(/ [A-Z]{2,4}$/, '').trim()
  return new Date(cleaned).toLocaleDateString('en-SG', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
}

function formatExpiry(expiryStr) {
  if (!expiryStr) return null
  // Strip timezone suffix (e.g. " SGT") before parsing
  const cleaned = expiryStr.replace(/ [A-Z]{2,4}$/, '').trim()
  const h = Math.ceil((new Date(cleaned) - new Date()) / 3600000)
  if (isNaN(h)) return null
  if (h < 0)  return { text: 'Expired', urgent: true }
  if (h < 6)  return { text: `Expires in ${h}h — act now!`, urgent: true }
  if (h < 24) return { text: `Expires in ${h} hours`, urgent: false }
  return { text: `Expires in ${Math.ceil(h / 24)} days`, urgent: false }
}
</script>

<template>
  <div>
  <AppNav />
  <main style="min-height:100vh; background: radial-gradient(circle at 12% 6%, #ffffff 0%, #f5f5f7 48%, #ececf1 100%); padding: 60px 0 80px;">
    <div style="max-width: 680px; margin: 0 auto; padding: 0 24px;">

      <!-- Back button -->
      <button
        @click="router.push('/my-bookings')"
        style="display:flex; align-items:center; gap:6px; background:none; border:none; color:#6e6e73; font-size:14px; font-weight:500; cursor:pointer; margin-bottom:28px; padding:0;"
        onmouseover="this.style.color='#1d1d1f'"
        onmouseout="this.style.color='#6e6e73'"
      >
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path d="M15 19l-7-7 7-7"/>
        </svg>
        Back to My Bookings
      </button>

      <!-- Loading -->
      <div v-if="loading" style="display:flex; flex-direction:column; align-items:center; gap:16px; padding:80px 0;">
        <div style="width:48px; height:48px; border:4px solid #f5f5f7; border-top-color:#e63946; border-radius:50%; animation:spin 0.8s linear infinite;"></div>
        <p style="font-size:14px; color:#6e6e73;">Loading your offer...</p>
      </div>

      <!-- Error -->
      <div v-else-if="error && !decision"
        style="background:white; border:1px solid #fecaca; border-radius:24px; padding:48px 32px; text-align:center;">
        <div style="width:56px; height:56px; background:#fef2f2; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px;">
          <svg width="26" height="26" fill="none" stroke="#ef4444" stroke-width="2" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/>
          </svg>
        </div>
        <p style="font-weight:700; font-size:17px; color:#1d1d1f; margin:0 0 8px;">{{ error }}</p>
        <button @click="router.push('/my-bookings')"
          style="margin-top:16px; background:#1d1d1f; color:white; border:none; border-radius:100px; padding:10px 24px; font-size:14px; font-weight:600; cursor:pointer;">
          Back to My Bookings
        </button>
      </div>

      <!-- ── Decision result screens ──────────────────────── -->

      <!-- Accepted -->
      <div v-else-if="decision === 'accepted'"
        style="background:white; border:1px solid #bbf7d0; border-radius:28px; padding:56px 32px; text-align:center;">
        <div style="width:72px; height:72px; background:#f0fdf4; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 20px;">
          <svg width="36" height="36" fill="none" stroke="#22c55e" stroke-width="2.5" viewBox="0 0 24 24">
            <path d="M5 13l4 4L19 7"/>
          </svg>
        </div>
        <h1 style="font-size:30px; font-weight:700; color:#1d1d1f; margin:0 0 10px; letter-spacing:-0.02em;">Rebooking Confirmed!</h1>
        <p style="font-size:15px; color:#6e6e73; margin:0 0 28px; line-height:1.6;">
          You've been rebooked onto <strong style="color:#1d1d1f;">Flight {{ newFlight?.flightNumber }}</strong> on {{ formatDate(newFlight?.date) }}.
          A confirmation email has been sent to you.
        </p>
        <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:16px; padding:16px 20px; margin-bottom:28px; display:inline-block;">
          <p style="font-size:12px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#15803d; margin:0 0 4px;">New Flight</p>
          <p style="font-size:18px; font-weight:700; color:#1d1d1f; margin:0;">{{ newFlight?.flightNumber }} · {{ newFlight?.departureTime }} → {{ newFlight?.arrivalTime }}</p>
          <p style="font-size:13px; color:#6e6e73; margin:4px 0 0;">{{ formatDate(newFlight?.date) }}</p>
        </div>
        <br/>
        <button @click="router.push('/my-bookings')"
          style="background:#1d1d1f; color:white; border:none; border-radius:100px; padding:12px 32px; font-size:14px; font-weight:600; cursor:pointer;">
          View My Bookings
        </button>
      </div>

      <!-- Rejected -->
      <div v-else-if="decision === 'rejected'"
        style="background:white; border:1px solid #e5e7eb; border-radius:28px; padding:56px 32px; text-align:center;">
        <div style="width:72px; height:72px; background:#f9fafb; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 20px;">
          <svg width="36" height="36" fill="none" stroke="#6b7280" stroke-width="2" viewBox="0 0 24 24">
            <path d="M9 14l2-2 2 2M15 10l-2 2-2-2M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/>
          </svg>
        </div>
        <h1 style="font-size:30px; font-weight:700; color:#1d1d1f; margin:0 0 10px; letter-spacing:-0.02em;">Offer Rejected</h1>
        <p style="font-size:15px; color:#6e6e73; margin:0 0 28px; line-height:1.6;">
          Your original booking has been cancelled and a <strong style="color:#1d1d1f;">full refund</strong> has been initiated.
          Please allow 5–10 business days for the refund to appear.
        </p>
        <button @click="router.push('/my-bookings')"
          style="background:#1d1d1f; color:white; border:none; border-radius:100px; padding:12px 32px; font-size:14px; font-weight:600; cursor:pointer;">
          View My Bookings
        </button>
      </div>

      <!-- ── Main offer view ──────────────────────────────── -->
      <template v-else-if="offer && origFlight && newFlight">

        <!-- Header -->
        <div style="margin-bottom:28px;">
          <p style="font-size:11px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:#e63946; margin:0 0 6px;">Flight Disruption Notice</p>
          <h1 style="font-size:36px; font-weight:700; letter-spacing:-0.025em; color:#1d1d1f; margin:0 0 8px;">Your Rebooking Offer</h1>
          <p style="font-size:14px; color:#6e6e73; margin:0;">
            We've cancelled your original flight and found you an alternative. Please review and respond below.
          </p>
        </div>

        <!-- Expiry warning -->
        <div
          v-if="offer.expiryTime && formatExpiry(offer.expiryTime)"
          :style="{
            background: formatExpiry(offer.expiryTime).urgent ? '#fff7ed' : '#fffbeb',
            border: '1px solid ' + (formatExpiry(offer.expiryTime).urgent ? '#fed7aa' : '#fef08a'),
            borderRadius: '14px', padding: '12px 16px',
            display: 'flex', alignItems: 'center', gap: '10px',
            marginBottom: '20px'
          }"
        >
          <svg width="16" height="16" fill="none" stroke="#d97706" stroke-width="2" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
          </svg>
          <p style="font-size:13px; font-weight:600; color:#92400e; margin:0;">
            {{ formatExpiry(offer.expiryTime).text }}
          </p>
        </div>

        <!-- Offer ID + booking ref -->
        <div style="background:white; border:1px solid rgba(0,0,0,0.08); border-radius:20px; padding:20px 24px; margin-bottom:16px; display:flex; gap:28px; flex-wrap:wrap;">
          <div>
            <p style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#6e6e73; margin:0 0 3px;">Offer Reference</p>
            <p style="font-size:15px; font-weight:700; color:#1d1d1f; font-family:monospace; margin:0;">#{{ offer.offerID }}</p>
          </div>
          <div>
            <p style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#6e6e73; margin:0 0 3px;">Original Booking</p>
            <p style="font-size:15px; font-weight:700; color:#1d1d1f; font-family:monospace; margin:0;">#{{ offer.bookingID }}</p>
          </div>
          <div>
            <p style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#6e6e73; margin:0 0 3px;">Passenger</p>
            <p style="font-size:15px; font-weight:700; color:#1d1d1f; margin:0;">{{ currentPassenger?.FirstName }} {{ currentPassenger?.LastName }}</p>
          </div>
        </div>

        <!-- Flight comparison -->
        <!-- ⚠️ MOCK DATA — Flight Service Integration Required -->
        <div style="display:flex; align-items:center; gap:6px; background:#fff0f0; border:1px solid #fca5a5; border-radius:8px; padding:6px 12px; margin-bottom:10px;">
          <svg width="12" height="12" fill="#dc2626" viewBox="0 0 20 20"><path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 4a1 1 0 011 1v3a1 1 0 11-2 0V7a1 1 0 011-1zm0 7a1 1 0 100 2 1 1 0 000-2z"/></svg>
          <span style="font-size:11px; font-weight:700; color:#dc2626; letter-spacing:0.05em;">[ MOCK — Flight details pending Flight Service integration. Replace origFlight &amp; newFlight with GET /flights/{id} ]</span>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">

          <!-- Original flight — cancelled -->
          <div style="background:white; border:1.5px solid #fecaca; border-radius:20px; padding:20px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:14px;">
              <p style="font-size:11px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#6e6e73; margin:0;">Original Flight</p>
              <span style="background:#fef2f2; color:#dc2626; border:1px solid #fecaca; border-radius:100px; padding:3px 10px; font-size:11px; font-weight:700;">Cancelled</span>
            </div>
            <p style="font-size:22px; font-weight:700; color:#1d1d1f; margin:0 0 4px; text-decoration:line-through; opacity:0.5;">{{ origFlight.flightNumber }}</p>
            <p style="font-size:13px; color:#6e6e73; margin:0 0 10px; text-decoration:line-through; opacity:0.5;">{{ formatDate(origFlight.date) }}</p>
            <div style="display:flex; align-items:center; gap:8px; opacity:0.5;">
              <div style="text-align:center;">
                <p style="font-size:18px; font-weight:700; color:#1d1d1f; margin:0;">{{ origFlight.departureTime }}</p>
                <p style="font-size:11px; color:#6e6e73; margin:2px 0 0;">SIN</p>
              </div>
              <div style="flex:1; height:1px; background:#e5e7eb; position:relative;">
                <svg width="14" height="14" fill="#9ca3af" style="position:absolute; right:-2px; top:-7px;" viewBox="0 0 24 24">
                  <path d="M5 12h14M13 6l6 6-6 6"/>
                </svg>
              </div>
              <div style="text-align:center;">
                <p style="font-size:18px; font-weight:700; color:#1d1d1f; margin:0;">{{ origFlight.arrivalTime }}</p>
                <p style="font-size:11px; color:#6e6e73; margin:2px 0 0;">NRT</p>
              </div>
            </div>
          </div>

          <!-- New flight — proposed -->
          <div style="background:white; border:2px solid #86efac; border-radius:20px; padding:20px; position:relative;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:14px;">
              <p style="font-size:11px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#6e6e73; margin:0;">Alternative Flight</p>
              <span style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0; border-radius:100px; padding:3px 10px; font-size:11px; font-weight:700;">✓ Available</span>
            </div>
            <p style="font-size:22px; font-weight:700; color:#1d1d1f; margin:0 0 4px;">{{ newFlight.flightNumber }}</p>
            <p style="font-size:13px; color:#6e6e73; margin:0 0 10px;">{{ formatDate(newFlight.date) }}</p>
            <div style="display:flex; align-items:center; gap:8px;">
              <div style="text-align:center;">
                <p style="font-size:18px; font-weight:700; color:#1d1d1f; margin:0;">{{ newFlight.departureTime }}</p>
                <p style="font-size:11px; color:#6e6e73; margin:2px 0 0;">SIN</p>
              </div>
              <div style="flex:1; height:1px; background:#e5e7eb; position:relative;">
                <svg width="14" height="14" fill="#6b7280" style="position:absolute; right:-2px; top:-7px;" viewBox="0 0 24 24">
                  <path d="M5 12h14M13 6l6 6-6 6"/>
                </svg>
              </div>
              <div style="text-align:center;">
                <p style="font-size:18px; font-weight:700; color:#1d1d1f; margin:0;">{{ newFlight.arrivalTime }}</p>
                <p style="font-size:11px; color:#6e6e73; margin:2px 0 0;">NRT</p>
              </div>
            </div>
            <!-- No fare difference label -->
            <p style="font-size:11px; color:#15803d; font-weight:600; margin:12px 0 0; text-align:center;">
              ✓ No additional charge — fare difference absorbed by airline
            </p>
          </div>

        </div>

        <!-- Coupon code -->
        <div v-if="offer.couponID"
          style="background:white; border:1px solid rgba(0,0,0,0.08); border-radius:20px; padding:20px 24px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;">
          <div style="display:flex; align-items:center; gap:14px;">
            <div style="width:40px; height:40px; background:#fef9c3; border-radius:12px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
              <svg width="20" height="20" fill="none" stroke="#ca8a04" stroke-width="2" viewBox="0 0 24 24">
                <path d="M7 7h.01M17 17h.01M7.5 17.5l9-9M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div>
              <p style="font-size:12px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#6e6e73; margin:0 0 3px;">Compensation Coupon</p>
              <p style="font-size:13px; color:#6e6e73; margin:0;">As an apology for the inconvenience, please enjoy this discount on your next booking.</p>
            </div>
          </div>
          <div style="background:#fefce8; border:1.5px dashed #fde047; border-radius:12px; padding:10px 20px; text-align:center; flex-shrink:0;">
            <p style="font-size:11px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#a16207; margin:0 0 2px;">Coupon Code</p>
            <p style="font-size:18px; font-weight:800; font-family:monospace; color:#1d1d1f; margin:0; letter-spacing:0.05em;">{{ couponCode || 'COUPON-' + offer.couponID }}</p>
            <p v-if="!couponCode" style="font-size:10px; color:#a16207; margin:4px 0 0; font-weight:600;">Full code available once Coupon Service is ready</p>
          </div>
        </div>

        <!-- What happens section -->
        <div style="background:white; border:1px solid rgba(0,0,0,0.08); border-radius:20px; padding:20px 24px; margin-bottom:24px;">
          <p style="font-size:12px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#6e6e73; margin:0 0 16px;">What happens when you...</p>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
            <div style="padding:16px; background:#fef2f2; border-radius:14px; border:1px solid #fecaca;">
              <p style="font-size:13px; font-weight:700; color:#dc2626; margin:0 0 6px;">✗ Reject</p>
              <p style="font-size:12px; color:#991b1b; margin:0; line-height:1.6;">Your original booking will be cancelled and a full refund will be issued to your original payment method within 5–10 business days.</p>
            </div>
            <div style="padding:16px; background:#f0fdf4; border-radius:14px; border:1px solid #bbf7d0;">
              <p style="font-size:13px; font-weight:700; color:#15803d; margin:0 0 6px;">✓ Accept</p>
              <p style="font-size:12px; color:#166534; margin:0; line-height:1.6;">You'll be confirmed on the alternative flight at no extra charge. A new booking confirmation will be emailed to you.</p>
            </div>
          </div>
        </div>

        <!-- Error inline -->
        <div v-if="error"
          style="background:#fef2f2; border:1px solid #fecaca; border-radius:14px; padding:14px 18px; margin-bottom:16px; font-size:13px; color:#dc2626;">
          {{ error }}
        </div>

        <!-- CTA buttons -->
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
          <button
            @click="showConfirm = 'reject'"
            :disabled="submitting"
            style="padding:16px; border-radius:16px; border:2px solid #fecaca; background:#fef2f2; font-size:15px; font-weight:700; color:#dc2626; cursor:pointer; transition:all 0.2s;"
            onmouseover="this.style.background='#fee2e2'; this.style.borderColor='#fca5a5'"
            onmouseout="this.style.background='#fef2f2'; this.style.borderColor='#fecaca'"
          >
            ✗ Reject & Get Refund
          </button>
          <button
            @click="showConfirm = 'accept'"
            :disabled="submitting"
            style="padding:16px; border-radius:16px; border:none; background:#22c55e; font-size:15px; font-weight:700; color:white; cursor:pointer; transition:background 0.2s;"
            onmouseover="this.style.background='#16a34a'"
            onmouseout="this.style.background='#22c55e'"
          >
            <span v-if="submitting" style="display:flex; align-items:center; justify-content:center; gap:8px;">
              <span style="width:16px; height:16px; border:2px solid rgba(255,255,255,0.3); border-top-color:white; border-radius:50%; animation:spin 0.8s linear infinite; display:inline-block;"></span>
              Processing...
            </span>
            <span v-else>✓ Accept Rebooking</span>
          </button>
        </div>

        <p style="text-align:center; font-size:12px; color:#6e6e73; margin-top:16px;">
          By accepting, you agree to the new flight details above. No payment is required.
        </p>

      </template>

      <!-- ── Confirmation modal ──────────────────────────── -->
      <div v-if="showConfirm"
        style="position:fixed; inset:0; background:rgba(0,0,0,0.5); backdrop-filter:blur(4px); display:flex; align-items:center; justify-content:center; z-index:100; padding:24px;">
        <div style="background:white; border-radius:28px; padding:36px 32px; max-width:400px; width:100%; text-align:center; box-shadow:0 32px 64px rgba(0,0,0,0.2);">

          <!-- Accept confirmation -->
          <template v-if="showConfirm === 'accept'">
            <div style="width:56px; height:56px; background:#f0fdf4; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px;">
              <svg width="26" height="26" fill="none" stroke="#22c55e" stroke-width="2.5" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>
            </div>
            <h2 style="font-size:20px; font-weight:700; color:#1d1d1f; margin:0 0 8px;">Confirm Acceptance</h2>
            <p style="font-size:14px; color:#6e6e73; margin:0 0 24px; line-height:1.6;">
              You'll be rebooked onto <strong style="color:#1d1d1f;">{{ newFlight?.flightNumber }}</strong> on {{ formatDate(newFlight?.date) }} at no extra charge.
            </p>
            <div style="display:flex; gap:10px;">
              <button @click="showConfirm = null"
                style="flex:1; padding:12px; border-radius:12px; border:1.5px solid rgba(0,0,0,0.12); background:white; font-size:14px; font-weight:600; color:#6e6e73; cursor:pointer;">
                Go Back
              </button>
              <button @click="acceptOffer"
                style="flex:1; padding:12px; border-radius:12px; border:none; background:#1d1d1f; font-size:14px; font-weight:600; color:white; cursor:pointer;">
                Yes, Accept
              </button>
            </div>
          </template>

          <!-- Reject confirmation -->
          <template v-else-if="showConfirm === 'reject'">
            <div style="width:56px; height:56px; background:#fef2f2; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px;">
              <svg width="26" height="26" fill="none" stroke="#ef4444" stroke-width="2" viewBox="0 0 24 24"><path d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>
            </div>
            <h2 style="font-size:20px; font-weight:700; color:#1d1d1f; margin:0 0 8px;">Confirm Rejection</h2>
            <p style="font-size:14px; color:#6e6e73; margin:0 0 24px; line-height:1.6;">
              Your booking will be <strong style="color:#1d1d1f;">cancelled</strong> and you'll receive a <strong style="color:#1d1d1f;">full refund</strong> within 5–10 business days.
            </p>
            <div style="display:flex; gap:10px;">
              <button @click="showConfirm = null"
                style="flex:1; padding:12px; border-radius:12px; border:1.5px solid rgba(0,0,0,0.12); background:white; font-size:14px; font-weight:600; color:#6e6e73; cursor:pointer;">
                Go Back
              </button>
              <button @click="rejectOffer"
                style="flex:1; padding:12px; border-radius:12px; border:none; background:#e63946; font-size:14px; font-weight:600; color:white; cursor:pointer;">
                Yes, Get Refund
              </button>
            </div>
          </template>

        </div>
      </div>

    </div>
  </main>
  </div>
</template>

<style scoped>
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>