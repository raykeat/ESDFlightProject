const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');
const crypto = require('crypto');
const axios = require('axios');
const app = express();

app.use(cors());
app.use(express.json());

const db = mysql.createPool({
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || 'rootpassword',
  database: process.env.DB_NAME || 'voucher_db',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

const EXTERNAL_VOUCHER_MODE = process.env.EXTERNAL_VOUCHER_MODE || 'tremendous';
const TREMENDOUS_API_URL = process.env.TREMENDOUS_API_URL || 'https://testflight.tremendous.com/api/v2';
const TREMENDOUS_API_KEY = process.env.TREMENDOUS_API_KEY || '';
const TREMENDOUS_CAMPAIGN_ID = process.env.TREMENDOUS_CAMPAIGN_ID || '';
const TREMENDOUS_FUNDING_SOURCE_ID = process.env.TREMENDOUS_FUNDING_SOURCE_ID || '';
const DERIVED_STATUS_SQL = `CASE WHEN usedAt IS NOT NULL THEN 'USED' WHEN expiryDate < CURDATE() THEN 'EXPIRED' ELSE 'ACTIVE' END`;

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
    minMiles: 500,
    expiryDays: 365,
    description: 'Convert miles into cash-style credit to reduce the amount paid on flight bookings.',
    calculateValue: (miles) => miles / 100
  },
  IN_FLIGHT_PERKS: {
    name: 'In-flight Perks Voucher',
    rate: 500,  // 500 miles per pass
    minMiles: 500,
    expiryDays: 90,
    benefits: ['Food Credits', 'Entertainment Bundles', 'Wi-Fi Passes'],
    description: 'Redeem for food credits, entertainment bundles, and Wi-Fi passes during your trip.',
    calculateValue: () => 1  // 1 pass
  },
  PARTNER_GIFT: {
    name: 'Partner Gift Card',
    rate: 1500,
    minMiles: 1500,
    expiryDays: 365,
    provider: 'tremendous',
    providerProduct: 'partner-gift-sandbox',
    description: 'External partner e-gift voucher via provider integration',
    calculateValue: () => 15
  }
};

function ensureSchema() {
  const addColumnStatements = [
    'ALTER TABLE vouchers ADD COLUMN providerName VARCHAR(50) NULL',
    'ALTER TABLE vouchers ADD COLUMN providerProductId VARCHAR(100) NULL',
    'ALTER TABLE vouchers ADD COLUMN externalOrderId VARCHAR(100) NULL',
    'ALTER TABLE vouchers ADD COLUMN redemptionUrl VARCHAR(500) NULL'
  ];

  addColumnStatements.forEach((sql) => {
    db.query(sql, (err) => {
      if (!err) return;
      // ER_DUP_FIELDNAME = 1060 (column already exists), ignore this case
      if (err.errno !== 1060) {
        console.error('Schema migration warning:', err.message);
      }
    });
  });

  console.log('Voucher schema migration check complete');
}

