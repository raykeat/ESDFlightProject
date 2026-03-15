const express = require('express');
const axios = require('axios');
const cors = require('cors');
const app = express();
const amqp = require('amqplib');



app.use(cors({
  origin: 'http://localhost:5173',
  credentials: true
}));

app.use(express.json());

// Configuration - service URLs from environment variables
const BOOKING_SERVICE_URL = process.env.BOOKING_SERVICE_URL || 'http://booking-service:3000';
const PASSENGER_SERVICE_URL = process.env.PASSENGER_SERVICE_URL || 'http://passenger-service:3000';
const FLIGHT_SERVICE_URL = process.env.FLIGHT_SERVICE_URL || 'http://flight-service:3000';
const PAYMENT_SERVICE_URL = process.env.PAYMENT_SERVICE_URL || 'http://payment-service:5000';
const NOTIFICATION_SERVICE_URL = process.env.NOTIFICATION_SERVICE_URL || 'http://notification-service:3000';
const RABBITMQ_URL             = process.env.RABBITMQ_URL            || 'amqp://guest:guest@rabbitmq:5672';  // ← add this



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
      'booking.confirmed',                          // routing key — consumed by notification-service
      Buffer.from(JSON.stringify(bookingData)),
      { persistent: true }                          // message survives RabbitMQ restart
    );
 
    console.log('✓ Published booking.confirmed to RabbitMQ');
    console.log('  Payload:', JSON.stringify(bookingData, null, 2));
 
    await channel.close();
  } catch (err) {
    // Log the error but don't fail the booking — email is non-critical
    console.error('✗ Failed to publish to RabbitMQ:', err.message);
  } finally {
    if (connection) await connection.close();
  }
}
 
// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'OK', 
    service: 'booking-composite-service',
    dependencies: {
      bookingService: 'pending',
      passengerService: 'pending',
      flightService: 'pending',
      paymentService: 'pending',
      notificationService: 'pending'
    }
  });
});




