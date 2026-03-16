CREATE TABLE seats (
    SeatID INT AUTO_INCREMENT PRIMARY KEY,
    FlightID INT NOT NULL,
    SeatNumber VARCHAR(5) NOT NULL,
    Status ENUM('available', 'unavailable', 'hold') DEFAULT 'available',
    PassengerID INT NULL
);

INSERT INTO seats (FlightID, SeatNumber, Status)
VALUES
(10001, '12A', 'available'),
(10001, '12B', 'available'),
(10001, '12C', 'available'),
(10001, '13A', 'available'),
(10001, '13B', 'available');