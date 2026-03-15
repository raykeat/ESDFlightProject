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
  database:           process.env.DB_NAME     || 'bookingdb',
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
      console.log('✓ Connected to booking-db');
      connection.release();
    }
  });
}

waitForDB();

// ==========================================
// GET /health
// ==========================================
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'booking-service' });
});

// ==========================================
// POST /bookings
// Create a booking record (status: Pending)
// ==========================================
app.post('/bookings', (req, res) => {
  const { passengerID, flightID, amount, seatNumber } = req.body;

  pool.query(
    'INSERT INTO booking (passengerID, flightID, status, amount, seatNumber) VALUES (?, ?, "Pending", ?, ?)',
    [passengerID, flightID, amount, seatNumber],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({
        bookingID: result.insertId,
        status:    'Pending',
        message:   'Booking created successfully'
      });
    }
  );
});

// ==========================================
// GET /bookings?flightID={flightID}
// Get bookings by flight
// ==========================================
app.get('/bookings', (req, res) => {
  const { flightID } = req.query;

  pool.query(
    'SELECT * FROM booking WHERE flightID = ?',
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
// GET /bookings/passenger/:passengerID
// Get all bookings for a passenger
// ==========================================
app.get('/bookings/passenger/:passengerID', (req, res) => {
  const { passengerID } = req.params;

  pool.query(
    'SELECT * FROM booking WHERE passengerID = ? ORDER BY createdAt DESC',
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
// GET /bookings/:bookingID
// Get booking by ID
// ==========================================
app.get('/bookings/:bookingID', (req, res) => {
  const { bookingID } = req.params;

  pool.query(
    'SELECT * FROM booking WHERE bookingID = ?',
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
// PUT /bookings/:bookingID/status
// Update booking status
// ==========================================
app.put('/bookings/:bookingID/status', (req, res) => {
  const { bookingID } = req.params;
  const { status }    = req.body;

  pool.query(
    'UPDATE booking SET status = ? WHERE bookingID = ?',
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
// DELETE /booking/:bookingID
// Delete a booking
// ==========================================
app.delete('/booking/:bookingID', (req, res) => {
  const { bookingID } = req.params;

  pool.query(
    'DELETE FROM booking WHERE bookingID = ?',
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
  console.log(`Booking service running on port ${PORT}`);
});