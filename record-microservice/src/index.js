const express = require('express');
const mysql   = require('mysql2');
const app     = express();

app.use(express.json());

// ==========================================
// DATABASE — use pool + retry instead of
// createConnection() which crashes on startup
// if the DB isn't ready yet
// ==========================================
const pool = mysql.createPool({
  host:               process.env.DB_HOST     || 'localhost',
  user:               process.env.DB_USER     || 'root',
  password:           process.env.DB_PASSWORD || 'rootpassword',
  database:           process.env.DB_NAME     || 'recorddb',
  waitForConnections: true,
  connectionLimit:    10,
  queueLimit:         0
});

// Retry connecting until DB is ready (handles race condition with Docker healthcheck)
function waitForDB(retries = 10, delay = 3000) {
  pool.getConnection((err, connection) => {
    if (err) {
      if (retries === 0) {
        console.error('Could not connect to database after multiple retries. Exiting.');
        process.exit(1);
      }
      console.log(`Database not ready, retrying in ${delay/1000}s... (${retries} retries left)`);
      setTimeout(() => waitForDB(retries - 1, delay), delay);
    } else {
      console.log('✓ Connected to record-db');
      connection.release();
    }
  });
}

waitForDB();

// ==========================================
// GET /health
// ==========================================
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'record-service' });
});

// ==========================================
// POST /records
// Create a booking record (status: Pending)
// ==========================================
app.post('/records', (req, res) => {
  const { passengerID, flightID, amount, amountPaid, seatID, seatNumber } = req.body;
  const normalizedAmount = amountPaid ?? amount;
  const parsedSeatID = Number.parseInt(seatID ?? seatNumber, 10);
  const normalizedSeatID = Number.isNaN(parsedSeatID) ? null : parsedSeatID;

  pool.query(
    'INSERT INTO booking (PassengerID, FlightID, SeatID, AmountPaid, bookingstatus) VALUES (?, ?, ?, ?, "Pending")',
    [passengerID, flightID, normalizedSeatID, normalizedAmount],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({
        bookingID: result.insertId,
        status: 'Pending',
        message:   'Booking Record created successfully'
      });
    }
  );
});

// ==========================================
// GET /records?flightID={flightID}
// Get booking records by flight
// ==========================================
app.get('/records', (req, res) => {
  const { flightID } = req.query;

  pool.query(
    `SELECT
      BookingID AS bookingID,
      FlightID AS flightID,
      SeatID AS seatID,
      SeatID AS seatNumber,
      PassengerID AS passengerID,
      AmountPaid AS amount,
      AmountPaid AS amountPaid,
      bookingstatus AS status,
      bookingstatus AS bookingstatus,
      CreatedTime AS createdAt,
      CreatedTime AS createdTime
    FROM booking
    WHERE FlightID = ?`,
    [flightID],
    (err, results) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.json(results);
    }
  );
});

// ==========================================
// GET /records/passenger/:passengerID
// Get all booking records for a passenger
// ==========================================
app.get('/records/passenger/:passengerID', (req, res) => {
  const { passengerID } = req.params;

  pool.query(
    `SELECT
      BookingID AS bookingID,
      FlightID AS flightID,
      SeatID AS seatID,
      SeatID AS seatNumber,
      PassengerID AS passengerID,
      AmountPaid AS amount,
      AmountPaid AS amountPaid,
      bookingstatus AS status,
      bookingstatus AS bookingstatus,
      CreatedTime AS createdAt,
      CreatedTime AS createdTime
    FROM booking
    WHERE PassengerID = ?
    ORDER BY CreatedTime DESC`,
    [passengerID],
    (err, results) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.json(results);
    }
  );
});

// ==========================================
// GET /records/:bookingID
// Get booking records by ID
// ==========================================
app.get('/records/:bookingID', (req, res) => {
  const { bookingID } = req.params;

  pool.query(
    `SELECT
      BookingID AS bookingID,
      FlightID AS flightID,
      SeatID AS seatID,
      SeatID AS seatNumber,
      PassengerID AS passengerID,
      AmountPaid AS amount,
      AmountPaid AS amountPaid,
      bookingstatus AS status,
      bookingstatus AS bookingstatus,
      CreatedTime AS createdAt,
      CreatedTime AS createdTime
    FROM booking
    WHERE BookingID = ?`,
    [bookingID],
    (err, results) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (results.length === 0) {
        return res.status(404).json({ error: 'Booking not found' });
      }
      res.json(results[0]);
    }
  );
});

// ==========================================
// PUT /records/:bookingID/status
// Update booking record status
// ==========================================
app.put('/records/:bookingID/status', (req, res) => {
  const { bookingID } = req.params;
  const { status }    = req.body;

  pool.query(
    'UPDATE booking SET bookingstatus = ? WHERE BookingID = ?',
    [status, bookingID],
    (err) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.json({ message: 'Booking status updated successfully' });
    }
  );
});

// ==========================================
// DELETE /record/:bookingID
// Delete a booking record
// ==========================================
app.delete('/record/:bookingID', (req, res) => {
  const { bookingID } = req.params;

  pool.query(
    'DELETE FROM booking WHERE BookingID = ?',
    [bookingID],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (result.affectedRows === 0) {
        return res.status(404).json({ error: 'Booking not found' });
      }
      res.json({ message: 'Booking deleted successfully' });
    }
  );
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Record service running on port ${PORT}`);
});