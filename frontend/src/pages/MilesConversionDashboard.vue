<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'
import { apiUrl } from '../config/api'

const router = useRouter()
const { currentPassenger, isSignedIn } = usePassengerSession()

const loading = ref(false)
const errorMessage = ref('')
const vouchers = ref([])
const transactions = ref([])

const searchQuery = ref('')
const statusFilter = ref('ALL')
const typeFilter = ref('ALL')
const dateFilter = ref('ALL')

const statusOptions = ['ALL', 'ACTIVE', 'USED', 'EXPIRED']
const typeOptions = ['ALL', 'TRAVEL_CREDIT', 'IN_FLIGHT_PERKS', 'PARTNER_GIFT']

onMounted(async () => {
  if (!isSignedIn.value) {
    router.replace('/auth')
    return
  }
  await loadDashboardData()
})

async function loadDashboardData() {
  loading.value = true
  errorMessage.value = ''

  try {
    const passengerID = currentPassenger.value?.passenger_id
    const [vouchersResponse, transactionsResponse] = await Promise.all([
      axios.get(apiUrl(`/api/loyalty/vouchers/${passengerID}`)),
      axios.get(apiUrl(`/api/loyalty/transactions/${passengerID}?limit=500`)),
    ])

    const vouchersData = Array.isArray(vouchersResponse.data)
      ? vouchersResponse.data
      : (vouchersResponse.data?.vouchers || vouchersResponse.data?.data || [])

    const transactionsData = Array.isArray(transactionsResponse.data)
      ? transactionsResponse.data
      : (transactionsResponse.data?.transactions || transactionsResponse.data?.data || [])

    vouchers.value = Array.isArray(vouchersData) ? vouchersData : []
    transactions.value = Array.isArray(transactionsData) ? transactionsData : []
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
    errorMessage.value = 'Unable to load loyalty dashboard right now. Please try again.'
    vouchers.value = []
    transactions.value = []
  } finally {
    loading.value = false
  }
}

function parseDate(input) {
  const value = new Date(input)
  return Number.isNaN(value.getTime()) ? null : value
}

