CREATE DATABASE IF NOT EXISTS paymentdb;
USE paymentdb;

CREATE TABLE IF NOT EXISTS payment (
    paymentID          INT AUTO_INCREMENT PRIMARY KEY,
    bookingID          INT NOT NULL,
    passengerID        INT NOT NULL,
    amount             DOUBLE NOT NULL,
    status             VARCHAR(50) NOT NULL,       -- 'Completed', 'Refunded', 'Failed'
    stripeChargeID     VARCHAR(100),               -- stored after payment so refund can look it up
    refundID           VARCHAR(100),
    cancellationReason VARCHAR(255),
    idempotencyKey     VARCHAR(100) UNIQUE,        -- prevents double charging on retries
    chargedAt          TIMESTAMP NULL,
    refundedAt         TIMESTAMP NULL,
    createdAt          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);