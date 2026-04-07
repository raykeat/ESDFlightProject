const express = require('express');
const mysql   = require('mysql2');
const cors    = require('cors');
const app     = express();

app.use(cors({
  origin: [
    'http://localhost:5173',
    'http://localhost:5174',
  ],
  credentials: true,
}));

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
      ensureBookingSchema();
    }
  });
}

waitForDB();

function ensureBookingSchema() {
  const addColumnStatements = [
    'ALTER TABLE booking ADD COLUMN inFlightPerksVoucherID INT NULL',
    'ALTER TABLE booking ADD COLUMN inFlightPerksVoucherCode VARCHAR(50) NULL',
    'ALTER TABLE booking ADD COLUMN inFlightPerksAppliedAt TIMESTAMP NULL',
    'ALTER TABLE booking ADD COLUMN originalAmountPaid DECIMAL(10,2) NULL',
    'ALTER TABLE booking ADD COLUMN travelCreditVoucherID INT NULL',
    'ALTER TABLE booking ADD COLUMN travelCreditVoucherCode VARCHAR(50) NULL',
    'ALTER TABLE booking ADD COLUMN travelCreditAppliedAmount DECIMAL(10,2) NULL',
    'ALTER TABLE booking ADD COLUMN travelCreditAppliedAt TIMESTAMP NULL',
    'ALTER TABLE booking ADD COLUMN milesAwarded INT NULL',
    'ALTER TABLE booking ADD COLUMN milesTransactionID INT NULL',
    'ALTER TABLE booking ADD COLUMN milesAwardedAt TIMESTAMP NULL',
  ];

  addColumnStatements.forEach((statement) => {
    pool.query(statement, (err) => {
      if (!err) return;
      if (err.errno !== 1060) {
        console.error('Schema migration warning:', err.message);
      }
    });
  });

  console.log('Booking schema migration check complete');
}

// ==========================================
// GET /health
// ==========================================
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'record-service' });
});

