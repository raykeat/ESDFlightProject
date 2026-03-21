<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  flightId: {
    type: [Number, String],
    required: true
  },
  maxSeats: {
    type: Number,
    default: 1
  },
  seatsData: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['seatSelected'])

const seats = ref([])
const loading = ref(true)
const selectedSeats = ref([])

function mapSeats(seatData) {
  if (!Array.isArray(seatData) || seatData.length === 0) return []

  return seatData.map(seat => {
    const seatNumber = seat.SeatNumber || seat.seatNumber || ''
    const rowMatch = seatNumber.match(/\d+/)
    const colMatch = seatNumber.match(/[A-Za-z]+/)

    return {
      id: seatNumber,
      row: rowMatch ? parseInt(rowMatch[0]) : 0,
      col: colMatch ? colMatch[0] : '',
      isAvailable: String(seat.Status || seat.status || '').toLowerCase() === 'available'
    }
  }).filter(seat => seat.id)
}

watch(
  () => props.seatsData,
  (newSeatData) => {
    seats.value = mapSeats(newSeatData)
    loading.value = false
  },
  { immediate: true }
)

function selectSeat(seat) {
  if (!seat.isAvailable) return
  
  const idx = selectedSeats.value.indexOf(seat.id)
  if (idx !== -1) {
    selectedSeats.value.splice(idx, 1) // Deselect
  } else {
    if (selectedSeats.value.length < props.maxSeats) {
      selectedSeats.value.push(seat.id) // Select
    } else {
      if (props.maxSeats === 1) {
        selectedSeats.value = [seat.id]
      } else {
        return
      }
    }
  }
  
  emit('seatSelected', selectedSeats.value)
}

const getRowSeats = (rowNum) => seats.value.filter(s => s.row === rowNum).sort((a,b) => a.col.localeCompare(b.col))
const uniqueRows = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
</script>

