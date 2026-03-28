<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { usePassengerSession } from '../composables/usePassengerSession'

const router = useRouter()
const { currentPassenger, clearPassenger } = usePassengerSession()

const profileMenuOpen = ref(false)
const profileMenuRef = ref(null)

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

function closeMenuOnOutsideClick(event) {
  if (!profileMenuRef.value?.contains(event.target)) {
    profileMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeMenuOnOutsideClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeMenuOnOutsideClick)
})
</script>

<template>
  <section class="relative mx-auto max-w-[1240px] px-6 pt-6 md:px-10 lg:px-16">
    <header class="animate__animated animate__fadeInDown sticky top-4 z-20 flex items-center justify-between rounded-[28px] border border-black/5 bg-white/75 px-5 py-3 backdrop-blur-xl md:px-7">
      <span class="cursor-pointer text-sm font-semibold tracking-[0.18em] text-[#1d1d1f]" @click="router.push('/')">BLAZE AIR</span>

      <RouterLink
        v-if="!currentPassenger"
        to="/auth"
        class="rounded-full border border-[#e63946]/40 bg-white/80 px-5 py-2 text-xs font-semibold tracking-[0.12em] text-[#1d1d1f] transition-all duration-300 hover:border-[#e63946] hover:shadow-[0_0_24px_rgba(230,57,70,0.3)]"
      >
        Sign In
      </RouterLink>

      <div v-else ref="profileMenuRef" class="relative">
        <button
          class="flex items-center gap-2 rounded-full border border-black/10 bg-white/85 px-3 py-1.5"
          @click="profileMenuOpen = !profileMenuOpen"
        >
          <span class="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#1d1d1f] text-white">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M20 21a8 8 0 0 0-16 0" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </span>
          <span class="text-xs font-semibold tracking-[0.08em] text-[#1d1d1f]">{{ displayName }}</span>
          <svg viewBox="0 0 20 20" class="h-4 w-4 text-[#6e6e73]" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z" clip-rule="evenodd" />
          </svg>
        </button>

        <div
          v-if="profileMenuOpen"
          class="absolute right-0 mt-2 w-44 overflow-hidden rounded-2xl border border-black/15 bg-white py-1 shadow-[0_18px_32px_rgba(15,23,42,0.16)]"
        >
          <RouterLink
            to="/profile"
            class="block px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="profileMenuOpen = false"
          >
            View Profile
          </RouterLink>
          <RouterLink
            to="/my-bookings"
            class="block px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="profileMenuOpen = false"
          >
            My Bookings
          </RouterLink>
          <RouterLink
            to="/loyalty/convert"
            class="block px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="profileMenuOpen = false"
          >
            Convert Miles
          </RouterLink>
          <RouterLink
            to="/my-vouchers"
            class="block px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#1d1d1f] transition hover:bg-[#f5f5f7]"
            @click="profileMenuOpen = false"
          >
            My Vouchers
          </RouterLink>
          <div class="mx-4 my-1 border-t border-black/8"></div>
          <button
            class="block w-full px-4 py-2 text-left text-xs font-semibold uppercase tracking-[0.12em] text-[#6e6e73] transition hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
            @click="handleLogout"
          >
            Log Out
          </button>
        </div>
      </div>
    </header>
  </section>
</template>