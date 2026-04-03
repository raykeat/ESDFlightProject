<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { apiUrl } from '../config/api'

const router = useRouter()

const flights         = ref([])
const loading         = ref(true)
const error           = ref(null)
const filterStatus    = ref('Available')
const searchQuery     = ref('')
const landingStatusByFlightId = ref({})
const showLandModal   = ref(false)
const selectedLandingFlight = ref(null)
const showCancelModal = ref(false)
const selectedFlight  = ref(null)
const cancelReason    = ref('')
const cancelling      = ref(false)
const cancelError     = ref('')
const cancelSuccess   = ref(null)
const staffSession    = ref(null)
const affectedPassengersCount = ref(0)
const countingAffectedPassengers = ref(false)
const affectedPassengersByFlightId = ref({})

const STATUS_FILTERS = ['Available', 'Unavailable', 'Landed', 'Cancelled']

onMounted(async () => {
  const session = sessionStorage.getItem('staffSession')
  if (!session) { router.push('/staff/login'); return }
  staffSession.value = JSON.parse(session)
  await loadFlights()
})

async function loadFlights() {
  loading.value = true
  error.value   = null
  try {
    let response

    try {
      response = await axios.get(apiUrl('/api/flights'))
    } catch (primaryError) {
      console.warn('Primary flights endpoint unavailable, falling back to available flights endpoint.', primaryError)
      response = await axios.get(apiUrl('/api/flight/available'))
    }

    flights.value = Array.isArray(response.data)
      ? response.data
      : Array.isArray(response.data?.flights)
        ? response.data.flights
        : []

    await loadAffectedPassengersForFlights(flights.value)
  } catch (err) {
    error.value = 'Could not load flights. Please try again.'
  } finally {
    loading.value = false
  }
}

async function fetchAffectedPassengersCount(flightID) {
  if (!flightID) return 0

  const response = await axios.get(apiUrl('/api/records'), {
    params: {
      FlightID: flightID,
      bookingstatus: 'Confirmed',
    },
  })

  let records = response.data

  if (typeof records === 'string') {
    try {
      records = JSON.parse(records)
    } catch (parseError) {
      console.warn('Could not parse affected passengers response.', parseError)
      return 0
    }
  }

  return Array.isArray(records) ? records.length : 0
}

async function loadAffectedPassengersForFlights(flightList) {
  const uniqueFlightIds = [...new Set((flightList || []).map(flight => flight?.FlightID).filter(Boolean))]

  if (uniqueFlightIds.length === 0) {
    affectedPassengersByFlightId.value = {}
    return
  }

  const results = await Promise.allSettled(
    uniqueFlightIds.map(async (flightID) => ({
      flightID,
      count: await fetchAffectedPassengersCount(flightID),
    }))
  )

  const nextCounts = {}

  results.forEach((result) => {
    if (result.status === 'fulfilled') {
      nextCounts[result.value.flightID] = result.value.count
    }
  })

  affectedPassengersByFlightId.value = nextCounts
}

const filteredFlights = computed(() => {
  let result = flights.value
  if (filterStatus.value !== 'All')
    result = result.filter(f => f.Status?.toLowerCase() === filterStatus.value.toLowerCase())
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    result = result.filter(f =>
      f.FlightNumber?.toLowerCase().includes(q) ||
      f.Origin?.toLowerCase().includes(q) ||
      f.Destination?.toLowerCase().includes(q) ||
      String(f.FlightID).includes(q)
    )
  }
  return result
})

function countByStatus(status) {
  if (status === 'All') return flights.value.length
  return flights.value.filter(f => f.Status?.toLowerCase() === status.toLowerCase()).length
}

function openCancelModal(flight) {
  selectedFlight.value  = flight
  cancelReason.value    = ''
  cancelError.value     = ''
  cancelSuccess.value   = null
  affectedPassengersCount.value = 0
  showCancelModal.value = true
  loadAffectedPassengers(flight)
}

function openLandModal(flight) {
  selectedLandingFlight.value = flight
  showLandModal.value = true
}

function closeLandModal() {
  showLandModal.value = false
  selectedLandingFlight.value = null
}

function closeCancelModal() {
  showCancelModal.value = false
  selectedFlight.value  = null
  cancelReason.value    = ''
  cancelError.value     = ''
  affectedPassengersCount.value = 0
  countingAffectedPassengers.value = false
}

