CREATE TABLE IF NOT EXISTS record (
    BookingID INT AUTO_INCREMENT PRIMARY KEY,
    FlightID INT NOT NULL,
    SeatID INT NOT NULL,
    PassengerID INT NOT NULL,
    AmountPaid DECIMAL(10, 2) NOT NULL,
    bookingstatus ENUM('Confirmed', 'Pending', 'Cancelled', 'Failed') NOT NULL DEFAULT 'Pending',
    CreatedTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);