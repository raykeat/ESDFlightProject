<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePassengerSession } from '../composables/usePassengerSession'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()

const flights = ref([])
const loading = ref(true)
const selectedFlight = ref(null)
const selectedSeat = ref('')
const bookingInProgress = ref(false)

// Get search params from URL query
const searchParams = ref({
  departingCountry: route.query.departingCountry,
  arrivingCountry: route.query.arrivingCountry,
  departureDate: route.query.departureDate,
  returnDate: route.query.returnDate,
  passengers: parseInt(route.query.passengers) || 1,
  cabin: route.query.cabin
})

// Mock flight data (replace with actual API call to Flight Service)
onMounted(async () => {
  try {
    // TODO: Replace with actual Flight Service API call
    // const response = await axios.get(`http://localhost:3001/flights/available`, {
    //   params: searchParams.value
    // })
    // flights.value = response.data
    
    // Mock data for now
    setTimeout(() => {
      flights.value = [
        {
          flightID: 201,
          flightNumber: 'BA123',
          origin: searchParams.value.departingCountry,
          destination: searchParams.value.arrivingCountry,
          departureTime: '2026-04-15T08:30:00',
          arrivalTime: '2026-04-15T12:45:00',
          price: 299.99,
          availableSeats: 12,
          cabin: searchParams.value.cabin
        },
        {
          flightID: 202,
          flightNumber: 'BA456',
          origin: searchParams.value.departingCountry,
          destination: searchParams.value.arrivingCountry,
          departureTime: '2026-04-15T14:20:00',
          arrivalTime: '2026-04-15T18:35:00',
          price: 249.99,
          availableSeats: 8,
          cabin: searchParams.value.cabin
        },
        {
          flightID: 203,
          flightNumber: 'BA789',
          origin: searchParams.value.departingCountry,
          destination: searchParams.value.arrivingCountry,
          departureTime: '2026-04-15T19:45:00',
          arrivalTime: '2026-04-16T00:15:00',
          price: 199.99,
          availableSeats: 3,
          cabin: searchParams.value.cabin
        }
      ]
      loading.value = false
    }, 1000)
  } catch (error) {
    console.error('Error fetching flights:', error)
    loading.value = false
  }
})

function selectFlight(flight) {
  selectedFlight.value = flight
}

function bookFlight() {
  if (!selectedFlight.value) {
    alert('Please select a flight first')
    return
  }
  
  if (!selectedSeat.value) {
    alert('Please select a seat')
    return
  }
  
  if (!currentPassenger.value) {
    // Redirect to sign in if not logged in
    router.push({
      path: '/auth',
      query: { 
        redirect: '/search-results',
        ...searchParams.value,
        flightID: selectedFlight.value.flightID,
        seatNumber: selectedSeat.value
      }
    })
    return
  }
  
  // Proceed to booking — pass search params so Back button works correctly
  router.push({
    path: '/booking-confirmation',
    query: {
      flightID:         selectedFlight.value.flightID,
      seatNumber:       selectedSeat.value,
      amount:           selectedFlight.value.price,
      flightNumber:     selectedFlight.value.flightNumber,
      departingCountry: searchParams.value.departingCountry,
      arrivingCountry:  searchParams.value.arrivingCountry,
      departureDate:    searchParams.value.departureDate,
      returnDate:       searchParams.value.returnDate,
      passengers:       searchParams.value.passengers,
      cabin:            searchParams.value.cabin,
    }
  })
}
</script>

