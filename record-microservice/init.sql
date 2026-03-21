-- Consolidated schema for record-service
CREATE TABLE IF NOT EXISTS booking (
    BookingID INT AUTO_INCREMENT PRIMARY KEY,
    PassengerID INT NOT NULL,
    FlightID INT NOT NULL,
    AmountPaid DECIMAL(10,2) NOT NULL,
    bookingstatus ENUM('Confirmed', 'Pending', 'Cancelled', 'Failed') NOT NULL DEFAULT 'Pending',
    
    -- Added back columns for ESD Flight Project features
    seatNumber VARCHAR(50),      -- Supports comma-separated seats like '1A, 1B'
    returnFlightID INT,           -- Supports round-trip
    returnSeatNumber VARCHAR(50), -- Supports round-trip return seats
    
    CreatedTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);