import { computed, ref } from 'vue'

const storageKey = 'blaze-passenger-session'

function readInitialUser() {
  try {
    const raw = localStorage.getItem(storageKey)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

const currentPassenger = ref(readInitialUser())

export function usePassengerSession() {
  const isSignedIn = computed(() => Boolean(currentPassenger.value?.passenger_id))

  function setPassenger(passenger) {
    currentPassenger.value = passenger
    localStorage.setItem(storageKey, JSON.stringify(passenger))
  }

  function clearPassenger() {
    currentPassenger.value = null
    localStorage.removeItem(storageKey)
  }

  return {
    currentPassenger,
    isSignedIn,
    setPassenger,
    clearPassenger,
  }
}
