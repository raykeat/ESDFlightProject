<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { usePassengerSession } from '../composables/usePassengerSession'

const router = useRouter()
const { currentPassenger } = usePassengerSession()

const bookings = ref([])
const offers = ref([])
const payments = ref([])
const flightsById = ref({})

const loading = ref(true)
const error = ref(null)
const activeTab = ref('All')
const searchQuery = ref('')
const expandedBookingIds = ref(new Set())
const expandedInfoBookingIds = ref(new Set())
const resumingBookingIds = ref(new Set())

const BOOKING_TABS = ['All', 'Awaiting Payment', 'Upcoming', 'Awaiting Review']

onMounted(async () => {
  if (!currentPassenger.value) {
    router.push('/auth')
    return
  }
  await loadData()
})

async function loadData() {
  loading.value = true
  error.value = null

  try {
    const passengerId = currentPassenger.value.passenger_id

    const [bookingsRes, offersRes, paymentsRes] = await Promise.allSettled([
      axios.get(`http://localhost:3010/api/bookings/passenger/${passengerId}`),
      loadOffers(passengerId),
      axios.get('http://localhost:5001/payment'),
    ])

    if (bookingsRes.status !== 'fulfilled') {
      error.value = 'Unable to load your bookings right now.'
      return
    }

    bookings.value = normalizeCollectionResponse(bookingsRes.value.data)
    offers.value = offersRes.status === 'fulfilled' ? normalizeCollectionResponse(offersRes.value) : []

    const allPayments = paymentsRes.status === 'fulfilled' && Array.isArray(paymentsRes.value.data)
      ? paymentsRes.value.data
      : []

    payments.value = allPayments.filter(
      (payment) => Number(payment.passengerID) === Number(passengerId)
    )

    await hydrateFlightDetails()
  } catch (e) {
    error.value = 'Unable to load your bookings right now.'
  } finally {
    loading.value = false
  }
}

async function loadOffers(passengerId) {
  try {
    const response = await axios.get(`http://localhost:5002/offers`, {
      params: { passengerID: passengerId },
    })
    return response.data
  } catch (primaryError) {
    const status = primaryError?.response?.status
    if (status && status !== 404) {
      throw primaryError
    }

    const fallback = await axios.get(`http://localhost:5002/offer`, {
      params: { passengerID: passengerId },
    })
    return fallback.data
  }
}

function normalizeCollectionResponse(payload) {
  let data = payload

  if (typeof data === 'string') {
    try {
      data = JSON.parse(data)
    } catch {
      return []
    }
  }

  if (Array.isArray(data)) return data
  if (Array.isArray(data?.value)) return data.value
  if (Array.isArray(data?.data)) return data.data
  return []
}

async function hydrateFlightDetails() {
  const fromBookings = bookings.value
    .map((booking) => Number(booking.flightID))
    .filter((flightID) => Number.isFinite(flightID) && flightID > 0)

  const fromOffers = offers.value.flatMap((offer) => [
    Number(offer.origFlightID),
    Number(offer.newFlightID),
  ]).filter((flightID) => Number.isFinite(flightID) && flightID > 0)

  const uniqueFlightIds = [...new Set([...fromBookings, ...fromOffers])]

  if (!uniqueFlightIds.length) {
    flightsById.value = {}
    return
  }

  const map = {}
  const results = await Promise.allSettled(
    uniqueFlightIds.map(async (flightID) => {
      try {
        return await axios.get(`http://localhost:3003/flight/${flightID}`)
      } catch (primaryError) {
        return await axios.get(`http://localhost:3003/flights/${flightID}`)
      }
    })
  )

  results.forEach((result, idx) => {
    if (result.status === 'fulfilled') {
      map[uniqueFlightIds[idx]] = result.value.data
    }
  })

  flightsById.value = map
}

function normalizedStatus(status) {
  return String(status || '').trim()
}

function isCancelled(status) {
  return normalizedStatus(status).toLowerCase().startsWith('cancelled')
}

function bookingGroupKey(booking) {
  const bookedBy = Number(booking.bookedByPassengerID || booking.passengerID || booking.bookingID || 0)
  const createdAt = String(booking.createdAt || '').slice(0, 19)
  return [bookedBy, booking.flightID, normalizedStatus(booking.status), createdAt].join('|')
}

function getFlight(booking) {
  return flightsById.value[Number(booking.flightID)] || null
}

function getOfferForBooking(bookingLike) {
  const bookingIDs = Array.isArray(bookingLike?.bookingIDs)
    ? bookingLike.bookingIDs.map(Number)
    : [Number(bookingLike?.bookingID ?? bookingLike)]

  const matches = offers.value.filter((offer) => bookingIDs.includes(Number(offer.bookingID)))
  if (!matches.length) return null
  return matches.find((offer) => offer.status === 'Pending Response') || matches[0]
}

function hasPendingOffer(bookingLike) {
  const offer = getOfferForBooking(bookingLike)
  return Boolean(offer && offer.status === 'Pending Response')
}

function hasAcceptedOffer(bookingLike) {
  const offer = getOfferForBooking(bookingLike)
  return Boolean(offer && offer.status === 'Accepted')
}

function getOfferSnapshot(booking) {
  const offer = getOfferForBooking(booking)
  if (!offer || offer.status !== 'Pending Response') return null

  const original = flightsById.value[Number(offer.origFlightID)] || getFlight(booking)
  const proposed = flightsById.value[Number(offer.newFlightID)] || null

  return {
    offer,
    original,
    proposed,
    expiryText: getOfferExpiryLabel(offer),
  }
}

function getRefundForBooking(bookingLike) {
  const bookingIDs = Array.isArray(bookingLike?.bookingIDs)
    ? bookingLike.bookingIDs.map(Number)
    : [Number(bookingLike?.bookingID ?? bookingLike)]

  return payments.value.find(
    (payment) => bookingIDs.includes(Number(payment.bookingID)) && String(payment.status).toLowerCase() === 'refunded'
  ) || null
}

function hasRefund(bookingLike) {
  return Boolean(getRefundForBooking(bookingLike))
}

function getRefundSnapshot(booking) {
  const refund = getRefundForBooking(booking)
  if (!refund) return null

  const flight = getFlight(booking)

  return {
    refund,
    flight,
    amount: formatMoney(refund.amount),
    refundID: refund.refundID || 'Processing',
  }
}

