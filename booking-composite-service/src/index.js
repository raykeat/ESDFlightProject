const express = require('express');
const axios = require('axios');
const cors = require('cors');

const app = express();

app.use(cors({
  origin: [
    'http://localhost:5173',
    'http://localhost:5174',
  ],
  credentials: true
}));

app.use(express.json());

const RECORD_SERVICE_URL = process.env.RECORD_SERVICE_URL || 'http://record-service:3000';
const PASSENGER_SERVICE_URL = process.env.PASSENGER_SERVICE_URL || 'http://passenger-service:3000';
const FLIGHT_SERVICE_URL = process.env.FLIGHT_SERVICE_URL || 'http://flight-service:3000';
const SEATS_SERVICE_URL = process.env.SEATS_SERVICE_URL || 'http://seats-service:5003';

function normalizePassenger(raw) {
  if (!raw || typeof raw !== 'object') return null;

  const passengerId = raw.PassengerID ?? raw.passengerID ?? raw.id ?? raw.passenger_id;
  const email = raw.Email ?? raw.email;
  const firstName = raw.FirstName ?? raw.firstName ?? '';
  const lastName = raw.LastName ?? raw.lastName ?? '';

  if (!passengerId) return null;

  return {
    PassengerID: Number(passengerId),
    FirstName: firstName,
    LastName: lastName,
    Email: email || null,
  };
}

function normalizeFlight(raw) {
  if (!raw || typeof raw !== 'object') return null;

  const flightId = raw.FlightID ?? raw.flightID;
  if (!flightId) return null;

  return {
    FlightID: Number(flightId),
    FlightNumber: raw.FlightNumber ?? raw.flightNumber ?? null,
    Price: Number(raw.Price ?? raw.price ?? 0),
    Status: (raw.Status ?? raw.status ?? '').toString().toLowerCase(),
    Origin: raw.Origin ?? raw.origin ?? null,
    Destination: raw.Destination ?? raw.destination ?? null,
    Date: raw.Date ?? raw.date ?? null,
    DepartureTime: raw.DepartureTime ?? raw.departureTime ?? null,
  };
}

async function fetchPassenger(passengerID) {
  const candidates = [
    `${PASSENGER_SERVICE_URL}/passengers/${passengerID}`,
    `${PASSENGER_SERVICE_URL}/getpassenger/${passengerID}/`,
    `${PASSENGER_SERVICE_URL}/getpassenger/${passengerID}`,
  ];

  for (const url of candidates) {
    try {
      const response = await axios.get(url, { timeout: 10000 });
      const normalized = normalizePassenger(response.data);
      if (normalized) return normalized;
    } catch (error) {
      if (error.response?.status === 404) {
        continue;
      }
    }
  }

  return null;
}

async function fetchFlight(flightID) {
  const candidates = [
    `${FLIGHT_SERVICE_URL}/flight/${flightID}`,
    `${FLIGHT_SERVICE_URL}/flights/${flightID}`,
  ];

  for (const url of candidates) {
    try {
      const response = await axios.get(url, { timeout: 10000 });
      const normalized = normalizeFlight(response.data);
      if (normalized) return normalized;
    } catch (error) {
      if (error.response?.status === 404) {
        continue;
      }
    }
  }

  return null;
}

async function fetchSeatsForFlight(flightID) {
  const candidates = [
    `${SEATS_SERVICE_URL}/seats?FlightID=${flightID}`,
    `${SEATS_SERVICE_URL}/seats/${flightID}`,
  ];

  for (const url of candidates) {
    try {
      const response = await axios.get(url, { timeout: 10000 });
      if (Array.isArray(response.data)) {
        return response.data;
      }
    } catch (error) {
      if (error.response?.status === 404) {
        continue;
      }
    }
  }

  return [];
}

