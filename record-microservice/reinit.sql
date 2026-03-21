USE recorddb;
DROP TABLE IF EXISTS booking;
CREATE TABLE booking (
    BookingID INT AUTO_INCREMENT PRIMARY KEY,
    PassengerID INT NOT NULL,
    FlightID INT NOT NULL,
    AmountPaid DECIMAL(10,2) NOT NULL,
    bookingstatus ENUM('Confirmed', 'Pending', 'Cancelled', 'Failed') NOT NULL DEFAULT 'Pending',
    seatNumber VARCHAR(50),
    returnFlightID INT,
    returnSeatNumber VARCHAR(50),
    CreatedTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
