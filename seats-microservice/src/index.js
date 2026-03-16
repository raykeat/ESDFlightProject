const express = require("express");
const mysql = require("mysql2");
const cors = require("cors");

const app = express();
app.use(express.json());
app.use(cors());

const PORT = 5003;

const db = mysql.createConnection({
    host: "seats-db",
    user: "root",
    password: "root",
    database: "seats"
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


app.listen(PORT, () => {
    console.log(`Seats service running on port ${PORT}`);
});