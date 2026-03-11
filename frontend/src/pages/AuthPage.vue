<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createPassengerAccount, loginPassenger, getPassengerById } from '../services/passengerApi'
import { usePassengerSession } from '../composables/usePassengerSession'

const router = useRouter()
const { setPassenger } = usePassengerSession()

const activeTab = ref('signin')
const busy = ref(false)
const errorMessage = ref('')

const signInForm = ref({
  email: '',
  password: '',
})

const createForm = ref({
  firstName: '',
  lastName: '',
  passportNumber: '',
  email: '',
  password: '',
  nationality: '',
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

async function handleSignIn() {
  errorMessage.value = ''
  busy.value = true

  try {
    const email = signInForm.value.email.trim()
    const password = signInForm.value.password.trim()

    if (!email) {
      throw new Error('Please enter your email.')
    }
    if (!password) {
      throw new Error('Please enter your password.')
    }

    const loginResult = await loginPassenger(email, password)
    const passengerId = loginResult.passenger_id
    if (!passengerId) {
      throw new Error('Login failed: no passenger ID returned.')
    }

    const fullPassengerData = await getPassengerById(passengerId)
    setPassenger(fullPassengerData)
    router.push('/')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to sign in.'
  } finally {
    busy.value = false
  }
}

async function handleCreateAccount() {
  errorMessage.value = ''
  busy.value = true

  try {
    const passportNumber = parsePassportNumber(createForm.value.passportNumber.trim())
    if (!passportNumber) {
      throw new Error('Use a numeric passport number within JavaScript safe integer range.')
    }

    const password = createForm.value.password.trim()
    if (!password) {
      throw new Error('Please enter a password.')
    }

    const payload = {
      FirstName: createForm.value.firstName.trim(),
      LastName: createForm.value.lastName.trim(),
      PassportNumber: passportNumber,
      Email: createForm.value.email.trim(),
      Password: password,
      Nationality: createForm.value.nationality.trim(),
    }

    const createdPassenger = await createPassengerAccount(payload)
    setPassenger(createdPassenger)
    router.push('/')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to create account.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="min-h-screen px-6 py-8 md:px-10 lg:px-16">
    <section class="mx-auto max-w-[980px]">
      <header class="animate__animated animate__fadeInDown flex items-center justify-between rounded-[28px] border border-black/5 bg-white/80 px-5 py-3 backdrop-blur-xl md:px-7">
        <RouterLink to="/" class="text-sm font-semibold tracking-[0.18em] text-[#1d1d1f]">BLAZE AIR</RouterLink>
        <span class="text-xs font-semibold uppercase tracking-[0.15em] text-[#6e6e73]">Passenger Access</span>
      </header>

      <section class="animate__animated animate__fadeInUp mt-10 rounded-[34px] border border-black/5 bg-white/90 p-6 shadow-[0_22px_52px_rgba(15,23,42,0.08)] backdrop-blur-2xl md:p-8">
        <h1 class="text-4xl font-semibold tracking-[-0.03em] text-[#1d1d1f] md:text-5xl">Welcome aboard</h1>
        <p class="mt-3 max-w-2xl text-sm text-[#6e6e73] md:text-base">Sign in or create your passenger account using your email and password.</p>

        <div class="mt-6 inline-flex rounded-full border border-black/10 bg-[#f5f5f7] p-1">
          <button
            class="rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.12em] transition"
            :class="activeTab === 'signin' ? 'bg-[#1d1d1f] text-white' : 'text-[#6e6e73] hover:text-[#1d1d1f]'"
            @click="activeTab = 'signin'"
          >
            Sign In
          </button>
          <button
            class="rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.12em] transition"
            :class="activeTab === 'create' ? 'bg-[#1d1d1f] text-white' : 'text-[#6e6e73] hover:text-[#1d1d1f]'"
            @click="activeTab = 'create'"
          >
            Create Account
          </button>
        </div>

        <form v-if="activeTab === 'signin'" class="mt-8 grid gap-4 md:grid-cols-2" @submit.prevent="handleSignIn">
          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Email</span>
            <input
              v-model="signInForm.email"
              required
              type="email"
              placeholder="name@example.com"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>
          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Password</span>
            <input
              v-model="signInForm.password"
              required
              type="password"
              placeholder="Enter your password"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>

          <button
            type="submit"
            :disabled="busy"
            class="md:col-span-2 mt-2 w-full rounded-2xl bg-[#1d1d1f] px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-black hover:shadow-[0_8px_24px_rgba(29,29,31,0.35)] disabled:cursor-not-allowed disabled:opacity-70"
          >
            {{ busy ? 'Signing in...' : 'Sign In' }}
          </button>
        </form>

        <form v-else class="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3" @submit.prevent="handleCreateAccount">
          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">First Name</span>
            <input
              v-model="createForm.firstName"
              required
              type="text"
              placeholder="Avery"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>
          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Last Name</span>
            <input
              v-model="createForm.lastName"
              required
              type="text"
              placeholder="Morgan"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>
          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Passport Number</span>
            <input
              v-model="createForm.passportNumber"
              required
              type="text"
              inputmode="numeric"
              placeholder="987654321123456"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>
          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Email</span>
            <input
              v-model="createForm.email"
              required
              type="email"
              placeholder="name@example.com"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>
          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Nationality</span>
            <input
              v-model="createForm.nationality"
              required
              type="text"
              placeholder="Philippines"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>
          <label>
            <span class="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73]">Password</span>
            <input
              v-model="createForm.password"
              required
              type="password"
              placeholder="Create a password"
              class="w-full rounded-2xl border border-black/10 bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition focus:border-[#e63946]/65 focus:ring-2 focus:ring-[#e63946]/20"
            />
          </label>

          <button
            type="submit"
            :disabled="busy"
            class="md:col-span-2 lg:col-span-3 mt-2 w-full rounded-2xl bg-[#1d1d1f] px-5 py-3 text-sm font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-black hover:shadow-[0_8px_24px_rgba(29,29,31,0.35)] disabled:cursor-not-allowed disabled:opacity-70"
          >
            {{ busy ? 'Creating account...' : 'Create Account' }}
          </button>
        </form>

        <p v-if="errorMessage" class="mt-4 text-sm font-medium text-red-600">{{ errorMessage }}</p>
      </section>
    </section>
  </main>
</template>
