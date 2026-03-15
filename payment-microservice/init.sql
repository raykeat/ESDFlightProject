CREATE DATABASE IF NOT EXISTS paymentdb;
USE paymentdb;

CREATE TABLE IF NOT EXISTS payment (
    paymentID          INT          AUTO_INCREMENT PRIMARY KEY,
    bookingID          INT          NOT NULL,
    passengerID        INT          NOT NULL,
    amount             DOUBLE       NOT NULL,
    status             VARCHAR(50)  NOT NULL,           -- 'Pending', 'Completed', 'Refunded', 'Failed'
    stripeSessionID    VARCHAR(200) NULL,               -- Stripe Checkout Session ID (cs_...); populated on checkout creation
    stripeChargeID     VARCHAR(100) NULL,               -- Stripe Charge ID; populated after webhook confirms payment
    refundID           VARCHAR(100) NULL,               -- Stripe Refund ID (re_...); populated after refund
    idempotencyKey     VARCHAR(100) NULL UNIQUE,        -- MD5 hash; prevents duplicate charges on retry
    cancellationReason VARCHAR(255) NULL,               -- populated only for refunds (e.g. FlightCancelled); NULL otherwise
    chargedAt          TIMESTAMP    NULL,               -- timestamp when payment was confirmed via webhook
    refundedAt         TIMESTAMP    NULL,               -- timestamp when refund was processed
    createdAt          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);