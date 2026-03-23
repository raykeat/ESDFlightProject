const express = require("express");
const mysql = require("mysql2");
const cors = require("cors");

const app = express();
app.use(express.json());
app.use(cors());

const PORT = 5003;

const db = mysql.createPool({
    host:     process.env.DB_HOST     || "seats-db",
    user:     process.env.DB_USER     || "root",
    password: process.env.DB_PASSWORD || "rootpassword",
    database: process.env.DB_NAME     || "seats",
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
});

db.getConnection((err, connection) => {
    if (err) {
        console.log("Seats DB pool init warning:", err.message);
    } else {
        console.log("Seats DB connected");
        connection.release();
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


app.get('/seats', (req, res) => {
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

    db.query(query, params, (err, result) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }
        res.json(result);
    });
});

app.put('/seats/:seatID/hold', (req, res) => {
    const seatID = req.params.seatID;

    const query = 'UPDATE seats SET Status="hold" WHERE SeatID=? AND Status="available"';

    db.query(query, [seatID], (err, result) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }

        if (result.affectedRows === 0) {
            return res.status(409).json({ message: `Seat ${seatID} is not available for hold` });
        }

        db.query('SELECT SeatID, SeatNumber, Status FROM seats WHERE SeatID=?', [seatID], (selectErr, rows) => {
            if (selectErr) {
                return res.status(500).json({ error: selectErr.message });
            }
            if (!rows.length) {
                return res.status(404).json({ message: `Seat ${seatID} not found` });
            }

            return res.json({
                SeatID: rows[0].SeatID,
                SeatNumber: rows[0].SeatNumber,
                Status: rows[0].Status.charAt(0).toUpperCase() + rows[0].Status.slice(1)
            });
        });
    });
});

app.put('/seats/cancel', (req, res) => {
    const flightID = req.query.FlightID || req.query.flightID;

    if (!flightID) {
        return res.status(400).json({ message: 'FlightID is required' });
    }

    const query = 'UPDATE seats SET Status="cancelled", PassengerID=NULL WHERE FlightID=?';

    db.query(query, [flightID], (err, result) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }

        res.json({
            FlightID: Number(flightID),
            SeatsCancelled: result.affectedRows
        });
    });
});

app.listen(PORT, () => {
    console.log(`Seats service running on port ${PORT}`);
});