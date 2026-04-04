-- Consolidated schema for record-service
CREATE TABLE IF NOT EXISTS booking (
    BookingID INT AUTO_INCREMENT PRIMARY KEY,
    PassengerID INT NULL,
    BookedByPassengerID INT NULL,
    FlightID INT NOT NULL,
    AmountPaid DECIMAL(10,2) NOT NULL,
    bookingstatus ENUM('Confirmed', 'Pending', 'Cancelled', 'Failed', 'Refund Failed') NOT NULL DEFAULT 'Pending',
    IsGuest BOOLEAN NOT NULL DEFAULT FALSE,
    GuestFirstName VARCHAR(50) NULL,
    GuestLastName VARCHAR(50) NULL,
    GuestPassportNumber VARCHAR(20) NULL,
    
    -- Added back columns for ESD Flight Project features
    seatNumber VARCHAR(50),      -- Supports comma-separated seats like '1A, 1B'
    returnFlightID INT,           -- Supports round-trip
    returnSeatNumber VARCHAR(50), -- Supports round-trip return seats
    inFlightPerksVoucherID INT NULL,
    inFlightPerksVoucherCode VARCHAR(50) NULL,
    inFlightPerksAppliedAt TIMESTAMP NULL,
    originalAmountPaid DECIMAL(10,2) NULL,
    travelCreditVoucherID INT NULL,
    travelCreditVoucherCode VARCHAR(50) NULL,
    travelCreditAppliedAmount DECIMAL(10,2) NULL,
    travelCreditAppliedAt TIMESTAMP NULL,
    milesAwarded INT NULL,
    milesTransactionID INT NULL,
    milesAwardedAt TIMESTAMP NULL,
    
    CreatedTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE booking
    MODIFY COLUMN PassengerID INT NULL;

ALTER TABLE booking
    MODIFY COLUMN bookingstatus ENUM('Confirmed', 'Pending', 'Cancelled', 'Failed', 'Refund Failed') NOT NULL DEFAULT 'Pending';