// ==========================================
// POST /records
// Create a booking record (status: Pending)
// Supports both ESD project features and friend's naming
// ==========================================
app.post('/records', (req, res) => {
  const { 
    passengerID, PassengerID,
    bookedByPassengerID, BookedByPassengerID,
    flightID, FlightID,
    amount, AmountPaid, amountPaid,
    originalAmountPaid, OriginalAmountPaid,
    seatNumber,
    returnFlightID,
    returnSeatNumber,
    isGuest, IsGuest,
    guestFirstName, GuestFirstName,
    guestLastName, GuestLastName,
    guestPassportNumber, GuestPassportNumber,
    travelCreditVoucherID, TravelCreditVoucherID,
    travelCreditVoucherCode, TravelCreditVoucherCode,
    travelCreditAppliedAmount, TravelCreditAppliedAmount,
  } = req.body;

  const finalPassengerID = PassengerID ?? passengerID;
  const finalBookedByPassengerID = BookedByPassengerID ?? bookedByPassengerID ?? finalPassengerID;
  const finalFlightID     = FlightID     ?? flightID;
  const finalAmountPaid   = AmountPaid   ?? amountPaid ?? amount;
  const finalOriginalAmountPaid = OriginalAmountPaid ?? originalAmountPaid ?? finalAmountPaid;
  const finalIsGuest      = Boolean(IsGuest ?? isGuest);
  const finalGuestFirstName = GuestFirstName ?? guestFirstName ?? null;
  const finalGuestLastName = GuestLastName ?? guestLastName ?? null;
  const finalGuestPassportNumber = GuestPassportNumber ?? guestPassportNumber ?? null;
  const finalTravelCreditVoucherID = TravelCreditVoucherID ?? travelCreditVoucherID ?? null;
  const finalTravelCreditVoucherCode = TravelCreditVoucherCode ?? travelCreditVoucherCode ?? null;
  const finalTravelCreditAppliedAmount = TravelCreditAppliedAmount ?? travelCreditAppliedAmount ?? null;

  if (!finalFlightID || finalAmountPaid == null) {
    return res.status(400).json({ error: 'FlightID and amount are required' });
  }

  if (!finalBookedByPassengerID) {
    return res.status(400).json({ error: 'BookedByPassengerID is required' });
  }

  if (!finalPassengerID && !finalIsGuest) {
    return res.status(400).json({ error: 'PassengerID is required for non-guest bookings' });
  }

  if (finalIsGuest && (!finalGuestFirstName || !finalGuestLastName || !finalGuestPassportNumber)) {
    return res.status(400).json({ error: 'GuestFirstName, GuestLastName, and GuestPassportNumber are required for guest bookings' });
  }

  pool.query(
    `INSERT INTO booking (
      PassengerID, BookedByPassengerID, FlightID, AmountPaid, bookingstatus, seatNumber,
      returnFlightID, returnSeatNumber, IsGuest, GuestFirstName, GuestLastName, GuestPassportNumber,
      originalAmountPaid, travelCreditVoucherID, travelCreditVoucherCode, travelCreditAppliedAmount
    ) VALUES (?, ?, ?, ?, "Pending", ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      finalPassengerID, 
      finalBookedByPassengerID,
      finalFlightID, 
      finalAmountPaid, 
      seatNumber        || null, 
      returnFlightID    || null, 
      returnSeatNumber  || null,
      finalIsGuest,
      finalGuestFirstName,
      finalGuestLastName,
      finalGuestPassportNumber,
      finalOriginalAmountPaid,
      finalTravelCreditVoucherID,
      finalTravelCreditVoucherCode,
      finalTravelCreditAppliedAmount,
    ],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({
        bookingID: result.insertId,
        status: 'Pending',
        message: 'Booking Record created successfully'
      });
    }
  );
});

// ==========================================
// PUT /records/:bookingID/perks
// Attach in-flight perks metadata to a booking
// ==========================================
app.put('/records/:bookingID/perks', (req, res) => {
  const { bookingID } = req.params;
  const { passengerID, voucherID, voucherCode } = req.body;

  if (!passengerID || !voucherID || !voucherCode) {
    return res.status(400).json({ error: 'passengerID, voucherID, and voucherCode are required' });
  }

  pool.query(
    'SELECT BookingID, BookedByPassengerID, PassengerID, bookingstatus, inFlightPerksVoucherID FROM booking WHERE BookingID = ?',
    [bookingID],
    (selectErr, rows) => {
      if (selectErr) {
        console.error(selectErr);
        return res.status(500).json({ error: selectErr.message });
      }

      if (!rows.length) {
        return res.status(404).json({ error: 'Booking not found' });
      }

      const booking = rows[0];
      const ownerID = Number(booking.BookedByPassengerID || booking.PassengerID);

      if (ownerID !== Number(passengerID)) {
        return res.status(403).json({ error: 'Booking does not belong to this passenger' });
      }

      if (String(booking.bookingstatus) !== 'Confirmed') {
        return res.status(409).json({ error: 'In-flight perks can only be attached to confirmed bookings' });
      }

      if (booking.inFlightPerksVoucherID) {
        return res.status(409).json({ error: 'In-flight perks are already attached to this booking' });
      }

      pool.query(
        `UPDATE booking
         SET inFlightPerksVoucherID = ?, inFlightPerksVoucherCode = ?, inFlightPerksAppliedAt = NOW()
         WHERE BookingID = ?`,
        [voucherID, voucherCode, bookingID],
        (updateErr, result) => {
          if (updateErr) {
            console.error(updateErr);
            return res.status(500).json({ error: updateErr.message });
          }

          if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Booking not found' });
          }

          res.json({
            success: true,
            message: 'In-flight perks attached successfully',
          });
        }
      );
    }
  );
});

// ==========================================
// DELETE /records/:bookingID/perks
// Remove attached in-flight perks metadata
// ==========================================
app.delete('/records/:bookingID/perks', (req, res) => {
  const { bookingID } = req.params;

  pool.query(
    `UPDATE booking
     SET inFlightPerksVoucherID = NULL, inFlightPerksVoucherCode = NULL, inFlightPerksAppliedAt = NULL
     WHERE BookingID = ?`,
    [bookingID],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }

      if (result.affectedRows === 0) {
        return res.status(404).json({ error: 'Booking not found' });
      }

      res.json({ success: true, message: 'In-flight perks removed successfully' });
    }
  );
});

// ==========================================
// GET /records?flightID={flightID}
// Get booking records by flight
// ==========================================
app.get('/records', (req, res) => {
  const flightID = req.query.FlightID || req.query.flightID;
  const bookingStatus = req.query.BookingStatus || req.query.bookingstatus || req.query.status;

  if (!flightID) {
    return res.status(400).json({ error: 'FlightID is required' });
  }

  let sql = `SELECT
      BookingID AS bookingID,
      BookingID AS BookingID,
      FlightID AS flightID,
      FlightID AS FlightID,
      seatNumber AS seatID,
      seatNumber AS seatNumber,
      PassengerID AS passengerID,
      PassengerID AS PassengerID,
      BookedByPassengerID AS bookedByPassengerID,
      BookedByPassengerID AS BookedByPassengerID,
      IsGuest AS isGuest,
      IsGuest AS IsGuest,
      GuestFirstName AS guestFirstName,
      GuestFirstName AS GuestFirstName,
      GuestLastName AS guestLastName,
      GuestLastName AS GuestLastName,
      GuestPassportNumber AS guestPassportNumber,
      GuestPassportNumber AS GuestPassportNumber,
      AmountPaid AS amount,
      AmountPaid AS amountPaid,
      AmountPaid AS AmountPaid,
      originalAmountPaid,
      travelCreditVoucherID,
      travelCreditVoucherCode,
      travelCreditAppliedAmount,
      travelCreditAppliedAt,
      bookingstatus AS status,
      bookingstatus AS BookingStatus,
      bookingstatus AS bookingstatus,
      inFlightPerksVoucherID,
      inFlightPerksVoucherCode,
      inFlightPerksAppliedAt,
      milesAwarded,
      milesTransactionID,
      milesAwardedAt,
      CreatedTime AS createdAt,
      CreatedTime AS createdTime,
      CreatedTime AS CreatedTime
    FROM booking
    WHERE FlightID = ?`;

  const params = [flightID];
  if (bookingStatus) {
    sql += ' AND bookingstatus = ?';
    params.push(bookingStatus);
  }

  sql += ' ORDER BY CreatedTime ASC';

  pool.query(
    sql,
    params,
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
      seatNumber AS seatID,
      seatNumber AS seatNumber,
      PassengerID AS passengerID,
      BookedByPassengerID AS bookedByPassengerID,
      BookedByPassengerID AS BookedByPassengerID,
      IsGuest AS isGuest,
      IsGuest AS IsGuest,
      GuestFirstName AS guestFirstName,
      GuestFirstName AS GuestFirstName,
      GuestLastName AS guestLastName,
      GuestLastName AS GuestLastName,
      GuestPassportNumber AS guestPassportNumber,
      GuestPassportNumber AS GuestPassportNumber,
      AmountPaid AS amount,
      AmountPaid AS amountPaid,
      originalAmountPaid,
      travelCreditVoucherID,
      travelCreditVoucherCode,
      travelCreditAppliedAmount,
      travelCreditAppliedAt,
      bookingstatus AS status,
      bookingstatus AS bookingstatus,
      inFlightPerksVoucherID,
      inFlightPerksVoucherCode,
      inFlightPerksAppliedAt,
      milesAwarded,
      milesTransactionID,
      milesAwardedAt,
      CreatedTime AS createdAt,
      CreatedTime AS createdTime
    FROM booking
    WHERE PassengerID = ? OR BookedByPassengerID = ?
    ORDER BY CreatedTime DESC`,
    [passengerID, passengerID],
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
// GET /records/pending/expired?minutes=5
// Get pending booking records older than threshold
// ==========================================
app.get('/records/pending/expired', (req, res) => {
  const minutes = Number(req.query.minutes || 5);

  if (!Number.isFinite(minutes) || minutes <= 0) {
    return res.status(400).json({ error: 'minutes must be a positive number' });
  }

  pool.query(
    `SELECT
      BookingID AS bookingID,
      BookingID AS BookingID,
      FlightID AS flightID,
      FlightID AS FlightID,
      seatNumber AS seatNumber,
      seatNumber AS SeatNumber,
      PassengerID AS passengerID,
      PassengerID AS PassengerID,
      BookedByPassengerID AS bookedByPassengerID,
      BookedByPassengerID AS BookedByPassengerID,
      bookingstatus AS status,
      bookingstatus AS bookingstatus,
      CreatedTime AS createdAt,
      CreatedTime AS CreatedTime
    FROM booking
    WHERE bookingstatus = 'Pending'
      AND CreatedTime <= DATE_SUB(NOW(), INTERVAL ? MINUTE)
    ORDER BY CreatedTime ASC`,
    [minutes],
    (err, results) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      return res.json(results || []);
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
      seatNumber AS seatID,
      seatNumber AS seatNumber,
      PassengerID AS passengerID,
      BookedByPassengerID AS bookedByPassengerID,
      IsGuest AS isGuest,
      GuestFirstName AS guestFirstName,
      GuestLastName AS guestLastName,
      GuestPassportNumber AS guestPassportNumber,
      AmountPaid AS amount,
      AmountPaid AS amountPaid,
      originalAmountPaid,
      travelCreditVoucherID,
      travelCreditVoucherCode,
      travelCreditAppliedAmount,
      travelCreditAppliedAt,
      bookingstatus AS status,
      bookingstatus AS bookingstatus,
      inFlightPerksVoucherID,
      inFlightPerksVoucherCode,
      inFlightPerksAppliedAt,
      milesAwarded,
      milesTransactionID,
      milesAwardedAt,
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

app.put('/records/:bookingID', (req, res) => {
  const { bookingID } = req.params;
  const status = req.body.BookingStatus || req.body.bookingstatus || req.body.status;

  if (!status) {
    return res.status(400).json({ error: 'BookingStatus is required' });
  }

  pool.query(
    'UPDATE booking SET bookingstatus = ? WHERE BookingID = ?',
    [status, bookingID],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (result.affectedRows === 0) {
        return res.status(404).json({ error: 'Booking not found' });
      }
      return res.json({
        BookingID: Number(bookingID),
        BookingStatus: status
      });
    }
  );
});

app.put('/records/:bookingID/rebook', (req, res) => {
  const { bookingID } = req.params;
  const flightID = req.body.FlightID || req.body.flightID;
  const seatNumber = req.body.seatNumber || req.body.SeatNumber;
  const status = req.body.BookingStatus || req.body.bookingstatus || req.body.status || 'Confirmed';
  const travelCreditVoucherID = req.body.travelCreditVoucherID ?? req.body.TravelCreditVoucherID;
  const travelCreditVoucherCode = req.body.travelCreditVoucherCode ?? req.body.TravelCreditVoucherCode;
  const travelCreditAppliedAmount = req.body.travelCreditAppliedAmount ?? req.body.TravelCreditAppliedAmount;
  const inFlightPerksVoucherID = req.body.inFlightPerksVoucherID ?? req.body.InFlightPerksVoucherID;
  const inFlightPerksVoucherCode = req.body.inFlightPerksVoucherCode ?? req.body.InFlightPerksVoucherCode;

  if (!flightID || !seatNumber) {
    return res.status(400).json({ error: 'FlightID and seatNumber are required' });
  }

  const updateFields = ['FlightID = ?', 'seatNumber = ?', 'bookingstatus = ?'];
  const updateValues = [flightID, seatNumber, status];

  if (typeof travelCreditVoucherID !== 'undefined') {
    updateFields.push('travelCreditVoucherID = ?');
    updateValues.push(travelCreditVoucherID);
  }
  if (typeof travelCreditVoucherCode !== 'undefined') {
    updateFields.push('travelCreditVoucherCode = ?');
    updateValues.push(travelCreditVoucherCode);
  }
  if (typeof travelCreditAppliedAmount !== 'undefined') {
    updateFields.push('travelCreditAppliedAmount = ?');
    updateValues.push(travelCreditAppliedAmount);
  }
  if (typeof inFlightPerksVoucherID !== 'undefined') {
    updateFields.push('inFlightPerksVoucherID = ?');
    updateValues.push(inFlightPerksVoucherID);
  }
  if (typeof inFlightPerksVoucherCode !== 'undefined') {
    updateFields.push('inFlightPerksVoucherCode = ?');
    updateValues.push(inFlightPerksVoucherCode);
  }

  updateValues.push(bookingID);

  pool.query(
    `UPDATE booking SET ${updateFields.join(', ')} WHERE BookingID = ?`,
    updateValues,
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (result.affectedRows === 0) {
        return res.status(404).json({ error: 'Booking not found' });
      }

      return res.json({
        BookingID: Number(bookingID),
        FlightID: Number(flightID),
        seatNumber,
        BookingStatus: status,
      });
    }
  );
});

// ==========================================
// PUT /records/:bookingID/miles-awarded
// Mark a booking as having miles awarded (idempotent)
// ==========================================
app.put('/records/:bookingID/miles-awarded', (req, res) => {
  const { bookingID } = req.params;
  const { milesAwarded, transactionID } = req.body;

  if (!Number.isFinite(Number(milesAwarded)) || Number(milesAwarded) <= 0) {
    return res.status(400).json({ error: 'milesAwarded must be a positive number' });
  }

  pool.query(
    `UPDATE booking
     SET milesAwarded = ?, milesTransactionID = ?, milesAwardedAt = NOW()
     WHERE BookingID = ? AND milesAwardedAt IS NULL`,
    [Number(milesAwarded), transactionID || null, bookingID],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }

      if (result.affectedRows > 0) {
        return res.json({
          success: true,
          bookingID: Number(bookingID),
          milesAwarded: Number(milesAwarded),
          transactionID: transactionID || null,
          alreadyAwarded: false,
        });
      }

      pool.query(
        'SELECT BookingID, milesAwarded, milesTransactionID, milesAwardedAt FROM booking WHERE BookingID = ?',
        [bookingID],
        (selectErr, rows) => {
          if (selectErr) {
            console.error(selectErr);
            return res.status(500).json({ error: selectErr.message });
          }

          if (!rows.length) {
            return res.status(404).json({ error: 'Booking not found' });
          }

          return res.json({
            success: true,
            bookingID: Number(bookingID),
            milesAwarded: rows[0].milesAwarded,
            transactionID: rows[0].milesTransactionID,
            milesAwardedAt: rows[0].milesAwardedAt,
            alreadyAwarded: true,
          });
        }
      );
    }
  );
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Record service running on port ${PORT}`);
});
