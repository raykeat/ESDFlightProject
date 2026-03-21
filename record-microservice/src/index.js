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
  const { passengerID, flightID } = req.body;
  const seatID = req.body.seatID ?? req.body.SeatID ?? req.body.seatNumber;
  const amountPaid = req.body.amountPaid ?? req.body.AmountPaid ?? req.body.amount;

  if (!passengerID || !flightID || seatID == null || amountPaid == null) {
    return res.status(400).json({
      error: 'Missing required fields: passengerID, flightID, seatID, amountPaid'
    });
  }

  pool.query(
    'INSERT INTO record (PassengerID, FlightID, SeatID, bookingstatus, AmountPaid) VALUES (?, ?, ?, "Pending", ?)',
    [passengerID, flightID, seatID, amountPaid],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({
        bookingID: result.insertId,
        bookingstatus: 'Pending',
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
      PassengerID AS passengerID,
      AmountPaid AS amountPaid,
      bookingstatus,
      CreatedTime AS createdTime,
      bookingstatus AS status,
      AmountPaid AS amount,
      SeatID AS seatNumber
    FROM record
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
      PassengerID AS passengerID,
      AmountPaid AS amountPaid,
      bookingstatus,
      CreatedTime AS createdTime,
      bookingstatus AS status,
      AmountPaid AS amount,
      SeatID AS seatNumber
    FROM record
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
      PassengerID AS passengerID,
      AmountPaid AS amountPaid,
      bookingstatus,
      CreatedTime AS createdTime,
      bookingstatus AS status,
      AmountPaid AS amount,
      SeatID AS seatNumber
    FROM record
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
  const status = req.body.status ?? req.body.bookingstatus;
  const allowedStatuses = ['Confirmed', 'Pending', 'Cancelled', 'Failed'];

  if (!allowedStatuses.includes(status)) {
    return res.status(400).json({
      error: `Invalid status. Allowed values: ${allowedStatuses.join(', ')}`
    });
  }

  pool.query(
    'UPDATE record SET bookingstatus = ? WHERE BookingID = ?',
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
    'DELETE FROM record WHERE BookingID = ?',
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