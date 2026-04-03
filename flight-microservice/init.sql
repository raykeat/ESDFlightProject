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
    Status         ENUM('available', 'unavailable', 'cancelled', 'landed') NOT NULL DEFAULT 'available',
    CancellationReason VARCHAR(255) NULL,
    Meals          VARCHAR(50) NOT NULL,
    Beverages      VARCHAR(50) NOT NULL,
    Wifi           BOOLEAN NOT NULL,
    Baggage        VARCHAR(50) NOT NULL
);

CREATE INDEX idx_flight_origin_dest ON flights(Origin, Destination);
CREATE INDEX idx_flight_date ON flights(FlightDate);

INSERT INTO flights (FlightID, FlightNumber, Origin, Destination, FlightDate, DepartureTime, FlightDuration, ArrivalTime, Price, Status, Meals, Beverages, Wifi, Baggage)
VALUES
(70001, 'BA701', 'Dubai', 'Edinburgh', '2026-04-02', '08:15:00', '08:00:00', '16:15:00', 780.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(70002, 'BA702', 'Dubai', 'Edinburgh', '2026-04-04', '19:40:00', '08:05:00', '03:45:00', 760.00, 'available', '1 Hot Meal', '1 Selected', True, '30kg'),
(70003, 'BA703', 'Dubai', 'Edinburgh', '2026-04-06', '10:05:00', '08:10:00', '18:15:00', 795.00, 'available', '2 Hot Meals', 'Free-flow', True, '35kg'),
(70004, 'BA704', 'Dubai', 'Edinburgh', '2026-04-08', '22:20:00', '08:00:00', '06:20:00', 745.00, 'available', '1 Snack', '1 Selected', False, '25kg'),
(70005, 'BA705', 'Edinburgh', 'Dubai', '2026-04-10', '09:30:00', '08:00:00', '17:30:00', 770.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(70006, 'BA706', 'Edinburgh', 'Dubai', '2026-04-12', '18:10:00', '08:05:00', '02:15:00', 755.00, 'available', '1 Hot Meal', '1 Selected', True, '30kg'),
(71001, 'BA711', 'Singapore', 'Bangkok', '2026-04-02', '07:20:00', '03:00:00', '10:20:00', 365.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(71002, 'BA712', 'Bangkok', 'Singapore', '2026-04-03', '18:50:00', '03:00:00', '21:50:00', 360.00, 'available', '1 Snack', '1 Selected', False, '20kg'),
(72001, 'BA721', 'Singapore', 'Tokyo', '2026-04-09', '09:10:00', '07:00:00', '16:10:00', 840.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(72002, 'BA722', 'Tokyo', 'Singapore', '2026-04-16', '20:25:00', '07:00:00', '03:25:00', 825.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(73001, 'BA731', 'Singapore', 'London', '2026-04-15', '11:30:00', '14:00:00', '01:30:00', 1180.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(73002, 'BA732', 'London', 'Singapore', '2026-04-22', '13:10:00', '13:00:00', '02:10:00', 1160.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(74001, 'BA741', 'Singapore', 'New York', '2026-04-20', '21:45:00', '18:00:00', '15:45:00', 1720.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
(74002, 'BA742', 'New York', 'Singapore', '2026-04-28', '10:15:00', '18:00:00', '04:15:00', 1690.00, 'available', '2 Hot Meals', 'Free-flow', True, '30kg'),
(75001, 'BA751', 'Singapore', 'Dubai', '2026-04-25', '06:40:00', '07:30:00', '14:10:00', 930.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(75002, 'BA752', 'Dubai', 'Singapore', '2026-05-02', '16:20:00', '07:30:00', '23:50:00', 910.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(76001, 'BA761', 'Singapore', 'Edinburgh', '2026-05-09', '08:55:00', '15:30:00', '00:25:00', 1175.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(76002, 'BA762', 'Edinburgh', 'Singapore', '2026-05-10', '19:15:00', '15:30:00', '10:45:00', 1125.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(10001, 'BA233', 'Singapore', 'Bangkok', '2026-05-03', '00:30:00', '03:00:00', '03:30:00', 385.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(10002, 'BA234', 'Bangkok', 'Singapore', '2026-05-08', '12:00:00', '03:00:00', '15:00:00', 380.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(10003, 'BA245', 'Singapore', 'Bangkok', '2026-05-03', '14:15:00', '03:00:00', '17:15:00', 410.00, 'available', '1 Snack', '1 Selected', False, '20kg'),
(10004, 'BA246', 'Bangkok', 'Singapore', '2026-05-08', '19:45:00', '03:00:00', '22:45:00', 400.00, 'available', '1 Snack', '1 Selected', False, '20kg'),
(10005, 'BA247', 'Singapore', 'Bangkok', '2026-05-04', '08:10:00', '03:00:00', '11:10:00', 395.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(10006, 'BA248', 'Singapore', 'Bangkok', '2026-05-04', '13:40:00', '03:00:00', '16:40:00', 405.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(10007, 'BA249', 'Singapore', 'Bangkok', '2026-05-04', '20:55:00', '03:00:00', '23:55:00', 415.00, 'available', '1 Snack', 'Free-flow', False, '25kg'),
(20001, 'BA101', 'Singapore', 'Tokyo', '2026-05-04', '08:00:00', '07:00:00', '15:00:00', 850.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(20002, 'BA102', 'Tokyo', 'Singapore', '2026-05-10', '18:00:00', '07:00:00', '01:00:00', 820.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(20003, 'BA111', 'Singapore', 'Tokyo', '2026-05-04', '22:30:00', '07:00:00', '05:30:00', 790.00, 'available', '1 Hot Meal', '1 Selected', False, '30kg'),
(20004, 'BA112', 'Tokyo', 'Singapore', '2026-05-10', '09:15:00', '07:00:00', '16:15:00', 800.00, 'available', '1 Hot Meal', '1 Selected', False, '30kg'),
(30001, 'BA322', 'Singapore', 'London', '2026-05-05', '23:30:00', '14:00:00', '13:30:00', 1200.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(30002, 'BA323', 'London', 'Singapore', '2026-05-15', '10:00:00', '13:00:00', '23:00:00', 1150.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(30003, 'BA330', 'Singapore', 'London', '2026-05-05', '08:45:00', '14:00:00', '22:45:00', 1350.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(30004, 'BA331', 'London', 'Singapore', '2026-05-15', '21:20:00', '14:00:00', '11:20:00', 1300.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(40001, 'BA024', 'Singapore', 'New York', '2026-05-06', '10:00:00', '18:00:00', '04:00:00', 1800.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
(40002, 'BA025', 'New York', 'Singapore', '2026-05-20', '20:00:00', '18:00:00', '14:00:00', 1750.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
(40003, 'BA030', 'Singapore', 'New York', '2026-05-06', '23:55:00', '18:00:00', '17:55:00', 1650.00, 'available', '2 Hot Meals', 'Free-flow', True, '30kg'),
(40004, 'BA031', 'New York', 'Singapore', '2026-05-20', '08:30:00', '18:00:00', '02:30:00', 1600.00, 'available', '2 Hot Meals', 'Free-flow', True, '30kg'),
(50001, 'BA405', 'Singapore', 'Dubai', '2026-05-07', '02:00:00', '07:30:00', '09:30:00', 950.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(50002, 'BA406', 'Dubai', 'Singapore', '2026-05-18', '09:00:00', '07:30:00', '16:30:00', 900.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
(50003, 'BA415', 'Singapore', 'Dubai', '2026-05-07', '15:45:00', '07:30:00', '23:15:00', 980.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(50004, 'BA416', 'Dubai', 'Singapore', '2026-05-18', '23:10:00', '07:30:00', '06:40:00', 920.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(60001, 'BA800', 'Singapore', 'Edinburgh', '2026-05-05', '00:05:00', '15:30:00', '15:35:00', 1100.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(60002, 'BA801', 'Edinburgh', 'Singapore', '2026-05-15', '14:30:00', '15:30:00', '06:00:00', 1080.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
(60003, 'BA810', 'Singapore', 'Edinburgh', '2026-05-05', '13:15:00', '15:30:00', '04:45:00', 1250.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
(60004, 'BA811', 'Edinburgh', 'Singapore', '2026-05-15', '23:45:00', '15:30:00', '15:15:00', 1150.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg');
UPDATE flights
SET FlightNumber = CONCAT('BA', SUBSTRING(FlightNumber, 3))
WHERE FlightNumber NOT LIKE 'BA%';
