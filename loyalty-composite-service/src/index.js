const express = require('express');
const axios = require('axios');
const cors = require('cors');
const app = express();

app.use(cors());
app.use(express.json());

// Service URLs
const MILES_BALANCE_URL = process.env.MILES_BALANCE_URL || 'http://miles-balance-service:5001';
const MILES_TRANSACTION_URL = process.env.MILES_TRANSACTION_URL || 'http://miles-transaction-service:5002';
const VOUCHER_URL = process.env.VOUCHER_URL || 'http://voucher-service:5005';
const NOTIFICATION_URL = process.env.NOTIFICATION_URL || 'http://notification-service:3004';

// Voucher type definitions (consistent with Voucher Service)
const VOUCHER_TYPES = {
  TRAVEL_CREDIT: {
    name: 'Travel Credit',
    rate: 100,
    minMiles: 500,
    description: 'Convert miles into cash-style credit to reduce the amount paid on flight bookings.',
    calculateValue: (miles) => miles / 100
  },
  IN_FLIGHT_PERKS: {
    name: 'In-flight Perks Voucher',
    rate: 500,
    minMiles: 500,
    benefits: ['Food Credits', 'Entertainment Bundles', 'Wi-Fi Passes'],
    description: 'Redeem for food credits, entertainment bundles, and Wi-Fi passes during your trip.',
    calculateValue: () => 1
  },
  PARTNER_GIFT: {
    name: 'Partner Gift Card',
    rate: 1500,
    minMiles: 1500,
    calculateValue: () => 15
  }
};

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'loyalty-composite-service' });
});

// ==========================================
// GET /api/loyalty/balance/:passengerID
// Get balance with recent activity and active vouchers
// ==========================================
app.get('/api/loyalty/balance/:passengerID', async (req, res) => {
  const { passengerID } = req.params;

  try {
    const [balanceResponse, transactionsResponse, vouchersResponse] = await Promise.all([
      axios.get(`${MILES_BALANCE_URL}/miles-balance/${passengerID}`).catch(() => ({ data: null })),
      axios.get(`${MILES_TRANSACTION_URL}/transactions/${passengerID}?limit=10`).catch(() => ({ data: [] })),
      axios.get(`${VOUCHER_URL}/vouchers/${passengerID}?status=ACTIVE`).catch(() => ({ data: [] }))
    ]);

    res.json({
      passengerID: parseInt(passengerID),
      currentBalance: balanceResponse.data?.currentBalance || 0,
      recentTransactions: transactionsResponse.data || [],
      activeVouchers: vouchersResponse.data || [],
      totalVouchersCount: vouchersResponse.data?.length || 0
    });
  } catch (error) {
    console.error('Error fetching loyalty data:', error.message);
    res.status(500).json({ error: 'Failed to fetch loyalty data', message: error.message });
  }
});