function formatMoney(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '0.00'
  return amount.toFixed(2)
}

function formatBookedDate(value) {
  if (!value) return '--'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'

  const day = date.getUTCDate()
  const month = date.toLocaleString('en-SG', { month: 'long', timeZone: 'UTC' })
  const year = date.getUTCFullYear()
  const hours = date.getUTCHours()
  const minutes = String(date.getUTCMinutes()).padStart(2, '0')
  const period = hours >= 12 ? 'PM' : 'AM'
  const h12 = hours % 12 || 12

  return `${month} ${day}, ${year}, ${h12}:${minutes} ${period} SGT`
}

function formatFlightDate(flight) {
  if (!flight) return '--'

  if (flight.Date) {
    const [day, month, year] = String(flight.Date).split('/')
    const parsed = new Date(`${year}-${month}-${day}`)
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleDateString('en-SG', { month: 'short', day: 'numeric', year: 'numeric' })
    }
  }

  if (flight.FlightDate) {
    const parsed = new Date(flight.FlightDate)
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleDateString('en-SG', { month: 'short', day: 'numeric', year: 'numeric' })
    }
  }

  return '--'
}

function formatFlightDateNumeric(flight) {
  if (!flight) return '--'

  if (flight.Date) return flight.Date

  if (flight.FlightDate) {
    const parsed = new Date(flight.FlightDate)
    if (!Number.isNaN(parsed.getTime())) {
      const day = String(parsed.getDate()).padStart(2, '0')
      const month = String(parsed.getMonth() + 1).padStart(2, '0')
      const year = parsed.getFullYear()
      return `${day}/${month}/${year}`
    }
  }

  return '--'
}

function formatFlightTime(value) {
  if (!value) return '--'

  const clean = String(value).slice(0, 5)
  const [hours, minutes] = clean.split(':').map(Number)
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return clean

  const period = hours >= 12 ? 'PM' : 'AM'
  const h12 = hours % 12 || 12
  return `${h12}:${String(minutes).padStart(2, '0')} ${period}`
}

function parseSgtDateTime(value) {
  if (!value) return null
  const cleaned = String(value).replace(/ [A-Z]{2,4}$/, '').trim()
  const parsed = new Date(cleaned)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed
}

function parseBookingDate(value) {
  if (!value) return null
  const parsed = new Date(value)
  if (!Number.isNaN(parsed.getTime())) return parsed

  const cleaned = String(value).replace(' ', 'T')
  const fallback = new Date(cleaned)
  return Number.isNaN(fallback.getTime()) ? null : fallback
}

function getPendingHoldDeadline(booking) {
  const createdAt = parseBookingDate(booking?.createdAt)
  if (!createdAt) return null
  return new Date(createdAt.getTime() + 5 * 60 * 1000)
}

function getPendingHoldMinutesLeft(booking) {
  const deadline = getPendingHoldDeadline(booking)
  if (!deadline) return null
  return Math.max(0, Math.ceil((deadline.getTime() - Date.now()) / 60000))
}

function isPendingHoldExpired(booking) {
  const deadline = getPendingHoldDeadline(booking)
  if (!deadline) return true
  return deadline.getTime() <= Date.now()
}

function getOfferExpiryLabel(offer) {
  if (!offer) return null

  const expiry = parseSgtDateTime(offer.expiryTime)
  const created = parseSgtDateTime(offer.createdTime)

  let effectiveExpiry = expiry
  if (created) {
    const createdPlus24 = new Date(created.getTime() + 24 * 3600000)
    if (!effectiveExpiry || effectiveExpiry.getTime() < createdPlus24.getTime() - 3 * 3600000) {
      effectiveExpiry = createdPlus24
    }
  }

  if (!effectiveExpiry) return null

  const diffHours = Math.ceil((effectiveExpiry - new Date()) / 3600000)
  if (diffHours < 0) return 'Offer expired'
  if (diffHours < 24) return `Expires in ${diffHours}h`
  return `Expires in ${Math.ceil(diffHours / 24)} day(s)`
}

function parseFlightDateValue(flight) {
  if (!flight) return null

  if (flight.FlightDate) {
    const parsed = new Date(`${flight.FlightDate}T00:00:00`)
    if (!Number.isNaN(parsed.getTime())) return parsed
  }

  if (flight.Date) {
    const parts = String(flight.Date).split('/')
    if (parts.length === 3) {
      const parsed = new Date(`${parts[2]}-${parts[1]}-${parts[0]}T00:00:00`)
      if (!Number.isNaN(parsed.getTime())) return parsed
    }
  }

  return null
}

function daysUntilFlight(flight) {
  const flightDate = parseFlightDateValue(flight)
  if (!flightDate) return null

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const diffMs = flightDate.getTime() - today.getTime()
  return Math.ceil(diffMs / 86400000)
}

function getTripCountdown(booking) {
  const flight = getFlight(booking)
  const days = daysUntilFlight(flight)

  if (days === null) return 'Trip date unavailable'
  if (days <= 0) return 'Today'
  if (days === 1) return 'In 1 day'
  return `In ${days} days`
}

function getAirportCode(place) {
  if (!place) return '---'

  return String(place)
    .split(/[\s-]+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 3)
    .toUpperCase()
}

function passengerDisplayName() {
  const first = currentPassenger.value?.FirstName || currentPassenger.value?.firstName || ''
  const last = currentPassenger.value?.LastName || currentPassenger.value?.lastName || ''
  const combined = `${first} ${last}`.trim()

  if (combined) return combined
  return currentPassenger.value?.Email || currentPassenger.value?.email || 'Passenger'
}

function getTravellerName(bookingRecord) {
  const guestFirst = bookingRecord?.guestFirstName || bookingRecord?.GuestFirstName || ''
  const guestLast = bookingRecord?.guestLastName || bookingRecord?.GuestLastName || ''
  const guestName = `${guestFirst} ${guestLast}`.trim()

  if (guestName) return guestName
  if (Number(bookingRecord?.passengerID) === Number(currentPassenger.value?.passenger_id)) {
    return passengerDisplayName()
  }

  return passengerDisplayName()
}

function getTravellerNames(booking) {
  const records = Array.isArray(booking?.bookings) && booking.bookings.length
    ? booking.bookings
    : [booking]

  return [...new Set(records.map(getTravellerName).filter(Boolean))]
}

function primaryTravellerName(booking) {
  return getTravellerNames(booking)[0] || passengerDisplayName()
}

