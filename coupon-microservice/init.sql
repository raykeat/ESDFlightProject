CREATE DATABASE IF NOT EXISTS coupondb;
USE coupondb;

CREATE TABLE IF NOT EXISTS coupon (
    CouponID       INT             AUTO_INCREMENT PRIMARY KEY,
    CouponCode     VARCHAR(12)     NOT NULL UNIQUE,
    DiscountAmount DECIMAL(10,2)   NOT NULL,
    IsUsed         BOOLEAN         NOT NULL DEFAULT FALSE,
    UsedAt         DATETIME        NULL,
    ExpiryDate     DATETIME        NOT NULL,
    CreatedTime    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_coupon_code     ON coupon(CouponCode);
CREATE INDEX idx_coupon_expiry   ON coupon(ExpiryDate);
CREATE INDEX idx_coupon_is_used  ON coupon(IsUsed);

INSERT INTO coupon (CouponCode, DiscountAmount, IsUsed, UsedAt, ExpiryDate)
VALUES
('BLAZE-ABC123', 50.00, FALSE, NULL, DATE_ADD(NOW(), INTERVAL 2 YEAR)),
('BLAZE-USED01', 20.00, TRUE, NOW(), DATE_ADD(NOW(), INTERVAL 1 YEAR));
