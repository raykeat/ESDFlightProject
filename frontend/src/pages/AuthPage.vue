<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createPassengerAccount, loginPassenger, getPassengerById } from '../services/passengerApi'
import { usePassengerSession } from '../composables/usePassengerSession'

const router = useRouter()
const { setPassenger } = usePassengerSession()

const activeTab    = ref('signin')
const busy         = ref(false)
const errorMessage = ref('')

const signInForm = ref({ email: '', password: '' })
const createForm = ref({ firstName: '', lastName: '', passportNumber: '', email: '', password: '', nationality: '' })

function parsePassportNumber(rawValue) {
  if (!/^\d+$/.test(rawValue)) return null
  const numeric = Number(rawValue)
  if (!Number.isSafeInteger(numeric) || numeric <= 0) return null
  return numeric
}

async function handleSignIn() {
  errorMessage.value = ''
  busy.value = true
  try {
    const email    = signInForm.value.email.trim()
    const password = signInForm.value.password.trim()
    if (!email)    throw new Error('Please enter your email.')
    if (!password) throw new Error('Please enter your password.')
    const loginResult = await loginPassenger(email, password)
    const passengerId = loginResult.passenger_id
    if (!passengerId) throw new Error('Login failed: no passenger ID returned.')
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
    if (!passportNumber) throw new Error('Use a numeric passport number within JavaScript safe integer range.')
    const password = createForm.value.password.trim()
    if (!password) throw new Error('Please enter a password.')
    const payload = {
      FirstName:      createForm.value.firstName.trim(),
      LastName:       createForm.value.lastName.trim(),
      PassportNumber: passportNumber,
      Email:          createForm.value.email.trim(),
      Password:       password,
      Nationality:    createForm.value.nationality.trim(),
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
  <main style="min-height:100vh; background:radial-gradient(circle at 12% 6%, #ffffff 0%, #f5f5f7 48%, #ececf1 100%); padding:32px 24px;">
    <div style="max-width:960px; margin:0 auto;">

      <!-- Auth card -->
      <div style="background:rgba(255,255,255,0.92); backdrop-filter:blur(24px); border:1px solid rgba(0,0,0,0.06); border-radius:34px; padding:40px 48px; box-shadow:0 22px 52px rgba(15,23,42,0.08);">

        <h1 style="font-size:44px; font-weight:700; letter-spacing:-0.03em; color:#1d1d1f; margin:0 0 10px;">Welcome aboard</h1>
        <p style="font-size:15px; color:#6e6e73; margin:0 0 28px;">Sign in or create your passenger account using your email and password.</p>

        <!-- Tab switcher -->
        <div style="display:inline-flex; background:#f5f5f7; border:1px solid rgba(0,0,0,0.08); border-radius:100px; padding:4px; margin-bottom:32px;">
          <button
            @click="activeTab = 'signin'; errorMessage = ''"
            :style="{
              padding: '8px 22px', borderRadius: '100px', border: 'none',
              fontSize: '12px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase',
              cursor: 'pointer', transition: 'all 0.2s',
              background: activeTab === 'signin' ? '#1d1d1f' : 'transparent',
              color: activeTab === 'signin' ? 'white' : '#6e6e73',
            }"
          >Sign In</button>
          <button
            @click="activeTab = 'create'; errorMessage = ''"
            :style="{
              padding: '8px 22px', borderRadius: '100px', border: 'none',
              fontSize: '12px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase',
              cursor: 'pointer', transition: 'all 0.2s',
              background: activeTab === 'create' ? '#1d1d1f' : 'transparent',
              color: activeTab === 'create' ? 'white' : '#6e6e73',
            }"
          >Create Account</button>
        </div>

        <!-- Sign In form -->
        <form v-if="activeTab === 'signin'" @submit.prevent="handleSignIn" style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
          <label style="display:flex; flex-direction:column; gap:6px;">
            <span style="font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#6e6e73;">Email</span>
            <input v-model="signInForm.email" type="email" required placeholder="name@example.com"
              style="padding:12px 16px; border:1.5px solid rgba(0,0,0,0.1); border-radius:14px; font-size:14px; outline:none; background:#f9fafb; transition:border 0.2s;"
              onfocus="this.style.borderColor='#1d1d1f'; this.style.background='white'"
              onblur="this.style.borderColor='rgba(0,0,0,0.1)'; this.style.background='#f9fafb'"
            />
          </label>
          <label style="display:flex; flex-direction:column; gap:6px;">
            <span style="font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#6e6e73;">Password</span>
            <input v-model="signInForm.password" type="password" required placeholder="Enter your password"
              style="padding:12px 16px; border:1.5px solid rgba(0,0,0,0.1); border-radius:14px; font-size:14px; outline:none; background:#f9fafb; transition:border 0.2s;"
              onfocus="this.style.borderColor='#1d1d1f'; this.style.background='white'"
              onblur="this.style.borderColor='rgba(0,0,0,0.1)'; this.style.background='#f9fafb'"
            />
          </label>
          <button type="submit" :disabled="busy"
            style="grid-column:1/-1; margin-top:8px; padding:14px; background:#1d1d1f; color:white; border:none; border-radius:16px; font-size:13px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; cursor:pointer; transition:all 0.2s;"
            onmouseover="this.style.background='#000'; this.style.boxShadow='0 8px 24px rgba(29,29,31,0.35)'"
            onmouseout="this.style.background='#1d1d1f'; this.style.boxShadow='none'"
          >{{ busy ? 'Signing in...' : 'Sign In' }}</button>
        </form>

        <!-- Create Account form -->
        <form v-else @submit.prevent="handleCreateAccount" style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px;">
          <label v-for="(field, key) in {firstName:'First Name', lastName:'Last Name', passportNumber:'Passport Number', email:'Email', nationality:'Nationality', password:'Password'}" :key="key" style="display:flex; flex-direction:column; gap:6px;">
            <span style="font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#6e6e73;">{{ field }}</span>
            <input
              v-model="createForm[key]"
              :type="key === 'password' ? 'password' : key === 'email' ? 'email' : key === 'passportNumber' ? 'text' : 'text'"
              :inputmode="key === 'passportNumber' ? 'numeric' : undefined"
              required
              :placeholder="key === 'firstName' ? 'Avery' : key === 'lastName' ? 'Morgan' : key === 'passportNumber' ? '987654321' : key === 'email' ? 'name@example.com' : key === 'nationality' ? 'Singapore' : 'Create a password'"
              style="padding:12px 16px; border:1.5px solid rgba(0,0,0,0.1); border-radius:14px; font-size:14px; outline:none; background:#f9fafb; transition:border 0.2s;"
              onfocus="this.style.borderColor='#1d1d1f'; this.style.background='white'"
              onblur="this.style.borderColor='rgba(0,0,0,0.1)'; this.style.background='#f9fafb'"
            />
          </label>
          <button type="submit" :disabled="busy"
            style="grid-column:1/-1; margin-top:8px; padding:14px; background:#1d1d1f; color:white; border:none; border-radius:16px; font-size:13px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; cursor:pointer; transition:all 0.2s;"
            onmouseover="this.style.background='#000'; this.style.boxShadow='0 8px 24px rgba(29,29,31,0.35)'"
            onmouseout="this.style.background='#1d1d1f'; this.style.boxShadow='none'"
          >{{ busy ? 'Creating account...' : 'Create Account' }}</button>
        </form>

        <!-- Error -->
        <div v-if="errorMessage"
          style="margin-top:16px; background:#fef2f2; border:1px solid #fecaca; border-radius:12px; padding:12px 16px; font-size:13px; color:#dc2626;">
          {{ errorMessage }}
        </div>

      </div>

      <!-- Staff portal CTA -->
      <RouterLink to="/staff/login" style="display:block; margin-top:20px; text-decoration:none;">
        <div
          style="display:flex; align-items:center; justify-content:space-between; background:white; border:1.5px solid rgba(0,0,0,0.08); border-radius:20px; padding:18px 24px; box-shadow:0 2px 12px rgba(0,0,0,0.04); transition:all 0.2s; cursor:pointer;"
          onmouseover="this.style.borderColor='#1d1d1f'; this.style.boxShadow='0 8px 28px rgba(0,0,0,0.1)'; this.style.transform='translateY(-1px)'"
          onmouseout="this.style.borderColor='rgba(0,0,0,0.08)'; this.style.boxShadow='0 2px 12px rgba(0,0,0,0.04)'; this.style.transform='translateY(0)'"
        >
          <div style="display:flex; align-items:center; gap:14px;">
            <div style="width:40px; height:40px; background:#f5f5f7; border-radius:12px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
              <svg width="18" height="18" fill="none" stroke="#1d1d1f" stroke-width="2" viewBox="0 0 24 24">
                <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
              </svg>
            </div>
            <div>
              <p style="font-size:14px; font-weight:700; color:#1d1d1f; margin:0 0 2px;">Airline Staff?</p>
              <p style="font-size:12px; color:#6e6e73; margin:0;">Access the Staff Portal to manage flights</p>
            </div>
          </div>
          <svg width="16" height="16" fill="none" stroke="#6e6e73" stroke-width="2" viewBox="0 0 24 24">
            <path d="M9 18l6-6-6-6"/>
          </svg>
        </div>
      </RouterLink>

    </div>
  </main>
</template>