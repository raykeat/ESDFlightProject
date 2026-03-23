<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { updatePassengerAccount } from '../services/passengerApi'
import { usePassengerSession } from '../composables/usePassengerSession'

const router = useRouter()
const { currentPassenger, isSignedIn, setPassenger } = usePassengerSession()

const form = ref({
  firstName: '',
  lastName: '',
  passportNumber: '',
  email: '',
  nationality: '',
})

const busy = ref(false)
const successMessage = ref('')
const errorMessage = ref('')

onMounted(() => {
  if (!isSignedIn.value) {
    router.replace('/auth')
    return
  }

  form.value = {
    firstName: currentPassenger.value?.FirstName || '',
    lastName: currentPassenger.value?.LastName || '',
    passportNumber: String(currentPassenger.value?.PassportNumber || ''),
    email: currentPassenger.value?.Email || '',
    nationality: currentPassenger.value?.Nationality || '',
  }
})

function parsePassportNumber(rawValue) {
  if (!/^\d+$/.test(rawValue)) {
    return null
  }

  const numeric = Number(rawValue)
  if (!Number.isSafeInteger(numeric) || numeric <= 0) {
    return null
  }

  return numeric
}

async function handleUpdateProfile() {
  successMessage.value = ''
  errorMessage.value = ''
  busy.value = true

  try {
    const passengerId = currentPassenger.value?.passenger_id
    if (!passengerId) {
      throw new Error('No signed-in passenger session found.')
    }

    const passportNumber = parsePassportNumber(form.value.passportNumber.trim())
    if (!passportNumber) {
      throw new Error('Use a numeric passport number within JavaScript safe integer range.')
    }

    const payload = {
      FirstName: form.value.firstName.trim(),
      LastName: form.value.lastName.trim(),
      PassportNumber: passportNumber,
      Email: form.value.email.trim(),
      Nationality: form.value.nationality.trim(),
    }

    const updatedPassenger = await updatePassengerAccount(passengerId, payload)
    setPassenger(updatedPassenger)
    successMessage.value = 'Profile updated successfully.'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to update profile.'
  } finally {
    busy.value = false
  }
}

</script>

<template>
  <main class="min-h-screen px-6 py-8 md:px-10 lg:px-16">
    <section class="mx-auto max-w-[980px]">
      <section class="animate__animated animate__fadeInUp mt-2 rounded-[34px] border border-black/5 bg-white/90 p-6 shadow-[0_22px_52px_rgba(15,23,42,0.08)] backdrop-blur-2xl md:p-8">
        <h1 class="text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">View profile</h1>
        <p class="mt-3 max-w-2xl text-sm text-[#6e6e73] md:text-base">Update your passenger account details. Changes will reflect in your header profile immediately.</p>

        <form class="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3" @submit.prevent="handleUpdateProfile">
          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">First Name</span>
            <input
              v-model="form.firstName"
              required
              type="text"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>

          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Last Name</span>
            <input
              v-model="form.lastName"
              required
              type="text"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>

          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Passport Number</span>
            <input
              v-model="form.passportNumber"
              required
              type="text"
              inputmode="numeric"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>

          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Email</span>
            <input
              v-model="form.email"
              required
              type="email"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>

          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Nationality</span>
            <input
              v-model="form.nationality"
              required
              type="text"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>

          <button
            type="submit"
            :disabled="busy"
            class="md:col-span-2 lg:col-span-3 mt-2 w-full rounded-2xl bg-[#1d1d1f] px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-black hover:shadow-[0_8px_24px_rgba(29,29,31,0.35)] disabled:cursor-not-allowed disabled:opacity-70"
          >
            {{ busy ? 'Updating profile...' : 'Save Changes' }}
          </button>
        </form>

        <p v-if="successMessage" class="mt-4 text-sm font-medium text-emerald-700">{{ successMessage }}</p>
        <p v-if="errorMessage" class="mt-4 text-sm font-medium text-red-600">{{ errorMessage }}</p>
      </section>
    </section>
  </main>
</template>
