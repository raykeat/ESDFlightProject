-- vouchers table
CREATE TABLE IF NOT EXISTS vouchers (
    voucherID INT AUTO_INCREMENT PRIMARY KEY,
    passengerID INT NOT NULL,
    voucherCode VARCHAR(50) UNIQUE NOT NULL,
    voucherType VARCHAR(50) NOT NULL,
    voucherValue DECIMAL(10,2) NULL,
    milesRedeemed INT NOT NULL,
    expiryDate DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usedAt TIMESTAMP NULL,
    usedBookingID INT NULL,
    INDEX idx_passengerID (passengerID),
    INDEX idx_voucherCode (voucherCode)
);