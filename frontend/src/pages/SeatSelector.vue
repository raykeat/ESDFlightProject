<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  flightId: {
    type: [Number, String],
    required: true,
  },
  maxSeats: {
    type: Number,
    default: 1,
  },
  seatsData: {
    type: Array,
    default: () => [],
  },
  travelers: {
    type: Array,
    default: () => [],
  },
  initialAssignments: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['seatSelected'])

const seats = ref([])
const loading = ref(true)
const hasSeatMap = ref(false)
const activeTravelerIndex = ref(0)
const seatAssignments = ref([])

function mapSeats(seatData) {
  if (!Array.isArray(seatData) || seatData.length === 0) return []

  return seatData
    .map((seat) => {
      const seatNumber = seat.SeatNumber || seat.seatNumber || ''
      const rowMatch = seatNumber.match(/\d+/)
      const colMatch = seatNumber.match(/[A-Za-z]+/)

      return {
        id: seatNumber,
        row: rowMatch ? Number.parseInt(rowMatch[0], 10) : 0,
        col: colMatch ? colMatch[0] : '',
        status: String(seat.Status || seat.status || '').toLowerCase(),
      }
    })
    .filter((seat) => seat.id)
}

function buildInitialAssignments() {
  return Array.from({ length: props.maxSeats }, (_, index) => props.initialAssignments[index] || '')
}

function getTravelerName(traveler, index) {
  const fullName = `${traveler?.firstName || ''} ${traveler?.lastName || ''}`.trim()
  return fullName || `Passenger ${index + 1}`
}

watch(
  () => props.seatsData,
  (newSeatData) => {
    seats.value = mapSeats(newSeatData)
    hasSeatMap.value = Array.isArray(newSeatData) && newSeatData.length > 0
    loading.value = false
  },
  { immediate: true }
)

watch(
  () => props.initialAssignments,
  () => {
    seatAssignments.value = buildInitialAssignments()
  },
  { immediate: true, deep: true }
)

const uniqueRows = computed(() => {
  const rows = [...new Set(seats.value.map((seat) => seat.row).filter(Boolean))]
  return rows.sort((a, b) => a - b)
})

const travelersWithAssignments = computed(() =>
  Array.from({ length: props.maxSeats }, (_, index) => ({
    ...props.travelers[index],
    displayName: getTravelerName(props.travelers[index], index),
    seatNumber: seatAssignments.value[index] || '',
    index,
  }))
)

function getRowSeats(rowNum) {
  return seats.value
    .filter((seat) => seat.row === rowNum)
    .sort((a, b) => a.col.localeCompare(b.col))
}

function getAssignedTravelerIndex(seatId) {
  return seatAssignments.value.findIndex((assignment) => assignment === seatId)
}

function isSeatAvailable(seat) {
  return seat.status === 'available'
}

function isSeatHeld(seat) {
  return seat.status === 'hold'
}

function emitAssignments() {
  emit('seatSelected', [...seatAssignments.value])
}

function clearAssignment(index) {
  seatAssignments.value[index] = ''
  emitAssignments()
}

function selectTraveler(index) {
  activeTravelerIndex.value = index
}