// ==========================================
// POST /api/loyalty/convert
// Convert miles to a single voucher
// ==========================================
app.post('/api/loyalty/convert', async (req, res) => {
  const { passengerID, voucherType, milesToConvert, passengerEmail, passengerName } = req.body;

  // Validation
  if (!passengerID || !voucherType) {
    return res.status(400).json({
      success: false,
      error: 'Missing required fields: passengerID, voucherType'
    });
  }

  const typeConfig = VOUCHER_TYPES[voucherType];
  if (!typeConfig) {
    return res.status(400).json({
      success: false,
      error: `Invalid voucher type. Valid types: ${Object.keys(VOUCHER_TYPES).join(', ')}`
    });
  }

  let transactionID = null;

  try {
    // Step 1: Check current balance
    const balanceResponse = await axios.get(`${MILES_BALANCE_URL}/miles-balance/${passengerID}`);
    const currentBalance = balanceResponse.data.currentBalance;

    // Determine miles needed
    let milesNeeded;
    if (voucherType === 'TRAVEL_CREDIT') {
      if (!milesToConvert || milesToConvert <= 0) {
        return res.status(400).json({
          success: false,
          error: 'milesToConvert required for TRAVEL_CREDIT',
          minRequired: typeConfig.minMiles
        });
      }
      if (milesToConvert < typeConfig.minMiles) {
        return res.status(400).json({
          success: false,
          error: `Minimum ${typeConfig.minMiles} miles required for ${voucherType}`,
          currentMiles: currentBalance,
          requiredMiles: typeConfig.minMiles,
          shortfall: typeConfig.minMiles - currentBalance
        });
      }
      milesNeeded = milesToConvert;
    } else {
      milesNeeded = typeConfig.rate;
      if (currentBalance < milesNeeded) {
        return res.status(400).json({
          success: false,
          error: `Insufficient miles. Need ${milesNeeded} miles for ${voucherType}`,
          currentMiles: currentBalance,
          requiredMiles: milesNeeded,
          shortfall: milesNeeded - currentBalance
        });
      }
    }

    // Step 2: Deduct miles
    await axios.put(`${MILES_BALANCE_URL}/miles-balance/${passengerID}/deduct`, {
      amount: milesNeeded
    });

    // Step 3: Log transaction
    const transactionResponse = await axios.post(`${MILES_TRANSACTION_URL}/transactions`, {
      passengerID,
      milesDelta: -milesNeeded,
      transactionType: 'REDEEMED',
      description: `Converted ${milesNeeded} miles to ${voucherType}`,
      voucherType
    });
    transactionID = transactionResponse.data.transactionID;

    // Step 4: Generate voucher
    const voucherValue = typeConfig.calculateValue(milesNeeded);
    const voucherResponse = await axios.post(`${VOUCHER_URL}/vouchers`, {
      passengerID,
      voucherType,
      milesRedeemed: milesNeeded,
      voucherValue,
      passengerEmail,
      passengerName
    });

    const voucher = voucherResponse.data;

    // Step 5: Update transaction with voucher reference
    await axios.put(`${MILES_TRANSACTION_URL}/transactions/${transactionID}/reference`, {
      referenceID: voucher.voucherCode
    });

    // Step 6: Get new balance
    const newBalanceResponse = await axios.get(`${MILES_BALANCE_URL}/miles-balance/${passengerID}`);
    const newBalance = newBalanceResponse.data.currentBalance;

    // Step 7: Send notification (async, don't fail if it errors)
    try {
      await axios.post(`${NOTIFICATION_URL}/notifications/voucher`, {
        passengerID,
        passengerEmail,
        passengerName,
        voucherCode: voucher.voucherCode,
        voucherValue: voucher.voucherValue,
        voucherType,
        expiryDate: voucher.expiryDate,
        milesRedeemed: milesNeeded,
        remainingMiles: newBalance,
        providerName: voucher.providerName,
        externalOrderId: voucher.externalOrderId,
        redemptionUrl: voucher.redemptionUrl
      });
    } catch (emailError) {
      console.warn('Email notification failed, but voucher was created:', emailError.message);
    }

    // Calculate next voucher suggestion
    const nextVoucherSuggestion = calculateNextVoucherSuggestion(newBalance);

    // Return success response
    return res.status(200).json({
      success: true,
      message: `${voucherType} voucher generated successfully`,
      voucher: {
        code: voucher.voucherCode,
        type: voucherType,
        value: voucher.voucherValue,
        expiryDate: voucher.expiryDate,
        providerName: voucher.providerName,
        externalOrderId: voucher.externalOrderId,
        redemptionUrl: voucher.redemptionUrl
      },
      milesRedeemed: milesNeeded,
      remainingMiles: newBalance,
      nextVoucherSuggestion
    });

  } catch (error) {
    console.error('Error in conversion flow:', error.response?.data || error.message);

    // Compensating transaction: Rollback if voucher failed
    if (transactionID && error.response?.status !== 400) {
      try {
        // Restore miles
        await axios.put(`${MILES_BALANCE_URL}/miles-balance/${passengerID}/add`, {
          amount: voucherType === 'TRAVEL_CREDIT' ? milesToConvert : VOUCHER_TYPES[voucherType].rate
        });

        // Log rollback transaction
        await axios.post(`${MILES_TRANSACTION_URL}/transactions`, {
          passengerID,
          milesDelta: milesToConvert || VOUCHER_TYPES[voucherType].rate,
          transactionType: 'ROLLBACK',
          description: `Rollback of failed ${voucherType} conversion`,
          originalTransactionID: transactionID
        });

        const restoredBalance = await axios.get(`${MILES_BALANCE_URL}/miles-balance/${passengerID}`);

        return res.status(500).json({
          success: false,
          error: 'Voucher generation failed. Miles have been restored.',
          milesRestored: milesToConvert || VOUCHER_TYPES[voucherType].rate,
          remainingMiles: restoredBalance.data.currentBalance
        });
      } catch (rollbackError) {
        console.error('Rollback failed:', rollbackError.message);
        return res.status(500).json({
          success: false,
          error: 'Critical failure: Miles deducted but voucher failed. Manual intervention required.'
        });
      }
    }

    return res.status(500).json({
      success: false,
      error: error.response?.data?.error || error.message
    });
  }
});

