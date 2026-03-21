const express = require("express");
const mysql = require("mysql2");
const cors = require("cors");

const app = express();
app.use(express.json());
app.use(cors());

const PORT = 5003;

const dbHost = process.env.DB_HOST || 'seats-db';
const dbUser = process.env.DB_USER || 'root';
const dbName = process.env.DB_NAME || 'seats';

const candidatePasswords = [
    process.env.DB_PASSWORD,
    'rootpassword',
    'root'
].filter((pwd, index, arr) => pwd && arr.indexOf(pwd) === index);

let db = null;

function connectWithFallback(passwordIndex = 0) {
    if (passwordIndex >= candidatePasswords.length) {
        console.log('DB connection failed: exhausted password fallbacks');
        return;
    }

    const password = candidatePasswords[passwordIndex];

    db = mysql.createConnection({
        host: dbHost,
        user: dbUser,
        password,
        database: dbName
    });

    db.connect(err => {
        if (err) {
            console.log(`DB connection failed with configured password #${passwordIndex + 1}:`, err.message);
            connectWithFallback(passwordIndex + 1);
        } else {
            console.log('Seats DB connected');
        }
    });
}

connectWithFallback();

app.get("/seats/:flightID", (req, res) => {

    const flightID = req.params.flightID;

    const query = "SELECT * FROM seats WHERE FlightID = ?";

    db.query(query, [flightID], (err, result) => {
        if (err) {
            res.status(500).send(err);
        } else {
            res.json(result);
        }
    });

});

app.post("/seats/hold", (req, res) => {

    const { flightID, seatNumber, passengerID } = req.body;

    const checkQuery =
        "SELECT * FROM seats WHERE FlightID=? AND SeatNumber=? AND Status='available'";

    db.query(checkQuery, [flightID, seatNumber], (err, result) => {

        if (result.length === 0) {
            return res.status(400).json({ message: "Seat not available" });
        }

        const holdQuery =
            "UPDATE seats SET Status='hold', PassengerID=? WHERE FlightID=? AND SeatNumber=?";

        db.query(holdQuery, [passengerID, flightID, seatNumber], err => {

            if (err) {
                res.status(500).send(err);
            } else {
                res.json({ message: "Seat placed on hold" });
            }

        });

    });

});

app.post("/seats/confirm", (req, res) => {

    const { flightID, seatNumber } = req.body;

    const query =
        "UPDATE seats SET Status='unavailable' WHERE FlightID=? AND SeatNumber=?";

    db.query(query, [flightID, seatNumber], err => {

        if (err) {
            res.status(500).send(err);
        } else {
            res.json({ message: "Seat booking confirmed" });
        }

    });

});

app.post("/seats/release", (req, res) => {

    const { flightID, seatNumber } = req.body;

    const query =
        "UPDATE seats SET Status='available', PassengerID=NULL WHERE FlightID=? AND SeatNumber=?";

    db.query(query, [flightID, seatNumber], err => {

        if (err) {
            res.status(500).send(err);
        } else {
            res.json({ message: "Seat released" });
        }

    });

});


// ==========================================
// PUT /seats/release/:flightID
// Bulk release ALL seats on a cancelled flight
// Called by: Flight Cancellation Composite (Scenario 2 Phase 1)
// Sets all seats for the flight to available and clears PassengerID
// ==========================================
app.put('/seats/release/:flightID', (req, res) => {

    const flightID = req.params.flightID;

    const query =
        `UPDATE seats SET Status="available", PassengerID=NULL WHERE FlightID=?`;

    db.query(query, [flightID], (err, result) => {

        if (err) {
            return res.status(500).json({ error: err.message });
        }

        if (result.affectedRows === 0) {
            return res.status(404).json({ message: `No seats found for flight ${flightID}` });
        }

        res.json({
            message: `All seats released for flight ${flightID}`,
            seatsReleased: result.affectedRows
        });

    });

});


app.listen(PORT, () => {
    console.log(`Seats service running on port ${PORT}`);
});

app.get('/seats', (req, res) => {

    const flightID = req.query.FlightID || req.query.flightID;

    if (!flightID) {
        return res.status(400).json({ message: 'FlightID query parameter is required' });
    }

    const query = 'SELECT * FROM seats WHERE FlightID = ?';

    db.query(query, [flightID], (err, result) => {
        if (err) {
            return res.status(500).send(err);
        }
        res.json(result);
    });

});

app.put('/seats/:seatID/hold', (req, res) => {

    const { seatID } = req.params;

    const updateQuery =
        "UPDATE seats SET Status='hold' WHERE SeatID=? AND Status='available'";

    db.query(updateQuery, [seatID], (err, result) => {
        if (err) {
            return res.status(500).send(err);
        }

        if (result.affectedRows === 0) {
            return res.status(400).json({ message: 'Seat not available' });
        }

        const getQuery = 'SELECT SeatID, Status FROM seats WHERE SeatID=?';
        db.query(getQuery, [seatID], (fetchErr, rows) => {
            if (fetchErr) {
                return res.status(500).send(fetchErr);
            }
            res.json(rows[0]);
        });
    });

});

app.put('/seats/:seatID/book', (req, res) => {

    const { seatID } = req.params;
    const { PassengerID, passengerID } = req.body || {};
    const passengerIdToSet = PassengerID ?? passengerID ?? null;

    const query =
        "UPDATE seats SET Status='unavailable', PassengerID=? WHERE SeatID=? AND Status='hold'";

    db.query(query, [passengerIdToSet, seatID], (err, result) => {
        if (err) {
            return res.status(500).send(err);
        }

        if (result.affectedRows === 0) {
            return res.status(400).json({ message: 'Seat is not on hold' });
        }

        res.json({ SeatID: Number(seatID), Status: 'unavailable' });
    });

});