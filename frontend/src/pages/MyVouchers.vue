<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePassengerSession } from '../composables/usePassengerSession'
import axios from 'axios'

const router = useRouter()
const { currentPassenger, isSignedIn } = usePassengerSession()

const vouchers = ref([])
const loading = ref(false)
const errorMessage = ref('')
const activeTab = ref('all') // 'all', 'active', 'used', 'expired'

const filteredVouchers = computed(() => {
  if (activeTab.value === 'active') {
    return vouchers.value.filter(v => v.status === 'ACTIVE')
  } else if (activeTab.value === 'used') {
    return vouchers.value.filter(v => v.status === 'USED')
  } else if (activeTab.value === 'expired') {
    return vouchers.value.filter(v => v.status === 'EXPIRED')
  }
  return vouchers.value
})

onMounted(async () => {
  if (!isSignedIn.value) {
    router.replace('/auth')
    return
  }

  await fetchVouchers()
})

async function fetchVouchers() {
  loading.value = true
  errorMessage.value = ''
  try {
    const passengerID = currentPassenger.value?.passenger_id
    const loyaltyUrl = import.meta.env.VITE_LOYALTY_SERVICE_URL || 'http://localhost:5004'

    const response = await axios.get(
      `${loyaltyUrl}/api/loyalty/vouchers/${passengerID}`
    )

    // The loyalty service returns the array directly from voucher service
    const vouchersData = Array.isArray(response.data) ? response.data : (response.data.vouchers || response.data || [])
    vouchers.value = vouchersData
  } catch (error) {
    console.error('Voucher fetch error:', error)
    errorMessage.value = 'Unable to load your vouchers. Please try again.'
    vouchers.value = []
  } finally {
    loading.value = false
  }
}

function getStatusBadgeClass(status) {
  switch (status) {
    case 'ACTIVE':
      return 'bg-emerald-100 text-emerald-700'
    case 'USED':
      return 'bg-gray-100 text-gray-700'
    case 'EXPIRED':
      return 'bg-red-100 text-red-700'
    default:
      return 'bg-blue-100 text-blue-700'
  }
}

function getVoucherIcon(type) {
  switch (type) {
    case 'TRAVEL_CREDIT':
      return '✈️'
    case 'UPGRADE':
      return '⬆️'
    case 'LOUNGE_PASS':
      return '🏨'
    default:
      return '🎁'
  }
}

function copyToClipboard(code) {
  navigator.clipboard.writeText(code)
  alert('Voucher code copied to clipboard!')
}

function backToHome() {
  router.push('/')
}

function convertMore() {
  router.push('/loyalty/convert')
}
</script>

