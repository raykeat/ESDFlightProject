<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePassengerSession } from '../composables/usePassengerSession'
import axios from 'axios'

const router = useRouter()
const { currentPassenger, isSignedIn } = usePassengerSession()

const currentStep = ref(1) // 1: View Balance, 2: Multi-Select Vouchers, 3: Confirm, 4: Success
const currentBalance = ref(null)
const selectedVouchers = ref([]) // Array of voucher types selected
const generatedVouchers = ref([]) // Generated voucher codes
const travelCreditMiles = ref(500)
const loading = ref(false)
const errorMessage = ref('')

const voucherTypes = ref([])

const eligibleVouchers = computed(() => {
  if (!currentBalance.value) return []
  return voucherTypes.value.filter(v => currentBalance.value >= v.milesRequired)
})

const selectedVoucherDetails = computed(() => {
  return selectedVouchers.value
    .map(type => voucherTypes.value.find(v => v.type === type))
    .filter(Boolean)
})

const travelCreditMinMiles = computed(() => {
  const travelType = voucherTypes.value.find(v => v.type === 'TRAVEL_CREDIT')
  return travelType?.milesRequired || 500
})

const normalizedTravelCreditMiles = computed(() => {
  const parsed = Number(travelCreditMiles.value)
  if (!Number.isFinite(parsed)) return travelCreditMinMiles.value
  return Math.max(0, Math.floor(parsed))
})

function getVoucherMilesNeeded(voucher) {
  if (!voucher) return 0
  if (voucher.type === 'TRAVEL_CREDIT') {
    return Math.max(travelCreditMinMiles.value, normalizedTravelCreditMiles.value)
  }
  return voucher.milesValue || voucher.milesRequired || 0
}

const totalMilesNeeded = computed(() => {
  return selectedVoucherDetails.value.reduce((sum, v) => sum + getVoucherMilesNeeded(v), 0)
})

const totalMilesAfter = computed(() => {
  return (currentBalance.value || 0) - totalMilesNeeded.value
})

const isSelectionValid = computed(() => {
  if (selectedVouchers.value.length === 0) return false
  if (selectedVouchers.value.includes('TRAVEL_CREDIT') && normalizedTravelCreditMiles.value < travelCreditMinMiles.value) {
    return false
  }
  return totalMilesAfter.value >= 0
})

onMounted(async () => {
  if (!isSignedIn.value) {
    router.replace('/auth')
    return
  }

  // Fetch voucher types and balance
  await Promise.all([
    fetchVoucherTypes(),
    fetchBalance()
  ])
})

async function fetchBalance() {
  loading.value = true
  errorMessage.value = ''
  try {
    const passengerID = currentPassenger.value?.passenger_id
    const milesBalanceUrl = import.meta.env.VITE_MILES_BALANCE_SERVICE_URL || 'http://localhost:5006'
    
    try {
      // Try to fetch existing balance from miles-balance service
      const response = await axios.get(
        `${milesBalanceUrl}/miles-balance/${passengerID}`
      )
      currentBalance.value = response.data.currentBalance || response.data.balance || 0
    } catch (error) {
      // If 404 or no record, initialize with 2000 miles
      if (error.response?.status === 404 || error.message.includes('not found')) {
        const initResponse = await axios.post(
          `${milesBalanceUrl}/miles-balance/${passengerID}/initialize`,
          { welcomeBonus: 2000 }
        )
        currentBalance.value = initResponse.data.currentBalance || 2000
      } else {
        throw error
      }
    }
  } catch (error) {
    errorMessage.value = 'Unable to fetch your miles balance. Please try again.'
    console.error('Balance fetch error:', error)
  } finally {
    loading.value = false
  }
}

async function fetchVoucherTypes() {
  try {
    const voucherUrl = import.meta.env.VITE_VOUCHER_SERVICE_URL || 'http://localhost:5005'
    const response = await axios.get(
      `${voucherUrl}/vouchers/types`
    )
    
    // Map API response and add default UI properties if missing
    const types = response.data.voucherTypes || response.data.types || response.data
    voucherTypes.value = Array.isArray(types) ? types.map(type => ({
      type: type.type,
      name: type.name,
      description: type.description || '',
      milesRequired: type.minMiles || type.milesRequired || 0,
      milesValue: type.rate || type.milesValue || 0,
      icon: type.icon || '🎁',
      benefits: type.benefits || [],
    })) : []

    const travelType = voucherTypes.value.find(v => v.type === 'TRAVEL_CREDIT')
    if (travelType && travelCreditMiles.value < travelType.milesRequired) {
      travelCreditMiles.value = travelType.milesRequired
    }
  } catch (error) {
    console.error('Voucher types fetch error:', error)
    // Empty array - no voucher types available
    voucherTypes.value = []
  }
}

