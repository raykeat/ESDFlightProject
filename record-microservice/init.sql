DROP TABLE IF EXISTS booking;

CREATE TABLE booking (
    BookingID INT AUTO_INCREMENT PRIMARY KEY,
    FlightID INT NOT NULL,
    SeatID INT,
    PassengerID INT NOT NULL,
    AmountPaid DECIMAL(10,2) NOT NULL,
    bookingstatus ENUM('Confirmed', 'Pending', 'Cancelled', 'Failed') NOT NULL DEFAULT 'Pending',
    CreatedTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);