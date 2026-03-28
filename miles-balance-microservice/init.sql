-- passenger_miles table
CREATE TABLE IF NOT EXISTS passenger_miles (
    passengerID INT PRIMARY KEY,
    currentBalance INT NOT NULL DEFAULT 0,
    version INT NOT NULL DEFAULT 1,
    updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);