async function loadAffectedPassengers(flight) {
  if (!flight?.FlightID) return

  countingAffectedPassengers.value = true
  try {
    const count = await fetchAffectedPassengersCount(flight.FlightID)
    affectedPassengersCount.value = count
    affectedPassengersByFlightId.value = {
      ...affectedPassengersByFlightId.value,
      [flight.FlightID]: count,
    }
  } catch (err) {
    console.warn('Could not load affected passengers count.', err)
    affectedPassengersCount.value = 0
  } finally {
    countingAffectedPassengers.value = false
  }
}

function affectedCountForFlight(flightID) {
  return affectedPassengersByFlightId.value[flightID] ?? 0
}

async function confirmCancellation() {
  if (!cancelReason.value.trim()) { cancelError.value = 'Please enter a cancellation reason.'; return }
  cancelling.value  = true
  cancelError.value = ''
  try {
    const res = await axios.post(apiUrl('/api/cancel'), {
      flightID:           selectedFlight.value.FlightID,
      cancellationReason: cancelReason.value.trim()
    })
    cancelSuccess.value = res.data
    const idx = flights.value.findIndex(f => f.FlightID === selectedFlight.value.FlightID)
    if (idx !== -1) flights.value[idx].Status = 'cancelled'
  } catch (err) {
    cancelError.value = err.response?.data?.message || 'Cancellation failed. Please try again.'
  } finally {
    cancelling.value = false
  }
}

async function markFlightAsLanded(flight) {
  const flightID = flight?.FlightID
  if (!flightID) return

  landingStatusByFlightId.value = {
    ...landingStatusByFlightId.value,
    [flightID]: true,
  }

  try {
    await axios.put(`http://localhost:3003/flight/${flightID}/landed`)
    const idx = flights.value.findIndex(f => f.FlightID === flightID)
    if (idx !== -1) flights.value[idx].Status = 'landed'
  } catch (err) {
    const message = err.response?.data?.message || 'Failed to mark flight as landed.'
    window.alert(message)
  } finally {
    landingStatusByFlightId.value = {
      ...landingStatusByFlightId.value,
      [flightID]: false,
    }
  }
}

async function confirmMarkFlightAsLanded() {
  const flight = selectedLandingFlight.value
  if (!flight?.FlightID) return

  showLandModal.value = false
  await markFlightAsLanded(flight)
  selectedLandingFlight.value = null
}

function logout() {
  sessionStorage.removeItem('staffSession')
  router.push('/staff/login')
}

