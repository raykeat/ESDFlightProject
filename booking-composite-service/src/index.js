const express = require('express');
const axios = require('axios');
const cors = require('cors');
const app = express();
const amqp = require('amqplib');

app.use(cors({
  origin: [
    'http://localhost:5173',
    'http://localhost:5174',
  ],
  credentials: true
}));

app.use(express.json());

// Configuration - service URLs from environment variables
const PASSENGER_SERVICE_URL = (process.env.PASSENGER_SERVICE_URL || 'http://passenger-service:3000').replace(/\/$/, '');
const FLIGHT_SERVICE_URL = (process.env.FLIGHT_SERVICE_URL || 'http://flight-service:3000').replace(/\/$/, '');
const PAYMENT_SERVICE_URL = (process.env.PAYMENT_SERVICE_URL || 'http://payment-service:5000').replace(/\/$/, '');
const VOUCHER_SERVICE_URL = (process.env.VOUCHER_SERVICE_URL || 'http://voucher-service:5005').replace(/\/$/, '');
const NOTIFICATION_SERVICE_URL = (process.env.NOTIFICATION_SERVICE_URL || 'http://notification-service:3000').replace(/\/$/, '');
const SEATS_SERVICE_URL = (process.env.SEATS_SERVICE_URL || 'http://seats-service:5003').replace(/\/$/, '');
const RECORD_SERVICE_URL = (process.env.RECORD_SERVICE_URL || 'http://record-service:3000').replace(/\/$/, '');
const OFFER_SERVICE_URL = (process.env.OFFER_SERVICE_URL || 'http://offer-service:5000').replace(/\/$/, '');
const MILES_EARN_SERVICE_URL = (process.env.MILES_EARN_SERVICE_URL || 'http://miles-earn-service:5009').replace(/\/$/, '');
const RABBITMQ_URL             = process.env.RABBITMQ_URL            || 'amqp://guest:guest@rabbitmq:5672';
const STRIPE_MIN_AMOUNT        = 0.50;

// ==========================================
// RABBITMQ HELPER
// ==========================================
async function publishBookingConfirmed(bookingData) {
  let connection;
  try {
    connection = await amqp.connect(RABBITMQ_URL);
    const channel = await connection.createChannel();
 
    const exchange = 'airline_events';
    await channel.assertExchange(exchange, 'topic', { durable: true });
 
    channel.publish(
      exchange,
      'booking.confirmed',
      Buffer.from(JSON.stringify(bookingData)),
      { persistent: true }
    );
 
    console.log('✓ Published booking.confirmed to RabbitMQ');
    await channel.close();
  } catch (err) {
    console.error('✗ Failed to publish to RabbitMQ:', err.message);
  } finally {
    if (connection) await connection.close();
  }
}
 
// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'booking-composite-service' });
});

function buildCancelUrl(baseCancelUrl, frontendOrigin, outboundBookingID, returnBookingID) {
  try {
    const cancel = new URL(baseCancelUrl || `${frontendOrigin}/booking-confirmation`);
    cancel.searchParams.set('cancelled', 'true');
    cancel.searchParams.set('bookingID', String(outboundBookingID));
    if (returnBookingID) {
      cancel.searchParams.set('returnBookingID', String(returnBookingID));
    }
    return cancel.toString();
  } catch {
    const fallback = new URL(`${frontendOrigin}/booking-confirmation`);
    fallback.searchParams.set('cancelled', 'true');
    fallback.searchParams.set('bookingID', String(outboundBookingID));
    if (returnBookingID) {
      fallback.searchParams.set('returnBookingID', String(returnBookingID));
    }
    return fallback.toString();
  }
}

function firstNonEmpty(...values) {
  return values.find((value) => value !== undefined && value !== null && String(value).trim() !== '');
}

function normalizedStatus(status) {
  return String(status || '').trim();
}

function parseSeatNumbers(value) {
  return String(value || '')
    .split(',')
    .map((seat) => seat.trim())
    .filter(Boolean);
}

function parseIdList(value) {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value.map(Number).filter((id) => Number.isFinite(id) && id > 0);
  }
  return String(value)
    .split(',')
    .map((id) => Number(id.trim()))
    .filter((id) => Number.isFinite(id) && id > 0);
}

function isPendingRecordExpired(createdAt, holdMinutes = 5) {
  if (!createdAt) return true;
  const createdTime = new Date(createdAt);
  if (Number.isNaN(createdTime.getTime())) return true;

  return (Date.now() - createdTime.getTime()) > holdMinutes * 60 * 1000;
}

function getNormalizedFlightID(record) {
  return Number(firstNonEmpty(record.flightID, record.FlightID));
}

function getNormalizedSeatNumber(record) {
  return firstNonEmpty(record.seatNumber, record.SeatNumber, record.seatID, record.SeatID);
}

async function awardMilesForBookingIfCompleted({ bookingID, force = false }) {
  const bookingResponse = await axios.get(`${RECORD_SERVICE_URL}/records/${bookingID}`);
  const booking = bookingResponse.data;

  if (String(booking.status || '').toLowerCase() !== 'confirmed') {
    return { awarded: false, reason: 'booking_not_confirmed' };
  }

  if (booking.milesAwardedAt) {
    return {
      awarded: false,
      reason: 'already_awarded',
      milesAwardedAt: booking.milesAwardedAt,
      milesAwarded: booking.milesAwarded || null,
      transactionID: booking.milesTransactionID || null,
    };
  }

  const passengerID = Number(firstNonEmpty(booking.passengerID, booking.PassengerID));
  if (!passengerID) {
    return { awarded: false, reason: 'guest_or_missing_passenger' };
  }

  const flightID = Number(firstNonEmpty(booking.flightID, booking.FlightID));
  const flightResponse = await axios.get(`${FLIGHT_SERVICE_URL}/flight/${flightID}`);
  const flight = flightResponse.data || {};

  if (String(flight.Status || '').toLowerCase() === 'cancelled') {
    return { awarded: false, reason: 'flight_cancelled' };
  }

  const flightStatus = String(flight.Status || '').toLowerCase();
  const hasCompleted = flightStatus === 'landed';

  if (!force && !hasCompleted) {
    return {
      awarded: false,
      reason: 'flight_not_landed',
      flightStatus: flight.Status || null,
    };
  }

  const amountPaid = Number(firstNonEmpty(booking.amountPaid, booking.amount, booking.AmountPaid));
  const earnResponse = await axios.post(`${MILES_EARN_SERVICE_URL}/miles/earn`, {
    passengerID,
    flightCost: amountPaid,
    bookingReference: `BK-${String(bookingID).padStart(5, '0')}`,
    currency: 'SGD',
    milesPerDollar: 1,
  });

  await axios.put(`${RECORD_SERVICE_URL}/records/${bookingID}/miles-awarded`, {
    milesAwarded: earnResponse.data.earnedMiles,
    transactionID: earnResponse.data.transactionID,
  });

  return {
    awarded: true,
    bookingID,
    passengerID,
    flightID,
    earnedMiles: earnResponse.data.earnedMiles,
    transactionID: earnResponse.data.transactionID,
    newBalance: earnResponse.data.newBalance,
    forced: force,
  };
}

async function awardMilesForFlight(flightID, force = false) {
  const bookingsResponse = await axios.get(`${RECORD_SERVICE_URL}/records`, {
    params: {
      FlightID: flightID,
      bookingstatus: 'Confirmed',
    },
  });

  const bookings = Array.isArray(bookingsResponse.data) ? bookingsResponse.data : [];
  const results = await Promise.allSettled(
    bookings.map((booking) => awardMilesForBookingIfCompleted({
      bookingID: Number(firstNonEmpty(booking.bookingID, booking.BookingID)),
      force,
    }))
  );

  const summary = {
    flightID: Number(flightID),
    totalBookings: bookings.length,
    awarded: 0,
    skipped: 0,
    failed: 0,
    details: [],
  };

  results.forEach((result, index) => {
    const booking = bookings[index];
    const bookingID = Number(firstNonEmpty(booking.bookingID, booking.BookingID));

    if (result.status === 'fulfilled') {
      const value = result.value || {};
      if (value.awarded) {
        summary.awarded += 1;
      } else {
        summary.skipped += 1;
      }
      summary.details.push({ bookingID, ...value });
    } else {
      summary.failed += 1;
      summary.details.push({
        bookingID,
        awarded: false,
        reason: 'error',
        message: result.reason?.response?.data?.message || result.reason?.message || String(result.reason),
      });
    }
  });

  return summary;
}