// ==========================================
// POST /api/loyalty/convert-bundle
// Convert multiple vouchers in one transaction
// ==========================================
app.post('/api/loyalty/convert-bundle', async (req, res) => {
  const { passengerID, items, passengerEmail, passengerName } = req.body;

  if (!passengerID || !items || !Array.isArray(items) || items.length === 0) {
    return res.status(400).json({
      success: false,
      error: 'Missing required fields: passengerID and items array'
    });
  }

  let totalMilesNeeded = 0;
  const itemDetails = [];

  // Validate all items first
  for (const item of items) {
    const typeConfig = VOUCHER_TYPES[item.voucherType];
    if (!typeConfig) {
      return res.status(400).json({
        success: false,
        error: `Invalid voucher type: ${item.voucherType}`
      });
    }

    let milesNeeded;
    if (item.voucherType === 'TRAVEL_CREDIT') {
      if (!item.milesToConvert || item.milesToConvert < typeConfig.minMiles) {
        return res.status(400).json({
          success: false,
          error: `Minimum ${typeConfig.minMiles} miles required for TRAVEL_CREDIT`
        });
      }
      milesNeeded = item.milesToConvert;
    } else {
      milesNeeded = typeConfig.rate;
    }

    totalMilesNeeded += milesNeeded;
    itemDetails.push({
      ...item,
      milesNeeded,
      typeConfig
    });
  }

  let transactionID = null;

  try {
    // Step 1: Check balance
    const balanceResponse = await axios.get(`${MILES_BALANCE_URL}/miles-balance/${passengerID}`);
    const currentBalance = balanceResponse.data.currentBalance;

    if (currentBalance < totalMilesNeeded) {
      return res.status(400).json({
        success: false,
        error: 'Insufficient miles for bundle',
        currentMiles: currentBalance,
        requiredMiles: totalMilesNeeded,
        shortfall: totalMilesNeeded - currentBalance
      });
    }

    // Step 2: Deduct miles
    await axios.put(`${MILES_BALANCE_URL}/miles-balance/${passengerID}/deduct`, {
      amount: totalMilesNeeded
    });

    // Step 3: Log bundle transaction
    const transactionResponse = await axios.post(`${MILES_TRANSACTION_URL}/transactions`, {
      passengerID,
      milesDelta: -totalMilesNeeded,
      transactionType: 'REDEEMED',
      description: `Converted bundle: ${items.map(i => i.voucherType).join(', ')}`
    });
    transactionID = transactionResponse.data.transactionID;

    // Step 4: Generate all vouchers via bundle endpoint
    const voucherBundleResponse = await axios.post(`${VOUCHER_URL}/vouchers/bundle`, {
      passengerID,
      passengerEmail,
      passengerName,
      items: itemDetails.map(item => ({
        voucherType: item.voucherType,
        milesRedeemed: item.milesNeeded
      }))
    });

    const vouchers = voucherBundleResponse.data.vouchers;

    // Step 5: Update transaction with references
    const referenceIDs = vouchers.map(v => v.voucherCode).join(',');
    await axios.put(`${MILES_TRANSACTION_URL}/transactions/${transactionID}/reference`, {
      referenceID: referenceIDs
    });

    // Step 6: Get new balance
    const newBalanceResponse = await axios.get(`${MILES_BALANCE_URL}/miles-balance/${passengerID}`);
    const newBalance = newBalanceResponse.data.currentBalance;

    // Step 7: Send notification (async)
    try {
      await axios.post(`${NOTIFICATION_URL}/notifications/voucher-bundle`, {
        passengerID,
        passengerEmail,
        passengerName,
        vouchers,
        totalMilesRedeemed: totalMilesNeeded,
        remainingMiles: newBalance
      });
    } catch (emailError) {
      console.warn('Email notification failed:', emailError.message);
    }

    return res.status(200).json({
      success: true,
      message: 'Bundle converted successfully',
      vouchers,
      totalMilesRedeemed: totalMilesNeeded,
      remainingMiles: newBalance
    });

  } catch (error) {
    console.error('Error in bundle conversion:', error.response?.data || error.message);

    // Rollback if needed
    if (transactionID) {
      try {
        await axios.put(`${MILES_BALANCE_URL}/miles-balance/${passengerID}/add`, {
          amount: totalMilesNeeded
        });

        await axios.post(`${MILES_TRANSACTION_URL}/transactions`, {
          passengerID,
          milesDelta: totalMilesNeeded,
          transactionType: 'ROLLBACK',
          description: 'Rollback of failed bundle conversion',
          originalTransactionID: transactionID
        });
      } catch (rollbackError) {
        console.error('Rollback failed:', rollbackError.message);
      }
    }

    return res.status(500).json({
      success: false,
      error: error.response?.data?.error || error.message
    });
  }
});