<template>
  <div class="seat-selector-container py-2 flex flex-col items-center">
    <!-- Legend -->
    <div class="mb-8 flex flex-wrap items-center justify-center gap-4 md:gap-8 rounded-full border border-black/5 bg-white/60 px-6 py-3 shadow-[0_8px_16px_rgba(0,0,0,0.03)] backdrop-blur-md">
      <div class="flex items-center gap-2 group">
        <div class="h-3 w-3 rounded bg-white border border-black/10 shadow-[inset_0_1px_2px_rgba(0,0,0,0.05)] transition-transform group-hover:scale-110"></div> 
        <span class="text-[11px] font-bold uppercase tracking-[0.1em] text-[#6e6e73]">Available</span>
      </div>
      <div class="flex items-center gap-2 group">
        <div class="h-3 w-3 rounded bg-gradient-to-br from-[#f43f5e] to-[#e63946] shadow-[0_2px_8px_rgba(230,57,70,0.3)] ring-2 ring-[#e63946]/20 transition-transform group-hover:scale-110"></div> 
        <span class="text-[11px] font-bold uppercase tracking-[0.1em] text-[#1d1d1f]">Selected</span>
      </div>
      <div class="flex items-center gap-2 group">
        <div class="h-3 w-3 rounded bg-[#e5e5ea] shadow-[inset_0_1px_3px_rgba(0,0,0,0.1)] transition-transform group-hover:scale-110"></div> 
        <span class="text-[11px] font-bold uppercase tracking-[0.1em] text-[#a1a1a6]">Occupied</span>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex flex-col items-center py-16">
      <div class="relative flex h-12 w-12 items-center justify-center">
        <div class="absolute h-full w-full animate-ping rounded-full border-[2px] border-[#e63946]/20"></div>
        <div class="h-6 w-6 animate-spin rounded-full border-[3px] border-[#e63946] border-t-transparent"></div>
      </div>
      <p class="mt-4 text-[10px] font-bold uppercase tracking-[0.2em] text-[#6e6e73] animate-pulse">Configuring Cabin...</p>
    </div>

    <!-- The Aircraft Fuselage -->
    <div v-else class="relative mx-auto rounded-[60px] rounded-t-[140px] border-[12px] border-white/80 bg-gradient-to-b from-[#fbfbfd] to-[#f5f5f7] p-8 pb-16 shadow-[0_24px_50px_rgba(0,0,0,0.08),inset_0_4px_20px_rgba(0,0,0,0.04)] backdrop-blur-xl">
      <!-- Cockpit indication -->
      <div class="absolute top-0 left-1/2 h-[30px] w-[80px] -translate-x-1/2 -translate-y-1/2 rounded-full border-4 border-white bg-sky-100/50 shadow-inner"></div>

      <div class="mb-12 mt-6 text-center">
        <p class="text-[9px] font-bold uppercase tracking-[0.3em] text-[#a1a1a6]">Cockpit / Front</p>
        <div class="mx-auto mt-4 h-px w-12 bg-gradient-to-r from-transparent via-black/10 to-transparent"></div>
      </div>

      <div class="grid gap-y-4 relative">
        <!-- Center aisle visual divider -->
        <div class="absolute top-0 bottom-0 left-1/2 w-10 -translate-x-1/2 bg-[linear-gradient(to_bottom,rgba(0,0,0,0.02)_50%,transparent_50%)] bg-[length:100%_20px]"></div>

        <div v-for="row in uniqueRows" :key="row" class="relative flex items-center justify-between gap-2 z-10 w-fit mx-auto">
          <!-- Left side seats (A, B, C) -->
          <div class="flex gap-2">
            <button 
              v-for="seat in getRowSeats(row).slice(0, 3)" 
              :key="seat.id"
              :disabled="!seat.isAvailable"
              @click="selectSeat(seat)"
              class="relative flex h-10 w-10 items-center justify-center rounded-[10px] text-[11px] font-bold transition-all duration-300 transform-gpu"
              :class="[
                !seat.isAvailable 
                  ? 'bg-[#e5e5ea] text-[#a1a1a6] shadow-[inset_0_2px_4px_rgba(0,0,0,0.06)] cursor-not-allowed' 
                  : selectedSeats.includes(seat.id) 
                    ? 'bg-gradient-to-b from-[#f43f5e] to-[#e63946] text-white scale-110 shadow-[0_8px_16px_rgba(230,57,70,0.35),inset_0_1px_1px_rgba(255,255,255,0.4)] ring-2 ring-[#e63946]/30 -translate-y-1 z-20' 
                    : 'bg-white border border-black/5 text-[#1d1d1f] shadow-[0_2px_6px_rgba(0,0,0,0.04)] hover:-translate-y-0.5 hover:shadow-[0_6px_12px_rgba(0,0,0,0.08)] hover:border-[#e63946]/30'
              ]"
            >
              {{ seat.col }}
            </button>
          </div>

          <!-- Aisle with Row Number -->
          <div class="flex w-10 items-center justify-center">
            <span class="rounded-full bg-black/5 px-2 py-0.5 text-[9px] font-bold tracking-widest text-[#86868b]">{{ row }}</span>
          </div>

          <!-- Right side seats (D, E, F) -->
          <div class="flex gap-2">
            <button 
              v-for="seat in getRowSeats(row).slice(3, 6)" 
              :key="seat.id"
              :disabled="!seat.isAvailable"
              @click="selectSeat(seat)"
              class="relative flex h-10 w-10 items-center justify-center rounded-[10px] text-[11px] font-bold transition-all duration-300 transform-gpu"
              :class="[
                !seat.isAvailable 
                  ? 'bg-[#e5e5ea] text-[#a1a1a6] shadow-[inset_0_2px_4px_rgba(0,0,0,0.06)] cursor-not-allowed' 
                  : selectedSeats.includes(seat.id) 
                    ? 'bg-gradient-to-b from-[#f43f5e] to-[#e63946] text-white scale-110 shadow-[0_8px_16px_rgba(230,57,70,0.35),inset_0_1px_1px_rgba(255,255,255,0.4)] ring-2 ring-[#e63946]/30 -translate-y-1 z-20' 
                    : 'bg-white border border-black/5 text-[#1d1d1f] shadow-[0_2px_6px_rgba(0,0,0,0.04)] hover:-translate-y-0.5 hover:shadow-[0_6px_12px_rgba(0,0,0,0.08)] hover:border-[#e63946]/30'
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