function splitAmount(totalAmount, parts) {
  const totalCents = Math.round(Number(totalAmount || 0) * 100);
  const base = Math.floor(totalCents / parts);
  const remainder = totalCents % parts;

  return Array.from({ length: parts }, (_, index) => ((base + (index < remainder ? 1 : 0)) / 100));
}

function roundToCents(value) {
  return Math.round(Number(value || 0) * 100) / 100;
}

function getVoucherValue(voucher) {
  return Number(firstNonEmpty(voucher?.voucherValue, voucher?.value, voucher?.VoucherValue, voucher?.Value) || 0);
}

function calculateTravelCreditApplication(totalAmount, voucherValue) {
  const grossAmount = roundToCents(totalAmount);
  const rawVoucherValue = roundToCents(voucherValue);

  if (!Number.isFinite(grossAmount) || grossAmount <= 0) {
    throw new Error('Total amount must be greater than 0');
  }

  if (!Number.isFinite(rawVoucherValue) || rawVoucherValue <= 0) {
    return {
      appliedAmount: 0,
      payableAmount: grossAmount,
    };
  }

  const maxApplicable = roundToCents(grossAmount - STRIPE_MIN_AMOUNT);
  if (maxApplicable <= 0) {
    throw new Error(`Minimum charge amount is SGD $${STRIPE_MIN_AMOUNT.toFixed(2)}`);
  }

  if (rawVoucherValue > maxApplicable) {
    throw new Error(`Travel Credit exceeds the amount that can be charged for this booking. Please choose a smaller credit or a higher fare.`);
  }

  const appliedAmount = roundToCents(rawVoucherValue);
  const payableAmount = roundToCents(grossAmount - appliedAmount);

  if (payableAmount < STRIPE_MIN_AMOUNT) {
    throw new Error(`Travel Credit cannot reduce the payment below SGD $${STRIPE_MIN_AMOUNT.toFixed(2)}`);
  }

  return {
    appliedAmount,
    payableAmount,
  };
}

function proportionalSplit(amount, total, parts) {
  if (!Number.isFinite(amount) || amount <= 0) {
    return Array.from({ length: parts }, () => 0);
  }

  if (!Number.isFinite(total) || total <= 0) {
    return splitAmount(amount, parts);
  }

  const split = splitAmount(amount, parts);
  const splitTotal = roundToCents(split.reduce((sum, value) => sum + Number(value || 0), 0));
  const delta = roundToCents(amount - splitTotal);

  if (Math.abs(delta) < 0.01 || !split.length) {
    return split;
  }

  split[split.length - 1] = roundToCents(split[split.length - 1] + delta);
  return split;
}

async function getGroupBookingsForOffer(offer) {
  const primaryBookingResponse = await axios.get(`${RECORD_SERVICE_URL}/records/${offer.bookingID}`);
  const primaryBooking = primaryBookingResponse.data;
  const bookerID = Number(firstNonEmpty(
    primaryBooking.bookedByPassengerID,
    primaryBooking.BookedByPassengerID,
    primaryBooking.passengerID,
    primaryBooking.PassengerID,
    offer.passengerID
  ));
  const flightID = Number(firstNonEmpty(
    primaryBooking.flightID,
    primaryBooking.FlightID,
    offer.origFlightID
  ));

  const allBookingsResponse = await axios.get(`${RECORD_SERVICE_URL}/records/passenger/${bookerID}`);
  const allBookings = Array.isArray(allBookingsResponse.data) ? allBookingsResponse.data : [];

  return allBookings
    .filter((record) => {
      const sameBooker = Number(firstNonEmpty(
        record.bookedByPassengerID,
        record.BookedByPassengerID,
        record.passengerID,
        record.PassengerID
      )) === bookerID;
      const sameFlight = Number(firstNonEmpty(record.flightID, record.FlightID)) === flightID;
      return sameBooker && sameFlight;
    })
    .sort((a, b) => Number(firstNonEmpty(a.bookingID, a.BookingID)) - Number(firstNonEmpty(b.bookingID, b.BookingID)));
}

function buildTravelers(payload) {
  const {
    passengerID,
    seatNumber,
    returnSeatNumber,
    travelers,
  } = payload;

  const outboundSeats = parseSeatNumbers(seatNumber);
  const returnSeats = parseSeatNumbers(returnSeatNumber);
  const isRoundTrip = Boolean(payload.returnFlightID && payload.returnSeatNumber);

  if (!outboundSeats.length) {
    throw new Error('At least one outbound seat is required');
  }

  if (isRoundTrip && returnSeats.length !== outboundSeats.length) {
    throw new Error('Return seat count must match outbound seat count for group bookings');
  }

  if (!travelers || !Array.isArray(travelers) || !travelers.length) {
    return [{
      passengerID: Number(passengerID),
      bookedByPassengerID: Number(passengerID),
      isGuest: false,
      guestFirstName: null,
      guestLastName: null,
      guestPassportNumber: null,
      outboundSeatNumber: outboundSeats[0],
      returnSeatNumber: isRoundTrip ? returnSeats[0] : null,
    }];
  }

  if (travelers.length !== outboundSeats.length) {
    throw new Error('Traveller count must match the number of selected seats');
  }

  return travelers.map((traveler, index) => {
    const normalized = {
      passengerID: traveler.isGuest ? null : Number(traveler.passengerID || passengerID),
      bookedByPassengerID: Number(passengerID),
      isGuest: Boolean(traveler.isGuest),
      guestFirstName: traveler.guestFirstName || null,
      guestLastName: traveler.guestLastName || null,
      guestPassportNumber: traveler.guestPassportNumber || null,
      outboundSeatNumber: outboundSeats[index],
      returnSeatNumber: isRoundTrip ? returnSeats[index] : null,
    };

    if (!normalized.isGuest && !normalized.passengerID) {
      throw new Error('Primary traveller PassengerID is missing');
    }

    if (normalized.isGuest && (!normalized.guestFirstName || !normalized.guestLastName || !normalized.guestPassportNumber)) {
      throw new Error('Guest travellers require first name, last name, and passport number');
    }

    return normalized;
  });
}

async function getFlightEmailDetails(flightID) {
  try {
    const response = await axios.get(`${FLIGHT_SERVICE_URL}/flight/${flightID}`);
    const flight = response.data || {};

    return {
      flightNumber: firstNonEmpty(flight.FlightNumber, flight.flightNumber, flight.flight_number),
      origin: firstNonEmpty(flight.Origin, flight.origin),
      destination: firstNonEmpty(flight.Destination, flight.destination),
      departureDate: firstNonEmpty(flight.Date, flight.FlightDate, flight.DepartureDate, flight.departureDate, flight.departure_date),
    };
  } catch (err) {
    console.warn('Could not fetch flight details for notification:', err.message);
    return {};
  }
}

async function cleanupPendingRecords(records) {
  const uniqueRecords = records.filter(Boolean);

  for (const record of uniqueRecords) {
    const flightID = getNormalizedFlightID(record);
    const seatNumber = getNormalizedSeatNumber(record);
    const bookingID = Number(firstNonEmpty(record.bookingID, record.BookingID));

    if (flightID && seatNumber) {
      try {
        await axios.post(`${SEATS_SERVICE_URL}/seats/release`, { flightID, seatNumber });
      } catch (err) {
        console.warn(`Could not release held seat for booking ${bookingID}:`, err.response?.data?.message || err.message);
      }
    }

    if (bookingID) {
      try {
        await axios.delete(`${RECORD_SERVICE_URL}/record/${bookingID}`);
      } catch (err) {
        console.warn(`Could not delete expired pending booking ${bookingID}:`, err.response?.data?.message || err.message);
      }
    }
  }
}

