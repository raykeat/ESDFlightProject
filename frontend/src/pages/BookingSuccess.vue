<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const router = useRouter()
const bookingID = route.params.bookingID
const booking = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    // Fetch booking details
    const response = await axios.get(`http://localhost:3010/api/bookings/${bookingID}`)
    booking.value = response.data
  } catch (error) {
    console.error('Error fetching booking:', error)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="min-h-screen bg-[#f5f5f7] py-20">
    <div class="mx-auto max-w-[600px] px-6 md:px-10">
      <div v-if="loading" class="flex justify-center py-20">
        <div class="h-12 w-12 animate-spin rounded-full border-4 border-[#e63946] border-t-transparent"></div>
      </div>

      <div v-else class="rounded-[32px] border border-black/10 bg-white p-8 text-center shadow-[0_20px_48px_rgba(0,0,0,0.08)]">
        <!-- Success icon -->
        <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-green-100">
          <svg class="h-10 w-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
          </svg>
        </div>

        <h1 class="text-3xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">Booking Confirmed!</h1>
        <p class="mt-2 text-[#6e6e73]">Your flight has been successfully booked.</p>

        <div class="mt-8 rounded-2xl bg-[#f5f5f7] p-6 text-left">
          <div class="space-y-3">
            <div class="flex justify-between">
              <span class="text-[#6e6e73]">Booking Reference</span>
              <span class="font-mono font-medium text-[#1d1d1f]">#{{ bookingID }}</span>
            </div>
            <div v-if="booking" class="space-y-3">
              <div class="flex justify-between">
                <span class="text-[#6e6e73]">Flight</span>
                <span class="font-medium text-[#1d1d1f]">#{{ booking.flightID }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[#6e6e73]">Seat</span>
                <span class="font-medium text-[#1d1d1f]">{{ booking.seatNumber }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[#6e6e73]">Status</span>
                <span class="font-medium text-green-600">{{ booking.status }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[#6e6e73]">Amount</span>
                <span class="font-medium text-[#1d1d1f]">${{ booking.amount }}</span>
              </div>
            </div>
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