<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const email    = ref('')
const password = ref('')
const error    = ref('')
const busy     = ref(false)

const STAFF_CREDENTIALS = [
  { email: 'staff@blazeair.com', password: 'staff123', name: 'Blaze Air Staff' },
  { email: 'admin@blazeair.com', password: 'admin123', name: 'Blaze Air Admin' },
]

function handleLogin() {
  error.value = ''
  busy.value  = true
  try {
    const emailVal    = email.value.trim().toLowerCase()
    const passwordVal = password.value.trim()
    if (!emailVal || !passwordVal) throw new Error('Please enter both email and password.')
    const match = STAFF_CREDENTIALS.find(c => c.email === emailVal && c.password === passwordVal)
    if (!match) throw new Error('Invalid staff credentials. Please try again.')
    sessionStorage.setItem('staffSession', JSON.stringify({ email: match.email, name: match.name, role: 'staff' }))
    router.push('/staff/flights')
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main style="min-height:100vh; display:grid; grid-template-columns:1fr 1fr;">

    <!-- Left panel — dark brand side -->
    <div style="background:#1d1d1f; display:flex; flex-direction:column; justify-content:space-between; padding:48px; position:relative; overflow:hidden;">
      <!-- Background decoration -->
      <div style="position:absolute; top:-80px; right:-80px; width:300px; height:300px; background:rgba(230,57,70,0.08); border-radius:50%;"></div>
      <div style="position:absolute; bottom:-60px; left:-60px; width:200px; height:200px; background:rgba(255,255,255,0.03); border-radius:50%;"></div>

      <!-- Logo -->
      <div>
        <span style="font-size:13px; font-weight:700; letter-spacing:0.18em; color:white;">BLAZE AIR</span>
        <div style="display:inline-flex; align-items:center; gap:6px; background:rgba(230,57,70,0.15); border:1px solid rgba(230,57,70,0.3); border-radius:8px; padding:3px 10px; margin-left:12px;">
          <span style="width:6px; height:6px; background:#e63946; border-radius:50%;"></span>
          <span style="font-size:10px; font-weight:700; letter-spacing:0.1em; color:#e63946;">STAFF</span>
        </div>
      </div>

      <!-- Centre content -->
      <div style="position:relative; z-index:1;">
        <h2 style="font-size:40px; font-weight:700; letter-spacing:-0.03em; color:white; margin:0 0 16px; line-height:1.1;">
          Flight Operations<br/>Control Centre
        </h2>
        <p style="font-size:15px; color:rgba(255,255,255,0.5); margin:0 0 36px; line-height:1.6;">
          Manage flights, handle cancellations and oversee passenger rebooking — all from one place.
        </p>

        <!-- Feature list -->
        <div style="display:flex; flex-direction:column; gap:14px;">
          <div v-for="feat in ['View all active and cancelled flights', 'Cancel flights with one click', 'Automatic passenger notification via Kafka']" :key="feat"
            style="display:flex; align-items:center; gap:12px;">
            <div style="width:28px; height:28px; background:rgba(255,255,255,0.08); border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
              <svg width="14" height="14" fill="none" stroke="#22c55e" stroke-width="2.5" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>
            </div>
            <span style="font-size:13px; color:rgba(255,255,255,0.65);">{{ feat }}</span>
          </div>
        </div>
      </div>

      <!-- Passenger link -->
      <RouterLink to="/auth"
        style="display:inline-flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4); text-decoration:none; transition:color 0.2s;"
        onmouseover="this.style.color='rgba(255,255,255,0.8)'"
        onmouseout="this.style.color='rgba(255,255,255,0.4)'"
      >
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M15 19l-7-7 7-7"/></svg>
        Back to Passenger Portal
      </RouterLink>
    </div>

    <!-- Right panel — login form -->
    <div style="background:#f5f5f7; display:flex; align-items:center; justify-content:center; padding:48px;">
      <div style="width:100%; max-width:400px;">

        <div style="margin-bottom:36px;">
          <h1 style="font-size:30px; font-weight:700; letter-spacing:-0.02em; color:#1d1d1f; margin:0 0 8px;">Staff Sign In</h1>
          <p style="font-size:14px; color:#6e6e73; margin:0;">Enter your staff credentials to continue</p>
        </div>

        <!-- Form card -->
        <div style="background:white; border:1.5px solid rgba(0,0,0,0.08); border-radius:24px; padding:32px; box-shadow:0 8px 32px rgba(0,0,0,0.06);">

          <div style="display:flex; flex-direction:column; gap:16px; margin-bottom:20px;">
            <label style="display:flex; flex-direction:column; gap:6px;">
              <span style="font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#6e6e73;">Staff Email</span>
              <input v-model="email" type="email" placeholder="staff@blazeair.com" @keyup.enter="handleLogin"
                style="padding:12px 16px; border:1.5px solid rgba(0,0,0,0.1); border-radius:12px; font-size:14px; outline:none; background:#f9fafb; transition:all 0.2s;"
                onfocus="this.style.borderColor='#1d1d1f'; this.style.background='white'"
                onblur="this.style.borderColor='rgba(0,0,0,0.1)'; this.style.background='#f9fafb'"
              />
            </label>
            <label style="display:flex; flex-direction:column; gap:6px;">
              <span style="font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#6e6e73;">Password</span>
              <input v-model="password" type="password" placeholder="••••••••" @keyup.enter="handleLogin"
                style="padding:12px 16px; border:1.5px solid rgba(0,0,0,0.1); border-radius:12px; font-size:14px; outline:none; background:#f9fafb; transition:all 0.2s;"
                onfocus="this.style.borderColor='#1d1d1f'; this.style.background='white'"
                onblur="this.style.borderColor='rgba(0,0,0,0.1)'; this.style.background='#f9fafb'"
              />
            </label>
          </div>

          <!-- Error -->
          <div v-if="error"
            style="background:#fef2f2; border:1px solid #fecaca; border-radius:10px; padding:10px 14px; margin-bottom:16px; font-size:13px; color:#dc2626; display:flex; align-items:center; gap:8px;">
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/></svg>
            {{ error }}
          </div>

          <button @click="handleLogin" :disabled="busy"
            style="width:100%; padding:14px; background:#1d1d1f; color:white; border:none; border-radius:14px; font-size:13px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; cursor:pointer; transition:all 0.2s;"
            onmouseover="this.style.background='#000'; this.style.boxShadow='0 8px 24px rgba(29,29,31,0.3)'"
            onmouseout="this.style.background='#1d1d1f'; this.style.boxShadow='none'"
          >{{ busy ? 'Signing in...' : 'Sign In to Staff Portal' }}</button>
        </div>

        <!-- Demo hint -->
        <div style="margin-top:20px; background:white; border:1px solid rgba(0,0,0,0.08); border-radius:16px; padding:16px 20px;">
          <p style="font-size:11px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#6e6e73; margin:0 0 8px;">Demo Credentials</p>
          <div style="display:flex; flex-direction:column; gap:4px;">
            <p style="font-size:12px; font-family:monospace; color:#1d1d1f; margin:0;">staff@blazeair.com / staff123</p>
            <p style="font-size:12px; font-family:monospace; color:#1d1d1f; margin:0;">admin@blazeair.com / admin123</p>
          </div>
        </div>

      </div>
    </div>

  </main>
</template>