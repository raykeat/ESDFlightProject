CREATE DATABASE IF NOT EXISTS offerdb;
USE offerdb;

CREATE TABLE IF NOT EXISTS offer (
    offerID      INT             AUTO_INCREMENT PRIMARY KEY,
    bookingID    INT             NOT NULL,                              -- FK → Booking DB
    passengerID  INT             NOT NULL,                              -- FK → Passenger DB (OutSystems)
    origFlightID INT             NOT NULL,                              -- FK → Flight DB (cancelled flight)
    newFlightID  INT             NOT NULL,                              -- FK → Flight DB (alternative); always populated since Offer is Path A only
    newSeatID    INT             NULL,                                  -- logical reference to Seat Service; no DB-level FK
    couponID     INT             NULL,                                  -- FK → Coupon DB, populated after coupon created
    -- fareDiff removed — airline absorbs all fare differences per disruption policy
    status       ENUM(
                   'Pending Response',
                   'Accepted',
                   'Rejected',
                   'Expired'
                 )               NOT NULL    DEFAULT 'Pending Response', -- ENUM enforces valid values at DB level
    expiryTime   DATETIME        NULL,                                  -- now+24h for Path A offers
    respondedAt  DATETIME        NULL,                                  -- timestamp when passenger accepted/rejected; NULL if not yet responded or expired
    isDeleted    BOOLEAN         NOT NULL    DEFAULT FALSE,             -- soft delete — never hard delete for audit trail
    createdTime  TIMESTAMP       NOT NULL    DEFAULT CURRENT_TIMESTAMP,
    updatedTime  TIMESTAMP       NULL        ON UPDATE CURRENT_TIMESTAMP -- auto-updated on any row change
);

  ALTER TABLE offer
    ADD COLUMN IF NOT EXISTS newSeatID INT NULL;

-- ==========================================
-- INDEXES — speed up common query patterns
-- ==========================================
CREATE INDEX idx_offer_bookingID    ON offer(bookingID);     -- GET /offer?bookingID=
CREATE INDEX idx_offer_passengerID  ON offer(passengerID);   -- GET /offer?passengerID=
CREATE INDEX idx_offer_origFlightID ON offer(origFlightID);  -- GET /offer?origFlightID=
CREATE INDEX idx_offer_status       ON offer(status);        -- GET /offer?status=
CREATE INDEX idx_offer_isDeleted    ON offer(isDeleted);     -- all queries filter by isDeleted=FALSE

-- ==========================================
-- SAMPLE DATA
-- ==========================================
INSERT INTO offer (bookingID, passengerID, origFlightID, newFlightID, newSeatID, couponID, status, expiryTime, respondedAt) VALUES
(9,  1, 36251, 40001, NULL, 101, 'Pending Response', '2027-12-31 23:59:59', NULL),
(10, 2, 36251, 40001, NULL, 102, 'Accepted',         '2025-03-12 09:15:22', '2025-03-11 14:22:10'),
(11, 9, 36251, 40001, NULL, 103, 'Rejected',         '2025-03-12 09:15:22', '2025-03-11 16:05:33'),
(12, 4, 36251, 40001, NULL, 104, 'Expired',          '2025-03-12 09:15:22', NULL);