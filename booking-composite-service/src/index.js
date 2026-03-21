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

// ==========================================
// BOOKING FLOW - Scenario 1
// ==========================================
app.post('/api/bookings', async (req, res) => {
  const { passengerID, flightID, seatNumber, returnFlightID, returnSeatNumber, amount } = req.body;
  
  if (!passengerID || !flightID || !seatNumber) {
    return res.status(400).json({ 
      error: 'Missing required fields: passengerID, flightID, seatNumber' 
    });
  }
 
  console.log(`Starting booking flow for passenger ${passengerID}, flight ${flightID}, seat ${seatNumber}, returnFlight ${returnFlightID || 'N/A'}, amount ${amount}`);
 
  try {
    let passenger = null;

    // Step 1: Validate passenger exists (OutSystems External API)
    console.log('Step 1: Validating passenger...');
    // Correct endpoint from Swagger: /getpassenger/{passenger_id}/
    const passengerResponse = await axios.get(`${PASSENGER_SERVICE_URL}/getpassenger/${passengerID}/`);
    passenger = passengerResponse.data;
    if (!passenger) {
      throw new Error('Passenger not found');
    }
    console.log('✓ Passenger validated:', passenger.FirstName, passenger.LastName);

    // Step 2: Create pending booking
    console.log('Step 2: Creating pending booking...');

    // Fetch existing bookings for this passenger to calculate relative booking number
    let userBookingCount = 1;
    try {
      // Friend changed endpoint from /bookings to /records
      const existingBookingsResponse = await axios.get(`${RECORD_SERVICE_URL}/records/passenger/${passengerID}`);
      // Only count actual CONFIRMED bookings for the user-specific number
      const confirmedBookings = existingBookingsResponse.data.filter(b => b.status === 'Confirmed');
      userBookingCount = confirmedBookings.length + 1;
      console.log(`✓ Passenger has ${confirmedBookings.length} previous confirmed bookings. This is Booking #${userBookingCount}`);
    } catch (err) {
      console.warn('Could not fetch existing bookings for count, defaulting to 1', err.message);
    }

    // Step 2: Create pending booking in Booking Service
    console.log('Step 2: Creating pending booking...');
    const bookingResponse = await axios.post(`${RECORD_SERVICE_URL}/records`, {
      passengerID,
      flightID,
      amount: amount || 0,
      seatNumber,
      returnFlightID,
      returnSeatNumber
    });
    const booking = bookingResponse.data;
    console.log(`✓ Pending booking created with ID: ${booking.bookingID}`);

    // Step 3: Hold seats in Seats Service
    console.log('Step 3: Holding outbound seat(s)...');
    await axios.post(`${SEATS_SERVICE_URL}/seats/hold`, {
      flightID,
      seatNumber,
      passengerID
    });

    if (returnFlightID && returnSeatNumber) {
      console.log('Step 3b: Holding return seat(s)...');
      await axios.post(`${SEATS_SERVICE_URL}/seats/hold`, {
        flightID: returnFlightID,
        seatNumber: returnSeatNumber,
        passengerID
      });
    }
    console.log('✓ Seat(s) held successfully');

    // Step 4: Process payment (Mocked success)
    console.log('Step 4: Processing payment...');
    const paymentSuccess = true;

    if (paymentSuccess) {
      console.log('✓ Payment successful');

      // Step 5: Update booking to Confirmed
      // Friend also likely updated the status update endpoint to use /records
      await axios.put(`${RECORD_SERVICE_URL}/records/${booking.bookingID}/status`, {
        status: 'Confirmed'
      });

      // Step 6: Mark seats as BOOKED
      await axios.post(`${SEATS_SERVICE_URL}/seats/confirm`, { flightID, seatNumber });
      if (returnFlightID && returnSeatNumber) {
          await axios.post(`${SEATS_SERVICE_URL}/seats/confirm`, { flightID: returnFlightID, seatNumber: returnSeatNumber });
      }

      // Step 7: Notify via RabbitMQ
      await publishBookingConfirmed({
        booking_id:      booking.bookingID,
        passenger_name:  `${passenger.FirstName} ${passenger.LastName}`,
        passenger_email: passenger.Email,
        flight_number:   'SQ' + flightID, 
        origin:          'Origin', 
        destination:     'Destination',
        departure_date:  '2026-05-05',
        seat_number:     seatNumber,
        amount_paid:     amount
      });

      return res.status(201).json({
        success:   true,
        message:   'Booking confirmed successfully',
        bookingID: booking.bookingID,
        userBookingCount: userBookingCount,
        status:    'Confirmed'
      });
    } else {
      // ── FAILURE PATH ──────────────────────────────────────
      console.log('✗ Payment failed');
 
      // Update booking to Failed
      console.log('Step 6: Updating booking to Failed...');
      await axios.put(`${RECORD_SERVICE_URL}/records/${booking.bookingID}/status`, {
        status: 'Failed'
      });
      console.log('✓ Booking marked as Failed');
 
      // Return failure response
      return res.status(400).json({
        success: false,
        message: 'Payment failed. Booking cancelled.',
        bookingID: booking.bookingID,
        status: 'Failed'
      });
    }
  } catch (error) {
    const errorMsg = error.response?.data?.message || error.message;
    console.error('Error in booking flow:', errorMsg);

    // If we have a booking ID, we could attempt cleanup, but usually we just keep it as Failed
    return res.status(500).json({
      success: false,
      error: 'Booking failed',
      message: errorMsg
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