function toggleVoucherSelection(type) {
  const index = selectedVouchers.value.indexOf(type)
  if (index > -1) {
    selectedVouchers.value.splice(index, 1)
  } else {
    selectedVouchers.value.push(type)
    if (type === 'TRAVEL_CREDIT' && travelCreditMiles.value < travelCreditMinMiles.value) {
      travelCreditMiles.value = travelCreditMinMiles.value
    }
  }
}

function isVoucherSelected(type) {
  return selectedVouchers.value.includes(type)
}

function goBack() {
  if (currentStep.value > 1) {
    if (currentStep.value === 2) {
      selectedVouchers.value = []
    }
    currentStep.value -= 1
  }
}

function proceedToConfirmation() {
  if (isSelectionValid.value) {
    currentStep.value = 3
  }
}

async function executeConversion() {
  loading.value = true
  errorMessage.value = ''
  
  try {
    const passengerID = currentPassenger.value?.passenger_id
    const firstName = currentPassenger.value?.FirstName || currentPassenger.value?.firstName || ''
    const lastName = currentPassenger.value?.LastName || currentPassenger.value?.lastName || ''
    const passengerName = `${firstName} ${lastName}`.trim()
    const passengerEmail = currentPassenger.value?.Email || currentPassenger.value?.email || ''
    const loyaltyUrl = import.meta.env.VITE_LOYALTY_SERVICE_URL || 'http://localhost:5008'
    
    let response
    
    if (selectedVouchers.value.length === 1) {
      // Single conversion
      const voucher = selectedVoucherDetails.value[0]
      response = await axios.post(
        `${loyaltyUrl}/api/loyalty/convert`,
        {
          passengerID,
          passengerEmail,
          passengerName,
          voucherType: voucher.type,
          milesToConvert: getVoucherMilesNeeded(voucher)
        }
      )
      generatedVouchers.value = [response.data.voucher]
    } else {
      // Bundle conversion
      response = await axios.post(
        `${loyaltyUrl}/api/loyalty/convert-bundle`,
        {
          passengerID,
          passengerEmail,
          passengerName,
          items: selectedVouchers.value.map(type => {
            const voucher = selectedVoucherDetails.value.find(v => v.type === type)
            return {
              voucherType: type,
              milesToConvert: getVoucherMilesNeeded(voucher)
            }
          })
        }
      )
      generatedVouchers.value = response.data.vouchers || []
    }

    if (response.data.success) {
      currentBalance.value = response.data.remainingMiles
      currentStep.value = 4
    } else {
      errorMessage.value = response.data.error || 'Conversion failed. Please try again.'
    }
  } catch (error) {
    errorMessage.value = error.response?.data?.error || 'Conversion failed. Please try again.'
    console.error('Conversion error:', error)
  } finally {
    loading.value = false
  }
}

function backToHome() {
  router.push('/')
}

function viewMyVouchers() {
  router.push('/my-vouchers')
}
</script>