// ==========================================
// BOOKING FLOW - Scenario 1
// ==========================================
app.post('/api/bookings', async (req, res) => {
  const {
    passengerID,
    flightID,
    seatNumber,
    returnFlightID,
    returnSeatNumber,
    amount,
    outboundAmount,
    returnAmount,
    flightNumber,
    cancelUrl,
    frontendBaseUrl,
    travelers,
    selectedPerksVoucherID,
    selectedPerksVoucherCode,
    selectedPerksVoucherType,
    selectedTravelCreditVoucherID,
    selectedTravelCreditVoucherCode,
    selectedTravelCreditVoucherType,
    requestedPaymentAmount,
  } = req.body;
  
  if (!passengerID || !flightID || !seatNumber) {
    return res.status(400).json({ 
      error: 'Missing required fields: passengerID, flightID, seatNumber' 
    });
  }

  if ((returnFlightID && !returnSeatNumber) || (!returnFlightID && returnSeatNumber)) {
    return res.status(400).json({
      error: 'Both returnFlightID and returnSeatNumber are required for round-trip bookings'
    });
  }

  const isRoundTrip = Boolean(returnFlightID && returnSeatNumber);
  let travelerManifest = [];

  const outboundFare = isRoundTrip
    ? Number(outboundAmount ?? 0)
    : Number(amount ?? 0);
  const returnFare = isRoundTrip
    ? Number(returnAmount ?? amount ?? 0)
    : 0;

  if (!Number.isFinite(outboundFare) || outboundFare < 0 || !Number.isFinite(returnFare) || returnFare < 0) {
    return res.status(400).json({
      error: 'Invalid fare amount. outboundAmount/returnAmount must be valid numbers for round-trip.'
    });
  }

  let passenger = null;
  let outboundBooking = null;
  let returnBooking = null;
  const outboundBookings = [];
  const returnBookings = [];
  let outboundSeatHeld = false;
  let returnSeatHeld = false;
  let userBookingCount = 1;
  let travelCreditVoucher = null;
  let travelCreditApplication = { appliedAmount: 0, payableAmount: roundToCents(outboundFare + returnFare) };
  let travelCreditAlreadyRedeemed = false;
 
  console.log(`Starting booking flow for passenger ${passengerID}, flight ${flightID}, seat ${seatNumber}, returnFlight ${returnFlightID || 'N/A'}, amount ${amount}`);
 
  try {
    travelerManifest = buildTravelers(req.body);

    // Step 1: Validate passenger exists (OutSystems External API)
    console.log('Step 1: Validating passenger...');
    // Correct endpoint from Swagger: /getpassenger/{passenger_id}/
    const passengerResponse = await axios.get(`${PASSENGER_SERVICE_URL}/getpassenger/${passengerID}/`);
    passenger = passengerResponse.data;
    if (!passenger) {
      throw new Error('Passenger not found');
    }
    console.log('✓ Passenger validated:', passenger.FirstName, passenger.LastName);

    // Step 2: Fetch existing bookings to calculate user-facing booking number
    try {
      const existingBookingsResponse = await axios.get(`${RECORD_SERVICE_URL}/records/passenger/${passengerID}`);
      const confirmedBookings = existingBookingsResponse.data.filter(b => b.status === 'Confirmed');
      userBookingCount = confirmedBookings.length + 1;
      console.log(`✓ Passenger has ${confirmedBookings.length} previous confirmed bookings. This is Booking #${userBookingCount}`);
    } catch (err) {
      console.warn('Could not fetch existing bookings for count, defaulting to 1', err.message);
    }

    const totalBaseAmount = roundToCents(outboundFare + returnFare);

    if (selectedTravelCreditVoucherID && selectedTravelCreditVoucherCode && selectedTravelCreditVoucherType === 'TRAVEL_CREDIT') {
      const voucherResponse = await axios.get(`${VOUCHER_SERVICE_URL}/vouchers/code/${encodeURIComponent(selectedTravelCreditVoucherCode)}`);
      travelCreditVoucher = voucherResponse.data || {};

      if (Number(travelCreditVoucher.passengerID) !== Number(passengerID)) {
        return res.status(403).json({ error: 'This travel credit voucher does not belong to the signed-in passenger' });
      }

      if (String(travelCreditVoucher.voucherType || '') !== 'TRAVEL_CREDIT') {
        return res.status(400).json({ error: 'Only Travel Credit vouchers can be applied to flight payments' });
      }

      if (String(travelCreditVoucher.status || '') !== 'ACTIVE') {
        return res.status(409).json({ error: 'This Travel Credit voucher is no longer active' });
      }

      travelCreditApplication = calculateTravelCreditApplication(totalBaseAmount, getVoucherValue(travelCreditVoucher));
    }

    const outboundGrossSplits = splitAmount(outboundFare, travelerManifest.length);
    const returnGrossSplits = isRoundTrip ? splitAmount(returnFare, travelerManifest.length) : [];

    const outboundShareRatio = totalBaseAmount > 0 ? outboundFare / totalBaseAmount : 0;
    const returnShareRatio = totalBaseAmount > 0 ? returnFare / totalBaseAmount : 0;
    const outboundDiscount = roundToCents(travelCreditApplication.appliedAmount * outboundShareRatio);
    const returnDiscount = roundToCents(travelCreditApplication.appliedAmount - outboundDiscount);
    const adjustedOutboundFare = roundToCents(outboundFare - outboundDiscount);
    const adjustedReturnFare = roundToCents(returnFare - returnDiscount);
    const outboundNetSplits = splitAmount(adjustedOutboundFare, travelerManifest.length);
    const returnNetSplits = isRoundTrip ? splitAmount(adjustedReturnFare, travelerManifest.length) : [];

    // Step 3: Hold outbound seat(s)
    console.log('Step 5: Holding outbound seat(s)...');
    await axios.post(`${SEATS_SERVICE_URL}/seats/hold`, {
      flightID,
      seatNumber,
      passengerID
    });
    outboundSeatHeld = true;

    // Step 6: Hold return seat(s) if needed
    if (isRoundTrip) {
      console.log('Step 6: Holding return seat(s)...');
      await axios.post(`${SEATS_SERVICE_URL}/seats/hold`, {
        flightID: returnFlightID,
        seatNumber: returnSeatNumber,
        passengerID
      });
      returnSeatHeld = true;
    }
    console.log('✓ Seat(s) held successfully');

    // Step 5: Create outbound pending booking records
    console.log('Step 5b: Creating outbound pending booking records...');
    for (let i = 0; i < travelerManifest.length; i += 1) {
      const traveler = travelerManifest[i];
      const outboundBookingResponse = await axios.post(`${RECORD_SERVICE_URL}/records`, {
        passengerID: traveler.passengerID,
        bookedByPassengerID: traveler.bookedByPassengerID,
        flightID,
        amount: outboundNetSplits[i],
        originalAmountPaid: outboundGrossSplits[i],
        travelCreditVoucherID: travelCreditVoucher?.voucherID || null,
        travelCreditVoucherCode: travelCreditVoucher?.voucherCode || null,
        travelCreditAppliedAmount: roundToCents(outboundGrossSplits[i] - outboundNetSplits[i]),
        seatNumber: traveler.outboundSeatNumber,
        isGuest: traveler.isGuest,
        guestFirstName: traveler.guestFirstName,
        guestLastName: traveler.guestLastName,
        guestPassportNumber: traveler.guestPassportNumber,
      });
      outboundBookings.push({
        ...outboundBookingResponse.data,
        seatNumber: traveler.outboundSeatNumber,
        traveler,
      });
    }
    outboundBooking = outboundBookings[0];
    console.log(`✓ Created ${outboundBookings.length} outbound pending booking record(s)`);

    // Step 6b: Create return pending booking records
    if (isRoundTrip) {
      console.log('Step 6b: Creating return pending booking records...');
      for (let i = 0; i < travelerManifest.length; i += 1) {
        const traveler = travelerManifest[i];
        const returnBookingResponse = await axios.post(`${RECORD_SERVICE_URL}/records`, {
          passengerID: traveler.passengerID,
          bookedByPassengerID: traveler.bookedByPassengerID,
          flightID: returnFlightID,
          amount: returnNetSplits[i],
          originalAmountPaid: returnGrossSplits[i],
          travelCreditVoucherID: travelCreditVoucher?.voucherID || null,
          travelCreditVoucherCode: travelCreditVoucher?.voucherCode || null,
          travelCreditAppliedAmount: roundToCents(returnGrossSplits[i] - returnNetSplits[i]),
          seatNumber: traveler.returnSeatNumber,
          isGuest: traveler.isGuest,
          guestFirstName: traveler.guestFirstName,
          guestLastName: traveler.guestLastName,
          guestPassportNumber: traveler.guestPassportNumber,
        });
        returnBookings.push({
          ...returnBookingResponse.data,
          seatNumber: traveler.returnSeatNumber,
          traveler,
        });
      }
      returnBooking = returnBookings[0];
      console.log(`✓ Created ${returnBookings.length} return pending booking record(s)`);
    }

    // Step 7: Create Stripe checkout session via Payment Service
    console.log('Step 7: Creating checkout session in Payment Service...');
    const frontendOrigin = (frontendBaseUrl || 'http://localhost:5173').replace(/\/$/, '');
    let successUrl = `${frontendOrigin}/booking-success/${outboundBooking.bookingID}`
      + `?session_id={CHECKOUT_SESSION_ID}`
      + `&flightID=${encodeURIComponent(String(flightID))}`
      + `&seatNumber=${encodeURIComponent(String(seatNumber))}`;
    successUrl += `&groupBookingIDs=${encodeURIComponent(outboundBookings.map((booking) => booking.bookingID).join(','))}`;
    if (returnBooking) {
      successUrl += `&returnBookingID=${encodeURIComponent(String(returnBooking.bookingID))}`;
      successUrl += `&returnFlightID=${encodeURIComponent(String(returnFlightID))}`;
      successUrl += `&returnSeatNumber=${encodeURIComponent(String(returnSeatNumber))}`;
      successUrl += `&returnGroupBookingIDs=${encodeURIComponent(returnBookings.map((booking) => booking.bookingID).join(','))}`;
    }

    if (selectedPerksVoucherID && selectedPerksVoucherCode && selectedPerksVoucherType === 'IN_FLIGHT_PERKS') {
      successUrl += `&selectedPerksVoucherID=${encodeURIComponent(String(selectedPerksVoucherID))}`;
      successUrl += `&selectedPerksVoucherCode=${encodeURIComponent(String(selectedPerksVoucherCode))}`;
      successUrl += `&selectedPerksVoucherType=${encodeURIComponent(String(selectedPerksVoucherType))}`;
    }

    if (travelCreditVoucher) {
      successUrl += `&selectedTravelCreditVoucherID=${encodeURIComponent(String(travelCreditVoucher.voucherID))}`;
      successUrl += `&selectedTravelCreditVoucherCode=${encodeURIComponent(String(travelCreditVoucher.voucherCode))}`;
      successUrl += `&selectedTravelCreditVoucherType=${encodeURIComponent(String(travelCreditVoucher.voucherType))}`;
      successUrl += `&selectedTravelCreditVoucherValue=${encodeURIComponent(String(getVoucherValue(travelCreditVoucher)))}`;
    }

    const totalAmount = totalBaseAmount;
    const requestedAmount = Number(requestedPaymentAmount);
    const calculatedDiscountedAmount = travelCreditApplication.appliedAmount > 0
      ? travelCreditApplication.payableAmount
      : totalAmount;
    const discountedTotalAmount = Number.isFinite(requestedAmount) && requestedAmount > 0
      ? roundToCents(requestedAmount)
      : calculatedDiscountedAmount;
    const discountAmount = roundToCents(totalAmount - discountedTotalAmount);
    const finalCancelUrl = new URL(buildCancelUrl(
      cancelUrl,
      frontendOrigin,
      outboundBooking.bookingID,
      returnBooking?.bookingID || null
    ));
    finalCancelUrl.searchParams.set('groupBookingIDs', outboundBookings.map((booking) => booking.bookingID).join(','));
    if (returnBookings.length) {
      finalCancelUrl.searchParams.set('returnGroupBookingIDs', returnBookings.map((booking) => booking.bookingID).join(','));
    }
    if (travelCreditVoucher) {
      finalCancelUrl.searchParams.set('selectedTravelCreditVoucherID', String(travelCreditVoucher.voucherID));
      finalCancelUrl.searchParams.set('selectedTravelCreditVoucherCode', String(travelCreditVoucher.voucherCode));
      finalCancelUrl.searchParams.set('selectedTravelCreditVoucherType', String(travelCreditVoucher.voucherType));
    }

    const paymentPayload = {
      bookingID: outboundBooking.bookingID,
      userBookingCount,
      passengerID,
      amount: discountedTotalAmount,
      flightNumber: flightNumber || (isRoundTrip ? `SQ${flightID} & SQ${returnFlightID}` : `SQ${flightID}`),
      successUrl,
      cancelUrl: finalCancelUrl.toString(),
    };

    if (travelCreditVoucher && travelCreditApplication.appliedAmount > 0) {
      await axios.put(`${VOUCHER_SERVICE_URL}/vouchers/${travelCreditVoucher.voucherID}/redeem`, {
        bookingID: Number(outboundBooking.bookingID),
      });
      travelCreditAlreadyRedeemed = true;
    }

    const paymentResponse = await axios.post(`${PAYMENT_SERVICE_URL}/payment/checkout`, paymentPayload);

    return res.status(201).json({
      success: true,
      message: 'Pending booking created. Redirect to payment.',
      status: 'PendingPayment',
      bookingID: outboundBooking.bookingID,
      returnBookingID: returnBooking?.bookingID || null,
      bookingIDs: returnBooking
        ? [...outboundBookings.map((booking) => booking.bookingID), ...returnBookings.map((booking) => booking.bookingID)]
        : outboundBookings.map((booking) => booking.bookingID),
      outboundBookingIDs: outboundBookings.map((booking) => booking.bookingID),
      returnBookingIDs: returnBookings.map((booking) => booking.bookingID),
      userBookingCount,
      paymentID: paymentResponse.data.paymentID,
      stripeSessionID: paymentResponse.data.stripeSessionID,
      sessionUrl: paymentResponse.data.sessionUrl,
    });
  } catch (error) {
    const errorMsg = error.response?.data?.message || error.message;
    console.error('Error in booking flow:', errorMsg);

    // Best-effort cleanup for partially created records/holds
    try {
      for (const booking of outboundBookings) {
        await axios.put(`${RECORD_SERVICE_URL}/records/${booking.bookingID}/status`, { status: 'Failed' });
      }
      for (const booking of returnBookings) {
        await axios.put(`${RECORD_SERVICE_URL}/records/${booking.bookingID}/status`, { status: 'Failed' });
      }
      if (typeof outboundSeatHeld !== 'undefined' && outboundSeatHeld) {
        await axios.post(`${SEATS_SERVICE_URL}/seats/release`, { flightID, seatNumber });
      }
      if (typeof returnSeatHeld !== 'undefined' && returnSeatHeld) {
        await axios.post(`${SEATS_SERVICE_URL}/seats/release`, { flightID: returnFlightID, seatNumber: returnSeatNumber });
      }
      if (travelCreditVoucher && travelCreditAlreadyRedeemed) {
        await axios.put(`${VOUCHER_SERVICE_URL}/vouchers/${travelCreditVoucher.voucherID}/status`, { status: 'ACTIVE' }).catch(() => {});
      }
    } catch (cleanupErr) {
      console.warn('Cleanup after booking flow failure was partial:', cleanupErr.message);
    }

    return res.status(500).json({
      success: false,
      error: 'Booking failed',
      message: errorMsg
    });
  }
});

