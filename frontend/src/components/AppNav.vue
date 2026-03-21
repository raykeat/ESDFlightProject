<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePassengerSession } from '../composables/usePassengerSession'

const router = useRouter()
const { currentPassenger, isSignedIn, clearPassenger } = usePassengerSession()

const profileMenuOpen = ref(false)

const displayName = computed(() => {
  const first = currentPassenger.value?.FirstName || ''
  const last  = currentPassenger.value?.LastName  || ''
  return `${first} ${last}`.trim()
})

function handleLogout() {
  clearPassenger()
  profileMenuOpen.value = false
  router.push('/')
}

function closeMenu(e) {
  profileMenuOpen.value = false
}
</script>

<template>
  <div style="position:sticky; top:16px; z-index:50; padding: 0 24px; margin-bottom: 8px;">
    <header style="
      display:flex; align-items:center; justify-content:space-between;
      background:rgba(255,255,255,0.75); backdrop-filter:blur(20px);
      border:1px solid rgba(0,0,0,0.06); border-radius:28px;
      padding:12px 28px; box-shadow:0 4px 24px rgba(0,0,0,0.06);
    ">
      <!-- Logo -->
      <span
        style="font-size:13px; font-weight:700; letter-spacing:0.18em; color:#1d1d1f; cursor:pointer;"
        @click="router.push('/')"
      >BLAZE AIR</span>

      <!-- Nav links removed (Experience / Book / Fleet were landing page anchors that don't apply) -->

      <!-- Profile menu -->
      <div style="position:relative;">
        <button
          @click="profileMenuOpen = !profileMenuOpen"
          style="display:flex; align-items:center; gap:8px; background:rgba(255,255,255,0.85); border:1px solid rgba(0,0,0,0.1); border-radius:100px; padding:6px 14px 6px 6px; cursor:pointer; transition:all 0.2s;"
          onmouseover="this.style.borderColor='rgba(0,0,0,0.2)'"
          onmouseout="this.style.borderColor='rgba(0,0,0,0.1)'"
        >
          <span style="width:32px; height:32px; background:#1d1d1f; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
            <svg width="16" height="16" fill="none" stroke="white" stroke-width="2" viewBox="0 0 24 24">
              <path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/>
            </svg>
          </span>
          <span style="font-size:12px; font-weight:600; letter-spacing:0.06em; color:#1d1d1f;">{{ displayName }}</span>
          <svg width="14" height="14" fill="#6e6e73" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z"/>
          </svg>
        </button>

        <!-- Dropdown -->
        <div
          v-if="profileMenuOpen"
          style="position:absolute; right:0; top:calc(100% + 8px); width:176px; background:rgba(255,255,255,0.97); border:1px solid rgba(0,0,0,0.1); border-radius:16px; box-shadow:0 16px 30px rgba(15,23,42,0.12); overflow:hidden; z-index:100;"
        >
          <button @click="router.push('/profile'); profileMenuOpen=false"
            style="display:block; width:100%; text-align:left; padding:10px 16px; font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#1d1d1f; background:none; border:none; cursor:pointer; transition:background 0.15s;"
            onmouseover="this.style.background='#f5f5f7'" onmouseout="this.style.background='none'">
            View Profile
          </button>
          <button @click="router.push('/my-bookings'); profileMenuOpen=false"
            style="display:block; width:100%; text-align:left; padding:10px 16px; font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#1d1d1f; background:none; border:none; cursor:pointer; transition:background 0.15s;"
            onmouseover="this.style.background='#f5f5f7'" onmouseout="this.style.background='none'">
            My Bookings
          </button>
          <div style="margin:4px 16px; border-top:1px solid rgba(0,0,0,0.08);"></div>
          <button @click="handleLogout"
            style="display:block; width:100%; text-align:left; padding:10px 16px; font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#6e6e73; background:none; border:none; cursor:pointer; transition:all 0.15s;"
            onmouseover="this.style.background='#f5f5f7'; this.style.color='#1d1d1f'" onmouseout="this.style.background='none'; this.style.color='#6e6e73'">
            Log Out
          </button>
        </div>
      </div>
    </header>
  </div>
</template>