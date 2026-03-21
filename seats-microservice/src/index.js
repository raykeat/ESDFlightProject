const express = require("express");
const mysql = require("mysql2");
const cors = require("cors");

const app = express();
app.use(express.json());
app.use(cors());

const PORT = 5003;

const db = mysql.createConnection({
    host:     process.env.DB_HOST     || "seats-db",
    user:     process.env.DB_USER     || "root",
    password: process.env.DB_PASSWORD || "rootpassword",
    database: process.env.DB_NAME     || "seats"
});

db.connect(err => {
    if (err) {
        console.log("DB connection failed:", err);
    } else {
        console.log("Seats DB connected");
    }
});

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
    const seatArray = String(seatNumber).split(',').map(s => s.trim());
    const placeholders = seatArray.map(() => '?').join(',');

    const checkQuery =
        `SELECT * FROM seats WHERE FlightID=? AND SeatNumber IN (${placeholders}) AND Status='available'`;

    db.query(checkQuery, [flightID, ...seatArray], (err, result) => {

        if (err) {
            return res.status(500).send(err);
        }

        if (result.length < seatArray.length) {
            return res.status(400).json({ message: "One or more seats not available" });
        }

        const holdQuery =
            `UPDATE seats SET Status='hold', PassengerID=? WHERE FlightID=? AND SeatNumber IN (${placeholders})`;

        db.query(holdQuery, [passengerID, flightID, ...seatArray], err => {

            if (err) {
                res.status(500).send(err);
            } else {
                res.json({ message: "Seats placed on hold" });
            }

        });

    });

});

app.post("/seats/confirm", (req, res) => {

    const { flightID, seatNumber } = req.body;
    const seatArray = String(seatNumber).split(',').map(s => s.trim());
    const placeholders = seatArray.map(() => '?').join(',');

    const query =
        `UPDATE seats SET Status='unavailable' WHERE FlightID=? AND SeatNumber IN (${placeholders})`;

    db.query(query, [flightID, ...seatArray], err => {

        if (err) {
            res.status(500).send(err);
        } else {
            res.json({ message: "Seat booking confirmed" });
        }

    });

});

app.post("/seats/release", (req, res) => {

    const { flightID, seatNumber } = req.body;
    const seatArray = String(seatNumber).split(',').map(s => s.trim());
    const placeholders = seatArray.map(() => '?').join(',');

    const query =
        `UPDATE seats SET Status='available', PassengerID=NULL WHERE FlightID=? AND SeatNumber IN (${placeholders})`;

    db.query(query, [flightID, ...seatArray], err => {

        if (err) {
            res.status(500).send(err);
        } else {
            res.json({ message: "Seats released" });
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