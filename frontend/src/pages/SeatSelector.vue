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
  <div class="seat-selector-container flex h-full flex-col">
    <!-- Legend -->
    <div class="mb-3 flex flex-wrap items-center justify-center gap-5 rounded-full border border-black/5 bg-white/60 px-4 py-2 shadow-[0_8px_16px_rgba(0,0,0,0.03)] backdrop-blur-md">
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
    <div v-else class="flex min-h-0 flex-1 flex-col items-center justify-center">
      <div class="w-full max-w-[960px] rounded-[22px] border border-black/6 bg-[#f8f8fa] px-8 py-4">
        <div class="mb-3 text-center">
          <p class="text-[9px] font-bold uppercase tracking-[0.2em] text-[#a1a1a6]">Cabin Front</p>
        </div>

        <div class="relative mx-auto w-fit">
          <div class="absolute left-1/2 top-0 h-full w-10 -translate-x-1/2 bg-[linear-gradient(to_bottom,rgba(0,0,0,0.025)_50%,transparent_50%)] bg-[length:100%_22px]"></div>

          <div v-for="row in uniqueRows" :key="row" class="relative z-10 mx-auto mb-2 flex w-fit items-center justify-between gap-2.5 last:mb-0">
            <div class="flex gap-2.5">
              <button
                v-for="seat in getRowSeats(row).slice(0, 3)"
                :key="seat.id"
                :disabled="!seat.isAvailable"
                @click="selectSeat(seat)"
                class="relative flex h-10 w-10 transform-gpu items-center justify-center rounded-[10px] text-[12px] font-bold transition-all duration-200"
                :class="[
                  !seat.isAvailable
                    ? 'bg-[#e5e5ea] text-[#a1a1a6] shadow-[inset_0_2px_4px_rgba(0,0,0,0.06)] cursor-not-allowed'
                    : selectedSeats.includes(seat.id)
                      ? 'bg-gradient-to-b from-[#f43f5e] to-[#e63946] text-white scale-105 shadow-[0_6px_12px_rgba(230,57,70,0.35)] ring-2 ring-[#e63946]/30 z-20'
                      : 'bg-white border border-black/5 text-[#1d1d1f] shadow-[0_1px_4px_rgba(0,0,0,0.04)] hover:border-[#e63946]/30'
                ]"
              >
                {{ seat.col }}
              </button>
            </div>

            <div class="flex w-10 items-center justify-center">
              <span class="rounded-full bg-black/5 px-2.5 py-0.5 text-[10px] font-bold tracking-widest text-[#86868b]">{{ row }}</span>
            </div>

            <div class="flex gap-2.5">
              <button
                v-for="seat in getRowSeats(row).slice(3, 6)"
                :key="seat.id"
                :disabled="!seat.isAvailable"
                @click="selectSeat(seat)"
                class="relative flex h-10 w-10 transform-gpu items-center justify-center rounded-[10px] text-[12px] font-bold transition-all duration-200"
                :class="[
                  !seat.isAvailable
                    ? 'bg-[#e5e5ea] text-[#a1a1a6] shadow-[inset_0_2px_4px_rgba(0,0,0,0.06)] cursor-not-allowed'
                    : selectedSeats.includes(seat.id)
                      ? 'bg-gradient-to-b from-[#f43f5e] to-[#e63946] text-white scale-105 shadow-[0_6px_12px_rgba(230,57,70,0.35)] ring-2 ring-[#e63946]/30 z-20'
                      : 'bg-white border border-black/5 text-[#1d1d1f] shadow-[0_1px_4px_rgba(0,0,0,0.04)] hover:border-[#e63946]/30'
                ]"
              >
                {{ seat.col }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>