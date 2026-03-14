CREATE DATABASE IF NOT EXISTS paymentdb;
USE paymentdb;

CREATE TABLE IF NOT EXISTS payment (
    paymentID          INT          AUTO_INCREMENT PRIMARY KEY,
    bookingID          INT          NOT NULL,
    passengerID        INT          NOT NULL,
    amount             DOUBLE       NOT NULL,
    status             VARCHAR(50)  NOT NULL,         
    stripeChargeID     VARCHAR(100) NULL,             
    refundID           VARCHAR(100) NULL,                                                     
    idempotencyKey     VARCHAR(100) NULL UNIQUE,      
    cancellationReason VARCHAR(255) NULL,             
    chargedAt          TIMESTAMP    NULL,             
    refundedAt         TIMESTAMP    NULL,             
    createdAt          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);