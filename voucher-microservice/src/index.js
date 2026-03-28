const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');
const crypto = require('crypto');
const app = express();

app.use(cors());
app.use(express.json());

const db = mysql.createConnection({
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || 'rootpassword',
  database: process.env.DB_NAME || 'voucher_db'
});

// Helper function to generate unique voucher code
function generateVoucherCode() {
  const prefix = 'VCH';
  const random = crypto.randomBytes(6).toString('hex').toUpperCase();
  return `${prefix}-${random.slice(0, 4)}-${random.slice(4, 8)}-${random.slice(8, 12)}`;
}

// Voucher type definitions
const VOUCHER_TYPES = {
  TRAVEL_CREDIT: {
    name: 'Travel Credit',
    rate: 100,  // 100 miles = $1
    minMiles: 1000,
    expiryDays: 365,
    calculateValue: (miles) => miles / 100
  },
  UPGRADE: {
    name: 'Cabin Upgrade',
    rate: 500,  // 500 miles per upgrade
    minMiles: 2000,
    expiryDays: 180,
    calculateValue: () => 1  // 1 upgrade
  },
  LOUNGE_PASS: {
    name: 'Lounge Pass',
    rate: 2000,  // 2000 miles per pass
    minMiles: 2000,
    expiryDays: 90,
    calculateValue: () => 1  // 1 pass
  }
};

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'voucher-service' });
});

// GET /vouchers/types - Get available voucher types
app.get('/vouchers/types', (req, res) => {
  const types = Object.entries(VOUCHER_TYPES).map(([key, value]) => ({
    type: key,
    name: value.name,
    rate: value.rate,
    minMiles: value.minMiles,
    expiryDays: value.expiryDays
  }));

  res.json({ voucherTypes: types });
});

// GET /vouchers/types/:type - Get specific voucher type details
app.get('/vouchers/types/:type', (req, res) => {
  const { type } = req.params;
  const voucherType = VOUCHER_TYPES[type];

  if (!voucherType) {
    return res.status(404).json({ error: 'Voucher type not found' });
  }

  res.json({
    type,
    name: voucherType.name,
    rate: voucherType.rate,
    minMiles: voucherType.minMiles,
    expiryDays: voucherType.expiryDays
  });
});

// POST /vouchers - Generate new voucher
app.post('/vouchers', (req, res) => {
  const { passengerID, voucherType, milesRedeemed, voucherValue } = req.body;

  if (!passengerID || !voucherType || !milesRedeemed) {
    return res.status(400).json({ error: 'Missing required fields: passengerID, voucherType, milesRedeemed' });
  }

  const typeConfig = VOUCHER_TYPES[voucherType];
  if (!typeConfig) {
    return res.status(400).json({ error: 'Invalid voucher type' });
  }

  // Validation rules mirror loyalty-composite:
  // - TRAVEL_CREDIT uses a min threshold
  // - Fixed vouchers require their fixed rate amount
  if (voucherType === 'TRAVEL_CREDIT') {
    if (milesRedeemed < typeConfig.minMiles) {
      return res.status(400).json({
        error: `Minimum ${typeConfig.minMiles} miles required for ${voucherType}`,
        minRequired: typeConfig.minMiles
      });
    }
  } else if (milesRedeemed < typeConfig.rate) {
    return res.status(400).json({
      error: `Insufficient milesRedeemed for ${voucherType}. Need ${typeConfig.rate}`,
      requiredMiles: typeConfig.rate
    });
  }

  const voucherCode = generateVoucherCode();
  const expiryDate = new Date();
  expiryDate.setDate(expiryDate.getDate() + typeConfig.expiryDays);

  // Calculate value if not provided
  let finalValue = voucherValue;
  if (!finalValue && typeConfig.calculateValue) {
    finalValue = typeConfig.calculateValue(milesRedeemed);
  }

  db.query(
    `INSERT INTO vouchers (passengerID, voucherCode, voucherType, voucherValue, milesRedeemed, expiryDate, status) 
     VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')`,
    [passengerID, voucherCode, voucherType, finalValue, milesRedeemed, expiryDate.toISOString().split('T')[0]],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }

      res.status(201).json({
        success: true,
        voucherID: result.insertId,
        voucherCode,
        voucherType,
        voucherValue: finalValue,
        milesRedeemed,
        expiryDate: expiryDate.toISOString().split('T')[0],
        status: 'ACTIVE'
      });
    }
  );
});