function formatDateTime(input) {
  const date = parseDate(input)
  if (!date) return 'N/A'

  return new Intl.DateTimeFormat('en-SG', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatDate(input) {
  const date = parseDate(input)
  if (!date) return 'N/A'

  return new Intl.DateTimeFormat('en-SG', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  }).format(date)
}

function getVoucherType(voucher) {
  return voucher?.voucherType || voucher?.type || 'UNKNOWN'
}

function getVoucherCode(voucher) {
  return voucher?.voucherCode || voucher?.code || 'N/A'
}

function getVoucherValue(voucher) {
  const raw = Number(voucher?.voucherValue ?? voucher?.value)
  return Number.isFinite(raw) ? raw : null
}

function getMilesRedeemed(voucher) {
  const miles = Number(voucher?.milesRedeemed)
  return Number.isFinite(miles) ? miles : 0
}

function getCreatedAt(voucher) {
  return voucher?.createdAt || voucher?.created_at || voucher?.issuedAt || null
}

function getTransactionCreatedAt(transaction) {
  return transaction?.createdAt || transaction?.created_at || null
}

function getStatusClass(status) {
  if (status === 'ACTIVE') return 'bg-emerald-100 text-emerald-700'
  if (status === 'USED') return 'bg-gray-100 text-gray-700'
  if (status === 'EXPIRED') return 'bg-red-100 text-red-700'
  return 'bg-blue-100 text-blue-700'
}

function getTypeBadgeClass(type) {
  if (type === 'TRAVEL_CREDIT') return 'bg-[#1d1d1f]/10 text-[#1d1d1f]'
  if (type === 'IN_FLIGHT_PERKS') return 'bg-emerald-100 text-emerald-700'
  if (type === 'PARTNER_GIFT') return 'bg-amber-100 text-amber-800'
  return 'bg-[#f5f5f7] text-[#6e6e73]'
}

function getTypeLabel(type) {
  if (type === 'TRAVEL_CREDIT') return 'Travel Credit'
  if (type === 'IN_FLIGHT_PERKS') return 'In-flight Perks'
  if (type === 'PARTNER_GIFT') return 'Partner Gift'
  return type
}

function formatMoney(value) {
  if (!Number.isFinite(value)) return 'N/A'
  return `$${value.toFixed(2)}`
}

function getNormalizedVoucherDollarValue(voucher) {
  const type = getVoucherType(voucher)
  const miles = getMilesRedeemed(voucher)

  // Keep Travel Credit exact, since it is already cash-style.
  if (type === 'TRAVEL_CREDIT') {
    return getVoucherValue(voucher)
  }

  // For non-cash vouchers, show approximate value using 100 miles ~= $1.
  if (Number.isFinite(miles) && miles > 0) {
    return miles / 100
  }

  return getVoucherValue(voucher)
}

function formatVoucherDisplayValue(voucher) {
  const type = getVoucherType(voucher)
  const normalizedValue = getNormalizedVoucherDollarValue(voucher)

  if (!Number.isFinite(normalizedValue)) {
    return 'N/A'
  }

  if (type === 'TRAVEL_CREDIT') {
    return formatMoney(normalizedValue)
  }

  return `~${formatMoney(normalizedValue)}`
}

function isWithinDateFilterByDate(dateInput) {
  if (dateFilter.value === 'ALL') return true

  const created = parseDate(dateInput)
  if (!created) return false

  const now = new Date()
  const msPerDay = 24 * 60 * 60 * 1000
  const ageInDays = Math.floor((now.getTime() - created.getTime()) / msPerDay)

  if (dateFilter.value === '7D') return ageInDays <= 7
  if (dateFilter.value === '30D') return ageInDays <= 30
  if (dateFilter.value === '90D') return ageInDays <= 90

  return true
}

function getTransactionTypeLabel(type) {
  const normalized = String(type || '').toUpperCase()
  if (normalized === 'EARNED') return 'Miles Earned'
  if (normalized === 'REDEEMED') return 'Miles Redeemed'
  if (normalized === 'ROLLBACK') return 'Rollback'
  return normalized || 'UNKNOWN'
}

function getTransactionTypeClass(type) {
  const normalized = String(type || '').toUpperCase()
  if (normalized === 'EARNED') return 'bg-emerald-100 text-emerald-700'
  if (normalized === 'REDEEMED') return 'bg-amber-100 text-amber-800'
  if (normalized === 'ROLLBACK') return 'bg-gray-100 text-gray-700'
  return 'bg-blue-100 text-blue-700'
}

function formatMiles(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return '0'
  const absolute = Math.abs(parsed).toLocaleString()
  return parsed > 0 ? `+${absolute}` : `-${absolute}`
}

const sortedVouchers = computed(() => {
  return [...vouchers.value].sort((a, b) => {
    const aTime = parseDate(getCreatedAt(a))?.getTime() || 0
    const bTime = parseDate(getCreatedAt(b))?.getTime() || 0
    return bTime - aTime
  })
})

const filteredVouchers = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()

  return sortedVouchers.value.filter((voucher) => {
    const type = getVoucherType(voucher)
    const status = String(voucher?.status || '').toUpperCase()
    const code = getVoucherCode(voucher).toLowerCase()

    const matchesStatus = statusFilter.value === 'ALL' || status === statusFilter.value
    const matchesType = typeFilter.value === 'ALL' || type === typeFilter.value
    const matchesDate = isWithinDateFilterByDate(getCreatedAt(voucher))
    const matchesSearch =
      query.length === 0 ||
      code.includes(query) ||
      type.toLowerCase().includes(query) ||
      String(getMilesRedeemed(voucher)).includes(query)

    return matchesStatus && matchesType && matchesDate && matchesSearch
  })
})

const sortedTransactions = computed(() => {
  return [...transactions.value].sort((a, b) => {
    const aTime = parseDate(getTransactionCreatedAt(a))?.getTime() || 0
    const bTime = parseDate(getTransactionCreatedAt(b))?.getTime() || 0
    return bTime - aTime
  })
})

const earnedFlightTransactions = computed(() => {
  return sortedTransactions.value.filter((transaction) => {
    const type = String(transaction?.transactionType || '').toUpperCase()
    if (type !== 'EARNED') return false

    const reference = String(transaction?.referenceID || '').toUpperCase()
    const description = String(transaction?.description || '').toLowerCase()
    return reference.startsWith('BK-') || description.includes('flight')
  })
})

const filteredEarnedTransactions = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()

  return earnedFlightTransactions.value.filter((transaction) => {
    const description = String(transaction?.description || '').toLowerCase()
    const reference = String(transaction?.referenceID || '').toLowerCase()
    const matchesDate = isWithinDateFilterByDate(getTransactionCreatedAt(transaction))
    const matchesQuery =
      query.length === 0 ||
      description.includes(query) ||
      reference.includes(query) ||
      String(transaction?.milesDelta || '').includes(query)

    return matchesDate && matchesQuery
  })
})

