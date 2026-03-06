const express = require('express');
const axios = require('axios');
const app = express();

app.use(express.json());

// Configuration - service URLs from environment variables
const BOOKING_SERVICE_URL = process.env.BOOKING_SERVICE_URL || 'http://booking-service:3000';
const PASSENGER_SERVICE_URL = process.env.PASSENGER_SERVICE_URL || 'http://passenger-service:3000';
const FLIGHT_SERVICE_URL = process.env.FLIGHT_SERVICE_URL || 'http://flight-service:3000';
const PAYMENT_SERVICE_URL = process.env.PAYMENT_SERVICE_URL || 'http://payment-service:3000';
const NOTIFICATION_SERVICE_URL = process.env.NOTIFICATION_SERVICE_URL || 'http://notification-service:3000';

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
    const passengerValid = true; // Mock response
    if (!passengerValid) {
      throw new Error('Passenger not found');
    }
    console.log('✓ Passenger validated');

    // Step 2: Check seat availability (mock for now)
    console.log('Step 2: Checking seat availability...');
    // TODO: Call Flight Service once coded
    const seatAvailable = true; // Mock response
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
    const paymentSuccess = true; // Mock - change to false to test failure path
    
    if (paymentSuccess) {
      // SUCCESS PATH
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

      // Step 8: Send confirmation email (mock)
      console.log('Step 8: Sending confirmation email...');
      // TODO: Call Notification Service when ready
      console.log('✓ Confirmation email sent');

      // Return success response
      res.status(201).json({
        success: true,
        message: 'Booking confirmed successfully',
        bookingID: booking.bookingID,
        status: 'Confirmed',
        passengerID,
        flightID,
        seatNumber
      });

    } else {
      // FAILURE PATH
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

      // Step 8: Send failure notification (mock)
      console.log('Step 8: Sending failure notification...');
      // TODO: Call Notification Service when ready
      console.log('✓ Failure notification sent');

      // Return failure response
      res.status(400).json({
        success: false,
        message: 'Payment failed. Booking cancelled.',
        bookingID: booking.bookingID,
        status: 'Failed'
      });
    }

  } catch (error) {
    console.error('Error in booking flow:', error.message);
    
    // Attempt to clean up if we have a booking ID
    if (error.bookingID) {
      try {
        await axios.delete(`${BOOKING_SERVICE_URL}/booking/${error.bookingID}`);
        console.log('✓ Cleaned up pending booking');
      } catch (cleanupError) {
        console.error('Cleanup failed:', cleanupError.message);
      }
    }
    
    res.status(500).json({
      success: false,
      error: 'Booking failed',
      message: error.message
    });
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