// ==========================================
// FINALISE BOOKING AFTER PAYMENT SUCCESS
// ==========================================
app.post('/api/bookings/finalize', async (req, res) => {
  const {
    bookingID,
    returnBookingID,
    groupBookingIDs,
    returnGroupBookingIDs,
    sessionID,
    flightID,
    seatNumber,
    returnFlightID,
    returnSeatNumber,
    selectedPerksVoucherID,
    selectedPerksVoucherCode,
    selectedPerksVoucherType,
  } = req.body;

  if (!bookingID || !sessionID || !flightID || !seatNumber) {
    return res.status(400).json({
      error: 'Missing required fields: bookingID, sessionID, flightID, seatNumber'
    });
  }

  try {
    // 1) Verify payment
    const paymentResponse = await axios.get(`${PAYMENT_SERVICE_URL}/payment/verify-session/${sessionID}`);
    const payment = paymentResponse.data;

    if (payment.bookingID && Number(payment.bookingID) !== Number(bookingID)) {
      return res.status(400).json({
        error: 'Payment booking mismatch',
        message: `Payment belongs to booking ${payment.bookingID}, not ${bookingID}`
      });
    }

    if (payment.status && payment.status !== 'Completed') {
      return res.status(202).json({
        success: false,
        status: payment.status,
        message: 'Payment not completed yet',
        payment,
      });
    }

    const outboundBookingIDs = parseIdList(groupBookingIDs);
    if (!outboundBookingIDs.length) outboundBookingIDs.push(Number(bookingID));
    const inboundBookingIDs = parseIdList(returnGroupBookingIDs);
    if (!inboundBookingIDs.length && returnBookingID) inboundBookingIDs.push(Number(returnBookingID));
    const allBookingIDs = [...outboundBookingIDs, ...inboundBookingIDs];

    // 2) Confirm booking records
    for (const id of allBookingIDs) {
      await axios.put(`${RECORD_SERVICE_URL}/records/${id}/status`, { status: 'Confirmed' });
    }

    // 3) Confirm seats
    await axios.post(`${SEATS_SERVICE_URL}/seats/confirm`, { flightID, seatNumber });
    if (returnFlightID && returnSeatNumber) {
      await axios.post(`${SEATS_SERVICE_URL}/seats/confirm`, {
        flightID: returnFlightID,
        seatNumber: returnSeatNumber,
      });
    }

    // 4) Get passenger details for email
    let passenger = { FirstName: 'Passenger', LastName: '', Email: '' };
    try {
      const passengerResponse = await axios.get(
        `${PASSENGER_SERVICE_URL}/getpassenger/${payment.passengerID}/`
      );
      passenger = passengerResponse.data;
    } catch (err) {
      console.warn('Could not fetch passenger for notification:', err.message);
    }

    const outboundDetails = await getFlightEmailDetails(flightID);
    const outboundFlight = {
      leg: 'outbound',
      flight_id: flightID,
      booking_id: bookingID,
      flight_number: firstNonEmpty(req.body.flightNumber, outboundDetails.flightNumber, `SQ${flightID}`),
      origin: firstNonEmpty(req.body.origin, outboundDetails.origin, 'Origin'),
      destination: firstNonEmpty(req.body.destination, outboundDetails.destination, 'Destination'),
      departure_date: firstNonEmpty(req.body.departureDate, outboundDetails.departureDate, 'N/A'),
      seat_number: seatNumber,
    };

    const flights = [outboundFlight];

    if (returnFlightID && returnSeatNumber) {
      const returnDetails = await getFlightEmailDetails(returnFlightID);
      flights.push({
        leg: 'return',
        flight_id: returnFlightID,
        booking_id: returnBookingID || null,
        flight_number: firstNonEmpty(returnDetails.flightNumber, `SQ${returnFlightID}`),
        origin: firstNonEmpty(returnDetails.origin, outboundFlight.destination, 'Origin'),
        destination: firstNonEmpty(returnDetails.destination, outboundFlight.origin, 'Destination'),
        departure_date: firstNonEmpty(returnDetails.departureDate, 'N/A'),
        seat_number: returnSeatNumber,
      });
    }

    const passengerSummaries = [];
    for (const id of outboundBookingIDs) {
      try {
        const bookingResponse = await axios.get(`${RECORD_SERVICE_URL}/records/${id}`);
        const record = bookingResponse.data;
        const name = record.isGuest
          ? `${record.guestFirstName || ''} ${record.guestLastName || ''}`.trim()
          : `${passenger.FirstName} ${passenger.LastName}`.trim();

        passengerSummaries.push({
          bookingID: id,
          name,
          seatNumber: record.seatNumber,
        });
      } catch (err) {
        console.warn(`Could not fetch outbound group booking ${id} for notification:`, err.message);
      }
    }

    let perksAttachment = null;
    if (selectedPerksVoucherID && selectedPerksVoucherCode && selectedPerksVoucherType === 'IN_FLIGHT_PERKS') {
      try {
        const bookingServiceUrl = process.env.BOOKING_SERVICE_INTERNAL_URL || `http://localhost:${process.env.PORT || 3001}`;
        const perksResponse = await axios.post(`${bookingServiceUrl}/api/bookings/${bookingID}/in-flight-perks`, {
          passengerID: payment.passengerID,
          voucherID: Number(selectedPerksVoucherID),
          voucherCode: String(selectedPerksVoucherCode),
        });
        perksAttachment = {
          success: true,
          message: perksResponse.data?.message || 'In-flight perks attached successfully',
        };
      } catch (perksError) {
        perksAttachment = {
          success: false,
          message: perksError.response?.data?.message || perksError.response?.data?.error || perksError.message,
        };
      }
    }

    // 6) Publish booking.confirmed to RabbitMQ → Notification Service sends email
    await publishBookingConfirmed({
      booking_id:      bookingID,
      passenger_name:  `${passenger.FirstName} ${passenger.LastName}`,
      passenger_email: passenger.Email,
      flight_number:   outboundFlight.flight_number,
      origin:          outboundFlight.origin,
      destination:     outboundFlight.destination,
      departure_date:  outboundFlight.departure_date,
      seat_number:     outboundFlight.seat_number,
      amount_paid:     payment.amount,
      trip_type:       flights.length > 1 ? 'round_trip' : 'one_way',
      flights,
      passengers: passengerSummaries,
      group_size: passengerSummaries.length || 1,
      return_booking_id: returnBookingID || null,
    });

    return res.status(200).json({
      success: true,
      status: 'Confirmed',
      bookingID,
      returnBookingID: returnBookingID || null,
      bookingIDs: allBookingIDs,
      payment,
      perksAttachment,
    });

  } catch (error) {
    const status = error.response?.status || 500;
    const message = error.response?.data?.message || error.message;
    return res.status(status).json({
      success: false,
      error: 'Failed to finalise booking',
      message,
    });
  }
});