function selectSeat(seat) {
  if (!isSeatAvailable(seat)) return

  const currentlyAssignedIndex = getAssignedTravelerIndex(seat.id)
  if (currentlyAssignedIndex === activeTravelerIndex.value) {
    seatAssignments.value[activeTravelerIndex.value] = ''
    emitAssignments()
    return
  }

  if (currentlyAssignedIndex !== -1) {
    seatAssignments.value[currentlyAssignedIndex] = ''
  }

  seatAssignments.value[activeTravelerIndex.value] = seat.id
  emitAssignments()

  const nextEmptyIndex = seatAssignments.value.findIndex((assignment) => !assignment)
  if (nextEmptyIndex !== -1) {
    activeTravelerIndex.value = nextEmptyIndex
  }
}
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="mb-4 flex flex-wrap items-center justify-center gap-5 rounded-full border border-black/5 bg-white/60 px-4 py-2 shadow-[0_8px_16px_rgba(0,0,0,0.03)] backdrop-blur-md">
      <div class="flex items-center gap-2">
        <div class="h-3 w-3 rounded border border-black/10 bg-white"></div>
        <span class="text-[11px] font-bold uppercase tracking-[0.1em] text-[#6e6e73]">Available</span>
      </div>
      <div class="flex items-center gap-2">
        <div class="h-3 w-3 rounded bg-gradient-to-br from-[#f43f5e] to-[#e63946] shadow-[0_2px_8px_rgba(230,57,70,0.3)]"></div>
        <span class="text-[11px] font-bold uppercase tracking-[0.1em] text-[#1d1d1f]">Selected</span>
      </div>
      <div class="flex items-center gap-2">
        <div class="h-3 w-3 rounded bg-[#e5e5ea]"></div>
        <span class="text-[11px] font-bold uppercase tracking-[0.1em] text-[#a1a1a6]">Occupied</span>
      </div>
      <div class="flex items-center gap-2">
        <div class="h-3 w-3 rounded bg-[#111827]"></div>
        <span class="text-[11px] font-bold uppercase tracking-[0.1em] text-[#4b5563]">Awaiting Payment</span>
      </div>
    </div>

    <div v-if="loading" class="flex flex-1 flex-col items-center justify-center py-16">
      <div class="relative flex h-12 w-12 items-center justify-center">
        <div class="absolute h-full w-full animate-ping rounded-full border-[2px] border-[#e63946]/20"></div>
        <div class="h-6 w-6 animate-spin rounded-full border-[3px] border-[#e63946] border-t-transparent"></div>
      </div>
      <p class="mt-4 text-[10px] font-bold uppercase tracking-[0.2em] text-[#6e6e73]">Configuring Cabin...</p>
    </div>

    <div v-else-if="!hasSeatMap" class="flex flex-1 flex-col items-center justify-center rounded-[22px] border border-dashed border-[#e63946]/20 bg-white/70 px-6 py-12 text-center">
      <p class="text-xs font-bold uppercase tracking-[0.16em] text-[#e63946]">Seat Map Unavailable</p>
      <p class="mt-3 max-w-md text-sm text-[#6e6e73]">
        This flight does not have any seat records loaded yet, so the cabin is not actually fully occupied.
      </p>
      <p class="mt-2 text-sm text-[#6e6e73]">
        Reinitialize the seats database after updating the seed data to make the available seats appear.
      </p>
    </div>

    <div v-else class="grid min-h-0 flex-1 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div class="min-h-0 rounded-[22px] border border-black/6 bg-[#f8f8fa] px-6 py-5">
        <div class="mb-3 text-center">
          <p class="text-[9px] font-bold uppercase tracking-[0.2em] text-[#a1a1a6]">Cabin Front</p>
        </div>

        <div class="mx-auto w-fit overflow-auto pr-2">
          <div class="relative mx-auto w-fit">
            <div class="absolute left-1/2 top-0 h-full w-10 -translate-x-1/2 bg-[linear-gradient(to_bottom,rgba(0,0,0,0.025)_50%,transparent_50%)] bg-[length:100%_22px]"></div>

            <div
              v-for="row in uniqueRows"
              :key="row"
              class="relative z-10 mx-auto mb-2 flex w-fit items-center justify-between gap-2.5 last:mb-0"
            >
              <div class="flex gap-2.5">
                <button
                  v-for="seat in getRowSeats(row).slice(0, 3)"
                  :key="seat.id"
                  :disabled="!isSeatAvailable(seat)"
                  @click="selectSeat(seat)"
                  class="relative flex h-10 w-10 items-center justify-center rounded-[10px] text-[12px] font-bold transition-all duration-200"
                  :title="isSeatHeld(seat) ? 'Reserved while another customer completes payment' : ''"
                  :class="[
                    isSeatHeld(seat)
                      ? 'cursor-not-allowed bg-[#111827] text-white shadow-[0_6px_12px_rgba(15,23,42,0.18)]'
                      : !isSeatAvailable(seat)
                        ? 'cursor-not-allowed bg-[#e5e5ea] text-[#a1a1a6]'
                      : getAssignedTravelerIndex(seat.id) !== -1
                        ? 'z-20 scale-105 bg-gradient-to-b from-[#f43f5e] to-[#e63946] text-white shadow-[0_6px_12px_rgba(230,57,70,0.35)] ring-2 ring-[#e63946]/30'
                        : 'bg-white text-[#1d1d1f] shadow-[0_1px_4px_rgba(0,0,0,0.04)] hover:border-[#e63946]/30'
                  ]"
                >
                  {{ seat.id }}
                  <span
                    v-if="getAssignedTravelerIndex(seat.id) !== -1"
                    class="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-white text-[9px] font-bold text-[#e63946]"
                  >
                    {{ getAssignedTravelerIndex(seat.id) + 1 }}
                  </span>
                </button>
              </div>

              <div class="flex w-10 items-center justify-center">
                <span class="rounded-full bg-black/5 px-2.5 py-0.5 text-[10px] font-bold tracking-widest text-[#86868b]">{{ row }}</span>
              </div>

              <div class="flex gap-2.5">
                <button
                  v-for="seat in getRowSeats(row).slice(3, 6)"
                  :key="seat.id"
                  :disabled="!isSeatAvailable(seat)"
                  @click="selectSeat(seat)"
                  class="relative flex h-10 w-10 items-center justify-center rounded-[10px] text-[12px] font-bold transition-all duration-200"
                  :title="isSeatHeld(seat) ? 'Reserved while another customer completes payment' : ''"
                  :class="[
                    isSeatHeld(seat)
                      ? 'cursor-not-allowed bg-[#111827] text-white shadow-[0_6px_12px_rgba(15,23,42,0.18)]'
                      : !isSeatAvailable(seat)
                        ? 'cursor-not-allowed bg-[#e5e5ea] text-[#a1a1a6]'
                      : getAssignedTravelerIndex(seat.id) !== -1
                        ? 'z-20 scale-105 bg-gradient-to-b from-[#f43f5e] to-[#e63946] text-white shadow-[0_6px_12px_rgba(230,57,70,0.35)] ring-2 ring-[#e63946]/30'
                        : 'bg-white text-[#1d1d1f] shadow-[0_1px_4px_rgba(0,0,0,0.04)] hover:border-[#e63946]/30'
                  ]"
                >
                  {{ seat.id }}
                  <span
                    v-if="getAssignedTravelerIndex(seat.id) !== -1"
                    class="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-white text-[9px] font-bold text-[#e63946]"
                  >
                    {{ getAssignedTravelerIndex(seat.id) + 1 }}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <aside class="rounded-[22px] border border-black/8 bg-[#fcfcfd] p-5">
        <div class="border-b border-[#e7ecf6] pb-4">
          <p class="text-xs font-bold uppercase tracking-[0.16em] text-[#e63946]">Passenger Seat Assignment</p>
          <p class="mt-2 text-sm text-[#6e6e73]">Choose a traveller first, then click a seat in the cabin map.</p>
        </div>

        <div class="mt-5 space-y-3">
          <button
            v-for="traveler in travelersWithAssignments"
            :key="traveler.id || traveler.index"
            class="w-full rounded-[20px] border px-4 py-4 text-left transition"
            :class="traveler.index === activeTravelerIndex
              ? 'border-[#e63946]/30 bg-[#fff5f5] shadow-[0_12px_24px_rgba(230,57,70,0.10)]'
              : 'border-black/8 bg-white hover:border-[#e63946]/20'"
            @click="selectTraveler(traveler.index)"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-start gap-3">
                <div class="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg border border-[#f3c7cc] bg-white text-sm font-bold text-[#e63946]">
                  {{ traveler.index + 1 }}
                </div>
                <div>
                  <p class="text-base font-bold text-[#1d1d1f]">{{ traveler.displayName }}</p>
                  <p class="mt-1 text-sm" :class="traveler.seatNumber ? 'text-[#e63946]' : 'text-[#6e6e73]'">
                    {{ traveler.seatNumber || 'Seat not selected' }}
                  </p>
                </div>
              </div>

              <button
                v-if="traveler.seatNumber"
                type="button"
                class="text-lg leading-none text-[#a1a1a6]"
                @click.stop="clearAssignment(traveler.index)"
              >
                ×
              </button>
            </div>
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>