const totalVouchers = computed(() => vouchers.value.length)

const totalMilesConverted = computed(() => {
  return vouchers.value.reduce((sum, voucher) => sum + getMilesRedeemed(voucher), 0)
})

const totalMonetaryValue = computed(() => {
  return vouchers.value.reduce((sum, voucher) => {
    const value = getNormalizedVoucherDollarValue(voucher)
    return sum + (Number.isFinite(value) ? value : 0)
  }, 0)
})

const totalMilesEarnedFromFlights = computed(() => {
  return earnedFlightTransactions.value.reduce((sum, transaction) => {
    const delta = Number(transaction?.milesDelta)
    return sum + (Number.isFinite(delta) && delta > 0 ? delta : 0)
  }, 0)
})

const lastLoyaltyActivityAt = computed(() => {
  const voucherTime = parseDate(sortedVouchers.value[0] ? getCreatedAt(sortedVouchers.value[0]) : null)?.getTime() || 0
  const transactionTime = parseDate(sortedTransactions.value[0] ? getTransactionCreatedAt(sortedTransactions.value[0]) : null)?.getTime() || 0

  const latest = Math.max(voucherTime, transactionTime)
  return latest > 0 ? new Date(latest) : null
})

function goToConvertMiles() {
  router.push('/loyalty/convert')
}

function goToVouchers() {
  router.push('/my-vouchers')
}

function clearFilters() {
  searchQuery.value = ''
  statusFilter.value = 'ALL'
  typeFilter.value = 'ALL'
  dateFilter.value = 'ALL'
}
</script>

