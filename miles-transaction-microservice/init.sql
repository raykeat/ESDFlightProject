-- transactions table
CREATE TABLE IF NOT EXISTS transactions (
    transactionID INT AUTO_INCREMENT PRIMARY KEY,
    passengerID INT NOT NULL,
    milesDelta INT NOT NULL,
    transactionType VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    referenceID VARCHAR(100) NULL,
    originalTransactionID INT NULL,
    voucherType VARCHAR(50) NULL,
    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_passengerID (passengerID)
);