// ==========================================
// POST /api/bookings/:bookingID/award-miles
// Award miles only when flight has completed.
// For demo: pass { force: true } to award immediately.
// ==========================================
app.post('/api/bookings/:bookingID/award-miles', async (req, res) => {
  const { bookingID } = req.params;
  const { force = false } = req.body || {};

  if (!Number.isFinite(Number(bookingID)) || Number(bookingID) <= 0) {
    return res.status(400).json({ error: 'bookingID must be a positive number' });
  }

  try {
    const result = await awardMilesForBookingIfCompleted({
      bookingID: Number(bookingID),
      force: Boolean(force),
    });

    if (result.awarded) {
      return res.status(200).json({ success: true, ...result });
    }

    if (result.reason === 'already_awarded') {
      return res.status(200).json({ success: true, ...result });
    }

    if (result.reason === 'flight_not_landed' || result.reason === 'booking_not_confirmed') {
      return res.status(409).json({ success: false, ...result });
    }

    return res.status(400).json({ success: false, ...result });
  } catch (error) {
    return res.status(error.response?.status || 500).json({
      success: false,
      error: 'Failed to award miles',
      message: error.response?.data || error.message,
    });
  }
});

// ==========================================
// POST /api/flights/:flightID/award-miles
// Award miles for all confirmed bookings on a landed flight.
// ==========================================
app.post('/api/flights/:flightID/award-miles', async (req, res) => {
  const { flightID } = req.params;
  const { force = false } = req.body || {};

  if (!Number.isFinite(Number(flightID)) || Number(flightID) <= 0) {
    return res.status(400).json({ error: 'flightID must be a positive number' });
  }

  try {
    const summary = await awardMilesForFlight(Number(flightID), Boolean(force));
    return res.status(200).json({ success: true, ...summary });
  } catch (error) {
    return res.status(error.response?.status || 500).json({
      success: false,
      error: 'Failed to award flight miles',
      message: error.response?.data || error.message,
    });
  }
});

