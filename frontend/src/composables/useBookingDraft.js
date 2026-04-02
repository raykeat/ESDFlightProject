import { ref } from 'vue'

const storageKey = 'blaze-booking-draft'

function canUseSessionStorage() {
  return typeof window !== 'undefined' && typeof window.sessionStorage !== 'undefined'
}

function readInitialDraft() {
  if (!canUseSessionStorage()) return null

  try {
    const raw = window.sessionStorage.getItem(storageKey)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

const bookingDraft = ref(readInitialDraft())

function persistDraft(nextDraft) {
  bookingDraft.value = nextDraft

  if (!canUseSessionStorage()) return

  if (!nextDraft) {
    window.sessionStorage.removeItem(storageKey)
    return
  }

  window.sessionStorage.setItem(storageKey, JSON.stringify(nextDraft))
}

export function useBookingDraft() {
  function setBookingDraft(nextDraft) {
    persistDraft(nextDraft)
  }

  function patchBookingDraft(patch) {
    persistDraft({
      ...(bookingDraft.value || {}),
      ...patch,
    })
  }

  function clearBookingDraft() {
    persistDraft(null)
  }

  return {
    bookingDraft,
    setBookingDraft,
    patchBookingDraft,
    clearBookingDraft,
  }
}
