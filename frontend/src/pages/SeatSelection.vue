<script setup>
import { ref, onMounted } from "vue"
import axios from "axios"
import { useRoute, useRouter } from "vue-router"

const route = useRoute()
const router = useRouter()

const flightID = route.query.flightID
const seats = ref([])
const selectedSeat = ref(null)

async function loadSeats() {
  const res = await axios.get(`http://localhost:5003/seats/${flightID}`)
  seats.value = res.data
}

function selectSeat(seat) {
  if (seat.Status !== "Available") return
  selectedSeat.value = seat
}

async function confirmSeat() {
  if (!selectedSeat.value) return

  await axios.post("http://localhost:5003/seats/hold", {
    seatID: selectedSeat.value.SeatID,
    passengerID: 1
  })

  router.push({
    path: "/booking-confirmation",
    query: {
      seatID: selectedSeat.value.SeatID
    }
  })
}

onMounted(loadSeats)
</script>

<template>
  <div class="seat-container">
    <h1>Select Your Seat</h1>

    <div class="seat-grid">
      <div
        v-for="seat in seats"
        :key="seat.SeatID"
        class="seat"
        :class="seat.Status"
        @click="selectSeat(seat)"
      >
        {{ seat.SeatNumber }}
      </div>
    </div>

    <button
      v-if="selectedSeat"
      class="confirm-btn"
      @click="confirmSeat"
    >
      Confirm Seat {{ selectedSeat.SeatNumber }}
    </button>
  </div>
</template>

<style>
.seat-container {
  text-align: center;
}

.seat-grid {
  display: grid;
  grid-template-columns: repeat(6, 60px);
  gap: 10px;
  justify-content: center;
  margin-top: 20px;
}

.seat {
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
}

.Available {
  background: #4CAF50;
  color: white;
}

.Unavailable {
  background: #999;
  color: white;
}

.Hold {
  background: orange;
  color: white;
}

.confirm-btn {
  margin-top: 20px;
  padding: 10px 20px;
}
</style>