<template>
  <main class="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#fdf6f3] via-[#f3f7fb] to-[#eef7f2] px-6 pb-10 pt-8 md:px-10 lg:px-16">
    <div class="pointer-events-none absolute -left-24 top-24 h-72 w-72 rounded-full bg-[#f43f5e]/12 blur-3xl"></div>
    <div class="pointer-events-none absolute right-0 top-0 h-80 w-80 rounded-full bg-[#38bdf8]/12 blur-3xl"></div>
    <div class="pointer-events-none absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-[#22c55e]/10 blur-3xl"></div>
    <section class="mx-auto max-w-[1260px]">
      <div class="animate__animated animate__fadeInUp rounded-[34px] border border-black/5 bg-gradient-to-br from-white/90 via-white/80 to-[#fff1f1]/80 p-8 shadow-[0_22px_52px_rgba(15,23,42,0.08)] backdrop-blur-2xl md:p-10">
        <div class="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.14em] text-[#6e6e73]">Loyalty Analytics</p>
            <h1 class="mt-3 text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">Loyalty Activity Dashboard</h1>
            <p class="mt-3 max-w-2xl text-sm text-[#6e6e73] md:text-base">
              A complete ledger of miles earned from completed flights and miles converted into vouchers.
            </p>
          </div>

          <div class="grid gap-2 sm:grid-cols-2">
            <button
              @click="goToConvertMiles"
              class="rounded-2xl border border-black/10 bg-white px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            >
              Convert Miles
            </button>
            <button
              @click="goToVouchers"
              class="rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:shadow-[0_8px_30px_rgba(230,57,70,0.35)]"
            >
              View Vouchers
            </button>
          </div>
        </div>
      </div>

      <div class="mt-7 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article class="rounded-2xl border border-black/8 bg-gradient-to-br from-white to-[#fff4f4] p-5 shadow-[0_12px_34px_rgba(15,23,42,0.08)]">
          <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Total Conversions</p>
          <p class="mt-3 text-3xl font-semibold text-[#1d1d1f]">{{ totalVouchers.toLocaleString() }}</p>
          <p class="mt-2 text-xs text-[#6e6e73]">All vouchers ever generated by miles redemption.</p>
        </article>

        <article class="rounded-2xl border border-black/8 bg-gradient-to-br from-white to-[#f4f9ff] p-5 shadow-[0_12px_34px_rgba(15,23,42,0.08)]">
          <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Miles Converted</p>
          <p class="mt-3 text-3xl font-semibold text-[#1d1d1f]">{{ totalMilesConverted.toLocaleString() }}</p>
          <p class="mt-2 text-xs text-[#6e6e73]">Cumulative miles moved into voucher rewards.</p>
        </article>

        <article class="rounded-2xl border border-black/8 bg-gradient-to-br from-white to-[#f6f9f6] p-5 shadow-[0_12px_34px_rgba(15,23,42,0.08)]">
          <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Issued Value</p>
          <p class="mt-3 text-3xl font-semibold text-[#1d1d1f]">{{ formatMoney(totalMonetaryValue) }}</p>
          <p class="mt-2 text-xs text-[#6e6e73]">Includes approximate values for non-cash vouchers (100 miles ~= $1).</p>
        </article>

        <article class="rounded-2xl border border-black/8 bg-gradient-to-br from-[#e63946]/5 via-transparent to-[#ff6b6b]/5 p-5 shadow-[0_12px_34px_rgba(15,23,42,0.08)]">
          <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Miles Earned (Flights)</p>
          <p class="mt-3 text-3xl font-semibold text-[#1d1d1f]">{{ totalMilesEarnedFromFlights.toLocaleString() }}</p>
          <p class="mt-2 text-xs text-[#6e6e73]">Latest activity: {{ formatDateTime(lastLoyaltyActivityAt) }}</p>
        </article>
      </div>

      <section class="mt-7 rounded-3xl border border-black/8 bg-gradient-to-br from-white/90 to-[#f7f8fb]/90 p-5 shadow-[0_20px_52px_rgba(15,23,42,0.10)] backdrop-blur md:p-6">
        <div class="grid gap-3 lg:grid-cols-[1.2fr_repeat(3,minmax(0,1fr))_auto]">
          <label class="block">
            <span class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Search</span>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Code, type, miles..."
              class="w-full rounded-xl border border-black/10 bg-[#f5f5f7] px-3 py-2.5 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>

          <label class="block">
            <span class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Status</span>
            <select
              v-model="statusFilter"
              class="w-full rounded-xl border border-black/10 bg-[#f5f5f7] px-3 py-2.5 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            >
              <option v-for="status in statusOptions" :key="status" :value="status">{{ status }}</option>
            </select>
          </label>

          <label class="block">
            <span class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Voucher Type</span>
            <select
              v-model="typeFilter"
              class="w-full rounded-xl border border-black/10 bg-[#f5f5f7] px-3 py-2.5 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            >
              <option v-for="type in typeOptions" :key="type" :value="type">{{ type }}</option>
            </select>
          </label>

          <label class="block">
            <span class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Date Window</span>
            <select
              v-model="dateFilter"
              class="w-full rounded-xl border border-black/10 bg-[#f5f5f7] px-3 py-2.5 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            >
              <option value="ALL">ALL</option>
              <option value="7D">LAST 7 DAYS</option>
              <option value="30D">LAST 30 DAYS</option>
              <option value="90D">LAST 90 DAYS</option>
            </select>
          </label>

          <button
            @click="clearFilters"
            class="self-end rounded-xl border border-black/10 bg-white px-4 py-2.5 text-xs font-semibold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
          >
            Reset
          </button>
        </div>
      </section>

      <section class="mt-6 overflow-hidden rounded-3xl border border-black/8 bg-gradient-to-br from-white/95 to-[#fff7f7]/90 shadow-[0_20px_60px_rgba(15,23,42,0.10)]">
        <div class="border-b border-black/8 bg-gradient-to-r from-[#fff5f5] to-[#fff0f1] px-6 py-4">
          <h2 class="text-lg font-semibold text-[#1d1d1f]">Conversion Transactions</h2>
          <p class="mt-1 text-xs text-[#6e6e73]">Showing {{ filteredVouchers.length }} of {{ vouchers.length }} records</p>
        </div>

        <div v-if="loading" class="px-6 py-16 text-center text-sm text-[#6e6e73]">
          Loading conversion history...
        </div>

        <div v-else-if="errorMessage" class="px-6 py-8">
          <p class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{{ errorMessage }}</p>
        </div>

        <div v-else-if="filteredVouchers.length === 0" class="px-6 py-16 text-center">
          <p class="text-5xl">🧾</p>
          <p class="mt-3 text-lg font-semibold text-[#1d1d1f]">No conversion records match this filter</p>
          <p class="mt-2 text-sm text-[#6e6e73]">Try resetting filters or convert miles to generate your first voucher transaction.</p>
          <button
            @click="goToConvertMiles"
            class="mt-5 rounded-xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-5 py-2.5 text-xs font-semibold uppercase tracking-[0.12em] text-white transition hover:shadow-[0_8px_20px_rgba(230,57,70,0.35)]"
          >
            Convert Miles
          </button>
        </div>

        <div v-else class="overflow-x-auto">
          <table class="min-w-[980px] w-full">
            <thead>
              <tr class="bg-[#f5f5f7] text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">
                <th class="px-6 py-3">Date</th>
                <th class="px-6 py-3">Voucher Code</th>
                <th class="px-6 py-3">Type</th>
                <th class="px-6 py-3">Miles</th>
                <th class="px-6 py-3">Value</th>
                <th class="px-6 py-3">Expiry</th>
                <th class="px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="voucher in filteredVouchers"
                :key="voucher.voucherID || getVoucherCode(voucher)"
                class="border-t border-black/5 text-sm transition hover:bg-[#fff8f8]"
              >
                <td class="px-6 py-4 font-medium text-[#1d1d1f]">{{ formatDateTime(getCreatedAt(voucher)) }}</td>
                <td class="px-6 py-4 font-mono text-xs text-[#1d1d1f]">{{ getVoucherCode(voucher) }}</td>
                <td class="px-6 py-4">
                  <span :class="['inline-flex rounded-lg px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.1em]', getTypeBadgeClass(getVoucherType(voucher))]">
                    {{ getTypeLabel(getVoucherType(voucher)) }}
                  </span>
                </td>
                <td class="px-6 py-4 font-semibold text-[#1d1d1f]">{{ getMilesRedeemed(voucher).toLocaleString() }}</td>
                <td class="px-6 py-4 font-semibold text-[#1d1d1f]">{{ formatVoucherDisplayValue(voucher) }}</td>
                <td class="px-6 py-4 text-[#6e6e73]">{{ formatDate(voucher.expiryDate) }}</td>
                <td class="px-6 py-4">
                  <span :class="['inline-flex rounded-lg px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.1em]', getStatusClass(voucher.status)]">
                    {{ voucher.status || 'UNKNOWN' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="mt-6 overflow-hidden rounded-3xl border border-black/8 bg-gradient-to-br from-white/95 to-[#f5f8fb]/90 shadow-[0_20px_60px_rgba(15,23,42,0.10)]">
        <div class="border-b border-black/8 bg-gradient-to-r from-[#f5f5f7] to-[#efefef] px-6 py-4">
          <h2 class="text-lg font-semibold text-[#1d1d1f]">Miles Earned From Completed Flights</h2>
          <p class="mt-1 text-xs text-[#6e6e73]">Showing {{ filteredEarnedTransactions.length }} of {{ earnedFlightTransactions.length }} records</p>
        </div>

        <div v-if="loading" class="px-6 py-16 text-center text-sm text-[#6e6e73]">
          Loading earned miles history...
        </div>

        <div v-else-if="errorMessage" class="px-6 py-8">
          <p class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{{ errorMessage }}</p>
        </div>

        <div v-else-if="filteredEarnedTransactions.length === 0" class="px-6 py-16 text-center">
          <p class="text-5xl">🛬</p>
          <p class="mt-3 text-lg font-semibold text-[#1d1d1f]">No earned miles records in this filter</p>
          <p class="mt-2 text-sm text-[#6e6e73]">Miles appear here after bookings are confirmed and flights are marked as landed.</p>
        </div>

        <div v-else class="overflow-x-auto">
          <table class="min-w-[920px] w-full">
            <thead>
              <tr class="bg-[#f5f5f7] text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">
                <th class="px-6 py-3">Date</th>
                <th class="px-6 py-3">Booking Ref</th>
                <th class="px-6 py-3">Type</th>
                <th class="px-6 py-3">Miles</th>
                <th class="px-6 py-3">Description</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in filteredEarnedTransactions"
                :key="entry.transactionID"
                class="border-t border-black/5 text-sm transition hover:bg-[#fff8f8]"
              >
                <td class="px-6 py-4 font-medium text-[#1d1d1f]">{{ formatDateTime(getTransactionCreatedAt(entry)) }}</td>
                <td class="px-6 py-4 font-mono text-xs text-[#1d1d1f]">{{ entry.referenceID || 'N/A' }}</td>
                <td class="px-6 py-4">
                  <span :class="['inline-flex rounded-lg px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.1em]', getTransactionTypeClass(entry.transactionType)]">
                    {{ getTransactionTypeLabel(entry.transactionType) }}
                  </span>
                </td>
                <td class="px-6 py-4 font-semibold text-emerald-700">{{ formatMiles(entry.milesDelta) }}</td>
                <td class="px-6 py-4 text-[#6e6e73]">{{ entry.description || 'N/A' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>
  </main>
</template>