function resolveSeat(seats, requestedSeatID, requestedSeatNumber) {
  if (!Array.isArray(seats) || seats.length === 0) {
    return null;
  }

  if (requestedSeatID != null) {
    return seats.find((seat) => Number(seat.SeatID) === Number(requestedSeatID)) || null;
  }

  if (requestedSeatNumber) {
    return seats.find(
      (seat) => String(seat.SeatNumber).toUpperCase() === String(requestedSeatNumber).toUpperCase()
    ) || null;
  }

  return null;
}

async function holdSeatById(seatID) {
  return axios.put(`${SEATS_SERVICE_URL}/seats/${seatID}/hold`, {}, { timeout: 10000 });
}

async function bookSeatById(seatID, passengerID) {
  return axios.put(
    `${SEATS_SERVICE_URL}/seats/${seatID}/book`,
    { PassengerID: passengerID },
    { timeout: 10000 }
  );
}

async function releaseSeatByFlightAndSeatNumber(flightID, seatNumber) {
  if (!flightID || !seatNumber) return;

  try {
    await axios.post(
      `${SEATS_SERVICE_URL}/seats/release`,
      {
        flightID,
        seatNumber,
      },
      { timeout: 10000 }
    );
  } catch (error) {
    console.error('Seat release rollback failed:', error.message);
  }
}

app.get('/health', (req, res) => {
  res.json({
    status: 'OK',
    service: 'booking-composite-service',
    dependencies: {
      recordService: RECORD_SERVICE_URL,
      passengerService: PASSENGER_SERVICE_URL,
      flightService: FLIGHT_SERVICE_URL,
      seatsService: SEATS_SERVICE_URL,
    }
  });
});

app.post('/api/bookings', async (req, res) => {
  const passengerID = Number(req.body.passengerID ?? req.body.PassengerID);
  const flightID = Number(req.body.flightID ?? req.body.FlightID);

  const requestedSeatID = req.body.seatID ?? req.body.SeatID;
  const requestedSeatNumber = req.body.seatNumber ?? req.body.SeatNumber;

  if (!passengerID || !flightID || (requestedSeatID == null && !requestedSeatNumber)) {
    return res.status(400).json({
      error: 'Missing required fields: passengerID, flightID, and one of seatID/seatNumber'
    });
  }

  let heldSeat = null;

  try {
    const passenger = await fetchPassenger(passengerID);
    if (!passenger) {
      return res.status(404).json({ error: 'Passenger not found' });
    }

    const flight = await fetchFlight(flightID);
    if (!flight) {
      return res.status(404).json({ error: 'Flight not found' });
    }

    if (flight.Status && flight.Status !== 'available') {
      return res.status(400).json({ error: `Flight is not available (status: ${flight.Status})` });
    }

    const seats = await fetchSeatsForFlight(flightID);
    const seat = resolveSeat(seats, requestedSeatID, requestedSeatNumber);

    if (!seat) {
      return res.status(404).json({ error: 'Seat not found for flight' });
    }

    if (String(seat.Status).toLowerCase() !== 'available') {
      return res.status(400).json({ error: 'Seat not available' });
    }

    await holdSeatById(seat.SeatID);
    heldSeat = seat;

    const amountPaid = Number(req.body.amountPaid ?? req.body.AmountPaid ?? req.body.amount ?? flight.Price);
    if (!amountPaid || amountPaid <= 0) {
      await releaseSeatByFlightAndSeatNumber(flightID, seat.SeatNumber);
      return res.status(400).json({ error: 'Invalid amountPaid' });
    }

    const recordResponse = await axios.post(
      `${RECORD_SERVICE_URL}/records`,
      {
        passengerID,
        flightID,
        seatID: Number(seat.SeatID),
        amountPaid,
      },
      { timeout: 10000 }
    );

    const booking = recordResponse.data || {};

    return res.status(201).json({
      success: true,
      bookingID: booking.bookingID,
      bookingstatus: booking.bookingstatus || booking.status || 'Pending',
      status: booking.status || booking.bookingstatus || 'Pending',
      passengerID,
      flightID,
      seatID: Number(seat.SeatID),
      seatNumber: seat.SeatNumber,
      amountPaid,
      amount: amountPaid,
      passenger,
      flight,
      message: 'Pending booking created. Proceed to payment.'
    });
  } catch (error) {
    if (heldSeat) {
      await releaseSeatByFlightAndSeatNumber(flightID, heldSeat.SeatNumber);
    }

    console.error('Booking creation failed:', error.message);
    return res.status(500).json({
      success: false,
      error: 'Booking creation failed',
      message: error.response?.data?.message || error.response?.data?.error || error.message,
    });
  }
});

