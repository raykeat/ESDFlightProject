<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePassengerSession } from '../composables/usePassengerSession'
import { useBookingDraft } from '../composables/useBookingDraft'

const route = useRoute()
const router = useRouter()
const { currentPassenger } = usePassengerSession()
const { bookingDraft, setBookingDraft } = useBookingDraft()

const isRoundTrip = computed(() => route.query.tripType === 'round-trip' && Boolean(route.query.returnFlightID))
const passengerCount = computed(() => Math.max(1, Number.parseInt(route.query.passengers, 10) || 1))

const flightSelection = computed(() => ({
  tripType: route.query.tripType || 'one-way',
  departingCountry: route.query.departingCountry || '',
  arrivingCountry: route.query.arrivingCountry || '',
  departureDate: route.query.departureDate || '',
  returnDate: route.query.returnDate || '',
  passengers: passengerCount.value,
  outboundFlightID: Number.parseInt(route.query.outboundFlightID || route.query.flightID, 10) || null,
  outboundFlightNumber: route.query.outboundFlightNumber || route.query.flightNumber || '',
  outboundOrigin: route.query.outboundOrigin || route.query.departingCountry || '',
  outboundDestination: route.query.outboundDestination || route.query.arrivingCountry || '',
  outboundPrice: Number.parseFloat(route.query.outboundPrice || route.query.price || 0) || 0,
  returnFlightID: Number.parseInt(route.query.returnFlightID || '', 10) || null,
  returnFlightNumber: route.query.returnFlightNumber || '',
  returnOrigin: route.query.returnOrigin || route.query.arrivingCountry || '',
  returnDestination: route.query.returnDestination || route.query.departingCountry || '',
  returnPrice: Number.parseFloat(route.query.returnPrice || 0) || 0,
}))

