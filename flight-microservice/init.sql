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
    Status         ENUM('available', 'unavailable', 'cancelled') NOT NULL DEFAULT 'available',
    Meals          VARCHAR(50) NOT NULL,
    Beverages      VARCHAR(50) NOT NULL,
    Wifi           BOOLEAN NOT NULL,
    Baggage        VARCHAR(50) NOT NULL
);

CREATE INDEX idx_flight_origin_dest ON flights(Origin, Destination);
CREATE INDEX idx_flight_date ON flights(FlightDate);

INSERT INTO flights (FlightID, FlightNumber, Origin, Destination, FlightDate, DepartureTime, FlightDuration, ArrivalTime, Price, Status, Meals, Beverages, Wifi, Baggage)
VALUES
(10001, 'BA233', 'Singapore', 'Bangkok', '2026-05-03', '00:30:00', '03:00:00', '03:30:00', 385.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(10002, 'BA234', 'Bangkok', 'Singapore', '2026-05-08', '12:00:00', '03:00:00', '15:00:00', 380.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(10003, 'BA245', 'Singapore', 'Bangkok', '2026-05-03', '14:15:00', '03:00:00', '17:15:00', 410.00, 'available', '1 Snack', '1 Selected', False, '20kg'),
(10004, 'BA246', 'Bangkok', 'Singapore', '2026-05-08', '19:45:00', '03:00:00', '22:45:00', 400.00, 'available', '1 Snack', '1 Selected', False, '20kg'),
(20001, 'JL101', 'Singapore', 'Tokyo', '2026-05-04', '08:00:00', '07:00:00', '15:00:00', 850.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(20002, 'JL102', 'Tokyo', 'Singapore', '2026-05-10', '18:00:00', '07:00:00', '01:00:00', 820.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(20003, 'JL111', 'Singapore', 'Tokyo', '2026-05-04', '22:30:00', '07:00:00', '05:30:00', 790.00, 'available', '1 Hot Meal', '1 Selected', False, '30kg'),
(20004, 'JL112', 'Tokyo', 'Singapore', '2026-05-10', '09:15:00', '07:00:00', '16:15:00', 800.00, 'available', '1 Hot Meal', '1 Selected', False, '30kg'),
(30001, 'SQ322', 'Singapore', 'London', '2026-05-05', '23:30:00', '14:00:00', '13:30:00', 1200.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(30002, 'SQ323', 'London', 'Singapore', '2026-05-15', '10:00:00', '13:00:00', '23:00:00', 1150.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(30003, 'SQ330', 'Singapore', 'London', '2026-05-05', '08:45:00', '14:00:00', '22:45:00', 1350.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(30004, 'SQ331', 'London', 'Singapore', '2026-05-15', '21:20:00', '14:00:00', '11:20:00', 1300.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(40001, 'SQ024', 'Singapore', 'New York', '2026-05-06', '10:00:00', '18:00:00', '04:00:00', 1800.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
(40002, 'SQ025', 'New York', 'Singapore', '2026-05-20', '20:00:00', '18:00:00', '14:00:00', 1750.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
(40003, 'SQ030', 'Singapore', 'New York', '2026-05-06', '23:55:00', '18:00:00', '17:55:00', 1650.00, 'available', '2 Hot Meals', 'Free-flow', True, '30kg'),
(40004, 'SQ031', 'New York', 'Singapore', '2026-05-20', '08:30:00', '18:00:00', '02:30:00', 1600.00, 'available', '2 Hot Meals', 'Free-flow', True, '30kg'),
(50001, 'EK405', 'Singapore', 'Dubai', '2026-05-07', '02:00:00', '07:30:00', '09:30:00', 950.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(50002, 'EK406', 'Dubai', 'Singapore', '2026-05-18', '09:00:00', '07:30:00', '16:30:00', 900.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(50003, 'EK415', 'Singapore', 'Dubai', '2026-05-07', '15:45:00', '07:30:00', '23:15:00', 980.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(50004, 'EK416', 'Dubai', 'Singapore', '2026-05-18', '23:10:00', '07:30:00', '06:40:00', 920.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(60001, 'BA800', 'Singapore', 'Edinburgh', '2026-05-05', '00:05:00', '15:30:00', '15:35:00', 1100.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(60002, 'BA801', 'Edinburgh', 'Singapore', '2026-05-15', '14:30:00', '15:30:00', '06:00:00', 1080.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(60003, 'BA810', 'Singapore', 'Edinburgh', '2026-05-05', '13:15:00', '15:30:00', '04:45:00', 1250.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
(60004, 'BA811', 'Edinburgh', 'Singapore', '2026-05-15', '23:45:00', '15:30:00', '15:15:00', 1150.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg');