// GET booking by ID
app.get('/api/bookings/:bookingID', async (req, res) => {
  const { bookingID } = req.params;
  try {
    const response = await axios.get(`${RECORD_SERVICE_URL}/records/${bookingID}`);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch booking', message: error.message });
  }
});

// GET passenger bookings
app.get('/api/bookings/passenger/:passengerID', async (req, res) => {
  const { passengerID } = req.params;
  try {
    const response = await axios.get(`${RECORD_SERVICE_URL}/records/passenger/${passengerID}`);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch bookings', message: error.message });
  }
});

app.post('/api/bookings/:bookingID/in-flight-perks', async (req, res) => {
  const { bookingID } = req.params;
  const { passengerID, voucherID, voucherCode } = req.body;

  if (!passengerID || !voucherID || !voucherCode) {
    return res.status(400).json({
      error: 'passengerID, voucherID, and voucherCode are required',
    });
  }

  try {
    const bookingResponse = await axios.get(`${RECORD_SERVICE_URL}/records/${bookingID}`);
    const booking = bookingResponse.data || {};
    const ownerID = Number(booking.bookedByPassengerID || booking.BookedByPassengerID || booking.passengerID || booking.PassengerID);

    if (ownerID !== Number(passengerID)) {
      return res.status(403).json({
        error: 'This booking does not belong to the signed-in passenger',
      });
    }

    if (String(booking.status || booking.bookingstatus || '').trim() !== 'Confirmed') {
      return res.status(409).json({
        error: 'In-flight perks can only be attached to confirmed bookings',
      });
    }

    if (booking.inFlightPerksVoucherID || booking.InFlightPerksVoucherID) {
      return res.status(409).json({
        error: 'In-flight perks are already attached to this booking',
      });
    }

    const voucherResponse = await axios.get(`${VOUCHER_SERVICE_URL}/vouchers/code/${encodeURIComponent(voucherCode)}`);
    const voucher = voucherResponse.data || {};

    if (Number(voucher.passengerID) !== Number(passengerID)) {
      return res.status(403).json({
        error: 'This voucher does not belong to the signed-in passenger',
      });
    }

    if (voucher.voucherType !== 'IN_FLIGHT_PERKS') {
      return res.status(400).json({
        error: 'Only in-flight perks vouchers can be attached to bookings',
      });
    }

    if (voucher.status !== 'ACTIVE') {
      return res.status(409).json({
        error: 'This voucher is no longer active',
      });
    }

    await axios.put(`${RECORD_SERVICE_URL}/records/${bookingID}/perks`, {
      passengerID,
      voucherID,
      voucherCode,
    });

    try {
      await axios.put(`${VOUCHER_SERVICE_URL}/vouchers/${voucherID}/redeem`, {
        bookingID: Number(bookingID),
      });
    } catch (redeemError) {
      await axios.delete(`${RECORD_SERVICE_URL}/records/${bookingID}/perks`).catch(() => {});
      throw redeemError;
    }

    const updatedBookingResponse = await axios.get(`${RECORD_SERVICE_URL}/records/${bookingID}`);

    return res.status(200).json({
      success: true,
      message: 'In-flight perks attached successfully',
      booking: updatedBookingResponse.data,
      voucher: {
        voucherID,
        voucherCode,
      },
    });
  } catch (error) {
    const message = error.response?.data?.error || error.response?.data?.message || error.message;
    return res.status(error.response?.status || 500).json({
      success: false,
      error: 'Failed to attach in-flight perks',
      message,
    });
  }
});

app.post('/api/bookings/:bookingID/travel-credit/release', async (req, res) => {
  const { bookingID } = req.params;
  const { passengerID, voucherID, voucherCode } = req.body;

  try {
    const bookingResponse = await axios.get(`${RECORD_SERVICE_URL}/records/${bookingID}`);
    const booking = bookingResponse.data || {};
    const ownerID = Number(firstNonEmpty(
      booking.bookedByPassengerID,
      booking.BookedByPassengerID,
      booking.passengerID,
      booking.PassengerID
    ));

    if (passengerID && ownerID !== Number(passengerID)) {
      return res.status(403).json({
        error: 'This booking does not belong to the signed-in passenger',
      });
    }

    const storedVoucherID = Number(firstNonEmpty(booking.travelCreditVoucherID, booking.TravelCreditVoucherID, voucherID));
    const storedVoucherCode = firstNonEmpty(booking.travelCreditVoucherCode, booking.TravelCreditVoucherCode, voucherCode);

    if (!storedVoucherID || !storedVoucherCode) {
      return res.status(404).json({
        error: 'No Travel Credit voucher is attached to this booking',
      });
    }

    await axios.put(`${VOUCHER_SERVICE_URL}/vouchers/${storedVoucherID}/status`, { status: 'ACTIVE' });

    return res.status(200).json({
      success: true,
      message: 'Travel Credit voucher released successfully',
    });
  } catch (error) {
    return res.status(error.response?.status || 500).json({
      success: false,
      error: 'Failed to release Travel Credit voucher',
      message: error.response?.data?.message || error.response?.data?.error || error.message,
    });
  }
});

app.post('/api/rebooking/accept', async (req, res) => {
  const { offerID, bookingIDs, seatAssignments, frontendBaseUrl } = req.body;

  if (!offerID || !Array.isArray(bookingIDs) || !bookingIDs.length || !Array.isArray(seatAssignments) || !seatAssignments.length) {
    return res.status(400).json({
      error: 'offerID, bookingIDs, and seatAssignments are required',
    });
  }

  if (bookingIDs.length !== seatAssignments.length) {
    return res.status(400).json({
      error: 'bookingIDs and seatAssignments must have the same length',
    });
  }

  const normalizedBookingIDs = bookingIDs.map(Number).filter((id) => Number.isFinite(id) && id > 0);
  const normalizedSeatAssignments = seatAssignments
    .map((seat) => String(seat || '').trim())
    .filter(Boolean);

  if (normalizedBookingIDs.length !== normalizedSeatAssignments.length) {
    return res.status(400).json({
      error: 'Invalid bookingIDs or seatAssignments payload',
    });
  }

  try {
    const offerResponse = await axios.get(`${OFFER_SERVICE_URL}/offer/${offerID}`);
    const offer = offerResponse.data;

    if (String(offer.status) !== 'Pending Response') {
      return res.status(409).json({
        error: 'Offer can no longer be accepted',
        status: offer.status,
      });
    }

    const recordResponses = await Promise.all(
      normalizedBookingIDs.map((bookingID) => axios.get(`${RECORD_SERVICE_URL}/records/${bookingID}`))
    );
    const records = recordResponses.map((response) => response.data);

    const newFlightID = Number(offer.newFlightID);
    const origFlightID = Number(offer.origFlightID);
    const seatNumberCsv = normalizedSeatAssignments.join(',');

    await axios.post(`${SEATS_SERVICE_URL}/seats/hold`, {
      flightID: newFlightID,
      seatNumber: seatNumberCsv,
      passengerID: Number(offer.passengerID),
    });

    try {
      await axios.post(`${SEATS_SERVICE_URL}/seats/confirm`, {
        flightID: newFlightID,
        seatNumber: seatNumberCsv,
      });
    } catch (confirmError) {
      await axios.post(`${SEATS_SERVICE_URL}/seats/release`, {
        flightID: newFlightID,
        seatNumber: seatNumberCsv,
      }).catch(() => {});
      throw confirmError;
    }

    for (let index = 0; index < normalizedBookingIDs.length; index += 1) {
      await axios.put(`${RECORD_SERVICE_URL}/records/${normalizedBookingIDs[index]}/rebook`, {
        FlightID: newFlightID,
        seatNumber: normalizedSeatAssignments[index],
        BookingStatus: 'Confirmed',
      });
    }

    await axios.put(`${OFFER_SERVICE_URL}/offer/${offerID}`, {
      status: 'Accepted',
    });

    let passenger = { FirstName: 'Passenger', LastName: '', Email: '' };
    try {
      const passengerResponse = await axios.get(
        `${PASSENGER_SERVICE_URL}/getpassenger/${offer.passengerID}/`
      );
      passenger = passengerResponse.data;
    } catch (err) {
      console.warn('Could not fetch passenger for rebooking notification:', err.message);
    }

    const newFlightDetails = await getFlightEmailDetails(newFlightID);
    const passengerSummaries = records.map((record, index) => ({
      bookingID: normalizedBookingIDs[index],
      name: record.isGuest
        ? `${record.guestFirstName || ''} ${record.guestLastName || ''}`.trim()
        : `${passenger.FirstName} ${passenger.LastName}`.trim(),
      seatNumber: normalizedSeatAssignments[index],
    }));

    await publishBookingConfirmed({
      booking_id: normalizedBookingIDs[0],
      passenger_name: `${passenger.FirstName} ${passenger.LastName}`.trim() || 'Passenger',
      passenger_email: passenger.Email,
      flight_number: firstNonEmpty(newFlightDetails.flightNumber, `SQ${newFlightID}`),
      origin: firstNonEmpty(newFlightDetails.origin, 'Origin'),
      destination: firstNonEmpty(newFlightDetails.destination, 'Destination'),
      departure_date: firstNonEmpty(newFlightDetails.departureDate, 'N/A'),
      seat_number: seatNumberCsv,
      amount_paid: records.reduce((sum, record) => sum + Number(firstNonEmpty(record.amount, record.amountPaid, record.AmountPaid) || 0), 0),
      trip_type: 'one_way',
      flights: [{
        leg: 'rebooked',
        flight_id: newFlightID,
        booking_id: normalizedBookingIDs[0],
        flight_number: firstNonEmpty(newFlightDetails.flightNumber, `SQ${newFlightID}`),
        origin: firstNonEmpty(newFlightDetails.origin, 'Origin'),
        destination: firstNonEmpty(newFlightDetails.destination, 'Destination'),
        departure_date: firstNonEmpty(newFlightDetails.departureDate, 'N/A'),
        seat_number: seatNumberCsv,
      }],
      passengers: passengerSummaries,
      group_size: passengerSummaries.length,
      original_flight_id: origFlightID,
      frontend_base_url: frontendBaseUrl || null,
    });

    return res.status(200).json({
      success: true,
      offerID: Number(offerID),
      bookingIDs: normalizedBookingIDs,
      flightID: newFlightID,
      seatAssignments: normalizedSeatAssignments,
    });
  } catch (error) {
    return res.status(error.response?.status || 500).json({
      error: 'Failed to accept rebooking with seats',
      message: error.response?.data?.message || error.message,
    });
  }
});

