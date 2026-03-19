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

INSERT INTO flights (FlightID, FlightNumber, Origin, Destination, FlightDate, DepartureTime, FlightDuration, ArrivalTime, Price, Status)
VALUES
(10001, 'BA233', 'Singapore', 'Bangkok', '2026-05-03', '00:30:00', '03:00:00', '03:30:00', 385.00, 'available'),
(10002, 'BA234', 'Bangkok', 'Singapore', '2026-05-08', '12:00:00', '03:00:00', '15:00:00', 380.00, 'available'),
(20001, 'JL101', 'Singapore', 'Tokyo', '2026-05-04', '08:00:00', '07:00:00', '15:00:00', 850.00, 'available'),
(20002, 'JL102', 'Tokyo', 'Singapore', '2026-05-10', '18:00:00', '07:00:00', '01:00:00', 820.00, 'available'),
(30001, 'SQ322', 'Singapore', 'London', '2026-05-05', '23:30:00', '14:00:00', '13:30:00', 1200.00, 'available'),
(30002, 'SQ323', 'London', 'Singapore', '2026-05-15', '10:00:00', '13:00:00', '23:00:00', 1150.00, 'available'),
(40001, 'SQ024', 'Singapore', 'New York', '2026-05-06', '10:00:00', '18:00:00', '04:00:00', 1800.00, 'available'),
(40002, 'SQ025', 'New York', 'Singapore', '2026-05-20', '20:00:00', '18:00:00', '14:00:00', 1750.00, 'available'),
(50001, 'EK405', 'Singapore', 'Dubai', '2026-05-07', '02:00:00', '07:30:00', '09:30:00', 950.00, 'available'),
(50002, 'EK406', 'Dubai', 'Singapore', '2026-05-18', '09:00:00', '07:30:00', '16:30:00', 900.00, 'available');