function statusStyle(status) {
  const s = status?.toLowerCase()
  if (s === 'available')   return { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0', dot: '#22c55e' }
  if (s === 'unavailable') return { bg: '#fefce8', color: '#a16207', border: '#fef08a', dot: '#eab308' }
  if (s === 'landed')      return { bg: '#ecfeff', color: '#0e7490', border: '#a5f3fc', dot: '#06b6d4' }
  if (s === 'cancelled')   return { bg: '#fef2f2', color: '#dc2626', border: '#fecaca', dot: '#ef4444' }
  return                          { bg: '#f9fafb', color: '#6b7280', border: '#e5e7eb', dot: '#9ca3af' }
}
</script>

<template>
  <main style="min-height:100vh; background:#f0f2f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">

    <!-- ── Top Navigation ─────────────────────────────────── -->
    <header style="background:#0f172a; position:sticky; top:0; z-index:50; border-bottom:1px solid rgba(255,255,255,0.06);">
      <div style="max-width:1200px; margin:0 auto; padding:0 32px; height:64px; display:flex; align-items:center; justify-content:space-between;">

        <!-- Left: brand -->
        <div style="display:flex; align-items:center; gap:16px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <rect width="28" height="28" rx="8" fill="#e63946"/>
              <path d="M14 6l2.5 5.5H22l-4.5 3.5 1.5 5.5L14 17l-5 3.5 1.5-5.5L6 11.5h5.5L14 6z" fill="white"/>
            </svg>
            <span style="font-size:15px; font-weight:800; letter-spacing:0.15em; color:white;">BLAZE AIR</span>
          </div>
          <div style="width:1px; height:20px; background:rgba(255,255,255,0.15);"></div>
          <span style="font-size:12px; font-weight:600; letter-spacing:0.1em; text-transform:uppercase; color:rgba(255,255,255,0.5);">Operations</span>
        </div>

        <!-- Right: staff info + logout -->
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="display:flex; align-items:center; gap:8px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.1); border-radius:100px; padding:6px 14px 6px 8px;">
            <div style="width:28px; height:28px; background:#e63946; border-radius:50%; display:flex; align-items:center; justify-content:center;">
              <svg width="14" height="14" fill="none" stroke="white" stroke-width="2" viewBox="0 0 24 24">
                <path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/>
              </svg>
            </div>
            <span style="font-size:13px; font-weight:500; color:rgba(255,255,255,0.85);">{{ staffSession?.name }}</span>
          </div>
          <button @click="logout"
            style="display:flex; align-items:center; gap:6px; font-size:12px; font-weight:600; color:rgba(255,255,255,0.5); background:transparent; border:1px solid rgba(255,255,255,0.12); border-radius:8px; padding:7px 14px; cursor:pointer; transition:all 0.2s; letter-spacing:0.04em;"
            onmouseover="this.style.color='white'; this.style.borderColor='rgba(255,255,255,0.3)'"
            onmouseout="this.style.color='rgba(255,255,255,0.5)'; this.style.borderColor='rgba(255,255,255,0.12)'"
          >
            <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>
            </svg>
            Sign Out
          </button>
        </div>
      </div>
    </header>

    <!-- ── Sub-header: page title + stats ────────────────── -->
    <div style="background:#1e293b; border-bottom:1px solid rgba(255,255,255,0.05);">
      <div style="max-width:1200px; margin:0 auto; padding:24px 32px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:20px;">
        <div>
          <p style="font-size:11px; font-weight:600; letter-spacing:0.15em; text-transform:uppercase; color:rgba(255,255,255,0.4); margin:0 0 4px;">Flight Operations</p>
          <h1 style="font-size:26px; font-weight:700; color:white; margin:0; letter-spacing:-0.02em;">Flight Management</h1>
        </div>
        <!-- Stat pills -->
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <div v-for="s in [{label:'Total', key:'All', color:'#60a5fa'}, {label:'Available', key:'Available', color:'#4ade80'}, {label:'Landed', key:'Landed', color:'#22d3ee'}, {label:'Cancelled', key:'Cancelled', color:'#f87171'}]" :key="s.key"
            style="background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.1); border-radius:12px; padding:10px 16px; text-align:center; min-width:70px;">
            <p :style="{fontSize:'20px', fontWeight:'800', color:s.color, margin:'0 0 2px', lineHeight:'1'}">{{ countByStatus(s.key) }}</p>
            <p style="font-size:10px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:rgba(255,255,255,0.4); margin:0;">{{ s.label }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Main content ───────────────────────────────────── -->
    <div style="max-width:1200px; margin:0 auto; padding:28px 32px;">

      <!-- Toolbar: search + filters + refresh -->
      <div style="background:white; border-radius:16px; border:1px solid rgba(0,0,0,0.07); padding:16px 20px; margin-bottom:16px; display:flex; flex-wrap:wrap; gap:12px; align-items:center; box-shadow:0 1px 4px rgba(0,0,0,0.04);">
        <!-- Search -->
        <div style="position:relative; flex:1; min-width:220px;">
          <svg width="15" height="15" fill="none" stroke="#9ca3af" stroke-width="2" viewBox="0 0 24 24"
            style="position:absolute; left:13px; top:50%; transform:translateY(-50%);">
            <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
          </svg>
          <input v-model="searchQuery" placeholder="Search flight number, origin, destination..."
            style="width:100%; box-sizing:border-box; padding:10px 14px 10px 38px; border:1.5px solid #e5e7eb; border-radius:10px; font-size:13px; outline:none; background:#f9fafb; color:#1d1d1f; transition:all 0.2s;"
            onfocus="this.style.borderColor='#0f172a'; this.style.background='white'"
            onblur="this.style.borderColor='#e5e7eb'; this.style.background='#f9fafb'"
          />
        </div>

        <!-- Status filters -->
        <div style="display:flex; gap:6px; flex-wrap:wrap;">
          <button v-for="status in STATUS_FILTERS" :key="status"
            @click="filterStatus = status"
            :style="{
              padding:'7px 14px', borderRadius:'8px', fontSize:'12px', fontWeight:'600',
              cursor:'pointer', border:'1.5px solid', transition:'all 0.15s', letterSpacing:'0.03em',
              background: filterStatus === status ? '#0f172a' : 'transparent',
              color: filterStatus === status ? 'white' : '#6b7280',
              borderColor: filterStatus === status ? '#0f172a' : '#e5e7eb',
            }"
          >{{ status }} <span :style="{ opacity: filterStatus === status ? 0.6 : 0.8 }">{{ countByStatus(status) }}</span></button>
        </div>

        <!-- Refresh -->
        <button @click="loadFlights"
          style="display:flex; align-items:center; gap:6px; padding:9px 16px; background:#f9fafb; border:1.5px solid #e5e7eb; border-radius:10px; font-size:12px; font-weight:600; color:#374151; cursor:pointer; transition:all 0.2s; white-space:nowrap;"
          onmouseover="this.style.borderColor='#0f172a'; this.style.color='#0f172a'"
          onmouseout="this.style.borderColor='#e5e7eb'; this.style.color='#374151'"
        >
          <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Refresh
        </button>
      </div>

      <!-- Loading skeletons -->
      <div v-if="loading" style="display:flex; flex-direction:column; gap:2px;">
        <div v-for="i in 5" :key="i"
          style="height:64px; background:white; border-radius:4px; animation:pulse 1.5s ease-in-out infinite; opacity:0.7;">
        </div>
      </div>

      <!-- Error state -->
      <div v-else-if="error"
        style="background:white; border:1px solid #fecaca; border-radius:16px; padding:40px; text-align:center;">
        <svg width="40" height="40" fill="none" stroke="#ef4444" stroke-width="1.5" viewBox="0 0 24 24" style="margin:0 auto 12px; display:block;">
          <circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/>
        </svg>
        <p style="font-size:15px; font-weight:600; color:#1d1d1f; margin:0 0 6px;">{{ error }}</p>
        <button @click="loadFlights"
          style="background:#0f172a; color:white; border:none; border-radius:10px; padding:9px 22px; font-size:13px; font-weight:600; cursor:pointer; margin-top:8px;">
          Try Again
        </button>
      </div>

      <!-- Empty state -->
      <div v-else-if="filteredFlights.length === 0"
        style="background:white; border:1px solid rgba(0,0,0,0.07); border-radius:16px; padding:60px; text-align:center;">
        <svg width="40" height="40" fill="none" stroke="#9ca3af" stroke-width="1.5" viewBox="0 0 24 24" style="margin:0 auto 12px; display:block;">
          <path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
        </svg>
        <p style="font-size:15px; font-weight:600; color:#1d1d1f; margin:0 0 4px;">No flights found</p>
        <p style="font-size:13px; color:#9ca3af; margin:0;">Try a different filter or search term</p>
      </div>

      <!-- Flights table -->
      <div v-else style="background:white; border:1px solid rgba(0,0,0,0.07); border-radius:16px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,0.04);">

        <!-- Table header -->
        <div style="display:grid; grid-template-columns:70px 120px 1fr 1fr 110px 100px 120px 110px 120px; padding:12px 24px; background:#f8fafc; border-bottom:1.5px solid #e2e8f0;">
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#94a3b8;">ID</span>
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#94a3b8;">Flight</span>
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#94a3b8;">From</span>
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#94a3b8;">To</span>
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#94a3b8;">Date</span>
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#94a3b8;">Departs</span>
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#94a3b8;">Affected</span>
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#94a3b8;">Status</span>
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#94a3b8;">Action</span>
        </div>

        <!-- Rows -->
        <div v-for="(flight, idx) in filteredFlights" :key="flight.FlightID"
          :style="{
            display:'grid', gridTemplateColumns:'70px 120px 1fr 1fr 110px 100px 120px 110px 120px',
            padding:'16px 24px', alignItems:'center',
            borderBottom: idx < filteredFlights.length - 1 ? '1px solid #f1f5f9' : 'none',
            background: flight.Status?.toLowerCase() === 'cancelled' ? '#fafafa' : 'white',
            transition:'background 0.15s',
            opacity: flight.Status?.toLowerCase() === 'cancelled' ? '0.75' : '1',
          }"
          onmouseover="this.style.background='#f8fafc'"
          onmouseout="this.style.background = this.dataset.cancelled === 'true' ? '#fafafa' : 'white'"
          :data-cancelled="flight.Status?.toLowerCase() === 'cancelled'"
        >
          <!-- ID -->
          <span style="font-size:12px; font-family:monospace; color:#94a3b8; font-weight:500;">#{{ flight.FlightID }}</span>

          <!-- Flight number -->
          <div style="display:flex; align-items:center; gap:8px;">
            <div style="width:30px; height:30px; background:#f1f5f9; border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
              <svg width="14" height="14" fill="#64748b" viewBox="0 0 24 24"><path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
            </div>
            <span style="font-size:14px; font-weight:700; color:#0f172a; letter-spacing:0.02em;">{{ flight.FlightNumber }}</span>
          </div>

          <!-- Origin -->
          <div>
            <p style="font-size:13px; font-weight:500; color:#1e293b; margin:0;">{{ flight.Origin }}</p>
          </div>

          <!-- Destination -->
          <div>
            <p style="font-size:13px; font-weight:500; color:#1e293b; margin:0;">{{ flight.Destination }}</p>
          </div>

          <!-- Date -->
          <span style="font-size:12px; color:#64748b; font-weight:500;">{{ flight.Date }}</span>

          <!-- Departure time -->
          <span style="font-size:14px; font-weight:600; color:#1e293b;">{{ flight.DepartureTime }}</span>

          <!-- Affected passengers -->
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="min-width:30px; font-size:16px; font-weight:800; color:#0f172a; line-height:1;">
              {{ affectedCountForFlight(flight.FlightID) }}
            </span>
            <span style="font-size:11px; color:#94a3b8; line-height:1.3;">
              confirmed<br>passengers
            </span>
          </div>

          <!-- Status badge -->
          <div :style="{
            display:'inline-flex', alignItems:'center', gap:'5px',
            background: statusStyle(flight.Status).bg,
            color: statusStyle(flight.Status).color,
            border: '1px solid ' + statusStyle(flight.Status).border,
            borderRadius:'6px', padding:'4px 10px',
            fontSize:'11px', fontWeight:'700', letterSpacing:'0.04em', width:'fit-content'
          }">
            <span :style="{ width:'5px', height:'5px', borderRadius:'50%', background:statusStyle(flight.Status).dot, flexShrink:0 }"></span>
            {{ flight.Status?.charAt(0).toUpperCase() + flight.Status?.slice(1).toLowerCase() }}
          </div>

          <!-- Action -->
          <div style="display:flex; gap:8px; align-items:center;">
            <button
              v-if="flight.Status?.toLowerCase() !== 'cancelled' && flight.Status?.toLowerCase() !== 'landed'"
              @click="openLandModal(flight)"
              :disabled="Boolean(landingStatusByFlightId[flight.FlightID])"
              style="display:flex; align-items:center; gap:5px; background:white; color:#0e7490; border:1.5px solid #a5f3fc; border-radius:8px; padding:6px 10px; font-size:12px; font-weight:600; cursor:pointer; transition:all 0.2s; letter-spacing:0.02em;"
              onmouseover="this.style.background='#ecfeff'; this.style.borderColor='#22d3ee'"
              onmouseout="this.style.background='white'; this.style.borderColor='#a5f3fc'"
            >
              <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path d="M20 6L9 17l-5-5"/>
              </svg>
              {{ landingStatusByFlightId[flight.FlightID] ? 'Updating...' : 'Mark Landed' }}
            </button>

            <button v-if="flight.Status?.toLowerCase() !== 'cancelled' && flight.Status?.toLowerCase() !== 'landed'"
              @click="openCancelModal(flight)"
              style="display:flex; align-items:center; gap:5px; background:white; color:#dc2626; border:1.5px solid #fecaca; border-radius:8px; padding:6px 10px; font-size:12px; font-weight:600; cursor:pointer; transition:all 0.2s; letter-spacing:0.02em;"
              onmouseover="this.style.background='#fef2f2'; this.style.borderColor='#ef4444'"
              onmouseout="this.style.background='white'; this.style.borderColor='#fecaca'"
            >
              <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
              Cancel
            </button>

            <span v-if="flight.Status?.toLowerCase() === 'landed'" style="font-size:11px; color:#0891b2; font-style:italic;">Landed</span>
            <span v-else-if="flight.Status?.toLowerCase() === 'cancelled'" style="font-size:11px; color:#cbd5e1; font-style:italic;">—</span>
          </div>
        </div>

        <!-- Table footer -->
        <div style="padding:12px 24px; background:#f8fafc; border-top:1px solid #e2e8f0;">
          <p style="font-size:12px; color:#94a3b8; margin:0;">
            Showing <strong style="color:#64748b;">{{ filteredFlights.length }}</strong> of <strong style="color:#64748b;">{{ flights.length }}</strong> flights
          </p>
        </div>

      </div>
    </div>

    <!-- ── Land Confirmation Modal ───────────────────────── -->
    <div v-if="showLandModal"
      style="position:fixed; inset:0; background:rgba(15,23,42,0.65); backdrop-filter:blur(6px); display:flex; align-items:center; justify-content:center; z-index:100; padding:24px;"
      @click.self="closeLandModal">

      <div style="background:white; border-radius:24px; max-width:520px; width:100%; box-shadow:0 40px 80px rgba(0,0,0,0.3); overflow:hidden;">
        <div style="height:4px; background:linear-gradient(90deg,#0e7490,#06b6d4);"></div>

        <div style="padding:28px 32px 24px;">
          <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:18px;">
            <div style="display:flex; align-items:center; gap:14px;">
              <div style="width:48px; height:48px; background:#ecfeff; border:1px solid #a5f3fc; border-radius:14px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                <svg width="22" height="22" fill="none" stroke="#0e7490" stroke-width="2" viewBox="0 0 24 24">
                  <path d="M20 6L9 17l-5-5"/>
                </svg>
              </div>
              <div>
                <h2 style="font-size:19px; font-weight:700; color:#0f172a; margin:0 0 3px;">Mark flight as landed?</h2>
                <p style="font-size:13px; color:#64748b; margin:0; line-height:1.5;">Passengers will see this flight as completed in My Bookings and miles will be released for eligible bookings.</p>
              </div>
            </div>
            <button @click="closeLandModal"
              style="width:32px; height:32px; background:#f1f5f9; border:none; border-radius:8px; display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; transition:background 0.15s;"
              onmouseover="this.style.background='#e2e8f0'"
              onmouseout="this.style.background='#f1f5f9'"
            >
              <svg width="13" height="13" fill="none" stroke="#64748b" stroke-width="2.5" viewBox="0 0 24 24">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:16px; padding:18px 20px; margin-bottom:16px;">
            <p style="font-size:11px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#64748b; margin:0 0 10px;">Flight details</p>
            <p style="font-size:18px; font-weight:800; color:#0f172a; margin:0 0 6px;">{{ selectedLandingFlight?.FlightNumber || '—' }}</p>
            <p style="font-size:13px; color:#475569; margin:0;">{{ selectedLandingFlight?.Origin }} to {{ selectedLandingFlight?.Destination }}</p>
            <p style="font-size:12px; color:#64748b; margin:8px 0 0;">{{ selectedLandingFlight?.Date }} · {{ selectedLandingFlight?.DepartureTime }} - {{ selectedLandingFlight?.ArrivalTime }}</p>
          </div>

          <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:12px; padding:12px 14px;">
            <div>
              <p style="font-size:11px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#166534; margin:0 0 4px;">Confirmation</p>
              <p style="font-size:13px; color:#14532d; margin:0;">This action can be reversed only by updating the flight status again.</p>
            </div>
            <div style="font-size:24px; font-weight:800; color:#16a34a; line-height:1;">Landed</div>
          </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; border-top:1px solid #f1f5f9;">
          <button @click="closeLandModal"
            style="padding:16px; border:none; background:white; font-size:14px; font-weight:600; color:#64748b; cursor:pointer; transition:all 0.2s; border-radius:0 0 0 24px; letter-spacing:0.02em;"
            onmouseover="this.style.background='#f8fafc'; this.style.color='#0f172a'"
            onmouseout="this.style.background='white'; this.style.color='#64748b'"
          >Keep Scheduled</button>
          <button @click="confirmMarkFlightAsLanded"
            style="padding:16px; border:none; background:#0e7490; font-size:14px; font-weight:700; color:white; cursor:pointer; transition:background 0.2s; border-radius:0 0 24px 0; letter-spacing:0.02em;"
            onmouseover="this.style.background='#155e75'"
            onmouseout="this.style.background='#0e7490'"
          >Mark Landed</button>
        </div>
      </div>
    </div>

    <!-- ── Cancel Modal ───────────────────────────────────── -->
    <div v-if="showCancelModal"
      style="position:fixed; inset:0; background:rgba(15,23,42,0.65); backdrop-filter:blur(6px); display:flex; align-items:center; justify-content:center; z-index:100; padding:24px;"
      @click.self="closeCancelModal">

      <div style="background:white; border-radius:24px; max-width:500px; width:100%; box-shadow:0 40px 80px rgba(0,0,0,0.3); overflow:hidden;">

        <!-- Success -->
        <div v-if="cancelSuccess" style="padding:44px 36px; text-align:center;">
          <div style="width:72px; height:72px; background:linear-gradient(135deg,#f0fdf4,#dcfce7); border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 20px; box-shadow:0 8px 24px rgba(34,197,94,0.2);">
            <svg width="32" height="32" fill="none" stroke="#16a34a" stroke-width="2.5" viewBox="0 0 24 24">
              <path d="M5 13l4 4L19 7"/>
            </svg>
          </div>
          <h2 style="font-size:22px; font-weight:700; color:#0f172a; margin:0 0 8px;">Flight Cancelled</h2>
          <p style="font-size:14px; color:#64748b; margin:0 0 24px; line-height:1.6;">
            <strong style="color:#0f172a;">{{ cancelSuccess.flightNumber }}</strong> All affected passengers will be notified automatically.
          </p>
          <div style="display:flex; gap:10px; justify-content:center; margin-bottom:24px;">
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:12px 20px; text-align:center; flex:1;">
              <p style="font-size:28px; font-weight:800; color:#0f172a; margin:0; line-height:1;">{{ Math.max(cancelSuccess.PassengersAffected || 0, affectedPassengersCount) }}</p>
              <p style="font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#94a3b8; margin:6px 0 0;">Passengers Affected</p>
            </div>
          </div>
          <button @click="closeCancelModal"
            style="width:100%; padding:13px; background:#0f172a; color:white; border:none; border-radius:14px; font-size:14px; font-weight:700; cursor:pointer; transition:background 0.2s; letter-spacing:0.04em;"
            onmouseover="this.style.background='#1e293b'"
            onmouseout="this.style.background='#0f172a'"
          >Done</button>
        </div>

        <!-- Confirm -->
        <div v-else>
          <!-- Red top bar -->
          <div style="height:4px; background:linear-gradient(90deg,#dc2626,#ef4444);"></div>

          <div style="padding:28px 32px 0;">
            <!-- Header row -->
            <div style="display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:22px;">
              <div style="display:flex; align-items:center; gap:14px;">
                <div style="width:48px; height:48px; background:#fef2f2; border:1px solid #fecaca; border-radius:14px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                  <svg width="22" height="22" fill="none" stroke="#dc2626" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                  </svg>
                </div>
                <div>
                  <h2 style="font-size:19px; font-weight:700; color:#0f172a; margin:0 0 3px;">Cancel Flight</h2>
                  <p style="font-size:13px; color:#94a3b8; margin:0;">This will notify all affected passengers</p>
                </div>
              </div>
              <button @click="closeCancelModal"
                style="width:32px; height:32px; background:#f1f5f9; border:none; border-radius:8px; display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; transition:background 0.15s;"
                onmouseover="this.style.background='#e2e8f0'"
                onmouseout="this.style.background='#f1f5f9'"
              >
                <svg width="13" height="13" fill="none" stroke="#64748b" stroke-width="2.5" viewBox="0 0 24 24">
                  <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>

            <!-- Flight card -->
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:16px; padding:18px 20px; margin-bottom:20px;">
              <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:14px;">
                <div>
                  <p style="font-size:24px; font-weight:800; color:#0f172a; margin:0; letter-spacing:-0.02em;">{{ selectedFlight?.DepartureTime || '—' }}</p>
                  <p style="font-size:12px; font-weight:500; color:#64748b; margin:3px 0 0;">{{ selectedFlight?.Origin }}</p>
                </div>
                <div style="flex:1; display:flex; flex-direction:column; align-items:center; padding:0 14px;">
                  <div style="width:100%; display:flex; align-items:center; gap:4px;">
                    <div style="flex:1; height:1px; background:#cbd5e1;"></div>
                    <div style="width:28px; height:28px; background:white; border:1px solid #e2e8f0; border-radius:50%; display:flex; align-items:center; justify-content:center;">
                      <svg width="13" height="13" fill="#64748b" viewBox="0 0 24 24"><path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
                    </div>
                    <div style="flex:1; height:1px; background:#cbd5e1;"></div>
                  </div>
                </div>
                <div style="text-align:right;">
                  <p style="font-size:24px; font-weight:800; color:#0f172a; margin:0; letter-spacing:-0.02em;">{{ selectedFlight?.ArrivalTime || '—' }}</p>
                  <p style="font-size:12px; font-weight:500; color:#64748b; margin:3px 0 0;">{{ selectedFlight?.Destination }}</p>
                </div>
              </div>
              <div style="display:flex; gap:6px; flex-wrap:wrap; border-top:1px solid #e2e8f0; padding-top:12px;">
                <span style="background:white; border:1px solid #e2e8f0; border-radius:6px; padding:3px 10px; font-size:12px; font-weight:700; color:#0f172a;">{{ selectedFlight?.FlightNumber }}</span>
                <span style="background:white; border:1px solid #e2e8f0; border-radius:6px; padding:3px 10px; font-size:11px; font-weight:500; color:#64748b; font-family:monospace;">ID #{{ selectedFlight?.FlightID }}</span>
                <span style="background:white; border:1px solid #e2e8f0; border-radius:6px; padding:3px 10px; font-size:12px; color:#64748b;">{{ selectedFlight?.Date }}</span>
              </div>
            </div>

            <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; background:#fff7ed; border:1px solid #fed7aa; border-radius:12px; padding:12px 14px; margin-bottom:16px;">
              <div>
                <p style="font-size:11px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#c2410c; margin:0 0 4px;">Affected Passengers</p>
                <p style="font-size:13px; color:#7c2d12; margin:0;">{{ countingAffectedPassengers ? 'Checking confirmed bookings...' : `${affectedPassengersCount} confirmed passenger(s) will be affected.` }}</p>
              </div>
              <div style="font-size:24px; font-weight:800; color:#c2410c; line-height:1;">{{ countingAffectedPassengers ? '...' : affectedPassengersCount }}</div>
            </div>

            <!-- Reason input -->
            <div style="margin-bottom:16px;">
              <label style="display:flex; align-items:center; gap:5px; font-size:11px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#374151; margin-bottom:8px;">
                Cancellation Reason <span style="color:#dc2626;">*</span>
              </label>
              <textarea v-model="cancelReason"
                placeholder="e.g. Severe weather conditions, technical fault, crew unavailability..."
                rows="3"
                style="width:100%; box-sizing:border-box; padding:12px 16px; border:1.5px solid #e5e7eb; border-radius:12px; font-size:13px; color:#1e293b; outline:none; resize:vertical; font-family:inherit; background:#f9fafb; transition:all 0.2s; line-height:1.5;"
                onfocus="this.style.borderColor='#0f172a'; this.style.background='white'"
                onblur="this.style.borderColor='#e5e7eb'; this.style.background='#f9fafb'"
              ></textarea>
            </div>

            <!-- Error -->
            <div v-if="cancelError"
              style="background:#fef2f2; border:1px solid #fecaca; border-radius:10px; padding:10px 14px; margin-bottom:14px; font-size:13px; color:#dc2626; display:flex; align-items:center; gap:8px;">
              <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/></svg>
              {{ cancelError }}
            </div>
          </div>

          <!-- Bottom buttons -->
          <div style="display:grid; grid-template-columns:1fr 1fr; border-top:1px solid #f1f5f9; margin-top:8px;">
            <button @click="closeCancelModal"
              style="padding:16px; border:none; background:white; font-size:14px; font-weight:600; color:#64748b; cursor:pointer; transition:all 0.2s; border-radius:0 0 0 24px; letter-spacing:0.02em;"
              onmouseover="this.style.background='#f8fafc'; this.style.color='#0f172a'"
              onmouseout="this.style.background='white'; this.style.color='#64748b'"
            >Keep Flight</button>
            <button @click="confirmCancellation" :disabled="cancelling"
              style="padding:16px; border:none; background:#dc2626; font-size:14px; font-weight:700; color:white; cursor:pointer; transition:background 0.2s; border-radius:0 0 24px 0; letter-spacing:0.02em;"
              onmouseover="this.style.background='#b91c1c'"
              onmouseout="this.style.background='#dc2626'"
            >
              <span v-if="cancelling" style="display:flex; align-items:center; justify-content:center; gap:8px;">
                <span style="width:14px; height:14px; border:2px solid rgba(255,255,255,0.3); border-top-color:white; border-radius:50%; animation:spin 0.8s linear infinite; display:inline-block;"></span>
                Cancelling...
              </span>
              <span v-else>Confirm Cancellation</span>
            </button>
          </div>
        </div>

      </div>
    </div>

  </main>
</template>

<style scoped>
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
@keyframes spin { to{transform:rotate(360deg)} }
</style>
