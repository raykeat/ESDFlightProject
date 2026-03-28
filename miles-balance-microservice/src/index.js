const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');
const app = express();

app.use(cors());
app.use(express.json());

const db = mysql.createConnection({
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || 'rootpassword',
  database: process.env.DB_NAME || 'miles_balance_db'
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'miles-balance-service' });
});

// GET /miles-balance/:passengerID - Get current balance
app.get('/miles-balance/:passengerID', (req, res) => {
  const { passengerID } = req.params;

  db.query(
    'SELECT passengerID, currentBalance FROM passenger_miles WHERE passengerID = ?',
    [passengerID],
    (err, results) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (results.length === 0) {
        return res.status(404).json({ error: 'Passenger not found' });
      }
      res.json({
        passengerID: parseInt(passengerID),
        currentBalance: results[0].currentBalance
      });
    }
  );
});

// PUT /miles-balance/:passengerID/deduct - Deduct miles
app.put('/miles-balance/:passengerID/deduct', (req, res) => {
  const { passengerID } = req.params;
  const { amount } = req.body;

  if (!amount || amount <= 0) {
    return res.status(400).json({ error: 'Valid amount required' });
  }

  db.query(
    'UPDATE passenger_miles SET currentBalance = currentBalance - ? WHERE passengerID = ? AND currentBalance >= ?',
    [amount, passengerID, amount],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (result.affectedRows === 0) {
        return res.status(400).json({ error: 'Insufficient miles' });
      }

      db.query(
        'SELECT currentBalance FROM passenger_miles WHERE passengerID = ?',
        [passengerID],
        (err, results) => {
          res.json({
            success: true,
            newBalance: results[0].currentBalance
          });
        }
      );
    }
  );
});

// PUT /miles-balance/:passengerID/add - Add miles (for rollback)
app.put('/miles-balance/:passengerID/add', (req, res) => {
  const { passengerID } = req.params;
  const { amount } = req.body;

  if (!amount || amount <= 0) {
    return res.status(400).json({ error: 'Valid amount required' });
  }

  db.query(
    'UPDATE passenger_miles SET currentBalance = currentBalance + ? WHERE passengerID = ?',
    [amount, passengerID],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }

      db.query(
        'SELECT currentBalance FROM passenger_miles WHERE passengerID = ?',
        [passengerID],
        (err, results) => {
          res.json({
            success: true,
            newBalance: results[0].currentBalance
          });
        }
      );
    }
  );
});

// POST /miles-balance/:passengerID/initialize - Initialize new passenger
app.post('/miles-balance/:passengerID/initialize', (req, res) => {
  const { passengerID } = req.params;
  const { welcomeBonus = 5000 } = req.body;

  db.query(
    'INSERT INTO passenger_miles (passengerID, currentBalance) VALUES (?, ?) ON DUPLICATE KEY UPDATE currentBalance = currentBalance + ?',
    [passengerID, welcomeBonus, welcomeBonus],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }

      db.query(
        'SELECT currentBalance FROM passenger_miles WHERE passengerID = ?',
        [passengerID],
        (err, results) => {
          res.json({
            success: true,
            passengerID: parseInt(passengerID),
            currentBalance: results[0].currentBalance,
            message: 'Passenger initialized'
          });
        }
      );
    }
  );
});

const PORT = process.env.PORT || 5001;
app.listen(PORT, () => {
  console.log(`Miles Balance Service running on port ${PORT}`);
});