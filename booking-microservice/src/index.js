const express = require('express');
const mysql = require('mysql2');
const app = express();

app.use(express.json());

// Database connection - uses environment variables from Docker
const db = mysql.createConnection({
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || 'password',
  database: process.env.DB_NAME || 'bookingdb'
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'booking-service' });
});

// Create a booking
app.post('/bookings', (req, res) => {
  const { passengerID, flightID, amount, seatNumber } = req.body;
  
  db.query(
    'INSERT INTO booking (passengerID, flightID, status, amount, seatNumber) VALUES (?, ?, "Pending", ?, ?)',
    [passengerID, flightID, amount, seatNumber],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({ 
        bookingID: result.insertId, 
        status: 'Pending',
        message: 'Booking created successfully'
      });
    }
  );
});

// Get bookings by flight
app.get('/bookings', (req, res) => {
  const { flightID } = req.query;
  
  db.query(
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

// Update booking status
app.put('/bookings/:bookingID/status', (req, res) => {
  const { bookingID } = req.params;
  const { status } = req.body;
  
  db.query(
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

// Get booking by ID
app.get('/bookings/:bookingID', (req, res) => {
  const { bookingID } = req.params;
  
  db.query(
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

// Delete a booking - DELETE /booking/{bookingID}
app.delete('/booking/:bookingID', (req, res) => {
  const { bookingID } = req.params;
  
  db.query(
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