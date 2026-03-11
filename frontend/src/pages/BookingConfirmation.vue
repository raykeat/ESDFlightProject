<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()

const booking = ref(null)
const loading = ref(false)
const error = ref(null)

const bookingDetails = ref({
  flightID: parseInt(route.query.flightID),
  seatNumber: route.query.seatNumber,
  amount: parseFloat(route.query.amount)
})

async function confirmBooking() {
  if (!currentPassenger.value) {
    router.push('/auth')
    return
  }

  loading.value = true
  error.value = null

  try {
    // Call Booking Composite Service
    console.log(currentPassenger.value);
    console.log(currentPassenger.value.passenger_id);
    console.log(bookingDetails.value.flightID);
    console.log(bookingDetails.value.seatNumber);
    const response = await axios.post('http://localhost:3010/api/bookings', {
      passengerID: currentPassenger.value.passenger_id,
      flightID: bookingDetails.value.flightID,
      seatNumber: bookingDetails.value.seatNumber
      // amount is not needed - composite service will get it from flight service
    })

    booking.value = response.data
    
    if (response.data.success) {
      // Redirect to success page or show success message
      setTimeout(() => {
        router.push(`/booking-success/${response.data.bookingID}`)
      }, 2000)
    }
  } catch (err) {
    console.error('Booking failed:', err)
    error.value = err.response?.data?.message || 'Booking failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="min-h-screen bg-[#f5f5f7] py-20">
    <div class="mx-auto max-w-[600px] px-6 md:px-10">
      <div class="rounded-[32px] border border-black/10 bg-white p-8 shadow-[0_20px_48px_rgba(0,0,0,0.08)]">
        <h1 class="text-3xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">Confirm Your Booking</h1>
        
        <div class="mt-8 space-y-4">
          <div class="flex justify-between border-b border-black/10 pb-4">
            <span class="text-[#6e6e73]">Flight</span>
            <span class="font-medium text-[#1d1d1f]">#{{ bookingDetails.flightID }}</span>
          </div>
          
          <div class="flex justify-between border-b border-black/10 pb-4">
            <span class="text-[#6e6e73]">Seat</span>
            <span class="font-medium text-[#1d1d1f]">{{ bookingDetails.seatNumber }}</span>
          </div>
          
          <div class="flex justify-between border-b border-black/10 pb-4">
            <span class="text-[#6e6e73]">Passenger</span>
            <span class="font-medium text-[#1d1d1f]">{{ currentPassenger?.FirstName }} {{ currentPassenger?.LastName }}</span>
          </div>
          
          <div class="flex justify-between text-lg font-semibold">
            <span>Total</span>
            <span class="text-[#e63946]">${{ bookingDetails.amount }}</span>
          </div>
        </div>

        <!-- Error message -->
        <div v-if="error" class="mt-6 rounded-xl bg-red-50 p-4 text-sm text-red-600">
          {{ error }}
        </div>

        <!-- Confirm button -->
        <button
          class="mt-8 w-full rounded-2xl bg-[#1d1d1f] py-4 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-black disabled:opacity-50"
          :disabled="loading"
          @click="confirmBooking"
        >
          <span v-if="loading" class="flex items-center justify-center gap-2">
            <span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
            Processing...
          </span>
          <span v-else>Confirm & Pay</span>
        </button>

        <p class="mt-4 text-center text-xs text-[#6e6e73]">
          By confirming, you agree to our terms of service and privacy policy.
        </p>
      </div>
    </div>
  </main>
</template>