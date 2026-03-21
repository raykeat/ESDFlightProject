CREATE DATABASE IF NOT EXISTS flightdb;
USE flightdb;

CREATE TABLE IF NOT EXISTS flights (
    FlightID       INT AUTO_INCREMENT PRIMARY KEY,
    FlightNumber   VARCHAR(10) NOT NULL,
    Origin         VARCHAR(50) NOT NULL,
    Destination    VARCHAR(50) NOT NULL,
    FlightDate     DATE NOT NULL,
    DepartureTime  TIME NOT NULL,
    FlightDuration TIME NOT NULL,
    ArrivalTime    TIME NOT NULL,
    Price          DECIMAL(10,2) NOT NULL,
    Status         ENUM('available', 'unavailable', 'cancelled') NOT NULL DEFAULT 'available'
);

CREATE INDEX idx_flight_origin_dest ON flights(Origin, Destination);
CREATE INDEX idx_flight_date ON flights(FlightDate);

DELETE FROM flights;

INSERT INTO flights (FlightID, FlightNumber, Origin, Destination, FlightDate, DepartureTime, FlightDuration, ArrivalTime, Price, Status)
VALUES
(36251, 'BL101', 'Singapore', 'Tokyo', '2026-05-04', '08:00:00', '07:00:00', '15:00:00', 850.00, 'available'),
(36252, 'BL103', 'Singapore', 'Tokyo', '2026-05-05', '13:30:00', '07:00:00', '20:30:00', 835.00, 'available'),
(36253, 'BL106', 'Singapore', 'Tokyo', '2026-05-06', '23:55:00', '07:05:00', '07:00:00', 870.00, 'available'),
(10001, 'BL102', 'Tokyo', 'Singapore', '2026-12-04', '18:00:00', '07:00:00', '01:00:00', 820.00, 'available'),
(10002, 'BL104', 'Tokyo', 'Singapore', '2026-05-11', '10:20:00', '07:00:00', '17:20:00', 810.00, 'available'),
(10003, 'BL107', 'Tokyo', 'Singapore', '2026-05-12', '16:40:00', '07:05:00', '23:45:00', 845.00, 'available');