// ==========================================
// BOOKING FLOW - Scenario 1
// ==========================================
// POST /api/bookings - Complete booking flow
app.post('/api/bookings', async (req, res) => {
  const { passengerID, flightID, seatNumber } = req.body;
  
  if (!passengerID || !flightID || !seatNumber) {
    return res.status(400).json({ 
      error: 'Missing required fields: passengerID, flightID, seatNumber' 
    });
  }
 
  console.log(`Starting booking flow for passenger ${passengerID}, flight ${flightID}, seat ${seatNumber}`);
 
  try {
    // Step 1: Validate passenger exists (mock for now)
    console.log('Step 1: Validating passenger...');
    // TODO: Call Passenger Service once coded
    const passengerValid = true;
    if (!passengerValid) {
      throw new Error('Passenger not found');
    }
    console.log('✓ Passenger validated');
 
    // Step 2: Check seat availability (mock for now)
    console.log('Step 2: Checking seat availability...');
    // TODO: Call Flight Service once coded
    const seatAvailable = true;
    if (!seatAvailable) {
      throw new Error('Seat not available');
    }
    console.log('✓ Seat available');
 
    // Step 3: Create pending booking in Booking Service
    console.log('Step 3: Creating pending booking...');
    const bookingResponse = await axios.post(`${BOOKING_SERVICE_URL}/bookings`, {
      passengerID,
      flightID,
      amount: 299.99, // TODO: Get actual price from Flight Service once coded
      seatNumber
    });
    const booking = bookingResponse.data;
    console.log(`✓ Pending booking created with ID: ${booking.bookingID}`);
 
    // Step 4: Hold seat in Flight Service (mock for now)
    console.log('Step 4: Holding seat...');
    // TODO: Call Flight Service to hold seat once coded
    console.log('✓ Seat held');
 
    // Step 5: Process payment (mock for now)
    console.log('Step 5: Processing payment...');
    // TODO: Call Payment Service once coded
    const paymentSuccess = true; // Change to false to test failure path
 
    if (paymentSuccess) {
      // ── SUCCESS PATH ──────────────────────────────────────
      console.log('✓ Payment successful');
 
      // Step 6: Update booking to Confirmed
      console.log('Step 6: Updating booking to Confirmed...');
      await axios.put(`${BOOKING_SERVICE_URL}/bookings/${booking.bookingID}/status`, {
        status: 'Confirmed'
      });
      console.log('✓ Booking confirmed');
 
      // Step 7: Mark seat as BOOKED in Flight Service (mock)
      console.log('Step 7: Marking seat as BOOKED...');
      // TODO: Call Flight Service to mark seat as BOOKED
      console.log('✓ Seat marked as BOOKED');
 
      // Step 8: Publish to RabbitMQ → Notification Service → SendGrid email
      console.log('Step 8: Publishing booking confirmation to RabbitMQ...');
      await publishBookingConfirmed({
        booking_id:      booking.bookingID,
        passenger_name:  'Test Passenger',                        // TODO: replace with Passenger Service
        passenger_email: 'ay.choung.2024@computing.smu.edu.sg',  // TODO: replace with Passenger Service
        flight_number:   'SQ123',                                 // TODO: replace with Flight Service
        origin:          'Singapore (SIN)',                       // TODO: replace with Flight Service
        destination:     'Tokyo (NRT)',                           // TODO: replace with Flight Service
        departure_date:  '2025-06-15 10:30',                      // TODO: replace with Flight Service
        seat_number:     seatNumber,
        amount_paid:     299.99                                    // TODO: replace with Payment Service
      });
 
      // Return success response
      return res.status(201).json({
        success: true,
        message: 'Booking confirmed successfully',
        bookingID: booking.bookingID,
        status: 'Confirmed',
        passengerID,
        flightID,
        seatNumber
      });
 
    } else {
      // ── FAILURE PATH ──────────────────────────────────────
      console.log('✗ Payment failed');
 
      // Step 6: Update booking to Failed
      console.log('Step 6: Updating booking to Failed...');
      await axios.put(`${BOOKING_SERVICE_URL}/bookings/${booking.bookingID}/status`, {
        status: 'Failed'
      });
      console.log('✓ Booking marked as Failed');
 
      // Step 7: Release seat hold in Flight Service (mock)
      console.log('Step 7: Releasing seat hold...');
      // TODO: Call Flight Service to release seat hold
      console.log('✓ Seat hold released');
 
      // Step 8: No notification sent on payment failure
      console.log('Step 8: Skipping notification — payment failed');
 
      // Return failure response
      return res.status(400).json({
        success: false,
        message: 'Payment failed. Booking cancelled.',
        bookingID: booking.bookingID,
        status: 'Failed'
      });
    }
 
  } catch (error) {
    console.error('Error in booking flow:', error.message);
 
    if (error.bookingID) {
      try {
        await axios.delete(`${BOOKING_SERVICE_URL}/booking/${error.bookingID}`);
        console.log('✓ Cleaned up pending booking');
      } catch (cleanupError) {
        console.error('Cleanup failed:', cleanupError.message);
      }
    }
 
    return res.status(500).json({
      success: false,
      error: 'Booking failed',
      message: error.message
    });
  }
});
 

// ==========================================
// GET /api/bookings/:bookingID
// Get a single booking by ID
// Called by BookingSuccess.vue after payment
// ==========================================
app.get('/api/bookings/:bookingID', async (req, res) => {
  const { bookingID } = req.params;
  try {
    const response = await axios.get(`${BOOKING_SERVICE_URL}/bookings/${bookingID}`);
    res.json(response.data);
  } catch (error) {
    if (error.response?.status === 404) {
      return res.status(404).json({ error: 'Booking not found' });
    }
    console.error('Error fetching booking:', error.message);
    res.status(500).json({ error: 'Failed to fetch booking', message: error.message });
  }
});

// ==========================================
// GET /api/bookings/passenger/:passengerID
// Get all bookings for a passenger
// Called by MyBookings.vue
// ==========================================
app.get('/api/bookings/passenger/:passengerID', async (req, res) => {
  const { passengerID } = req.params;
  try {
    const response = await axios.get(`${BOOKING_SERVICE_URL}/bookings/passenger/${passengerID}`);
    res.json(response.data);
  } catch (error) {
    console.error('Error fetching bookings for passenger:', error.message);
    res.status(500).json({ error: 'Failed to fetch bookings', message: error.message });
  }
});

// ==========================================
// TODO: Scenario 2
// ==========================================


// ==========================================
// TODO: Scenario 3
// ==========================================


const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Booking Composite Service running on port ${PORT}`);
  console.log(`Using Booking Service at: ${BOOKING_SERVICE_URL}`);
});