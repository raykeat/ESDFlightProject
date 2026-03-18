<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  flightId: {
    type: [Number, String],
    required: true
  }
})

const emit = defineEmits(['seatSelected'])

const seats = ref([])
const loading = ref(true)
const selectedSeatId = ref(null)

// Mocking the database fetch
onMounted(async () => {
  loading.value = true
  try {
    // Logic: In a real app, you'd fetch based on props.flightId
    // const response = await fetch(`/api/flights/${props.flightId}/seats`)
    // seats.value = await response.json()

    // Mocking a standard 3-3 configuration plane layout
    const rows = 10
    const cols = ['A', 'B', 'C', 'D', 'E', 'F']
    const mockSeats = []

    for (let i = 1; i <= rows; i++) {
      cols.forEach(col => {
        mockSeats.push({
          id: `${i}${col}`,
          row: i,
          col: col,
          // Randomly making some seats occupied for the demo
          isAvailable: Math.random() > 0.2, 
          priceModifier: i < 3 ? 50 : 0 // Premium for front rows
        })
      })
    }
    
    setTimeout(() => {
      seats.value = mockSeats
      loading.value = false
    }, 800) // Simulate network delay
  } catch (error) {
    console.error("Failed to load seats:", error)
    loading.value = false
  }
})

function selectSeat(seat) {
  if (!seat.isAvailable) return
  
  selectedSeatId.value = seat.id
  emit('seatSelected', seat.id)
}

// Helper to group seats by row for the layout
const getRowSeats = (rowNum) => seats.value.filter(s => s.row === rowNum)
const uniqueRows = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
</script>

<template>
  <div class="seat-selector-container py-4">
    <div class="mb-6 flex items-center justify-center gap-8 text-sm font-medium text-[#6e6e73]">
      <div class="flex items-center gap-2">
        <div class="h-4 w-4 rounded-sm bg-white border border-black/10"></div> Available
      </div>
      <div class="flex items-center gap-2">
        <div class="h-4 w-4 rounded-sm bg-[#e63946]"></div> Selected
      </div>
      <div class="flex items-center gap-2">
        <div class="h-4 w-4 rounded-sm bg-[#d2d2d7]"></div> Occupied
      </div>
    </div>

    <div v-if="loading" class="flex flex-col items-center py-10">
      <div class="h-8 w-8 animate-spin rounded-full border-2 border-[#e63946] border-t-transparent"></div>
      <p class="mt-2 text-xs text-[#6e6e73]">Loading Seat Map...</p>
    </div>

    <div v-else class="mx-auto max-w-fit rounded-[40px] border-[8px] border-white bg-white p-8 shadow-inner ring-1 ring-black/5">
      <div class="mb-10 text-center text-[10px] font-bold uppercase tracking-widest text-[#86868b]">
        Front of Aircraft
      </div>

      <div class="grid gap-y-3">
        <div v-for="row in uniqueRows" :key="row" class="flex items-center gap-3">
          <span class="w-4 text-right text-[10px] font-medium text-[#86868b]">{{ row }}</span>
          
          <div class="flex gap-2">
            <button 
              v-for="seat in getRowSeats(row).slice(0, 3)" 
              :key="seat.id"
              :disabled="!seat.isAvailable"
              @click="selectSeat(seat)"
              :class="[
                'h-9 w-9 rounded-lg text-[10px] font-semibold transition-all duration-200',
                !seat.isAvailable ? 'bg-[#f5f5f7] text-[#d2d2d7] cursor-not-allowed' : 
                selectedSeatId === seat.id ? 'bg-[#e63946] text-white scale-110 shadow-md' : 'bg-white border-2 border-[#f5f5f7] text-[#1d1d1f] hover:border-[#e63946]/50'
              ]"
            >
              {{ seat.col }}
            </button>
          </div>

          <div class="mx-4 w-6"></div>

          <div class="flex gap-2">
            <button 
              v-for="seat in getRowSeats(row).slice(3, 6)" 
              :key="seat.id"
              :disabled="!seat.isAvailable"
              @click="selectSeat(seat)"
              :class="[
                'h-9 w-9 rounded-lg text-[10px] font-semibold transition-all duration-200',
                !seat.isAvailable ? 'bg-[#f5f5f7] text-[#d2d2d7] cursor-not-allowed' : 
                selectedSeatId === seat.id ? 'bg-[#e63946] text-white scale-110 shadow-md' : 'bg-white border-2 border-[#f5f5f7] text-[#1d1d1f] hover:border-[#e63946]/50'
              ]"
            >
              {{ seat.col }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>