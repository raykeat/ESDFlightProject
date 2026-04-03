const express = require('express');
const axios = require('axios');
const cors = require('cors');

const app = express();

app.use(cors());
app.use(express.json());

const PORT = parseInt(process.env.PORT || '5009', 10);
const DEFAULT_MILES_PER_DOLLAR = parseFloat(process.env.MILES_PER_DOLLAR || '1');

const MILES_BALANCE_URL = process.env.MILES_BALANCE_URL || 'http://miles-balance-service:5006';
const MILES_TRANSACTION_URL = process.env.MILES_TRANSACTION_URL || 'http://miles-transaction-service:5007';

function toPositiveNumber(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'miles-earn-service' });
});

// POST /miles/earn
// Body:
// {
//   "passengerID": 123,
//   "flightCost": 399.99,
//   "bookingReference": "BK-00001",
//   "currency": "USD",
//   "milesPerDollar": 1
// }
app.post('/miles/earn', async (req, res) => {
  const {
    passengerID,
    flightCost,
    bookingReference = null,
    currency = 'USD',
    milesPerDollar = DEFAULT_MILES_PER_DOLLAR
  } = req.body;

  const passengerIdInt = parseInt(passengerID, 10);
  const cost = toPositiveNumber(flightCost);
  const rate = toPositiveNumber(milesPerDollar);

  if (!Number.isInteger(passengerIdInt) || passengerIdInt <= 0) {
    return res.status(400).json({ error: 'passengerID must be a positive integer' });
  }

  if (cost === null) {
    return res.status(400).json({ error: 'flightCost must be a positive number' });
  }

  if (rate === null) {
    return res.status(400).json({ error: 'milesPerDollar must be a positive number' });
  }

  const earnedMiles = Math.floor(cost * rate);
  if (earnedMiles <= 0) {
    return res.status(400).json({
      error: 'Calculated miles is 0. Increase flightCost or milesPerDollar.'
    });
  }

  try {
    // Ensure passenger row exists without applying welcome bonus in this flow.
    await axios.post(`${MILES_BALANCE_URL}/miles-balance/${passengerIdInt}/initialize`, {
      welcomeBonus: 0
    });

    const addBalanceResponse = await axios.put(
      `${MILES_BALANCE_URL}/miles-balance/${passengerIdInt}/add`,
      { amount: earnedMiles }
    );

    const description = `Earned ${earnedMiles} miles from flight spend ${cost.toFixed(2)} ${currency}`;

    const transactionResponse = await axios.post(`${MILES_TRANSACTION_URL}/transactions`, {
      passengerID: passengerIdInt,
      milesDelta: earnedMiles,
      transactionType: 'EARNED',
      description,
      referenceID: bookingReference
    });

    return res.status(201).json({
      success: true,
      passengerID: passengerIdInt,
      flightCost: cost,
      currency,
      milesPerDollar: rate,
      earnedMiles,
      bookingReference,
      transactionID: transactionResponse.data.transactionID,
      newBalance: addBalanceResponse.data.newBalance
    });
  } catch (error) {
    console.error('Failed to award miles:', error.response?.data || error.message);
    return res.status(500).json({
      success: false,
      error: 'Failed to award miles',
      details: error.response?.data || error.message
    });
  }
});

app.listen(PORT, () => {
  console.log(`Miles Earn Service running on port ${PORT}`);
});