async function createPartnerReward({ passengerID, voucherType, voucherValue, passengerEmail, passengerName }) {
  if (EXTERNAL_VOUCHER_MODE === 'mock') {
    const mockOrderId = `MOCK-${Date.now()}-${passengerID}`;
    return {
      providerName: 'tremendous-mock',
      providerProductId: VOUCHER_TYPES[voucherType]?.providerProduct || 'partner-gift-sandbox',
      externalOrderId: mockOrderId,
      redemptionUrl: `https://sandbox.rewards.example/redeem/${mockOrderId}`
    };
  }

  if (EXTERNAL_VOUCHER_MODE !== 'tremendous') {
    throw new Error(`Unsupported EXTERNAL_VOUCHER_MODE: ${EXTERNAL_VOUCHER_MODE}`);
  }

  if (!TREMENDOUS_API_KEY) {
    throw new Error('TREMENDOUS_API_KEY is required when EXTERNAL_VOUCHER_MODE=tremendous');
  }

  if (!TREMENDOUS_CAMPAIGN_ID) {
    throw new Error('TREMENDOUS_CAMPAIGN_ID is required when EXTERNAL_VOUCHER_MODE=tremendous');
  }

  if (!TREMENDOUS_FUNDING_SOURCE_ID) {
    throw new Error('TREMENDOUS_FUNDING_SOURCE_ID is required when EXTERNAL_VOUCHER_MODE=tremendous');
  }

  try {
    const payload = {
      payment: { funding_source_id: TREMENDOUS_FUNDING_SOURCE_ID },
      rewards: [
        {
          campaign_id: TREMENDOUS_CAMPAIGN_ID,
          value: { denomination: voucherValue, currency_code: 'USD' },
          delivery: { method: 'LINK' },
          recipient: {
            name: passengerName,
            email: passengerEmail
          }
        }
      ]
    };

    const response = await axios.post(`${TREMENDOUS_API_URL}/orders`, payload, {
      headers: {
        Authorization: `Bearer ${TREMENDOUS_API_KEY}`,
        'Content-Type': 'application/json'
      },
      timeout: 10000
    });

    const order = response.data?.order || response.data || {};
    const reward = order?.rewards?.[0] || {};
    const redemptionLink = reward?.delivery?.link || reward?.reward_url || reward?.claim_url || '';

    return {
      providerName: 'tremendous',
      providerProductId: TREMENDOUS_CAMPAIGN_ID,
      externalOrderId: order.id || order.order_id || '',
      redemptionUrl: redemptionLink
    };
  } catch (error) {
    const providerBody = error.response?.data;
    const details = providerBody ? JSON.stringify(providerBody) : error.message;
    throw new Error(`External provider create reward failed: ${details}`);
  }
}

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
    expiryDays: value.expiryDays,
    description: value.description || ''
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
    expiryDays: voucherType.expiryDays,
    description: voucherType.description || ''
  });
});

