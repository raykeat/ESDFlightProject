const express = require('express');
const cors = require('cors');
const axios = require('axios');

const app = express();
app.use(express.json());
app.use(cors());

const PORT = process.env.PORT || 3006;
const FLIGHT_SERVICE_URL = process.env.FLIGHT_SERVICE_URL || 'http://flight-service:3000';
const SEATS_SERVICE_URL = process.env.SEATS_SERVICE_URL || 'http://seats-service:5003';

function sanitizeSeatRow(seat) {
  return {
    SeatNumber: seat.SeatNumber,
    Status: seat.Status,
  };
}

app.get('/health', (req, res) => {
  res.json({
    status: 'OK',
    service: 'flight-search-composite',
    dependencies: {
      flightService: FLIGHT_SERVICE_URL,
      seatsService: SEATS_SERVICE_URL,
    },
  });
});

app.get('/search/details', async (req, res) => {
  const flightID = Number(req.query.FlightID || req.query.flightID);

  if (!flightID) {
    return res.status(400).json({ error: 'FlightID query parameter is required' });
  }

  try {
    const [flightResponse, seatsResponse] = await Promise.all([
      axios.get(`${FLIGHT_SERVICE_URL}/flight/${flightID}`, { timeout: 10000 }),
      axios.get(`${SEATS_SERVICE_URL}/seats?FlightID=${flightID}`, { timeout: 10000 }),
    ]);

    const flight = flightResponse.data;
    const seatsRaw = Array.isArray(seatsResponse.data) ? seatsResponse.data : [];
    const seats = seatsRaw.map(sanitizeSeatRow);

    return res.json({
      FlightID: flight.FlightID,
      FlightNumber: flight.FlightNumber,
      Origin: flight.Origin,
      Destination: flight.Destination,
      Date: flight.Date,
      DepartureTime: flight.DepartureTime,
      FlightDuration: flight.FlightDuration,
      ArrivalTime: flight.ArrivalTime,
      Price: flight.Price,
      Status: flight.Status,
      Seats: seats,
    });
  } catch (error) {
    if (error.response?.status === 404) {
      return res.status(404).json({ error: 'Flight not found' });
    }

    return res.status(500).json({
      error: 'Failed to retrieve flight details',
      message: error.response?.data?.message || error.message,
    });
  }
});

app.listen(PORT, () => {
  console.log(`Flight Search Composite running on port ${PORT}`);
});