function additionalTravellerCount(booking) {
  return Math.max(getTravellerNames(booking).length - 1, 0)
}

function isPassengerListExpanded(booking) {
  return expandedBookingIds.value.has(Number(booking.bookingID))
}

function togglePassengerList(booking) {
  const next = new Set(expandedBookingIds.value)
  const id = Number(booking.bookingID)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expandedBookingIds.value = next
}

function isFlightInfoExpanded(booking) {
  return expandedInfoBookingIds.value.has(Number(booking.bookingID))
}

function toggleFlightInfo(booking) {
  const next = new Set(expandedInfoBookingIds.value)
  const id = Number(booking.bookingID)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expandedInfoBookingIds.value = next
}

function passengerCountLabel(booking) {
  const count = Number(booking?.travellerCount || 1)
  return `${count} passenger${count === 1 ? '' : 's'}`
}

function bookingNumberLabel(booking) {
  const ids = (Array.isArray(booking?.bookingIDs) ? booking.bookingIDs : [booking?.bookingID])
    .map((id) => Number(id))
    .filter((id) => Number.isFinite(id))
    .sort((a, b) => a - b)

  if (!ids.length) return 'Booking No. --'
  if (ids.length === 1) return `Booking No. ${ids[0]}`
  return `Booking No. ${ids[0]} - ${ids[ids.length - 1]}`
}

function isAwaitingReview(booking) {
  return hasPendingOffer(booking) || normalizedStatus(booking.status) === 'Refund Failed'
}

function isUpcoming(booking) {
  if (hasPendingOffer(booking) || hasRefund(booking) || isCancelled(booking.status)) {
    return false
  }

  const status = normalizedStatus(booking.status)
  if (status !== 'Confirmed') return false

  const days = daysUntilFlight(getFlight(booking))
  return days === null || days >= 0
}

const filteredBookings = computed(() => {
  let scopedBookings = groupedBookings.value

  if (activeTab.value === 'Awaiting Payment') {
    scopedBookings = scopedBookings.filter((booking) => normalizedStatus(booking.status) === 'Pending')
  } else if (activeTab.value === 'Upcoming') {
    scopedBookings = scopedBookings.filter((booking) => isUpcoming(booking))
  } else if (activeTab.value === 'Awaiting Review') {
    scopedBookings = scopedBookings.filter((booking) => isAwaitingReview(booking))
  }

  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return scopedBookings

  return scopedBookings.filter((booking) => {
    const flight = getFlight(booking)
    const fields = [
      booking.bookingID,
      booking.seatNumber,
      booking.amount,
      booking.status,
      flight?.FlightNumber,
      flight?.Origin,
      flight?.Destination,
      formatFlightDate(flight),
    ]

    return fields.some((field) => String(field || '').toLowerCase().includes(query))
  })
})

function countByTab(tab) {
  if (tab === 'All') return groupedBookings.value.length
  if (tab === 'Awaiting Payment') {
    return groupedBookings.value.filter((booking) => normalizedStatus(booking.status) === 'Pending').length
  }
  if (tab === 'Upcoming') {
    return groupedBookings.value.filter((booking) => isUpcoming(booking)).length
  }
  if (tab === 'Awaiting Review') {
    return groupedBookings.value.filter((booking) => isAwaitingReview(booking)).length
  }
  return 0
}

const groupedBookings = computed(() => {
  const groups = new Map()

  for (const booking of bookings.value) {
    const key = bookingGroupKey(booking)
    if (!groups.has(key)) {
      groups.set(key, {
        ...booking,
        bookingIDs: [Number(booking.bookingID)],
        bookings: [booking],
        travellerCount: 1,
        amount: Number(booking.amount || 0),
        seatNumber: booking.seatNumber || '--',
      })
      continue
    }

    const group = groups.get(key)
    group.bookingIDs.push(Number(booking.bookingID))
    group.bookings.push(booking)
    group.travellerCount += 1
    group.amount += Number(booking.amount || 0)
    group.seatNumber = [...new Set([...String(group.seatNumber || '').split(',').map((seat) => seat.trim()).filter(Boolean), booking.seatNumber].filter(Boolean))].join(', ')
  }

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      bookingID: Math.min(...group.bookingIDs),
      amount: Number(group.amount || 0),
    }))
    .sort((a, b) => new Date(b.createdAt || 0) - new Date(a.createdAt || 0))
})

function statusLabel(booking) {
  if (hasPendingOffer(booking)) return 'Review Required'
  if (hasAcceptedOffer(booking)) return 'Rebooked Flight'
  if (hasRefund(booking)) return 'Refunded'

  const status = normalizedStatus(booking.status)
  if (status === 'Refund Failed') return 'Refund Failed'
  if (status === 'Confirmed') return 'Ticket(s) issued'
  if (status === 'Pending') return 'Awaiting Payment'
  if (isCancelled(status)) return 'Cancelled'
  return status || 'Booking'
}

function statusBadgeClass(booking) {
  if (hasPendingOffer(booking)) return 'border-[#f8d6df] bg-[#fff5f7] text-[#d72660]'
  if (hasAcceptedOffer(booking)) return 'border-[#f4d6a6] bg-[#fff7e8] text-[#9a6200]'
  if (hasRefund(booking)) return 'border-[#d9dee8] bg-white text-[#475569]'

  const status = normalizedStatus(booking.status)
  if (status === 'Confirmed') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (status === 'Pending') return 'border-[#e63946]/20 bg-[#fff1f2] text-[#b42318]'
  if (status === 'Refund Failed') return 'border-amber-200 bg-amber-50 text-amber-700'
  if (isCancelled(status)) return 'border-rose-200 bg-rose-50 text-rose-700'
  return 'border-slate-200 bg-slate-50 text-slate-700'
}

function cardAccentClass(booking) {
  if (hasPendingOffer(booking)) return 'bg-[#ffd43b]'
  if (hasAcceptedOffer(booking)) return 'bg-[#d4a64c]'
  if (hasRefund(booking)) return 'bg-slate-400'

  const status = normalizedStatus(booking.status)
  if (status === 'Confirmed') return 'bg-[#12c48b]'
  if (status === 'Pending') return 'bg-[#e63946]'
  if (status === 'Refund Failed') return 'bg-amber-400'
  if (isCancelled(status)) return 'bg-[#e63946]'
  return 'bg-slate-300'
}

