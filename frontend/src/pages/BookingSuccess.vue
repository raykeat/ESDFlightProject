<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route  = useRoute()
const router = useRouter()

const bookingID = route.params.bookingID
const sessionID = route.query.session_id   // Stripe appends this to the successUrl

const booking    = ref(null)
const payment    = ref(null)
const loading    = ref(true)
const error      = ref(null)

onMounted(async () => {
  try {
    // Step 1: Verify the Stripe session and update payment to Completed
    if (sessionID) {
      const paymentResponse = await axios.get(
        `http://localhost:5001/payment/verify-session/${sessionID}`
      )
      payment.value = paymentResponse.data
    }

    // Step 2: Fetch booking details from Booking Composite
    const bookingResponse = await axios.get(
      `http://localhost:3010/api/bookings/${bookingID}`
    )
    booking.value = bookingResponse.data

  } catch (err) {
    console.error('Error confirming booking:', err)
    error.value = err.response?.data?.message || 'Could not confirm your booking. Please contact support.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="min-h-screen bg-[#f5f5f7] py-20">
    <div class="mx-auto max-w-[600px] px-6 md:px-10">

      <!-- Loading -->
      <div v-if="loading" class="flex flex-col items-center justify-center py-20 gap-4">
        <div class="h-12 w-12 animate-spin rounded-full border-4 border-[#e63946] border-t-transparent"></div>
        <p class="text-sm text-[#6e6e73]">Confirming your payment...</p>
      </div>

      <!-- Error -->
      <div
        v-else-if="error"
        class="rounded-[32px] border border-red-200 bg-white p-8 text-center shadow-[0_20px_48px_rgba(0,0,0,0.08)]"
      >
        <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-red-100">
          <svg class="h-10 w-10 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h1 class="text-2xl font-semibold text-[#1d1d1f]">Something went wrong</h1>
        <p class="mt-2 text-sm text-[#6e6e73]">{{ error }}</p>
        <button
          class="mt-8 rounded-2xl bg-[#1d1d1f] px-8 py-3 text-sm font-medium text-white hover:bg-black transition"
          @click="router.push('/')"
        >
          Back to Home
        </button>
      </div>

      <!-- Success -->
      <div
        v-else
        class="rounded-[32px] border border-black/10 bg-white p-8 text-center shadow-[0_20px_48px_rgba(0,0,0,0.08)]"
      >
        <!-- Success icon -->
        <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-green-100">
          <svg class="h-10 w-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>

        <h1 class="text-3xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">Booking Confirmed!</h1>
        <p class="mt-2 text-[#6e6e73]">Your flight has been successfully booked and payment received.</p>

        <!-- Booking details -->
        <div class="mt-8 rounded-2xl bg-[#f5f5f7] p-6 text-left">
          <div class="space-y-3">
            <div class="flex justify-between">
              <span class="text-[#6e6e73] text-sm">Booking Reference</span>
              <span class="font-mono font-medium text-[#1d1d1f]">#{{ bookingID }}</span>
            </div>

            <template v-if="booking">
              <div class="flex justify-between">
                <span class="text-[#6e6e73] text-sm">Flight</span>
                <span class="font-medium text-[#1d1d1f]">#{{ booking.flightID }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[#6e6e73] text-sm">Seat</span>
                <span class="font-medium text-[#1d1d1f]">{{ booking.seatNumber }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[#6e6e73] text-sm">Status</span>
                <span class="font-medium text-green-600">{{ booking.status }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[#6e6e73] text-sm">Amount Paid</span>
                <span class="font-medium text-[#1d1d1f]">${{ booking.amount?.toFixed(2) }}</span>
              </div>
            </template>

            <!-- Payment confirmation -->
            <template v-if="payment">
              <div class="border-t border-black/10 pt-3 flex justify-between">
                <span class="text-[#6e6e73] text-sm">Payment Status</span>
                <span class="font-medium text-green-600">{{ payment.status }}</span>
              </div>
            </template>
          </div>
        </div>

        <p class="mt-4 text-xs text-[#6e6e73]">
          A confirmation email has been sent to your registered email address.
        </p>

        <div class="mt-8 flex gap-4">
          <button
            class="flex-1 rounded-2xl border border-black/10 bg-white py-3 text-sm font-medium text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="router.push('/')"
          >
            Back to Home
          </button>
          <button
            class="flex-1 rounded-2xl bg-[#1d1d1f] py-3 text-sm font-medium text-white transition hover:bg-black"
            @click="router.push('/my-bookings')"
          >
            View My Bookings
          </button>
        </div>
      </div>

    </div>
  </main>
</template>