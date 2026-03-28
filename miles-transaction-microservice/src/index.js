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
  database: process.env.DB_NAME || 'miles_transaction_db'
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'miles-transaction-service' });
});

// POST /transactions - Log a transaction
app.post('/transactions', (req, res) => {
  const { passengerID, milesDelta, transactionType, description, referenceID, originalTransactionID, voucherType } = req.body;

  if (!passengerID || milesDelta === undefined || !transactionType) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  db.query(
    `INSERT INTO transactions (passengerID, milesDelta, transactionType, description, referenceID, originalTransactionID, voucherType) 
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [passengerID, milesDelta, transactionType, description, referenceID || null, originalTransactionID || null, voucherType || null],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({
        success: true,
        transactionID: result.insertId,
        message: 'Transaction logged successfully'
      });
    }
  );
});

// GET /transactions/:passengerID - Get transaction history
app.get('/transactions/:passengerID', (req, res) => {
  const { passengerID } = req.params;
  const { limit = 50 } = req.query;

  db.query(
    'SELECT * FROM transactions WHERE passengerID = ? ORDER BY createdAt DESC LIMIT ?',
    [passengerID, parseInt(limit)],
    (err, results) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.json(results);
    }
  );
});

// PUT /transactions/:transactionID/reference - Update reference ID
app.put('/transactions/:transactionID/reference', (req, res) => {
  const { transactionID } = req.params;
  const { referenceID } = req.body;

  db.query(
    'UPDATE transactions SET referenceID = ? WHERE transactionID = ?',
    [referenceID, transactionID],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.json({ success: true, message: 'Reference updated' });
    }
  );
});

// GET /transactions/:passengerID/summary - Get earned vs redeemed summary
app.get('/transactions/:passengerID/summary', (req, res) => {
  const { passengerID } = req.params;

  db.query(
    `SELECT 
      SUM(CASE WHEN milesDelta > 0 THEN milesDelta ELSE 0 END) as totalEarned,
      SUM(CASE WHEN milesDelta < 0 THEN milesDelta ELSE 0 END) as totalRedeemed
     FROM transactions WHERE passengerID = ?`,
    [passengerID],
    (err, results) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.json({
        passengerID: parseInt(passengerID),
        totalEarned: results[0].totalEarned || 0,
        totalRedeemed: Math.abs(results[0].totalRedeemed || 0),
        netBalance: (results[0].totalEarned || 0) + (results[0].totalRedeemed || 0)
      });
    }
  );
});

const PORT = process.env.PORT || 5002;
app.listen(PORT, () => {
  console.log(`Miles Transaction Service running on port ${PORT}`);
});