<template>
  <main class="min-h-screen bg-[#f5f5f7] pb-20">
    <div class="mx-auto max-w-[1240px] px-6 pt-8 md:px-10 lg:px-16">
      <!-- Header with search summary -->
      <div class="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 class="text-3xl font-semibold tracking-[-0.02em] text-[#1d1d1f]">Available Flights</h1>
          <p class="mt-2 text-[#6e6e73]">
            {{ searchParams.departingCountry }} → {{ searchParams.arrivingCountry }}
            • {{ new Date(searchParams.departureDate).toLocaleDateString() }}
            • {{ searchParams.passengers }} passenger{{ searchParams.passengers > 1 ? 's' : '' }}
            • {{ searchParams.cabin }}
          </p>
        </div>
        <div style="display:flex; gap:10px; align-items:center;">
          <RouterLink
            to="/"
            class="rounded-full border border-black/10 bg-white px-5 py-2 text-sm font-medium text-[#1d1d1f] transition hover:border-[#e63946]/30"
            style="display:flex; align-items:center; gap:6px;"
          >
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M15 19l-7-7 7-7"/></svg>
            Back to Home
          </RouterLink>
          <RouterLink
            to="/"
            class="rounded-full border border-black/10 bg-white px-5 py-2 text-sm font-medium text-[#1d1d1f] transition hover:border-[#e63946]/30"
          >
            Modify Search
          </RouterLink>
        </div>
      </div>

      <!-- Loading state -->
      <div v-if="loading" class="flex justify-center py-20">
        <div class="h-12 w-12 animate-spin rounded-full border-4 border-[#e63946] border-t-transparent"></div>
      </div>

      <!-- Flight results -->
      <div v-else class="grid gap-4">
        <article
          v-for="flight in flights"
          :key="flight.flightID"
          class="relative cursor-pointer rounded-[28px] border border-black/10 bg-white p-6 transition-all hover:shadow-[0_12px_32px_rgba(0,0,0,0.08)]"
          :class="{ 'ring-2 ring-[#e63946]': selectedFlight?.flightID === flight.flightID }"
          @click="selectFlight(flight)"
        >
          <div class="flex flex-wrap items-center justify-between gap-4">
            <div class="flex items-center gap-6">
              <div class="text-center">
                <p class="text-2xl font-semibold text-[#1d1d1f]">
                  {{ new Date(flight.departureTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}
                </p>
                <p class="text-sm text-[#6e6e73]">{{ flight.origin }}</p>
              </div>
              
              <div class="flex flex-col items-center px-4">
                <p class="text-xs text-[#6e6e73]">{{ flight.flightNumber }}</p>
                <div class="relative w-24">
                  <div class="h-[2px] w-full bg-[#e63946]/30"></div>
                  <svg class="absolute right-0 top-1/2 h-4 w-4 -translate-y-1/2 text-[#e63946]" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M3 10a.75.75 0 0 1 .75-.75h10.638L10.23 5.29a.75.75 0 1 1 1.04-1.08l5.5 5.25a.75.75 0 0 1 0 1.08l-5.5 5.25a.75.75 0 1 1-1.04-1.08l4.158-3.96H3.75A.75.75 0 0 1 3 10Z" clip-rule="evenodd" />
                  </svg>
                </div>
                <p class="text-xs text-[#6e6e73]">{{ flight.flightNumber }}</p>
              </div>
              
              <div class="text-center">
                <p class="text-2xl font-semibold text-[#1d1d1f]">
                  {{ new Date(flight.arrivalTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}
                </p>
                <p class="text-sm text-[#6e6e73]">{{ flight.destination }}</p>
              </div>
            </div>

            <div class="flex items-center gap-6">
              <div class="text-right">
                <p class="text-2xl font-semibold text-[#1d1d1f]">${{ flight.price }}</p>
                <p class="text-sm text-[#6e6e73]">{{ flight.availableSeats }} seats left</p>
              </div>
            </div>
          </div>

          <!-- Seat selection (shown when flight is selected) -->
          <div v-if="selectedFlight?.flightID === flight.flightID" class="mt-6 border-t border-black/10 pt-6">
            <p class="mb-3 text-sm font-semibold uppercase tracking-[0.1em] text-[#6e6e73]">Select Your Seat</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="seat in ['12A', '12B', '12C', '12D', '14A', '14B', '14C', '14D']"
                :key="seat"
                class="h-10 w-10 rounded-lg border text-sm font-medium transition"
                :class="selectedSeat === seat 
                  ? 'border-[#e63946] bg-[#e63946] text-white' 
                  : 'border-black/10 bg-[#f5f5f7] text-[#1d1d1f] hover:border-[#e63946]/30'"
                @click.stop="selectedSeat = seat"
              >
                {{ seat }}
              </button>
            </div>
          </div>
        </article>

        <!-- Book button -->
        <div v-if="selectedFlight" class="sticky bottom-6 mt-6 flex justify-end">
          <button
            class="rounded-full bg-[#1d1d1f] px-8 py-4 text-sm font-semibold uppercase tracking-[0.14em] text-white shadow-lg transition hover:bg-black hover:shadow-[0_12px_32px_rgba(29,29,31,0.35)] disabled:opacity-50"
            :disabled="!selectedSeat"
            @click="bookFlight"
          >
            Book Flight • ${{ selectedFlight.price }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>