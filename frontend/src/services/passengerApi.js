import { apiUrl } from '../config/api'

function extractApiError(result, fallbackMessage) {
  if (!result || typeof result !== 'object') {
    return fallbackMessage
  }

  if (typeof result.ErrorMessage === 'string' && result.ErrorMessage.trim()) {
    return result.ErrorMessage
  }

  if (typeof result.message === 'string' && result.message.trim()) {
    return result.message
  }

  if (Array.isArray(result.Errors) && result.Errors.length > 0) {
    const firstError = result.Errors.find((item) => typeof item === 'string' && item.trim())
    if (firstError) {
      return firstError
    }
  }

  return fallbackMessage
}

export async function createPassengerAccount(payload) {
  const response = await fetch(apiUrl('/api/passenger/create/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  let result = null
  try {
    result = await response.json()
  } catch {
    result = null
  }

  if (!response.ok) {
    const message = extractApiError(result, 'Unable to create account right now.')
    throw new Error(message)
  }

  return result
}

export async function getAllPassengers() {
  const response = await fetch(apiUrl('/api/passenger/getall/'))

  let result = null
  try {
    result = await response.json()
  } catch {
    result = null
  }

  if (!response.ok) {
    const message = extractApiError(result, 'Unable to load passengers right now.')
    throw new Error(message)
  }

  return Array.isArray(result) ? result : []
}

export async function getPassengerById(passengerId) {
  let response = await fetch(apiUrl(`/api/passenger/getpassenger/${passengerId}/`))

  if (!response.ok && response.status === 404) {
    response = await fetch(apiUrl(`/api/passenger/getpassenger/${passengerId}`))
  }

  let result = null
  try {
    result = await response.json()
  } catch {
    result = null
  }

  if (!response.ok) {
    const message = extractApiError(result, 'Unable to load passenger details right now.')
    throw new Error(message)
  }

  return result
}

export async function updatePassengerAccount(passengerId, payload) {
  const response = await fetch(apiUrl(`/api/passenger/update/${passengerId}/`), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  let result = null
  try {
    result = await response.json()
  } catch {
    result = null
  }

  if (!response.ok) {
    const message = extractApiError(result, 'Unable to update account right now.')
    throw new Error(message)
  }

  return result
}

export async function loginPassenger(email, password) {
  const response = await fetch(apiUrl('/api/passenger/login/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ Email: email, Password: password }),
  })

  let result = null
  try {
    result = await response.json()
  } catch {
    result = null
  }

  if (!response.ok) {
    const message = extractApiError(result, 'Invalid email or password.')
    throw new Error(message)
  }

  return result
}