// POST /vouchers/bundle - Generate multiple vouchers in one call
app.post('/vouchers/bundle', (req, res) => {
  const { passengerID, items } = req.body;

  if (!passengerID || !items || !Array.isArray(items) || items.length === 0) {
    return res.status(400).json({ error: 'Missing required fields: passengerID, items array' });
  }

  const results = [];
  const errors = [];

  // Process each item sequentially
  const processItem = (index, callback) => {
    if (index >= items.length) {
      return callback(null, results);
    }

    const item = items[index];
    const typeConfig = VOUCHER_TYPES[item.voucherType];

    if (!typeConfig) {
      errors.push({ item, error: 'Invalid voucher type' });
      return processItem(index + 1, callback);
    }

    if (item.voucherType === 'TRAVEL_CREDIT') {
      if (item.milesRedeemed < typeConfig.minMiles) {
        errors.push({
          item,
          error: `Minimum ${typeConfig.minMiles} miles required for ${item.voucherType}`,
          minRequired: typeConfig.minMiles
        });
        return processItem(index + 1, callback);
      }
    } else if (item.milesRedeemed < typeConfig.rate) {
      errors.push({
        item,
        error: `Insufficient milesRedeemed for ${item.voucherType}. Need ${typeConfig.rate}`,
        requiredMiles: typeConfig.rate
      });
      return processItem(index + 1, callback);
    }

    const voucherCode = generateVoucherCode();
    const expiryDate = new Date();
    expiryDate.setDate(expiryDate.getDate() + typeConfig.expiryDays);
    const voucherValue = typeConfig.calculateValue(item.milesRedeemed);

    db.query(
      `INSERT INTO vouchers (passengerID, voucherCode, voucherType, voucherValue, milesRedeemed, expiryDate, status) 
       VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')`,
      [passengerID, voucherCode, item.voucherType, voucherValue, item.milesRedeemed, expiryDate.toISOString().split('T')[0]],
      (err, result) => {
        if (err) {
          errors.push({ item, error: err.message });
        } else {
          results.push({
            voucherID: result.insertId,
            voucherCode,
            voucherType: item.voucherType,
            voucherValue,
            milesRedeemed: item.milesRedeemed,
            expiryDate: expiryDate.toISOString().split('T')[0]
          });
        }
        processItem(index + 1, callback);
      }
    );
  };

  processItem(0, (err, resultsList) => {
    if (errors.length > 0 && resultsList.length === 0) {
      return res.status(500).json({
        success: false,
        error: 'Failed to create any vouchers',
        errors
      });
    }

    res.status(201).json({
      success: true,
      vouchers: resultsList,
      errors: errors.length > 0 ? errors : undefined,
      partialSuccess: errors.length > 0 && resultsList.length > 0
    });
  });
});

// GET /vouchers/:passengerID - Get all vouchers for passenger
app.get('/vouchers/:passengerID', (req, res) => {
  const { passengerID } = req.params;
  const { status } = req.query;

  let query = 'SELECT * FROM vouchers WHERE passengerID = ?';
  const params = [passengerID];

  if (status) {
    query += ' AND status = ?';
    params.push(status);
  }

  query += ' ORDER BY createdAt DESC';

  db.query(query, params, (err, results) => {
    if (err) {
      console.error(err);
      return res.status(500).json({ error: err.message });
    }
    res.json(results);
  });
});

// GET /vouchers/code/:voucherCode - Get voucher by code
app.get('/vouchers/code/:voucherCode', (req, res) => {
  const { voucherCode } = req.params;

  db.query(
    'SELECT * FROM vouchers WHERE voucherCode = ?',
    [voucherCode],
    (err, results) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (results.length === 0) {
        return res.status(404).json({ error: 'Voucher not found' });
      }
      res.json(results[0]);
    }
  );
});

// PUT /vouchers/:voucherID/redeem - Mark voucher as used
app.put('/vouchers/:voucherID/redeem', (req, res) => {
  const { voucherID } = req.params;
  const { bookingID } = req.body;

  db.query(
    'UPDATE vouchers SET status = "USED", usedAt = NOW(), usedBookingID = ? WHERE voucherID = ? AND status = "ACTIVE"',
    [bookingID, voucherID],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (result.affectedRows === 0) {
        return res.status(404).json({ error: 'Voucher not found or already used/expired' });
      }
      res.json({ success: true, message: 'Voucher redeemed successfully' });
    }
  );
});

// PUT /vouchers/:voucherID/status - Update voucher status
app.put('/vouchers/:voucherID/status', (req, res) => {
  const { voucherID } = req.params;
  const { status } = req.body;

  db.query(
    'UPDATE vouchers SET status = ? WHERE voucherID = ?',
    [status, voucherID],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      res.json({ success: true, message: `Voucher status updated to ${status}` });
    }
  );
});

const PORT = process.env.PORT || 5003;
app.listen(PORT, () => {
  console.log(`Voucher Service running on port ${PORT}`);
});