async function resumePendingBooking(booking) {
  const id = Number(booking.bookingID)
  const next = new Set(resumingBookingIds.value)
  next.add(id)
  resumingBookingIds.value = next

  try {
    const response = await axios.post('http://localhost:3010/api/bookings/resume-payment', {
      bookingID: booking.bookingID,
      frontendBaseUrl: window.location.origin,
    })

    const sessionUrl = response.data?.sessionUrl
    if (!sessionUrl) {
      throw new Error('No checkout session URL returned')
    }

    window.location.href = sessionUrl
  } catch (err) {
    const status = err?.response?.status
    if (status === 410) {
      window.alert('This 5-minute payment hold has expired, so the seat has been released back for booking.')
      await loadData()
      return
    }

    window.alert(err?.response?.data?.message || 'We could not resume payment right now. Please try again.')
  } finally {
    const reset = new Set(resumingBookingIds.value)
    reset.delete(id)
    resumingBookingIds.value = reset
  }
}

function getOutcomeSummary(booking) {
  const offer = getOfferForBooking(booking)
  const refund = getRefundForBooking(booking)

  if (offer && offer.status === 'Pending Response') {
    return {
      title: 'Flight update available',
      detail: getOfferExpiryLabel(offer) || 'Please review the new rebooking option we prepared for you.',
      actionLabel: 'Review Offer',
      action: () => viewOffer(offer),
    }
  }

  if (offer && offer.status === 'Accepted') {
    const proposedFlight = flightsById.value[Number(offer.newFlightID)] || getFlight(booking)
    return {
      title: 'You were moved to a replacement flight',
      detail: proposedFlight
        ? `This trip was rebooked onto ${proposedFlight.FlightNumber} from ${proposedFlight.Origin} to ${proposedFlight.Destination}.`
        : 'This trip was successfully rebooked onto a replacement flight.',
      actionLabel: 'View Rebooking',
      action: () => viewOffer(offer),
    }
  }

  if (refund) {
    return {
      title: 'Refund completed',
      detail: `Refunded $${formatMoney(refund.amount)} to your original payment method.`,
      actionLabel: 'Book Again',
      action: () => router.push('/'),
    }
  }

  if (normalizedStatus(booking.status) === 'Pending') {
    const minutesLeft = getPendingHoldMinutesLeft(booking)
    const detail = isPendingHoldExpired(booking)
      ? 'This payment hold has expired. Reload to pick seats again.'
      : `Your seats are reserved while payment is pending. Complete payment within ${minutesLeft} minute${minutesLeft === 1 ? '' : 's'}.`

    return {
      title: 'Awaiting payment confirmation',
      detail,
      actionLabel: 'Continue Booking',
      action: () => resumePendingBooking(booking),
      disabled: isPendingHoldExpired(booking) || resumingBookingIds.value.has(Number(booking.bookingID)),
    }
  }

  return {
    title: 'Everything looks good',
    detail: 'Your itinerary is ready and your flight details are confirmed.',
    actionLabel: 'Book Again',
    action: () => router.push('/'),
    disabled: false,
  }
}

function paymentStatusLabel(booking) {
  if (hasRefund(booking)) return 'Refunded'
  if (hasPendingOffer(booking)) return 'Awaiting your review'
  if (hasAcceptedOffer(booking)) return 'Rebooked and confirmed'

  const status = normalizedStatus(booking.status)
  if (status === 'Pending') return 'Awaiting payment'
  if (status === 'Confirmed') return 'Payment completed'
  if (status === 'Refund Failed') return 'Refund issue'
  if (isCancelled(status)) return 'Cancelled'
  return status || 'Unknown'
}

function getAcceptedOfferSnapshot(booking) {
  const offer = getOfferForBooking(booking)
  if (!offer || offer.status !== 'Accepted') return null

  return {
    offer,
    original: flightsById.value[Number(offer.origFlightID)] || null,
    proposed: flightsById.value[Number(offer.newFlightID)] || getFlight(booking) || null,
  }
}

function normalizeBooleanFlag(value) {
  if (value === true || value === false) return value
  const normalized = String(value ?? '').trim().toLowerCase()
  return ['true', '1', 'yes', 'y', 'included', 'available'].includes(normalized)
}

function getFlightAmenities(flight) {
  if (!flight) return []

  const amenities = []
  const meals = String(flight.Meals || flight.meals || '').trim()
  const beverages = String(flight.Beverages || flight.beverages || '').trim()
  const baggage = String(flight.Baggage || flight.baggage || '').trim()
  const wifi = normalizeBooleanFlag(flight.Wifi ?? flight.wifi)

  if (baggage) amenities.push(`${baggage} baggage`)
  if (meals) amenities.push(meals)
  if (beverages) amenities.push(beverages)
  if (wifi) amenities.push('Wi-Fi included')

  return amenities
}

function getFlightBaggage(flight) {
  return String(flight?.Baggage || flight?.baggage || '').trim() || 'Included as shown in fare'
}

function getFlightMeals(flight) {
  return String(flight?.Meals || flight?.meals || '').trim() || 'Standard meal service'
}

function getFlightBeverages(flight) {
  return String(flight?.Beverages || flight?.beverages || '').trim() || 'Complimentary beverages'
}

function getFlightWifiLabel(flight) {
  return normalizeBooleanFlag(flight?.Wifi ?? flight?.wifi) ? 'Available onboard' : 'Not included'
}

function viewOffer(offer) {
  router.push({
    path: '/rebooking-offer',
    query: { offerID: offer.offerID, bookingID: offer.bookingID }
  })
}

function routeArtStyle(booking) {
  const destination = String(getFlight(booking)?.Destination || '').toLowerCase()

  if (destination.includes('london')) {
    return { background: 'linear-gradient(135deg, #8f1239 0%, #e63946 48%, #fecdd3 100%)' }
  }
  if (destination.includes('dubai')) {
    return { background: 'linear-gradient(135deg, #7c2d12 0%, #ea580c 48%, #fed7aa 100%)' }
  }
  if (destination.includes('edinburgh')) {
    return { background: 'linear-gradient(135deg, #7f1d1d 0%, #dc2626 46%, #fecaca 100%)' }
  }
  if (destination.includes('new york')) {
    return { background: 'linear-gradient(135deg, #3f3f46 0%, #71717a 45%, #e4e4e7 100%)' }
  }
  if (destination.includes('tokyo')) {
    return { background: 'linear-gradient(135deg, #9f1239 0%, #f43f5e 46%, #ffe4e6 100%)' }
  }
  return { background: 'linear-gradient(135deg, #991b1b 0%, #e63946 48%, #ffe4e6 100%)' }
}
</script>