<template>
  <main class="min-h-screen px-6 py-8 md:px-10 lg:px-16">
    <section class="mx-auto max-w-[980px]">
      <!-- Step 1: View Balance -->
      <section v-if="currentStep === 1" class="animate__animated animate__fadeInUp rounded-[34px] border border-black/5 bg-white/90 p-6 shadow-[0_22px_52px_rgba(15,23,42,0.08)] backdrop-blur-2xl md:p-8">
        <h1 class="text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">Convert Your Miles</h1>
        <p class="mt-3 max-w-2xl text-sm text-[#6e6e73] md:text-base">Transform your accumulated miles into premium vouchers and experiences with Blaze Air. Select one or more vouchers in your conversion bundle.</p>

        <div v-if="loading" class="mt-8 text-center">
          <p class="text-[#6e6e73]">Loading your miles balance and voucher options...</p>
        </div>

        <div v-else-if="voucherTypes.length === 0" class="mt-8 rounded-2xl border border-black/8 bg-[#fff5f5] p-6">
          <p class="text-sm text-[#6e6e73]">No voucher types available at this moment. Please try again later.</p>
        </div>

        <div v-else class="mt-8">
          <!-- Current Balance Card -->
          <div class="rounded-2xl border border-black/8 bg-gradient-to-br from-[#e63946]/5 via-transparent to-[#ff6b6b]/5 p-6 md:p-8">
            <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Your Miles Balance</p>
            <p class="mt-3 text-5xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-6xl">{{ currentBalance?.toLocaleString() }}</p>
            <p class="mt-2 text-sm text-[#6e6e73]">Available miles</p>
          </div>

          <!-- Eligible Vouchers Preview -->
          <div class="mt-8">
            <p class="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">What You Can Get</p>
            <div class="grid gap-3 md:grid-cols-3">
              <div
                v-for="voucher in eligibleVouchers"
                :key="voucher.type"
                class="rounded-2xl border border-black/8 bg-[#f5f5f7] p-4 text-center"
              >
                <p class="text-3xl">{{ voucher.icon }}</p>
                <p class="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">{{ voucher.name }}</p>
                <p class="mt-1 text-lg font-semibold text-[#1d1d1f]">
                  {{ voucher.type === 'TRAVEL_CREDIT' ? `From ${voucher.milesRequired?.toLocaleString()} miles` : `${(voucher.milesValue || voucher.milesRequired)?.toLocaleString()} miles` }}
                </p>
              </div>
            </div>
          </div>

          <button
            class="mt-8 w-full rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:shadow-[0_8px_30px_rgba(230,57,70,0.35)]"
            @click="currentStep = 2"
            :disabled="eligibleVouchers.length === 0"
          >
            {{ eligibleVouchers.length > 0 ? 'Select Vouchers' : 'Insufficient Miles' }}
          </button>

          <p v-if="errorMessage" class="mt-4 text-sm font-medium text-red-600">{{ errorMessage }}</p>
        </div>
      </section>

      <!-- Step 2: Multi-Select Vouchers -->
      <section v-if="currentStep === 2" class="animate__animated animate__fadeInUp rounded-[34px] border border-black/5 bg-white/90 p-6 shadow-[0_22px_52px_rgba(15,23,42,0.08)] backdrop-blur-2xl md:p-8">
        <h1 class="text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">Select Vouchers</h1>
        <p class="mt-3 max-w-2xl text-sm text-[#6e6e73] md:text-base">Choose one or more available vouchers. You can create a bundle and convert multiple vouchers in one transaction.</p>

        <div class="mt-8 space-y-4">
          <label
            v-for="voucher in eligibleVouchers"
            :key="voucher.type"
            class="flex items-start gap-4 rounded-2xl border-2 p-6 cursor-pointer transition"
            :class="isVoucherSelected(voucher.type) 
              ? 'border-[#e63946] bg-[#fff5f5]' 
              : 'border-black/10 bg-white hover:border-black/20'"
          >
            <input
              type="checkbox"
              :checked="isVoucherSelected(voucher.type)"
              @change="toggleVoucherSelection(voucher.type)"
              class="mt-1 h-5 w-5 rounded border-black/20 text-[#e63946] cursor-pointer"
            />
            <div class="flex-1">
              <p class="text-3xl">{{ voucher.icon }}</p>
              <p class="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">{{ voucher.type }}</p>
              <h3 class="mt-1 text-xl font-semibold text-[#1d1d1f]">{{ voucher.name }}</h3>
              <p class="mt-2 text-sm text-[#6e6e73]">{{ voucher.description }}</p>
              <div v-if="voucher.benefits.length > 0" class="mt-4 flex flex-wrap gap-2">
                <span v-for="benefit in voucher.benefits" :key="benefit" class="inline-block rounded-lg bg-[#f5f5f7] px-3 py-1 text-xs text-[#6e6e73]">{{ benefit }}</span>
              </div>

              <div v-if="voucher.type === 'TRAVEL_CREDIT' && isVoucherSelected(voucher.type)" class="mt-4 rounded-xl border border-black/10 bg-white p-4">
                <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Choose miles to convert</p>
                <input
                  v-model.number="travelCreditMiles"
                  type="number"
                  :min="travelCreditMinMiles"
                  step="100"
                  class="mt-2 w-full rounded-xl border border-black/10 bg-[#f5f5f7] px-3 py-2 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
                />
                <p class="mt-2 text-xs text-[#6e6e73]">Minimum: {{ travelCreditMinMiles.toLocaleString() }} miles</p>
              </div>

              <p class="mt-4 text-lg font-semibold text-[#1d1d1f]">
                {{ voucher.type === 'TRAVEL_CREDIT' ? `From ${voucher.milesRequired.toLocaleString()} miles` : `${(voucher.milesValue || voucher.milesRequired).toLocaleString()} miles` }}
              </p>
            </div>
          </label>
        </div>

        <!-- Selection Summary -->
        <div v-if="selectedVouchers.length > 0" class="mt-8 rounded-2xl border border-black/8 bg-[#f5f5f7] p-6">
          <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Bundle Summary</p>
          <div class="mt-4 space-y-2">
            <div v-for="voucher in selectedVoucherDetails" :key="voucher.type" class="flex justify-between">
              <span class="text-sm text-[#1d1d1f]">{{ voucher.name }}</span>
              <span class="text-sm font-semibold text-[#1d1d1f]">{{ getVoucherMilesNeeded(voucher).toLocaleString() }} miles</span>
            </div>
          </div>
          <div class="mt-4 border-t border-black/10 pt-4 flex justify-between">
            <span class="text-sm font-semibold text-[#1d1d1f]">Total Miles Needed</span>
            <span class="text-lg font-semibold text-[#e63946]">{{ totalMilesNeeded.toLocaleString() }}</span>
          </div>
          <div class="mt-2 flex justify-between">
            <span class="text-sm font-semibold text-[#1d1d1f]">Remaining After Conversion</span>
            <span class="text-lg font-semibold" :class="totalMilesAfter < 0 ? 'text-red-600' : 'text-[#1d1d1f]'">{{ totalMilesAfter.toLocaleString() }}</span>
          </div>
        </div>

        <div class="mt-8 grid gap-3 md:grid-cols-2">
          <button
            class="rounded-2xl border border-black/10 bg-white px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="goBack"
          >
            Back
          </button>
          <button
            class="rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:shadow-[0_8px_30px_rgba(230,57,70,0.35)] disabled:opacity-50"
            @click="proceedToConfirmation"
            :disabled="!isSelectionValid"
          >
            {{ selectedVouchers.length === 0 ? 'Select at least one' : 'Continue to Confirm' }}
          </button>
        </div>

        <p v-if="selectedVouchers.includes('TRAVEL_CREDIT') && normalizedTravelCreditMiles < travelCreditMinMiles" class="mt-4 text-sm font-medium text-red-600">
          Travel Credit requires at least {{ travelCreditMinMiles.toLocaleString() }} miles.
        </p>
      </section>

      <!-- Step 3: Confirm Conversion -->
      <section v-if="currentStep === 3" class="animate__animated animate__fadeInUp rounded-[34px] border border-black/5 bg-white/90 p-6 shadow-[0_22px_52px_rgba(15,23,42,0.08)] backdrop-blur-2xl md:p-8">
        <h1 class="text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">Confirm Your Conversion</h1>
        <p class="mt-3 max-w-2xl text-sm text-[#6e6e73] md:text-base">Review your selection before converting your miles to vouchers.</p>

        <div class="mt-8 space-y-6">
          <div v-for="(voucher, index) in selectedVoucherDetails" :key="voucher.type" class="rounded-2xl border border-black/8 bg-gradient-to-br from-[#e63946]/5 via-transparent to-[#ff6b6b]/5 p-6">
            <div class="flex items-start gap-4">
              <p class="text-4xl">{{ voucher.icon }}</p>
              <div class="flex-1">
                <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Item {{ index + 1 }}: {{ voucher.type }}</p>
                <h3 class="mt-1 text-xl font-semibold text-[#1d1d1f]">{{ voucher.name }}</h3>
                <p class="mt-2 text-sm text-[#6e6e73]">{{ getVoucherMilesNeeded(voucher).toLocaleString() }} miles</p>
              </div>
            </div>
          </div>
        </div>

        <div class="mt-8 rounded-2xl border border-black/8 bg-[#f5f5f7] p-6">
          <div class="space-y-3">
            <div class="flex justify-between">
              <span class="text-sm text-[#6e6e73]">Total Miles to Convert</span>
              <span class="text-sm font-semibold text-[#1d1d1f]">{{ totalMilesNeeded.toLocaleString() }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-sm text-[#6e6e73]">Current Balance</span>
              <span class="text-sm font-semibold text-[#1d1d1f]">{{ currentBalance?.toLocaleString() }}</span>
            </div>
            <div class="border-t border-black/10 pt-3 flex justify-between">
              <span class="text-sm font-semibold text-[#1d1d1f]">Remaining Balance</span>
              <span class="text-lg font-semibold text-[#e63946]">{{ totalMilesAfter.toLocaleString() }}</span>
            </div>
          </div>
        </div>

        <div class="mt-8 grid gap-3 md:grid-cols-2">
          <button
            class="rounded-2xl border border-black/10 bg-white px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="goBack"
            :disabled="loading"
          >
            Back
          </button>
          <button
            class="rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:shadow-[0_8px_30px_rgba(230,57,70,0.35)] disabled:opacity-70"
            @click="executeConversion"
            :disabled="loading"
          >
            {{ loading ? 'Processing...' : 'Confirm & Convert' }}
          </button>
        </div>

        <p v-if="errorMessage" class="mt-4 text-sm font-medium text-red-600">{{ errorMessage }}</p>
      </section>

      <!-- Step 4: Success -->
      <section v-if="currentStep === 4" class="animate__animated animate__fadeInUp rounded-[34px] border border-black/5 bg-white/90 p-6 shadow-[0_22px_52px_rgba(15,23,42,0.08)] backdrop-blur-2xl md:p-8">
        <div class="text-center">
          <div class="mx-auto inline-flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
            <svg class="h-8 w-8 text-emerald-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
          </div>
          <h1 class="mt-4 text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">Conversion Complete!</h1>
          <p class="mt-3 max-w-2xl text-sm text-[#6e6e73] md:text-base">Your miles have been successfully converted to {{ generatedVouchers.length }} voucher{{ generatedVouchers.length !== 1 ? 's' : '' }}.</p>
        </div>

        <!-- Generated Vouchers -->
        <div class="mt-8 space-y-4">
          <div v-for="(voucher, index) in generatedVouchers" :key="index" class="rounded-2xl border border-black/8 bg-[#f5f5f7] p-6">
            <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Voucher {{ index + 1 }}: {{ voucher.voucherType || voucher.type }}</p>
            <p class="mt-3 break-all text-2xl font-mono font-semibold text-[#1d1d1f]">{{ voucher.voucherCode || voucher.code }}</p>
            <p class="mt-3 text-sm text-[#6e6e73]">
              <span class="font-semibold">Value:</span> {{ voucher.voucherValue || 'N/A' }} 
              <span class="ml-4"><span class="font-semibold">Expires:</span> {{ voucher.expiryDate || 'N/A' }}</span>
            </p>
            <a
              v-if="voucher.redemptionUrl"
              :href="voucher.redemptionUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="mt-4 inline-flex rounded-xl border border-black/10 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#efefef]"
            >
              Open Redemption Link
            </a>
          </div>
        </div>

        <div class="mt-8 rounded-2xl border border-[#e63946]/20 bg-[#fff5f5] p-4 md:p-6">
          <p class="text-xs font-semibold uppercase tracking-[0.12em] text-[#e63946]">What's Next?</p>
          <ul class="mt-3 space-y-2 text-sm text-[#6e6e73]">
            <li class="flex gap-3">
              <span class="font-semibold text-[#1d1d1f]">•</span>
              <span>Your vouchers are now active and ready to use</span>
            </li>
            <li class="flex gap-3">
              <span class="font-semibold text-[#1d1d1f]">•</span>
              <span>Save your voucher codes for your records</span>
            </li>
            <li class="flex gap-3">
              <span class="font-semibold text-[#1d1d1f]">•</span>
              <span>Check your email for voucher details and terms</span>
            </li>
            <li class="flex gap-3">
              <span class="font-semibold text-[#1d1d1f]">•</span>
              <span>Your remaining balance: {{ currentBalance?.toLocaleString() }} miles</span>
            </li>
          </ul>
        </div>

        <div class="mt-8 grid gap-3 md:grid-cols-2">
          <button
            class="rounded-2xl border border-black/10 bg-white px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="backToHome"
          >
            Back to Home
          </button>
          <button
            class="rounded-2xl bg-[#1d1d1f] px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-black hover:shadow-[0_8px_24px_rgba(29,29,31,0.35)]"
            @click="viewMyVouchers"
          >
            View My Vouchers
          </button>
        </div>
      </section>
    </section>
  </main>
</template>
