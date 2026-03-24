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
const NOTIFICATION_SERVICE_URL = (process.env.NOTIFICATION_SERVICE_URL || 'http://notification-service:3000').replace(/\/$/, '');
const SEATS_SERVICE_URL = (process.env.SEATS_SERVICE_URL || 'http://seats-service:5003').replace(/\/$/, '');
const RECORD_SERVICE_URL = (process.env.RECORD_SERVICE_URL || 'http://record-service:3000').replace(/\/$/, '');
const RABBITMQ_URL             = process.env.RABBITMQ_URL            || 'amqp://guest:guest@rabbitmq:5672';

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
  let outboundSeatHeld = false;
  let returnSeatHeld = false;
  let userBookingCount = 1;
 
  console.log(`Starting booking flow for passenger ${passengerID}, flight ${flightID}, seat ${seatNumber}, returnFlight ${returnFlightID || 'N/A'}, amount ${amount}`);
 
  try {
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

    // Step 3: Create outbound pending booking in Record Service
    console.log('Step 3: Creating outbound pending booking...');
    const outboundBookingResponse = await axios.post(`${RECORD_SERVICE_URL}/records`, {
      passengerID,
      flightID,
      amount: outboundFare,
      seatNumber,
    });
    outboundBooking = outboundBookingResponse.data;
    console.log(`✓ Outbound pending booking created with ID: ${outboundBooking.bookingID}`);

    // Step 4: Optional return pending booking in Record Service
    if (isRoundTrip) {
      console.log('Step 4: Creating return pending booking...');
      const returnBookingResponse = await axios.post(`${RECORD_SERVICE_URL}/records`, {
        passengerID,
        flightID: returnFlightID,
        amount: returnFare,
        seatNumber: returnSeatNumber,
      });
      returnBooking = returnBookingResponse.data;
      console.log(`✓ Return pending booking created with ID: ${returnBooking.bookingID}`);
    }

    // Step 5: Hold outbound seat(s)
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

    // Step 7: Create Stripe checkout session via Payment Service
    console.log('Step 7: Creating checkout session in Payment Service...');
    const frontendOrigin = (frontendBaseUrl || 'http://localhost:5173').replace(/\/$/, '');
    let successUrl = `${frontendOrigin}/booking-success/${outboundBooking.bookingID}`
      + `?session_id={CHECKOUT_SESSION_ID}`
      + `&flightID=${encodeURIComponent(String(flightID))}`
      + `&seatNumber=${encodeURIComponent(String(seatNumber))}`;
    if (returnBooking) {
      successUrl += `&returnBookingID=${encodeURIComponent(String(returnBooking.bookingID))}`;
      successUrl += `&returnFlightID=${encodeURIComponent(String(returnFlightID))}`;
      successUrl += `&returnSeatNumber=${encodeURIComponent(String(returnSeatNumber))}`;
    }

    const totalAmount = outboundFare + returnFare;
    const finalCancelUrl = buildCancelUrl(
      cancelUrl,
      frontendOrigin,
      outboundBooking.bookingID,
      returnBooking?.bookingID || null
    );

    const paymentPayload = {
      bookingID: outboundBooking.bookingID,
      userBookingCount,
      passengerID,
      amount: totalAmount,
      flightNumber: flightNumber || (isRoundTrip ? `SQ${flightID} & SQ${returnFlightID}` : `SQ${flightID}`),
      successUrl,
      cancelUrl: finalCancelUrl,
    };

    const paymentResponse = await axios.post(`${PAYMENT_SERVICE_URL}/payment/checkout`, paymentPayload);

    return res.status(201).json({
      success: true,
      message: 'Pending booking created. Redirect to payment.',
      status: 'PendingPayment',
      bookingID: outboundBooking.bookingID,
      returnBookingID: returnBooking?.bookingID || null,
      bookingIDs: returnBooking
        ? [outboundBooking.bookingID, returnBooking.bookingID]
        : [outboundBooking.bookingID],
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
      if (typeof outboundBooking !== 'undefined' && outboundBooking?.bookingID) {
        await axios.put(`${RECORD_SERVICE_URL}/records/${outboundBooking.bookingID}/status`, { status: 'Failed' });
      }
      if (typeof returnBooking !== 'undefined' && returnBooking?.bookingID) {
        await axios.put(`${RECORD_SERVICE_URL}/records/${returnBooking.bookingID}/status`, { status: 'Failed' });
      }
      if (typeof outboundSeatHeld !== 'undefined' && outboundSeatHeld) {
        await axios.post(`${SEATS_SERVICE_URL}/seats/release`, { flightID, seatNumber });
      }
      if (typeof returnSeatHeld !== 'undefined' && returnSeatHeld) {
        await axios.post(`${SEATS_SERVICE_URL}/seats/release`, { flightID: returnFlightID, seatNumber: returnSeatNumber });
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
    sessionID,
    flightID,
    seatNumber,
    returnFlightID,
    returnSeatNumber,
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

    // 2) Confirm booking records
    await axios.put(`${RECORD_SERVICE_URL}/records/${bookingID}/status`, { status: 'Confirmed' });
    if (returnBookingID) {
      await axios.put(`${RECORD_SERVICE_URL}/records/${returnBookingID}/status`, { status: 'Confirmed' });
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

    // 5) Resolve flight details for notification (prefer request payload, fallback to flight-service)
    const flightDetails = await getFlightEmailDetails(flightID);
    const emailFlightNumber = firstNonEmpty(req.body.flightNumber, flightDetails.flightNumber, `SQ${flightID}`);
    const emailOrigin = firstNonEmpty(req.body.origin, flightDetails.origin, 'Origin');
    const emailDestination = firstNonEmpty(req.body.destination, flightDetails.destination, 'Destination');
    const emailDepartureDate = firstNonEmpty(req.body.departureDate, flightDetails.departureDate, 'N/A');

    // 6) Publish booking.confirmed to RabbitMQ → Notification Service sends email
    await publishBookingConfirmed({
      booking_id:      bookingID,
      passenger_name:  `${passenger.FirstName} ${passenger.LastName}`,
      passenger_email: passenger.Email,
      flight_number:   emailFlightNumber,
      origin:          emailOrigin,
      destination:     emailDestination,
      departure_date:  emailDepartureDate,
      seat_number:     seatNumber,
      amount_paid:     payment.amount
    });

    return res.status(200).json({
      success: true,
      status: 'Confirmed',
      bookingID,
      returnBookingID: returnBookingID || null,
      payment,
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

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Booking Composite Service running on port ${PORT}`);
});

// ==========================================
// CANCEL PENDING BOOKING(S) AFTER STRIPE CANCEL
// ==========================================
app.post('/api/bookings/cancel-pending', async (req, res) => {
  const { bookingID, returnBookingID } = req.body;

  if (!bookingID) {
    return res.status(400).json({ error: 'Missing required field: bookingID' });
  }

  const bookingIDs = [bookingID, returnBookingID].filter(Boolean).map(Number);
  const cancelled = [];
  const skipped = [];

  for (const id of bookingIDs) {
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