app.post('/api/bookings/:bookingID/finalize', async (req, res) => {
  const bookingID = Number(req.params.bookingID);
  const passengerID = Number(req.body.passengerID ?? req.body.PassengerID);

  if (!bookingID || !passengerID) {
    return res.status(400).json({ error: 'bookingID and passengerID are required' });
  }

  try {
    const bookingResponse = await axios.get(`${RECORD_SERVICE_URL}/records/${bookingID}`, { timeout: 10000 });
    const booking = bookingResponse.data || {};

    const currentStatus = String(booking.bookingstatus || booking.status || '').toLowerCase();
    if (currentStatus === 'confirmed') {
      return res.json({
        success: true,
        message: 'Booking already confirmed',
        bookingID,
        status: 'Confirmed'
      });
    }

    if (currentStatus && currentStatus !== 'pending') {
      return res.status(409).json({
        success: false,
        error: `Booking cannot be finalized from status: ${booking.bookingstatus || booking.status}`
      });
    }

    const seatID = booking.seatID;
    if (!seatID) {
      return res.status(500).json({ error: 'Booking is missing seatID' });
    }

    await axios.put(
      `${RECORD_SERVICE_URL}/records/${bookingID}/status`,
      { bookingstatus: 'Confirmed' },
      { timeout: 10000 }
    );

    try {
      await bookSeatById(seatID, passengerID);
    } catch (seatError) {
      await axios.put(
        `${RECORD_SERVICE_URL}/records/${bookingID}/status`,
        { bookingstatus: 'Pending' },
        { timeout: 10000 }
      );
      throw seatError;
    }

    return res.json({
      success: true,
      bookingID,
      status: 'Confirmed',
      bookingstatus: 'Confirmed',
      seatID,
      message: 'Booking finalized successfully'
    });
  } catch (error) {
    console.error('Booking finalization failed:', error.message);

    return res.status(500).json({
      success: false,
      error: 'Booking finalization failed',
      message: error.response?.data?.message || error.response?.data?.error || error.message,
    });
  }
});

app.get('/api/bookings/:bookingID', async (req, res) => {
  const { bookingID } = req.params;

  try {
    const response = await axios.get(`${RECORD_SERVICE_URL}/records/${bookingID}`, { timeout: 10000 });
    res.json(response.data);
  } catch (error) {
    if (error.response?.status === 404) {
      return res.status(404).json({ error: 'Booking not found' });
    }

    console.error('Error fetching booking:', error.message);
    res.status(500).json({ error: 'Failed to fetch booking', message: error.message });
  }
});

app.get('/api/bookings/passenger/:passengerID', async (req, res) => {
  const { passengerID } = req.params;

  try {
    const response = await axios.get(`${RECORD_SERVICE_URL}/records/passenger/${passengerID}`, { timeout: 10000 });
    res.json(response.data);
  } catch (error) {
    console.error('Error fetching bookings for passenger:', error.message);
    res.status(500).json({ error: 'Failed to fetch bookings', message: error.message });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Booking Composite Service running on port ${PORT}`);
  console.log(`Using Record Service at: ${RECORD_SERVICE_URL}`);
  console.log(`Using Passenger Service at: ${PASSENGER_SERVICE_URL}`);
  console.log(`Using Flight Service at: ${FLIGHT_SERVICE_URL}`);
  console.log(`Using Seats Service at: ${SEATS_SERVICE_URL}`);
});
