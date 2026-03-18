CREATE TABLE IF NOT EXISTS booking (
    bookingID INT AUTO_INCREMENT PRIMARY KEY,
    passengerID INT NOT NULL,
    flightID INT NOT NULL,
    status VARCHAR(50) NOT NULL,
    amount DOUBLE NOT NULL,
    seatNumber VARCHAR(4),
    refundID VARCHAR(100),
    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 2. SECOND: Insert test data
INSERT INTO booking (passengerID, flightID, status, amount, seatNumber) VALUES
(101, 201, 'Confirmed', 299.99, '12A'),
(102, 201, 'Confirmed', 299.99, '12B'),
(103, 202, 'Pending', 149.50, '8C'),
(104, 203, 'Cancelled+Refunded', 499.00, '1A'),
(105, 201, 'Confirmed', 299.99, '12C');

-- Optional: Add more varied test data
INSERT INTO booking (passengerID, flightID, status, amount, seatNumber) VALUES
(106, 204, 'Confirmed', 199.99, '15D'),
(107, 204, 'Failed', 199.99, '15E'),
(108, 205, 'Pending', 399.99, '3F');