// POST /vouchers - Generate new voucher
app.post('/vouchers', async (req, res) => {
  const { passengerID, voucherType, milesRedeemed, voucherValue, passengerEmail, passengerName } = req.body;

  if (!passengerID || !voucherType || !milesRedeemed) {
    return res.status(400).json({ error: 'Missing required fields: passengerID, voucherType, milesRedeemed' });
  }

  const typeConfig = VOUCHER_TYPES[voucherType];
  if (!typeConfig) {
    return res.status(400).json({ error: 'Invalid voucher type' });
  }

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

  let external = {
    providerName: null,
    providerProductId: null,
    externalOrderId: null,
    redemptionUrl: null
  };

  try {
    if (voucherType === 'PARTNER_GIFT') {
      external = await createPartnerReward({
        passengerID,
        voucherType,
        voucherValue: finalValue,
        passengerEmail,
        passengerName
      });
    }
  } catch (providerError) {
    return res.status(502).json({ error: providerError.message });
  }

  db.query(
    `INSERT INTO vouchers (
      passengerID, voucherCode, voucherType, voucherValue, milesRedeemed, expiryDate,
      providerName, providerProductId, externalOrderId, redemptionUrl
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      passengerID,
      voucherCode,
      voucherType,
      finalValue,
      milesRedeemed,
      expiryDate.toISOString().split('T')[0],
      external.providerName,
      external.providerProductId,
      external.externalOrderId,
      external.redemptionUrl
    ],
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
        status: 'ACTIVE',
        providerName: external.providerName,
        providerProductId: external.providerProductId,
        externalOrderId: external.externalOrderId,
        redemptionUrl: external.redemptionUrl
      });
    }
  );
});

// POST /vouchers/bundle - Generate multiple vouchers in one call
app.post('/vouchers/bundle', async (req, res) => {
  const { passengerID, items, passengerEmail, passengerName } = req.body;

  if (!passengerID || !items || !Array.isArray(items) || items.length === 0) {
    return res.status(400).json({ error: 'Missing required fields: passengerID, items array' });
  }

  const results = [];
  const errors = [];

  // Process each item sequentially
  const processItem = async (index, callback) => {
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

    let external = {
      providerName: null,
      providerProductId: null,
      externalOrderId: null,
      redemptionUrl: null
    };

    try {
      if (item.voucherType === 'PARTNER_GIFT') {
        external = await createPartnerReward({
          passengerID,
          voucherType: item.voucherType,
          voucherValue,
          passengerEmail,
          passengerName
        });
      }
    } catch (providerError) {
      errors.push({ item, error: providerError.message });
      return processItem(index + 1, callback);
    }

    db.query(
      `INSERT INTO vouchers (
          passengerID, voucherCode, voucherType, voucherValue, milesRedeemed, expiryDate,
        providerName, providerProductId, externalOrderId, redemptionUrl
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        passengerID,
        voucherCode,
        item.voucherType,
        voucherValue,
        item.milesRedeemed,
        expiryDate.toISOString().split('T')[0],
        external.providerName,
        external.providerProductId,
        external.externalOrderId,
        external.redemptionUrl
      ],
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
            expiryDate: expiryDate.toISOString().split('T')[0],
            providerName: external.providerName,
            providerProductId: external.providerProductId,
            externalOrderId: external.externalOrderId,
            redemptionUrl: external.redemptionUrl
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

  let query = `SELECT *, ${DERIVED_STATUS_SQL} AS derivedStatus FROM vouchers WHERE passengerID = ?`;
  const params = [passengerID];

  if (status) {
    const normalizedStatus = String(status).trim().toUpperCase();
    if (normalizedStatus === 'ACTIVE') {
      query += ' AND usedAt IS NULL AND expiryDate >= CURDATE()';
    } else if (normalizedStatus === 'USED') {
      query += ' AND usedAt IS NOT NULL';
    } else if (normalizedStatus === 'EXPIRED') {
      query += ' AND usedAt IS NULL AND expiryDate < CURDATE()';
    } else {
      return res.status(400).json({ error: 'Invalid status filter. Use ACTIVE, USED, or EXPIRED.' });
    }
  }

  query += ' ORDER BY createdAt DESC';

  db.query(query, params, (err, results) => {
    if (err) {
      console.error(err);
      return res.status(500).json({ error: err.message });
    }
    const normalizedResults = results.map((row) => ({
      ...row,
      status: row.derivedStatus
    }));
    res.json(normalizedResults);
  });
});

// GET /vouchers/code/:voucherCode - Get voucher by code
app.get('/vouchers/code/:voucherCode', (req, res) => {
  const { voucherCode } = req.params;

  db.query(
    `SELECT *, ${DERIVED_STATUS_SQL} AS derivedStatus FROM vouchers WHERE voucherCode = ?`,
    [voucherCode],
    (err, results) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (results.length === 0) {
        return res.status(404).json({ error: 'Voucher not found' });
      }
      res.json({
        ...results[0],
        status: results[0].derivedStatus
      });
    }
  );
});

// PUT /vouchers/:voucherID/redeem - Mark voucher as used
app.put('/vouchers/:voucherID/redeem', (req, res) => {
  const { voucherID } = req.params;
  const { bookingID } = req.body;

  db.query(
    'UPDATE vouchers SET usedAt = NOW(), usedBookingID = ? WHERE voucherID = ? AND usedAt IS NULL AND expiryDate >= CURDATE()',
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

  if (!status) {
    return res.status(400).json({ error: 'Missing required field: status' });
  }

  if (String(status).trim().toUpperCase() !== 'ACTIVE') {
    return res.status(400).json({ error: 'Only ACTIVE restore is supported' });
  }

  db.query(
    'UPDATE vouchers SET usedAt = NULL, usedBookingID = NULL WHERE voucherID = ? AND expiryDate >= CURDATE()',
    [voucherID],
    (err, result) => {
      if (err) {
        console.error(err);
        return res.status(500).json({ error: err.message });
      }
      if (result.affectedRows === 0) {
        return res.status(409).json({ error: 'Voucher cannot be restored (not found or expired)' });
      }
      res.json({ success: true, message: 'Voucher restored to ACTIVE state' });
    }
  );
});

const PORT = process.env.PORT || 5005;
app.listen(PORT, () => {
  ensureSchema();
  console.log(`External voucher mode: ${EXTERNAL_VOUCHER_MODE}`);
  console.log(`Voucher Service running on port ${PORT}`);
});