function formatDate(dateText) {
  if (!dateText) return '--'
  return new Date(`${dateText}T00:00:00`).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

function buildTravelerDrafts() {
  const existingTravellers = bookingDraft.value?.selectionKey === buildSelectionKey()
    ? bookingDraft.value.travelers || []
    : []

  return Array.from({ length: passengerCount.value }, (_, index) => {
    const existing = existingTravellers[index] || {}
    const isPrimary = index === 0

    return {
      id: existing.id || `traveller-${index + 1}`,
      isPrimary,
      firstName: isPrimary ? (currentPassenger.value?.FirstName || existing.firstName || '') : (existing.firstName || ''),
      lastName: isPrimary ? (currentPassenger.value?.LastName || existing.lastName || '') : (existing.lastName || ''),
      passportNumber: isPrimary ? String(currentPassenger.value?.PassportNumber || existing.passportNumber || '') : (existing.passportNumber || ''),
      nationality: existing.nationality || currentPassenger.value?.Nationality || '',
      label: isPrimary ? 'Primary passenger' : `Guest ${index}`,
    }
  })
}

function buildSelectionKey() {
  return [
    flightSelection.value.tripType,
    flightSelection.value.outboundFlightID,
    flightSelection.value.returnFlightID || 'one-way',
    flightSelection.value.departureDate,
    flightSelection.value.returnDate || '',
    passengerCount.value,
  ].join('|')
}

const travelers = ref(buildTravelerDrafts())
const contactDetails = ref({
  contactName: `${currentPassenger.value?.FirstName || ''} ${currentPassenger.value?.LastName || ''}`.trim(),
  email: currentPassenger.value?.Email || '',
})
const error = ref('')

watch(
  () => [currentPassenger.value?.passenger_id, route.fullPath],
  () => {
    travelers.value = buildTravelerDrafts()
    contactDetails.value = {
      contactName: `${currentPassenger.value?.FirstName || ''} ${currentPassenger.value?.LastName || ''}`.trim(),
      email: currentPassenger.value?.Email || '',
    }
  },
  { immediate: true }
)

const totalPrice = computed(() => {
  const outbound = flightSelection.value.outboundPrice * passengerCount.value
  const inbound = isRoundTrip.value ? flightSelection.value.returnPrice * passengerCount.value : 0
  return outbound + inbound
})

function validatePassengerDetails() {
  for (const traveller of travelers.value) {
    if (!traveller.firstName.trim() || !traveller.lastName.trim()) {
      return `Please enter the full name for ${traveller.isPrimary ? 'the primary passenger' : traveller.label}.`
    }

    if (!traveller.passportNumber.trim()) {
      return `Please enter the passport number for ${traveller.isPrimary ? 'the primary passenger' : traveller.label}.`
    }
  }

  if (!contactDetails.value.contactName.trim() || !contactDetails.value.email.trim()) {
    return 'Please complete the contact details before continuing.'
  }

  return ''
}

function goBack() {
  if (isRoundTrip.value) {
    router.push({
      path: '/search-results',
      query: {
        tripType: flightSelection.value.tripType,
        departingCountry: flightSelection.value.departingCountry,
        arrivingCountry: flightSelection.value.arrivingCountry,
        departureDate: flightSelection.value.departureDate,
        returnDate: flightSelection.value.returnDate,
        passengers: passengerCount.value,
        step: 'return',
        outboundFlightID: flightSelection.value.outboundFlightID,
        outboundFlightNumber: flightSelection.value.outboundFlightNumber,
        outboundOrigin: flightSelection.value.outboundOrigin,
        outboundDestination: flightSelection.value.outboundDestination,
        outboundPrice: flightSelection.value.outboundPrice,
      },
    })
    return
  }

  router.push({
    path: '/search-results',
    query: {
      tripType: flightSelection.value.tripType,
      departingCountry: flightSelection.value.departingCountry,
      arrivingCountry: flightSelection.value.arrivingCountry,
      departureDate: flightSelection.value.departureDate,
      returnDate: flightSelection.value.returnDate,
      passengers: passengerCount.value,
    },
  })
}

function continueToSeats() {
  error.value = validatePassengerDetails()
  if (error.value) return

  setBookingDraft({
    selectionKey: buildSelectionKey(),
    searchParams: {
      tripType: flightSelection.value.tripType,
      departingCountry: flightSelection.value.departingCountry,
      arrivingCountry: flightSelection.value.arrivingCountry,
      departureDate: flightSelection.value.departureDate,
      returnDate: flightSelection.value.returnDate,
      passengers: passengerCount.value,
    },
    flights: {
      outbound: {
        flightID: flightSelection.value.outboundFlightID,
        flightNumber: flightSelection.value.outboundFlightNumber,
        origin: flightSelection.value.outboundOrigin,
        destination: flightSelection.value.outboundDestination,
        price: flightSelection.value.outboundPrice,
      },
      return: isRoundTrip.value ? {
        flightID: flightSelection.value.returnFlightID,
        flightNumber: flightSelection.value.returnFlightNumber,
        origin: flightSelection.value.returnOrigin,
        destination: flightSelection.value.returnDestination,
        price: flightSelection.value.returnPrice,
      } : null,
    },
    travelers: travelers.value.map((traveller) => ({
      ...traveller,
      firstName: traveller.firstName.trim(),
      lastName: traveller.lastName.trim(),
      passportNumber: traveller.passportNumber.trim(),
      nationality: traveller.nationality?.trim?.() || '',
    })),
    contactDetails: {
      contactName: contactDetails.value.contactName.trim(),
      email: contactDetails.value.email.trim(),
    },
    seatAssignments: bookingDraft.value?.selectionKey === buildSelectionKey()
      ? bookingDraft.value.seatAssignments || { outbound: [], return: [] }
      : { outbound: [], return: [] },
  })

  router.push({
    path: '/flight-detail',
    query: {
      flightID: flightSelection.value.outboundFlightID,
      isReturn: 'false',
      tripType: flightSelection.value.tripType,
      departingCountry: flightSelection.value.departingCountry,
      arrivingCountry: flightSelection.value.arrivingCountry,
      departureDate: flightSelection.value.departureDate,
      returnDate: flightSelection.value.returnDate,
      passengers: passengerCount.value,
      outboundFlightID: flightSelection.value.outboundFlightID,
      outboundFlightNumber: flightSelection.value.outboundFlightNumber,
      outboundOrigin: flightSelection.value.outboundOrigin,
      outboundDestination: flightSelection.value.outboundDestination,
      outboundPrice: flightSelection.value.outboundPrice,
      returnFlightID: flightSelection.value.returnFlightID || '',
      returnFlightNumber: flightSelection.value.returnFlightNumber || '',
      returnOrigin: flightSelection.value.returnOrigin || '',
      returnDestination: flightSelection.value.returnDestination || '',
      returnPrice: flightSelection.value.returnPrice || '',
    },
  })
}
</script>

<template>
  <main class="relative min-h-screen overflow-hidden bg-[#f5f5f7] pb-20">
    <div class="pointer-events-none absolute inset-0">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_90%_12%,rgba(230,57,70,0.16),transparent_32%),radial-gradient(circle_at_8%_78%,rgba(29,29,31,0.05),transparent_30%)]"></div>
    </div>

    <div class="relative mx-auto max-w-[1400px] px-6 py-10">
      <div class="rounded-[34px] border border-white/80 bg-white/80 px-8 py-8 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur-2xl">
        <div class="mx-auto mb-10 max-w-[1200px]">
          <div class="grid grid-cols-3 items-start gap-6">
            <div class="flex items-start gap-3">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#e63946] text-sm font-bold text-white shadow-[0_10px_18px_rgba(230,57,70,0.22)]">1</div>
              <div class="min-w-0 flex-1 pt-1">
                <div class="h-1 rounded-full bg-[#e63946]"></div>
                <p class="mt-3 text-sm font-semibold text-[#e63946]">Fill in your info</p>
              </div>
            </div>
            <div class="flex items-start gap-3">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#eef0f5] text-sm font-bold text-[#7d8594]">2</div>
              <div class="min-w-0 flex-1 pt-1">
                <div class="h-1 rounded-full bg-[#d9dde6]"></div>
                <p class="mt-3 text-sm font-semibold text-[#1d1d1f]">Choose your seat</p>
              </div>
            </div>
            <div class="flex items-start gap-3">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#eef0f5] text-sm font-bold text-[#7d8594]">3</div>
              <div class="min-w-0 flex-1 pt-1">
                <div class="h-1 rounded-full bg-[#d9dde6]"></div>
                <p class="mt-3 text-sm font-semibold text-[#1d1d1f]">Finalise your payment</p>
              </div>
            </div>
          </div>
        </div>

        <div class="mx-auto grid max-w-[1200px] gap-10 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div class="space-y-8">
            <div class="rounded-[28px] border border-black/8 bg-white p-7 shadow-[0_16px_36px_rgba(15,23,42,0.04)]">
              <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h1 class="text-4xl font-bold tracking-[-0.04em] text-[#1d1d1f]">
                    Trip to {{ flightSelection.arrivingCountry }}
                  </h1>
                  <p class="mt-2 text-sm text-[#6e6e73]">Review your selected itinerary before assigning seats.</p>
                </div>
                <button class="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-[#e63946] transition hover:border-[#e63946]/30 hover:bg-[#fff5f5]" @click="goBack">
                  Change Flight
                </button>
              </div>

              <div class="space-y-4 rounded-[24px] border border-black/8 bg-[#fcfcfd] p-5">
                <div class="flex flex-wrap items-center gap-3 text-sm text-[#1d1d1f]">
                  <span class="font-bold">{{ flightSelection.outboundOrigin }}</span>
                  <span>→</span>
                  <span class="font-bold">{{ flightSelection.outboundDestination }}</span>
                  <span class="text-black/20">|</span>
                  <span>{{ formatDate(flightSelection.departureDate) }}</span>
                  <span class="text-black/20">|</span>
                  <span>{{ flightSelection.outboundFlightNumber }}</span>
                </div>
                <div v-if="isRoundTrip" class="flex flex-wrap items-center gap-3 text-sm text-[#1d1d1f]">
                  <span class="font-bold">{{ flightSelection.returnOrigin }}</span>
                  <span>→</span>
                  <span class="font-bold">{{ flightSelection.returnDestination }}</span>
                  <span class="text-black/20">|</span>
                  <span>{{ formatDate(flightSelection.returnDate) }}</span>
                  <span class="text-black/20">|</span>
                  <span>{{ flightSelection.returnFlightNumber }}</span>
                </div>
              </div>
            </div>

            <section class="rounded-[28px] border border-black/8 bg-white p-7 shadow-[0_16px_36px_rgba(15,23,42,0.04)]">
              <h2 class="text-3xl font-bold tracking-[-0.03em] text-[#1d1d1f]">Who's travelling?</h2>
              <div class="mt-5 rounded-[20px] bg-[#f7f7fb] p-5 text-sm text-[#4b5563]">
                <p><span class="font-bold">Names must match ID</span> Please enter the name exactly as it appears on the passport used for travel.</p>
                <p class="mt-3"><span class="font-bold">6-month validity</span> Make sure every passenger passport is valid for at least 6 months after the trip ends.</p>
              </div>

              <div class="mt-5 space-y-4">
                <article
                  v-for="(traveller, index) in travelers"
                  :key="traveller.id"
                  class="rounded-[22px] border border-black/8 bg-white p-5"
                >
                  <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p class="text-xl font-bold text-[#1d1d1f]">
                        {{ traveller.isPrimary ? `${traveller.firstName || 'Primary'} ${traveller.lastName || 'Passenger'}` : `Passenger ${index + 1}` }}
                      </p>
                      <p class="text-sm text-[#6e6e73]">
                        {{ traveller.isPrimary ? 'Primary passenger' : 'Guest passenger' }}
                      </p>
                    </div>
                    <span class="rounded-full bg-[#fff1f2] px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#e63946]">
                      {{ traveller.isPrimary ? 'Account holder' : `Guest ${index}` }}
                    </span>
                  </div>

                  <div class="grid gap-4 md:grid-cols-2">
                    <label class="block">
                      <span class="mb-2 block text-xs font-bold uppercase tracking-[0.12em] text-[#6e6e73]">First Name</span>
                      <input
                        v-model="traveller.firstName"
                        type="text"
                        class="w-full rounded-2xl border border-black/10 bg-[#fbfbfd] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/40 focus:bg-white"
                      />
                    </label>
                    <label class="block">
                      <span class="mb-2 block text-xs font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Last Name</span>
                      <input
                        v-model="traveller.lastName"
                        type="text"
                        class="w-full rounded-2xl border border-black/10 bg-[#fbfbfd] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/40 focus:bg-white"
                      />
                    </label>
                  </div>

                  <div class="mt-4 grid gap-4 md:grid-cols-2">
                    <label class="block">
                      <span class="mb-2 block text-xs font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Passport Number</span>
                      <input
                        v-model="traveller.passportNumber"
                        type="text"
                        class="w-full rounded-2xl border border-black/10 bg-[#fbfbfd] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/40 focus:bg-white"
                      />
                    </label>
                    <label class="block">
                      <span class="mb-2 block text-xs font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Nationality</span>
                      <input
                        v-model="traveller.nationality"
                        type="text"
                        class="w-full rounded-2xl border border-black/10 bg-[#fbfbfd] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/40 focus:bg-white"
                      />
                    </label>
                  </div>
                </article>
              </div>
            </section>

            <section class="rounded-[28px] border border-black/8 bg-white p-7 shadow-[0_16px_36px_rgba(15,23,42,0.04)]">
              <h2 class="text-3xl font-bold tracking-[-0.03em] text-[#1d1d1f]">Contact details</h2>
              <div class="mt-5 grid gap-4 md:grid-cols-2">
                <label class="block">
                  <span class="mb-2 block text-xs font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Contact Name</span>
                  <input
                    v-model="contactDetails.contactName"
                    type="text"
                    class="w-full rounded-2xl border border-black/10 bg-[#fbfbfd] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/40 focus:bg-white"
                  />
                </label>
                <label class="block">
                  <span class="mb-2 block text-xs font-bold uppercase tracking-[0.12em] text-[#6e6e73]">Email</span>
                  <input
                    v-model="contactDetails.email"
                    type="email"
                    class="w-full rounded-2xl border border-black/10 bg-[#fbfbfd] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/40 focus:bg-white"
                  />
                </label>
              </div>
            </section>

            <div v-if="error" class="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-600">
              {{ error }}
            </div>

            <div class="rounded-[28px] border border-black/8 bg-white p-6 shadow-[0_16px_36px_rgba(15,23,42,0.04)]">
              <p class="text-sm text-[#4b5563]">
                I have read and agreed to the Blaze Air booking terms and conditions.
              </p>
              <div class="mt-5 flex items-center justify-between gap-4 rounded-3xl border border-black/8 bg-[#fcfcfd] p-5">
                <div>
                  <p class="text-sm font-semibold text-[#6e6e73]">Total</p>
                  <p class="text-4xl font-bold tracking-[-0.03em] text-[#e63946]">S$ {{ totalPrice.toFixed(2) }}</p>
                </div>
                <button class="min-w-[240px] rounded-2xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-8 py-4 text-lg font-bold text-white shadow-[0_16px_30px_rgba(230,57,70,0.24)] transition hover:brightness-105" @click="continueToSeats">
                  Next
                </button>
              </div>
            </div>
          </div>

          <aside class="lg:pt-24">
            <div class="sticky top-6 rounded-[28px] border border-black/8 bg-white p-7 shadow-[0_24px_60px_rgba(15,23,42,0.08)]">
              <h2 class="text-2xl font-bold text-[#1d1d1f]">Price details</h2>
              <div class="mt-6 flex items-center justify-between text-lg font-semibold text-[#1d1d1f]">
                <span>Tickets ({{ passengerCount }} {{ passengerCount > 1 ? 'adults' : 'adult' }})</span>
                <span>S$ {{ totalPrice.toFixed(2) }}</span>
              </div>

              <div class="mt-8 space-y-3 border-b border-dashed border-black/10 pb-8 text-[#6e6e73]">
                <div class="flex items-center justify-between">
                  <span>Personal item</span>
                  <span>Free</span>
                </div>
                <div class="flex items-center justify-between">
                  <span>Carry-on baggage</span>
                  <span>Free</span>
                </div>
                <div class="flex items-center justify-between">
                  <span>Checked baggage</span>
                  <span>Free</span>
                </div>
              </div>

              <div class="mt-8 flex items-end justify-between gap-4">
                <span class="text-2xl font-bold text-[#1d1d1f]">Total</span>
                <span class="text-4xl font-bold tracking-[-0.04em] text-[#e63946]">S$ {{ totalPrice.toFixed(2) }}</span>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  </main>
</template>