app.post('/api/rebooking/reject', async (req, res) => {
  const { offerID } = req.body;

  if (!offerID) {
    return res.status(400).json({
      error: 'offerID is required',
    });
  }

  try {
    const offerResponse = await axios.get(`${OFFER_SERVICE_URL}/offer/${offerID}`);
    const offer = offerResponse.data;

    if (String(offer.status) !== 'Pending Response') {
      return res.status(409).json({
        error: 'Offer can no longer be rejected',
        status: offer.status,
      });
    }

    const groupBookings = await getGroupBookingsForOffer(offer);
    if (!groupBookings.length) {
      return res.status(404).json({
        error: 'Affected booking group not found',
      });
    }

    const normalizedStatuses = groupBookings.map((record) => normalizedStatus(firstNonEmpty(
      record.status,
      record.bookingstatus,
      record.BookingStatus
    )));
    const allPending = normalizedStatuses.every((status) => status === 'Pending');

    if (allPending) {
      for (const record of groupBookings) {
        const bookingID = Number(firstNonEmpty(record.bookingID, record.BookingID));
        const heldFlightID = Number(firstNonEmpty(record.flightID, record.FlightID));
        const heldSeatNumber = firstNonEmpty(record.seatNumber, record.SeatNumber);

        if (heldFlightID && heldSeatNumber) {
          try {
            await axios.post(`${SEATS_SERVICE_URL}/seats/release`, {
              flightID: heldFlightID,
              seatNumber: heldSeatNumber,
            });
          } catch (seatError) {
            console.warn(`Could not release held seat ${heldSeatNumber} for booking ${bookingID}:`, seatError.response?.data?.message || seatError.message);
          }
        }

        await axios.put(`${RECORD_SERVICE_URL}/records/${bookingID}`, {
          BookingStatus: 'Cancelled',
        });
      }

      await axios.put(`${OFFER_SERVICE_URL}/offer/${offerID}`, {
        status: 'Rejected',
      });

      return res.status(200).json({
        success: true,
        offerID: Number(offerID),
        bookingIDs: groupBookings.map((record) => Number(firstNonEmpty(record.bookingID, record.BookingID))),
        refundAmount: 0,
        refundRequired: false,
        message: 'Pending disrupted booking was cancelled with no refund required.',
      });
    }

    const refundAmount = groupBookings.reduce(
      (sum, record) => sum + Number(firstNonEmpty(record.amount, record.amountPaid, record.AmountPaid) || 0),
      0
    );

    const refundResponse = await axios.post(`${PAYMENT_SERVICE_URL}/payment/refund`, {
      BookingID: Number(offer.bookingID),
      PassengerID: Number(offer.passengerID),
      Amount: refundAmount,
      refundType: 'partial',
      refundAmount,
    });

    const refundPayload = refundResponse.data || {};
    const refundStatus = refundPayload.Status || refundPayload.status;

    if (refundResponse.status >= 400 || refundStatus !== 'Refunded') {
      for (const record of groupBookings) {
        await axios.put(`${RECORD_SERVICE_URL}/records/${firstNonEmpty(record.bookingID, record.BookingID)}`, {
          BookingStatus: 'Refund Failed',
        });
      }

      return res.status(502).json({
        error: 'Refund failed',
        message: refundPayload.message || 'The refund could not be completed.',
      });
    }

    for (const record of groupBookings) {
      await axios.put(`${RECORD_SERVICE_URL}/records/${firstNonEmpty(record.bookingID, record.BookingID)}`, {
        BookingStatus: 'Cancelled',
      });
    }

    await axios.put(`${OFFER_SERVICE_URL}/offer/${offerID}`, {
      status: 'Rejected',
    });

    return res.status(200).json({
      success: true,
      offerID: Number(offerID),
      bookingIDs: groupBookings.map((record) => Number(firstNonEmpty(record.bookingID, record.BookingID))),
      refundAmount,
      refundID: refundPayload.RefundID || refundPayload.refundID || null,
    });
  } catch (error) {
    return res.status(error.response?.status || 500).json({
      error: 'Failed to reject rebooking offer',
      message: error.response?.data?.message || error.message,
    });
  }
});

