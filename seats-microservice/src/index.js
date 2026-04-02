const express = require("express");
const mysql = require("mysql2");
const cors = require("cors");

const app = express();
app.use(express.json());
app.use(cors());

const PORT = 5003;
const DB_CONFIG = {
    host: process.env.DB_HOST || "seats-db",
    user: process.env.DB_USER || "root",
    password: process.env.DB_PASSWORD || "rootpassword",
    database: process.env.DB_NAME || "seats",
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
};

let db = createPool();

function createPool() {
    return mysql.createPool(DB_CONFIG);
}

function isRecoverableDbError(err) {
    return ['ECONNREFUSED', 'EAI_AGAIN', 'PROTOCOL_CONNECTION_LOST', 'PROTOCOL_ENQUEUE_AFTER_FATAL_ERROR'].includes(err?.code);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function runQuery(query, params = [], retries = 5) {
    for (let attempt = 0; attempt <= retries; attempt += 1) {
        try {
            const [rows] = await db.promise().query(query, params);
            return rows;
        } catch (err) {
            const shouldRetry = isRecoverableDbError(err) && attempt < retries;

            if (!shouldRetry) {
                throw err;
            }

            console.warn(`Seats DB query retry ${attempt + 1}/${retries}: ${err.code}`);

            try {
                await db.end();
            } catch (_) {
                // Ignore pool shutdown errors while rebuilding the connection pool.
            }

            db = createPool();
            await sleep(1500);
        }
    }
}

async function ensureHoldExpiryColumn() {
    try {
        const columns = await runQuery("SHOW COLUMNS FROM seats LIKE 'HoldExpiresAt'");
        if (!Array.isArray(columns) || columns.length === 0) {
            await runQuery("ALTER TABLE seats ADD COLUMN HoldExpiresAt DATETIME NULL");
            console.log("Added seats.HoldExpiresAt column");
        }
    } catch (err) {
        console.warn("Could not ensure HoldExpiresAt column:", err.message);
    }
}

async function releaseExpiredHolds() {
    await runQuery(
        "UPDATE seats SET Status='available', PassengerID=NULL, HoldExpiresAt=NULL WHERE Status='hold' AND HoldExpiresAt IS NOT NULL AND HoldExpiresAt <= UTC_TIMESTAMP()"
    );
}

(async () => {
    try {
        await runQuery("SELECT 1");
        await ensureHoldExpiryColumn();
        console.log("Seats DB connected");
    } catch (err) {
        console.log("Seats DB pool init warning:", err.message);
    }
})();

app.get("/seats/:flightID", async (req, res) => {
    const flightID = req.params.flightID;
    const query = "SELECT * FROM seats WHERE FlightID = ?";

    try {
        await releaseExpiredHolds();
        const result = await runQuery(query, [flightID]);
        res.json(result);
    } catch (err) {
        res.status(503).json({ message: "Seats database unavailable", error: err.code || err.message });
    }
});

app.post("/seats/hold", async (req, res) => {

    const { flightID, seatNumber, passengerID } = req.body;
    const seatArray = String(seatNumber).split(',').map(s => s.trim());
    const placeholders = seatArray.map(() => '?').join(',');

    const checkQuery =
        `SELECT * FROM seats WHERE FlightID=? AND SeatNumber IN (${placeholders}) AND Status='available'`;

    try {
        await releaseExpiredHolds();
        const result = await runQuery(checkQuery, [flightID, ...seatArray]);

        if (result.length < seatArray.length) {
            return res.status(400).json({ message: "One or more seats not available" });
        }

        const holdQuery =
            `UPDATE seats SET Status='hold', PassengerID=?, HoldExpiresAt=DATE_ADD(UTC_TIMESTAMP(), INTERVAL 5 MINUTE) WHERE FlightID=? AND SeatNumber IN (${placeholders})`;

        await runQuery(holdQuery, [passengerID, flightID, ...seatArray]);
        res.json({ message: "Seats placed on hold for 5 minutes" });
    } catch (err) {
        res.status(503).json({ message: "Seats database unavailable", error: err.code || err.message });
    }

});

app.post("/seats/refresh-hold", async (req, res) => {
    const { flightID, seatNumber } = req.body;
    const seatArray = String(seatNumber).split(',').map(s => s.trim()).filter(Boolean);

    if (!flightID || !seatArray.length) {
        return res.status(400).json({ message: "flightID and seatNumber are required" });
    }

    const placeholders = seatArray.map(() => '?').join(',');
    const refreshQuery =
        `UPDATE seats
         SET HoldExpiresAt=DATE_ADD(UTC_TIMESTAMP(), INTERVAL 5 MINUTE)
         WHERE FlightID=? AND SeatNumber IN (${placeholders}) AND Status='hold'`;

    try {
        await releaseExpiredHolds();
        const result = await runQuery(refreshQuery, [flightID, ...seatArray]);

        if (result.affectedRows < seatArray.length) {
            return res.status(409).json({ message: "One or more held seats are no longer reserved" });
        }

        res.json({ message: "Seat hold extended for 5 minutes" });
    } catch (err) {
        res.status(503).json({ message: "Seats database unavailable", error: err.code || err.message });
    }
});

app.post("/seats/confirm", async (req, res) => {

    const { flightID, seatNumber } = req.body;
    const seatArray = String(seatNumber).split(',').map(s => s.trim());
    const placeholders = seatArray.map(() => '?').join(',');

    const query =
        `UPDATE seats SET Status='unavailable', HoldExpiresAt=NULL WHERE FlightID=? AND SeatNumber IN (${placeholders})`;

    try {
        await runQuery(query, [flightID, ...seatArray]);
        res.json({ message: "Seat booking confirmed" });
    } catch (err) {
        res.status(503).json({ message: "Seats database unavailable", error: err.code || err.message });
    }

});

app.post("/seats/release", async (req, res) => {

    const { flightID, seatNumber } = req.body;
    const seatArray = String(seatNumber).split(',').map(s => s.trim());
    const placeholders = seatArray.map(() => '?').join(',');

    const query =
        `UPDATE seats SET Status='available', PassengerID=NULL, HoldExpiresAt=NULL WHERE FlightID=? AND SeatNumber IN (${placeholders})`;

    try {
        await runQuery(query, [flightID, ...seatArray]);
        res.json({ message: "Seats released" });
    } catch (err) {
        res.status(503).json({ message: "Seats database unavailable", error: err.code || err.message });
    }

});


// ==========================================
// PUT /seats/release/:flightID
// Bulk release ALL seats on a cancelled flight
// Called by: Flight Cancellation Composite (Scenario 2 Phase 1)
// Sets all seats for the flight to available and clears PassengerID
// ==========================================
app.put('/seats/release/:flightID', async (req, res) => {

    const flightID = req.params.flightID;

    const query =
        `UPDATE seats SET Status="available", PassengerID=NULL, HoldExpiresAt=NULL WHERE FlightID=?`;

    try {
        const result = await runQuery(query, [flightID]);
        if (result.affectedRows === 0) {
            return res.status(404).json({ message: `No seats found for flight ${flightID}` });
        }

        res.json({
            message: `All seats released for flight ${flightID}`,
            seatsReleased: result.affectedRows
        });
    } catch (err) {
        return res.status(503).json({ message: "Seats database unavailable", error: err.code || err.message });
    }

});


app.get('/seats', async (req, res) => {
    const flightID = req.query.FlightID || req.query.flightID;
    const status = req.query.Status || req.query.status;

    if (!flightID) {
        return res.status(400).json({ message: 'FlightID is required' });
    }

    let query = 'SELECT * FROM seats WHERE FlightID = ?';
    const params = [flightID];

    if (status) {
        query += ' AND Status = ?';
        params.push(String(status).toLowerCase());
    }

    query += ' ORDER BY SeatID ASC';

    try {
        await releaseExpiredHolds();
        const result = await runQuery(query, params);
        res.json(result);
    } catch (err) {
        return res.status(503).json({ message: "Seats database unavailable", error: err.code || err.message });
    }
});

app.put('/seats/:seatID/hold', async (req, res) => {
    const seatID = req.params.seatID;

    const query = 'UPDATE seats SET Status="hold", HoldExpiresAt=DATE_ADD(UTC_TIMESTAMP(), INTERVAL 5 MINUTE) WHERE SeatID=? AND Status="available"';

    try {
        await releaseExpiredHolds();
        const result = await runQuery(query, [seatID]);

        if (result.affectedRows === 0) {
            return res.status(409).json({ message: `Seat ${seatID} is not available for hold` });
        }

        const rows = await runQuery('SELECT SeatID, SeatNumber, Status FROM seats WHERE SeatID=?', [seatID]);
        if (!rows.length) {
            return res.status(404).json({ message: `Seat ${seatID} not found` });
        }

        return res.json({
            SeatID: rows[0].SeatID,
            SeatNumber: rows[0].SeatNumber,
            Status: rows[0].Status.charAt(0).toUpperCase() + rows[0].Status.slice(1)
        });
    } catch (err) {
        return res.status(503).json({ message: "Seats database unavailable", error: err.code || err.message });
    }
});

app.put('/seats/cancel', async (req, res) => {
    const flightID = req.query.FlightID || req.query.flightID;

    if (!flightID) {
        return res.status(400).json({ message: 'FlightID is required' });
    }

    const query = 'UPDATE seats SET Status="cancelled", PassengerID=NULL, HoldExpiresAt=NULL WHERE FlightID=?';

    try {
        const result = await runQuery(query, [flightID]);
        res.json({
            FlightID: Number(flightID),
            SeatsCancelled: result.affectedRows
        });
    } catch (err) {
        return res.status(503).json({ message: "Seats database unavailable", error: err.code || err.message });
    }
});

app.listen(PORT, () => {
    console.log(`Seats service running on port ${PORT}`);
});