<template>
  <main class="min-h-screen px-6 py-8 md:px-10 lg:px-16">
    <section class="mx-auto max-w-[1200px]">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">My Vouchers</h1>
        <p class="mt-3 max-w-2xl text-sm text-[#6e6e73] md:text-base">View and manage your converted mile vouchers. Use your voucher codes when booking your next flight.</p>
      </div>

      <!-- Tabs -->
      <div class="mb-8 flex gap-2 border-b border-black/10">
        <button
          v-for="tab in ['all', 'active', 'used', 'expired']"
          :key="tab"
          @click="activeTab = tab"
          class="px-4 py-3 text-sm font-semibold uppercase tracking-[0.12em] transition"
          :class="activeTab === tab
            ? 'border-b-2 border-[#e63946] text-[#1d1d1f]'
            : 'text-[#6e6e73] hover:text-[#1d1d1f]'"
        >
          {{ tab === 'all' ? 'All Vouchers' : tab.charAt(0).toUpperCase() + tab.slice(1) }}
        </button>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="text-center py-12">
        <p class="text-[#6e6e73]">Loading your vouchers...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="errorMessage" class="rounded-2xl border border-red-200 bg-red-50 p-6">
        <p class="text-sm text-red-700">{{ errorMessage }}</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="vouchers.length === 0" class="text-center py-12">
        <p class="text-2xl mb-4">🎁</p>
        <p class="text-lg font-semibold text-[#1d1d1f]">No vouchers yet</p>
        <p class="mt-2 text-sm text-[#6e6e73]">Convert your miles to create vouchers and unlock exclusive benefits.</p>
        <button
          @click="convertMore"
          class="mt-6 inline-flex rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-6 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:shadow-[0_8px_30px_rgba(230,57,70,0.35)]"
        >
          Convert Miles Now
        </button>
      </div>

      <!-- Vouchers Grid -->
      <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="(voucher, index) in filteredVouchers"
          :key="voucher.voucherCode || index"
          class="rounded-2xl border border-black/8 bg-gradient-to-br from-white to-[#f5f5f7] p-6 shadow-sm transition hover:shadow-[0_8px_24px_rgba(0,0,0,0.1)]"
        >
          <!-- Header with Icon and Status -->
          <div class="flex items-start justify-between gap-4">
            <div class="text-4xl">{{ getVoucherIcon(voucher.voucherType || voucher.type) }}</div>
            <span
              :class="['inline-flex rounded-lg px-3 py-1 text-xs font-semibold uppercase tracking-[0.1em]', getStatusBadgeClass(voucher.status || 'ACTIVE')]"
            >
              {{ voucher.status || 'ACTIVE' }}
            </span>
          </div>

          <!-- Voucher Details -->
          <div class="mt-4">
            <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">{{ voucher.voucherType || voucher.type }}</p>
            <h3 class="mt-2 text-lg font-semibold text-[#1d1d1f]">
              {{ voucher.voucherType === 'TRAVEL_CREDIT' ? 'Travel Credit' : 
                 voucher.voucherType === 'UPGRADE' ? 'Cabin Upgrade' :
                 voucher.voucherType === 'LOUNGE_PASS' ? 'Lounge Pass' : 'Voucher' }}
            </h3>
          </div>

          <!-- Voucher Code -->
          <div class="mt-6 rounded-lg border border-black/8 bg-white p-4">
            <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Voucher Code</p>
            <p class="mt-2 font-mono text-sm font-semibold text-[#1d1d1f] break-all">{{ voucher.voucherCode || voucher.code }}</p>
            <button
              @click="copyToClipboard(voucher.voucherCode || voucher.code)"
              class="mt-3 w-full rounded-lg border border-black/10 bg-[#f5f5f7] px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#e5e5e7]"
            >
              Copy Code
            </button>
          </div>

          <!-- Value and Expiry -->
          <div class="mt-4 space-y-2 text-sm">
            <div class="flex justify-between">
              <span class="text-[#6e6e73]">Value:</span>
              <span class="font-semibold text-[#1d1d1f]">{{ voucher.voucherValue || 'N/A' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[#6e6e73]">Expires:</span>
              <span class="font-semibold text-[#1d1d1f]">{{ voucher.expiryDate || 'N/A' }}</span>
            </div>
            <div v-if="voucher.usedDate" class="flex justify-between">
              <span class="text-[#6e6e73]">Used:</span>
              <span class="font-semibold text-[#1d1d1f]">{{ voucher.usedDate }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div v-if="voucher.status === 'ACTIVE'" class="mt-6">
            <button
              @click="() => router.push('/search-results')"
              class="w-full rounded-lg bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-white transition hover:shadow-[0_4px_12px_rgba(230,57,70,0.3)]"
            >
              Use This Voucher
            </button>
          </div>
        </div>
      </div>

      <!-- Bottom Actions -->
      <div class="mt-12 grid gap-3 md:grid-cols-2">
        <button
          @click="backToHome"
          class="rounded-2xl border border-black/10 bg-white px-6 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
        >
          Back to Home
        </button>
        <button
          @click="convertMore"
          class="rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-6 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:shadow-[0_8px_30px_rgba(230,57,70,0.35)]"
        >
          Convert More Miles
        </button>
      </div>
    </section>
  </main>
</template>