app.post('/api/bookings/resume-payment', async (req, res) => {
  const { bookingID, frontendBaseUrl } = req.body;

  if (!bookingID) {
    return res.status(400).json({ error: 'bookingID is required' });
  }

  try {
    const bookingResponse = await axios.get(`${RECORD_SERVICE_URL}/records/${bookingID}`);
    const seedBooking = bookingResponse.data;

    if (seedBooking.status !== 'Pending') {
      return res.status(409).json({
        error: 'Booking is no longer awaiting payment',
        status: seedBooking.status,
      });
    }

    const bookerID = Number(firstNonEmpty(seedBooking.bookedByPassengerID, seedBooking.BookedByPassengerID, seedBooking.passengerID, seedBooking.PassengerID));
    if (!bookerID) {
      return res.status(400).json({ error: 'Pending booking is missing a bookedByPassengerID' });
    }

    const allBookingsResponse = await axios.get(`${RECORD_SERVICE_URL}/records/passenger/${bookerID}`);
    const allBookings = Array.isArray(allBookingsResponse.data) ? allBookingsResponse.data : [];
    const groupFlightID = Number(firstNonEmpty(seedBooking.flightID, seedBooking.FlightID));

    const pendingGroup = allBookings
      .filter((record) => {
        return Number(firstNonEmpty(record.bookedByPassengerID, record.BookedByPassengerID, record.passengerID, record.PassengerID)) === bookerID
          && String(record.status) === 'Pending'
          && Number(firstNonEmpty(record.flightID, record.FlightID)) === groupFlightID;
      })
      .sort((a, b) => Number(firstNonEmpty(a.bookingID, a.BookingID)) - Number(firstNonEmpty(b.bookingID, b.BookingID)));

    if (!pendingGroup.length) {
      return res.status(404).json({ error: 'No pending booking group found' });
    }

    const groupCreatedAt = pendingGroup.reduce((oldest, record) => {
      const createdAt = firstNonEmpty(record.createdAt, record.createdTime, record.CreatedTime);
      if (!oldest) return createdAt;
      if (!createdAt) return oldest;
      return String(createdAt) < String(oldest) ? createdAt : oldest;
    }, firstNonEmpty(seedBooking.createdAt, seedBooking.createdTime, seedBooking.CreatedTime));

    if (isPendingRecordExpired(groupCreatedAt)) {
      await cleanupPendingRecords(pendingGroup);
      return res.status(410).json({
        error: 'Payment hold expired',
        message: 'The 5-minute payment hold expired and the seats have been released.',
      });
    }

    const distinctFlightIDs = [...new Set(pendingGroup.map(getNormalizedFlightID).filter((id) => Number.isFinite(id) && id > 0))];
    for (const flightID of distinctFlightIDs) {
      const seatNumbers = pendingGroup
        .filter((record) => getNormalizedFlightID(record) === flightID)
        .map(getNormalizedSeatNumber)
        .filter(Boolean)
        .join(',');

      if (!seatNumbers) continue;

      await axios.post(`${SEATS_SERVICE_URL}/seats/refresh-hold`, {
        flightID,
        seatNumber: seatNumbers,
      });
    }

    const groupedByFlight = distinctFlightIDs.map((flightID) => ({
      flightID,
      records: pendingGroup.filter((record) => getNormalizedFlightID(record) === flightID),
    })).sort((a, b) => {
      const firstA = Number(firstNonEmpty(a.records[0]?.bookingID, a.records[0]?.BookingID));
      const firstB = Number(firstNonEmpty(b.records[0]?.bookingID, b.records[0]?.BookingID));
      return firstA - firstB;
    });

    const outboundGroup = groupedByFlight[0];
    const returnGroup = groupedByFlight[1] || null;

    const frontendOrigin = (frontendBaseUrl || 'http://localhost:5173').replace(/\/$/, '');
    const outboundBookingID = Number(firstNonEmpty(outboundGroup.records[0]?.bookingID, outboundGroup.records[0]?.BookingID));
    const returnBookingID = returnGroup
      ? Number(firstNonEmpty(returnGroup.records[0]?.bookingID, returnGroup.records[0]?.BookingID))
      : null;

    let combinedFlightNumber = `Booking ${outboundBookingID}`;
    try {
      const outboundFlightResponse = await axios.get(`${FLIGHT_SERVICE_URL}/flight/${outboundGroup.flightID}`);
      const outboundFlightNumber = firstNonEmpty(
        outboundFlightResponse.data?.FlightNumber,
        outboundFlightResponse.data?.flightNumber,
        `SQ${outboundGroup.flightID}`
      );

      if (returnGroup) {
        const returnFlightResponse = await axios.get(`${FLIGHT_SERVICE_URL}/flight/${returnGroup.flightID}`);
        const returnFlightNumber = firstNonEmpty(
          returnFlightResponse.data?.FlightNumber,
          returnFlightResponse.data?.flightNumber,
          `SQ${returnGroup.flightID}`
        );
        combinedFlightNumber = `${outboundFlightNumber} & ${returnFlightNumber}`;
      } else {
        combinedFlightNumber = outboundFlightNumber;
      }
    } catch (err) {
      console.warn('Could not fetch flight numbers for resumed payment:', err.message);
    }

    let successUrl = `${frontendOrigin}/booking-success/${outboundBookingID}`
      + `?session_id={CHECKOUT_SESSION_ID}`
      + `&flightID=${encodeURIComponent(String(outboundGroup.flightID))}`
      + `&seatNumber=${encodeURIComponent(outboundGroup.records.map(getNormalizedSeatNumber).join(','))}`
      + `&groupBookingIDs=${encodeURIComponent(outboundGroup.records.map((record) => firstNonEmpty(record.bookingID, record.BookingID)).join(','))}`;

    if (returnGroup) {
      successUrl += `&returnBookingID=${encodeURIComponent(String(returnBookingID))}`;
      successUrl += `&returnFlightID=${encodeURIComponent(String(returnGroup.flightID))}`;
      successUrl += `&returnSeatNumber=${encodeURIComponent(returnGroup.records.map(getNormalizedSeatNumber).join(','))}`;
      successUrl += `&returnGroupBookingIDs=${encodeURIComponent(returnGroup.records.map((record) => firstNonEmpty(record.bookingID, record.BookingID)).join(','))}`;
    }

    const cancelUrlObject = new URL(buildCancelUrl(
      null,
      frontendOrigin,
      outboundBookingID,
      returnBookingID
    ));
    cancelUrlObject.searchParams.set('groupBookingIDs', outboundGroup.records.map((record) => firstNonEmpty(record.bookingID, record.BookingID)).join(','));
    if (returnGroup) {
      cancelUrlObject.searchParams.set('returnGroupBookingIDs', returnGroup.records.map((record) => firstNonEmpty(record.bookingID, record.BookingID)).join(','));
    }

    const paymentResponse = await axios.post(`${PAYMENT_SERVICE_URL}/payment/checkout`, {
      bookingID: outboundBookingID,
      passengerID: bookerID,
      amount: pendingGroup.reduce((sum, record) => sum + Number(firstNonEmpty(record.amount, record.amountPaid, record.AmountPaid) || 0), 0),
      flightNumber: combinedFlightNumber,
      successUrl,
      cancelUrl: cancelUrlObject.toString(),
    });

    return res.status(200).json({
      success: true,
      bookingID: outboundBookingID,
      bookingIDs: pendingGroup.map((record) => Number(firstNonEmpty(record.bookingID, record.BookingID))),
      sessionUrl: paymentResponse.data.sessionUrl,
      stripeSessionID: paymentResponse.data.stripeSessionID,
    });
  } catch (error) {
    return res.status(error.response?.status || 500).json({
      error: 'Failed to resume pending payment',
      message: error.response?.data?.message || error.message,
    });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Booking Composite Service running on port ${PORT}`);
});

// ==========================================
// CANCEL PENDING BOOKING(S) AFTER STRIPE CANCEL
// ==========================================
app.post('/api/bookings/cancel-pending', async (req, res) => {
  const { bookingID, returnBookingID, groupBookingIDs, returnGroupBookingIDs } = req.body;

  if (!bookingID) {
    return res.status(400).json({ error: 'Missing required field: bookingID' });
  }

  const bookingIDs = [
    ...parseIdList(groupBookingIDs),
    ...parseIdList(returnGroupBookingIDs),
    ...[bookingID, returnBookingID].filter(Boolean).map(Number),
  ];
  const uniqueBookingIDs = [...new Set(bookingIDs)];
  const cancelled = [];
  const skipped = [];

  for (const id of uniqueBookingIDs) {
    try {
      const recordResponse = await axios.get(`${RECORD_SERVICE_URL}/records/${id}`);
      const record = recordResponse.data;

      if (record.status !== 'Pending') {
        skipped.push({ bookingID: id, reason: `status=${record.status}` });
        continue;
      }

      await axios.post(`${SEATS_SERVICE_URL}/seats/release`, {
        flightID: record.flightID,
        seatNumber: record.seatNumber,
      });

      await axios.delete(`${RECORD_SERVICE_URL}/record/${id}`);
      cancelled.push(id);
    } catch (err) {
      if (err.response?.status === 404) {
        skipped.push({ bookingID: id, reason: 'already-deleted' });
      } else {
        return res.status(err.response?.status || 500).json({
          error: 'Failed to cancel pending booking(s)',
          message: err.response?.data?.message || err.message,
          cancelled,
          skipped,
        });
      }
    }
  }

  return res.status(200).json({
    success: true,
    message: 'Pending booking cleanup completed',
    cancelled,
    skipped,
  });
});