// ==========================================
// GET /api/loyalty/vouchers/:passengerID
// Get all vouchers for a passenger
// ==========================================
app.get('/api/loyalty/vouchers/:passengerID', async (req, res) => {
  const { passengerID } = req.params;
  const { status } = req.query;

  try {
    let url = `${VOUCHER_URL}/vouchers/${passengerID}`;
    if (status) {
      url += `?status=${status}`;
    }
    const response = await axios.get(url);
    res.json(response.data);
  } catch (error) {
    console.error('Error fetching vouchers:', error.message);
    res.status(500).json({ error: 'Failed to fetch vouchers', message: error.message });
  }
});

// Helper: Calculate next voucher suggestion based on remaining miles
function calculateNextVoucherSuggestion(remainingMiles) {
  const suggestions = [];

  if (remainingMiles >= VOUCHER_TYPES.IN_FLIGHT_PERKS.minMiles) {
    suggestions.push({
      type: 'IN_FLIGHT_PERKS',
      name: 'In-flight Perks Voucher',
      milesNeeded: VOUCHER_TYPES.IN_FLIGHT_PERKS.rate,
      currentProgress: `${remainingMiles}/${VOUCHER_TYPES.IN_FLIGHT_PERKS.rate}`,
      eligible: remainingMiles >= VOUCHER_TYPES.IN_FLIGHT_PERKS.rate
    });
  }

  if (remainingMiles >= VOUCHER_TYPES.TRAVEL_CREDIT.minMiles) {
    const potentialValue = VOUCHER_TYPES.TRAVEL_CREDIT.calculateValue(remainingMiles);
    suggestions.push({
      type: 'TRAVEL_CREDIT',
      name: 'Travel Credit',
      milesNeeded: remainingMiles,
      potentialValue: potentialValue.toFixed(2),
      eligible: true
    });
  }

  return suggestions.length > 0 ? suggestions[0] : null;
}

const PORT = process.env.PORT || 5008;
app.listen(PORT, () => {
  console.log(`Loyalty Composite Service running on port ${PORT}`);
});