<template>
  <main class="min-h-screen bg-[radial-gradient(circle_at_90%_8%,rgba(230,57,70,0.12),transparent_30%),radial-gradient(circle_at_12%_82%,rgba(255,255,255,0.72),transparent_42%),linear-gradient(180deg,#f8f8fa_0%,#f3f4f8_48%,#eceff4_100%)] pb-20 pt-8">
    <section class="mx-auto max-w-[1180px] px-4 md:px-8">
      <div class="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div class="flex flex-wrap items-center gap-3">
            <h1 class="text-4xl font-bold tracking-[-0.04em] text-[#132238] md:text-5xl">My Bookings</h1>
          </div>
          <p class="mt-3 text-sm text-[#556070]">
            {{ passengerDisplayName() }} |
            <span v-if="!loading">{{ groupedBookings.length }} booking{{ groupedBookings.length !== 1 ? 's' : '' }} total</span>
            <span v-else>Loading your trips...</span>
          </p>
        </div>

        <div class="w-full max-w-[360px]">
          <label for="booking-search" class="sr-only">Search bookings</label>
          <div class="flex items-center rounded-2xl border border-black/10 bg-white px-4 py-3 shadow-[0_8px_24px_rgba(15,23,42,0.04)]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="mr-3 text-[#6e6e73]">
              <circle cx="11" cy="11" r="7"></circle>
              <path d="M20 20L17 17"></path>
            </svg>
            <input
              id="booking-search"
              v-model="searchQuery"
              type="text"
              placeholder="Search by booking ID, flight, route..."
              class="w-full bg-transparent text-sm font-medium text-[#1d1d1f] outline-none placeholder:text-[#9ca3af]"
            />
          </div>
        </div>
      </div>

      <div class="mb-6 grid gap-2 rounded-2xl bg-white p-2 shadow-[0_16px_40px_rgba(15,23,42,0.06)] md:grid-cols-4">
        <button
          v-for="tab in BOOKING_TABS"
          :key="tab"
          @click="activeTab = tab"
          class="flex items-center justify-center gap-2 rounded-xl px-4 py-4 text-sm font-semibold transition"
          :class="activeTab === tab
            ? 'bg-gradient-to-r from-[#e63946] to-[#f43f5e] text-white shadow-[0_12px_26px_rgba(230,57,70,0.22)]'
            : 'text-[#1d1d1f] hover:bg-[#f5f5f7]'"
        >
          <span>{{ tab }}</span>
          <span
            class="rounded-md px-2 py-0.5 text-xs"
            :class="activeTab === tab ? 'bg-white/20 text-white' : 'bg-[#f5f5f7] text-[#6e6e73]'"
          >
            {{ countByTab(tab) }}
          </span>
        </button>
      </div>

      <div v-if="loading" class="space-y-4">
        <div v-for="i in 3" :key="i" class="h-72 animate-pulse rounded-[28px] bg-white shadow-[0_16px_40px_rgba(15,23,42,0.05)]"></div>
      </div>

      <div v-else-if="error" class="rounded-[28px] border border-rose-200 bg-white p-10 text-center shadow-[0_16px_40px_rgba(15,23,42,0.05)]">
        <p class="text-lg font-semibold text-[#132238]">{{ error }}</p>
        <button
          @click="loadData"
          class="mt-4 rounded-xl bg-gradient-to-r from-[#e63946] to-[#f43f5e] px-5 py-3 text-sm font-semibold text-white transition hover:shadow-[0_10px_24px_rgba(230,57,70,0.24)]"
        >
          Try Again
        </button>
      </div>

      <div v-else-if="filteredBookings.length === 0" class="rounded-[28px] bg-white p-10 text-center shadow-[0_16px_40px_rgba(15,23,42,0.05)]">
        <p class="text-lg font-semibold text-[#132238]">
          {{ searchQuery.trim() ? 'No matching bookings found' : activeTab === 'All' ? 'No bookings yet' : `No ${activeTab.toLowerCase()} bookings` }}
        </p>
        <p class="mt-2 text-sm text-[#6b7280]">
          {{ searchQuery.trim() ? 'Try a different booking ID, flight number, or route.' : 'Your future and past flight plans will appear here.' }}
        </p>
      </div>

      <div v-else class="space-y-6">
        <article
          v-for="booking in filteredBookings"
          :key="booking.bookingID"
          class="overflow-hidden rounded-[28px] bg-white shadow-[0_20px_50px_rgba(15,23,42,0.08)]"
        >
          <div class="h-1.5" :class="cardAccentClass(booking)"></div>

          <div class="border-b border-[#e8edf4] px-5 py-4 md:px-6">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="flex flex-wrap items-center gap-3 text-sm text-[#506077]">
                <span class="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[#fff1f2] text-xs font-bold text-[#e63946]">AIR</span>
                <span class="font-semibold text-[#243449]">{{ bookingNumberLabel(booking) }}</span>
                <span class="hidden text-[#c1c7d0] md:inline">|</span>
                <span>Booking Date: {{ formatBookedDate(booking.createdAt) }}</span>
              </div>

              <span class="rounded-xl border px-4 py-2 text-sm font-semibold" :class="statusBadgeClass(booking)">
                {{ statusLabel(booking) }}
              </span>
            </div>
          </div>

          <div class="px-5 pb-6 pt-5 md:px-6">
            <div class="mb-4 flex items-center gap-2 text-[#07a6c3]">
              <span class="inline-flex min-w-[58px] items-center justify-center rounded-full bg-[#fff1f2] px-3 py-1 text-[10px] font-bold tracking-[0.08em] text-[#e63946]">DATE</span>
              <span class="text-sm font-semibold text-[#e63946]">{{ getTripCountdown(booking) }}</span>
            </div>

            <div>
              <div>
                <div class="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 class="text-[28px] font-bold tracking-[-0.03em] text-[#132238]">
                      {{ getFlight(booking)?.Origin || 'Flight details unavailable' }}
                      <span class="mx-3 inline-flex items-center align-middle text-[#7c8ca5]">
                        <svg width="34" height="14" viewBox="0 0 34 14" fill="none" xmlns="http://www.w3.org/2000/svg" class="overflow-visible">
                          <path d="M1 7H24" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                          <path d="M19 3L24 7L19 11" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                          <path d="M12 4.2L15.8 7L12 9.8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" opacity="0.45"/>
                        </svg>
                      </span>
                      {{ getFlight(booking)?.Destination || '--' }}
                    </h2>
                  </div>

                  <div class="text-left lg:text-right">
                    <p class="text-[15px] font-medium text-[#6b7280]">Paid</p>
                    <p class="mt-1 text-3xl font-bold tracking-[-0.03em] text-[#132238]">${{ formatMoney(booking.amount) }}</p>
                  </div>
                </div>

                <div class="mt-5 rounded-2xl bg-[#f7f7f8] p-4">
                  <div class="grid gap-4 md:grid-cols-[1fr_120px_1fr_1fr_1fr] md:items-center">
                    <div>
                      <p class="text-3xl font-bold tracking-[-0.03em] text-[#132238]">{{ formatFlightTime(getFlight(booking)?.DepartureTime) }}</p>
                      <p class="mt-1 text-sm text-[#5f6b7d]">{{ formatFlightDate(getFlight(booking)) }}</p>
                    </div>

                    <div class="hidden items-center justify-center md:flex">
                      <div class="flex w-full items-center gap-2 text-[#c4ccd8]">
                        <span class="h-[2px] flex-1 bg-current"></span>
                        <span class="text-xs font-bold">AIR</span>
                        <span class="h-[2px] flex-1 bg-current"></span>
                      </div>
                    </div>

                    <div>
                      <p class="text-sm font-bold uppercase tracking-[0.12em] text-[#8a96a8]">
                        {{ getFlight(booking)?.FlightNumber || 'Flight pending' }}
                      </p>
                      <p class="mt-2 text-sm text-[#5f6b7d]">Seat {{ booking.seatNumber || '--' }}</p>
                    </div>

                    <div>
                      <p class="text-xl font-bold text-[#132238]">{{ primaryTravellerName(booking) }}</p>
                      <div class="mt-1 flex flex-wrap items-center gap-2">
                        <p class="text-sm text-[#5f6b7d]">{{ passengerCountLabel(booking) }}</p>
                        <span
                          v-if="hasAcceptedOffer(booking)"
                          class="inline-flex items-center rounded-full border border-[#f4d6a6] bg-[#fff7e8] px-3 py-1 text-xs font-semibold text-[#9a6200]"
                        >
                          Rebooked from disrupted flight
                        </span>
                        <button
                          v-if="getTravellerNames(booking).length > 1"
                          @click="togglePassengerList(booking)"
                          class="inline-flex items-center gap-1 rounded-full border border-[#e63946]/20 bg-[#fff1f2] px-3 py-1 text-xs font-semibold text-[#e63946] transition hover:border-[#e63946]/40"
                        >
                          <span>{{ isPassengerListExpanded(booking) ? 'Hide passengers' : `View ${additionalTravellerCount(booking)} more` }}</span>
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            class="transition"
                            :class="isPassengerListExpanded(booking) ? 'rotate-180' : ''"
                          >
                            <path d="M6 9l6 6 6-6"></path>
                          </svg>
                        </button>
                      </div>
                    </div>

                    <div>
                      <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-[#8a96a8]">Departure Status</p>
                      <p class="mt-2 text-sm font-semibold text-[#132238]">{{ normalizedStatus(booking.status) || 'Confirmed' }}</p>
                    </div>
                  </div>
                </div>

                <div
                  v-if="getTravellerNames(booking).length > 1 && isPassengerListExpanded(booking)"
                  class="mt-4 rounded-2xl border border-black/8 bg-white p-4"
                >
                  <div class="mb-3 flex items-center justify-between gap-3">
                    <p class="text-[11px] font-bold uppercase tracking-[0.14em] text-[#8a96a8]">Passengers</p>
                    <p class="text-xs font-medium text-[#5f6b7d]">{{ getTravellerNames(booking).length }} travellers on this flight</p>
                  </div>

                  <div class="space-y-3">
                    <div
                      v-for="traveller in booking.bookings"
                      :key="traveller.bookingID"
                      class="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#f7f7f8] px-4 py-3"
                    >
                      <div>
                        <p class="text-sm font-semibold text-[#132238]">{{ getTravellerName(traveller) }}</p>
                        <p class="mt-1 text-xs text-[#5f6b7d]">
                          {{ Number(traveller.isGuest) ? `Passport ${traveller.guestPassportNumber || '--'}` : 'Booker' }}
                        </p>
                      </div>

                      <div class="text-right">
                        <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-[#8a96a8]">Seat</p>
                        <p class="mt-1 text-sm font-semibold text-[#132238]">{{ traveller.seatNumber || '--' }}</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div
                  v-if="getOfferSnapshot(booking)"
                  class="mt-4 rounded-2xl border border-[#f8d6df] bg-gradient-to-r from-[#fff7f8] to-white p-4"
                >
                  <div class="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p class="text-sm font-bold uppercase tracking-[0.18em] text-[#e63946]">Flight Cancelled</p>
                      <p class="mt-1 text-xs text-[#7c8798]">{{ getOfferSnapshot(booking).expiryText || 'Offer available for review' }}</p>
                    </div>
                  </div>

                  <div class="mt-4 grid gap-3 md:grid-cols-[1fr_36px_1fr] md:items-center">
                    <div class="rounded-2xl border border-[#f8d6df] bg-white p-4">
                      <p class="text-[10px] font-bold uppercase tracking-[0.16em] text-[#e63946]">Cancelled</p>
                      <p class="mt-2 text-2xl font-bold text-[#132238]">{{ getOfferSnapshot(booking).original?.FlightNumber || 'N/A' }}</p>
                      <p class="mt-2 text-sm text-[#6e6e73]">
                        {{ formatFlightDateNumeric(getOfferSnapshot(booking).original) }} · {{ getOfferSnapshot(booking).original?.DepartureTime || '--' }}
                      </p>
                    </div>

                    <div class="hidden items-center justify-center text-[#9ca3af] md:flex">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                        <path d="M5 12h14"></path>
                        <path d="M13 5l7 7-7 7"></path>
                      </svg>
                    </div>

                    <div class="rounded-2xl border border-[#c8f1df] bg-[#f4fffa] p-4">
                      <p class="text-[10px] font-bold uppercase tracking-[0.16em] text-[#12a36d]">Proposed</p>
                      <p class="mt-2 text-2xl font-bold text-[#132238]">{{ getOfferSnapshot(booking).proposed?.FlightNumber || 'N/A' }}</p>
                      <p class="mt-2 text-sm text-[#6e6e73]">
                        {{ formatFlightDateNumeric(getOfferSnapshot(booking).proposed) }} · {{ getOfferSnapshot(booking).proposed?.DepartureTime || '--' }}
                      </p>
                    </div>
                  </div>

                  <p class="mt-5 text-sm text-[#6e6e73]">Booked on {{ formatBookedDate(booking.createdAt) }}</p>
                </div>

                <div
                  v-else-if="getRefundSnapshot(booking)"
                  class="mt-4 rounded-2xl border border-[#f8d6df] bg-gradient-to-r from-[#fff7f8] to-white p-4"
                >
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <p class="text-sm font-bold uppercase tracking-[0.18em] text-[#e63946]">Flight Cancelled</p>
                    <p class="rounded-full border border-[#f8d6df] bg-white px-3 py-1 text-sm font-semibold text-[#e63946]">
                      Refunded
                    </p>
                  </div>

                  <p class="mt-3 text-xl font-semibold text-[#132238]">
                    Your flight has been cancelled and your payment has been fully refunded.
                  </p>

                  <div class="mt-4 grid gap-3 md:grid-cols-2">
                    <div class="rounded-2xl border border-[#f8d6df] bg-white p-4">
                      <p class="text-[10px] font-bold uppercase tracking-[0.16em] text-[#e63946]">Cancelled Flight</p>
                      <p class="mt-2 text-2xl font-bold text-[#132238]">{{ getRefundSnapshot(booking).flight?.FlightNumber || 'N/A' }}</p>
                      <p class="mt-2 text-sm text-[#6e6e73]">
                        {{ formatFlightDateNumeric(getRefundSnapshot(booking).flight) }} · {{ getRefundSnapshot(booking).flight?.DepartureTime || '--' }}
                      </p>
                    </div>

                    <div class="rounded-2xl border border-[#f8d6df] bg-white p-4">
                      <p class="text-[10px] font-bold uppercase tracking-[0.16em] text-[#e63946]">Refund Amount</p>
                      <p class="mt-2 text-[42px] font-bold leading-none text-[#e63946]">${{ getRefundSnapshot(booking).amount }}</p>
                      <p class="mt-3 text-sm text-[#6e6e73]">Ref {{ getRefundSnapshot(booking).refundID }}</p>
                    </div>
                  </div>

                  <p class="mt-4 text-sm text-[#6e6e73]">
                    The refund was processed to your original payment method. Please allow 3-5 business days for the funds to appear in your account.
                  </p>

                  <p class="mt-5 text-sm text-[#6e6e73]">Booked on {{ formatBookedDate(booking.createdAt) }}</p>
                </div>

                <div class="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-[#edf1f6] pt-4">
                  <div>
                    <p class="text-sm font-semibold text-[#132238]">{{ getOutcomeSummary(booking).title }}</p>
                    <p class="mt-1 text-sm text-[#5f6b7d]">{{ getOutcomeSummary(booking).detail }}</p>
                  </div>

                  <div class="flex flex-wrap gap-3">
                    <button
                      @click="toggleFlightInfo(booking)"
                      class="inline-flex items-center gap-2 rounded-xl border border-black/10 px-4 py-3 text-sm font-semibold text-[#1d1d1f] transition hover:border-[#e63946]/30 hover:bg-[#f7f7f8]"
                    >
                      <span>{{ isFlightInfoExpanded(booking) ? 'Hide flight details' : 'View flight details' }}</span>
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        class="transition"
                        :class="isFlightInfoExpanded(booking) ? 'rotate-180' : ''"
                      >
                        <path d="M6 9l6 6 6-6"></path>
                      </svg>
                    </button>
                    <button
                      @click="getOutcomeSummary(booking).action()"
                      :disabled="getOutcomeSummary(booking).disabled"
                      class="rounded-xl px-4 py-3 text-sm font-semibold text-white transition"
                      :class="[
                        getOfferSnapshot(booking)
                          ? 'bg-[#ee8a00] hover:bg-[#d97706]'
                          : 'bg-gradient-to-r from-[#e63946] to-[#f43f5e] hover:shadow-[0_12px_28px_rgba(230,57,70,0.28)]',
                        getOutcomeSummary(booking).disabled ? 'cursor-not-allowed opacity-50 hover:shadow-none' : '',
                      ]"
                    >
                      {{ resumingBookingIds.has(Number(booking.bookingID)) ? 'Redirecting...' : getOutcomeSummary(booking).actionLabel }}
                    </button>
                  </div>
                </div>

                <div
                  v-if="isFlightInfoExpanded(booking)"
                  class="mt-4 rounded-2xl border border-black/8 bg-[#fcfcfd] p-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)]"
                >
                  <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p class="text-[11px] font-bold uppercase tracking-[0.14em] text-[#8a96a8]">Flight details</p>
                      <p class="mt-1 text-sm text-[#5f6b7d]">
                        {{ hasAcceptedOffer(booking)
                          ? 'Compare the original disrupted flight against your confirmed replacement.'
                          : 'Additional booking information for this leg.' }}
                      </p>
                    </div>
                    <span
                      class="rounded-full px-3 py-1 text-xs font-semibold"
                      :class="hasAcceptedOffer(booking) ? 'bg-[#fff7e8] text-[#9a6200]' : hasRefund(booking) ? 'bg-[#fff5f7] text-[#d72660]' : 'bg-[#f3f4f6] text-[#475569]'"
                    >
                      {{ hasAcceptedOffer(booking) ? 'Replacement confirmed' : paymentStatusLabel(booking) }}
                    </span>
                  </div>

                  <template v-if="hasAcceptedOffer(booking)">
                    <div class="grid gap-3 md:grid-cols-[1fr_36px_1fr] md:items-center">
                      <div class="rounded-2xl border border-[#f8d6df] bg-white p-4">
                        <p class="text-[10px] font-bold uppercase tracking-[0.16em] text-[#e63946]">Original cancelled flight</p>
                        <p class="mt-2 text-2xl font-bold text-[#132238]">{{ getAcceptedOfferSnapshot(booking)?.original?.FlightNumber || '--' }}</p>
                        <p class="mt-2 text-sm font-medium text-[#5f6b7d]">
                          {{ getAcceptedOfferSnapshot(booking)?.original?.Origin || '--' }} to {{ getAcceptedOfferSnapshot(booking)?.original?.Destination || '--' }}
                        </p>
                        <p class="mt-2 text-sm text-[#6e6e73]">
                          {{ formatFlightDate(getAcceptedOfferSnapshot(booking)?.original) }} ·
                          {{ formatFlightTime(getAcceptedOfferSnapshot(booking)?.original?.DepartureTime) }} to
                          {{ formatFlightTime(getAcceptedOfferSnapshot(booking)?.original?.ArrivalTime) }}
                        </p>
                      </div>

                      <div class="hidden items-center justify-center text-[#c79d4f] md:flex">
                        <svg width="28" height="20" viewBox="0 0 28 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M2 10H20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                          <path d="M14 4L21 10L14 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                          <path d="M22.5 10H26" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.55"/>
                        </svg>
                      </div>

                      <div class="rounded-2xl border border-[#f4d6a6] bg-gradient-to-r from-[#fff8ec] to-[#fffdf7] p-4">
                        <p class="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9a6200]">Confirmed replacement flight</p>
                        <p class="mt-2 text-2xl font-bold text-[#132238]">{{ getAcceptedOfferSnapshot(booking)?.proposed?.FlightNumber || '--' }}</p>
                        <p class="mt-2 text-sm font-medium text-[#5f6b7d]">
                          {{ getAcceptedOfferSnapshot(booking)?.proposed?.Origin || '--' }} to {{ getAcceptedOfferSnapshot(booking)?.proposed?.Destination || '--' }}
                        </p>
                        <p class="mt-2 text-sm text-[#6e6e73]">
                          {{ formatFlightDate(getAcceptedOfferSnapshot(booking)?.proposed) }} ·
                          {{ formatFlightTime(getAcceptedOfferSnapshot(booking)?.proposed?.DepartureTime) }} to
                          {{ formatFlightTime(getAcceptedOfferSnapshot(booking)?.proposed?.ArrivalTime) }}
                        </p>
                        <p class="mt-3 text-sm text-[#7a5a20]">
                          New seats confirmed: <span class="font-semibold text-[#9a6200]">{{ booking.seatNumber || '--' }}</span>
                        </p>
                      </div>
                    </div>
                  </template>

                  <div v-else>
                    <div class="grid gap-3 md:grid-cols-2">
                      <div class="rounded-xl bg-white p-4 ring-1 ring-black/5">
                        <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#8a96a8]">Baggage</p>
                        <p class="mt-2 text-base font-semibold text-[#132238]">{{ getFlightBaggage(getFlight(booking)) }}</p>
                        <p class="mt-1 text-sm text-[#5f6b7d]">Checked allowance from the booked fare.</p>
                      </div>

                      <div class="rounded-xl bg-white p-4 ring-1 ring-black/5">
                        <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#8a96a8]">Meals</p>
                        <p class="mt-2 text-base font-semibold text-[#132238]">{{ getFlightMeals(getFlight(booking)) }}</p>
                        <p class="mt-1 text-sm text-[#5f6b7d]">{{ getFlightBeverages(getFlight(booking)) }}</p>
                      </div>
                    </div>

                    <div class="mt-3 grid gap-3 md:grid-cols-2">
                      <div class="rounded-xl bg-white p-4 ring-1 ring-black/5">
                        <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#8a96a8]">Beverages</p>
                        <p class="mt-2 text-base font-semibold text-[#132238]">{{ getFlightBeverages(getFlight(booking)) }}</p>
                        <p class="mt-1 text-sm text-[#5f6b7d]">Served according to the flight's onboard service.</p>
                      </div>

                      <div class="rounded-xl bg-white p-4 ring-1 ring-black/5">
                        <p class="text-[10px] font-bold uppercase tracking-[0.12em] text-[#8a96a8]">Wi-Fi</p>
                        <p class="mt-2 text-base font-semibold text-[#132238]">{{ getFlightWifiLabel(getFlight(booking)) }}</p>
                        <p class="mt-1 text-sm text-[#5f6b7d]">
                          {{ normalizeBooleanFlag(getFlight(booking)?.Wifi ?? getFlight(booking)?.wifi) ? 'Stay connected during your journey.' : 'This fare does not include onboard internet.' }}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div
                    v-if="hasAcceptedOffer(booking)"
                    class="mt-4 rounded-xl border border-[#f4d6a6] bg-gradient-to-r from-[#fff8ec] to-[#fffdf7] p-4"
                  >
                    <p class="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9a6200]">Rebooking note</p>
                    <p class="mt-2 text-sm leading-6 text-[#7a5a20]">
                      This itinerary was moved to a replacement flight after disruption. The original flight is shown above for reference, while the replacement card reflects the new confirmed journey and saved seats.
                    </p>
                  </div>

                  <div
                    v-if="getOfferSnapshot(booking)"
                    class="mt-4 rounded-xl border border-[#f8d6df] bg-[#fff8fa] p-4"
                  >
                    <p class="text-[10px] font-bold uppercase tracking-[0.14em] text-[#d72660]">Offer status</p>
                    <p class="mt-2 text-sm leading-6 text-[#6b5563]">
                      Review required before {{ getOfferSnapshot(booking).expiryText || 'the stated expiry time' }}. The original flight was {{ getOfferSnapshot(booking).original?.FlightNumber || '--' }} and the proposed replacement is {{ getOfferSnapshot(booking).proposed?.FlightNumber || '--' }}.
                    </p>
                  </div>

                  <div
                    v-else-if="getRefundSnapshot(booking)"
                    class="mt-4 rounded-xl border border-[#f8d6df] bg-[#fff8fa] p-4"
                  >
                    <p class="text-[10px] font-bold uppercase tracking-[0.14em] text-[#d72660]">Refund status</p>
                    <p class="mt-2 text-sm leading-6 text-[#6b5563]">
                      Refund reference {{ getRefundSnapshot(booking).refundID }} for ${{ getRefundSnapshot(booking).amount }} was processed to the original payment method.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </article>
      </div>

      <p class="mt-10 text-center text-xs text-[#7c8798]">Need help with your booking? Contact support.</p>
    </section>
  </main>
</template>
