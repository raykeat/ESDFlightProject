CREATE DATABASE IF NOT EXISTS seats;
USE seats;

CREATE TABLE IF NOT EXISTS seats (
    SeatID INT AUTO_INCREMENT PRIMARY KEY,
    FlightID INT NOT NULL,
    SeatNumber VARCHAR(5) NOT NULL,
    Status ENUM('available', 'unavailable', 'hold') DEFAULT 'available',
    PassengerID INT NULL
);

TRUNCATE TABLE seats;

INSERT INTO seats (FlightID, SeatNumber, Status)
SELECT
    f.FlightID,
    CONCAT(r.row_num, c.col_letter) AS SeatNumber,
    'available' AS Status
FROM
    (
        SELECT 36251 AS FlightID
        UNION ALL SELECT 36252
        UNION ALL SELECT 36253
        UNION ALL SELECT 10001
        UNION ALL SELECT 10002
        UNION ALL SELECT 10003
    ) f
CROSS JOIN
    (
        SELECT 1 AS row_num
        UNION ALL SELECT 2
        UNION ALL SELECT 3
        UNION ALL SELECT 4
        UNION ALL SELECT 5
        UNION ALL SELECT 6
        UNION ALL SELECT 7
        UNION ALL SELECT 8
        UNION ALL SELECT 9
        UNION ALL SELECT 10
    ) r
CROSS JOIN
    (
        SELECT 'A' AS col_letter
        UNION ALL SELECT 'B'
        UNION ALL SELECT 'C'
        UNION ALL SELECT 'D'
        UNION ALL SELECT 'E'
        UNION ALL SELECT 'F'
    ) c;

UPDATE seats
SET Status = 'unavailable'
WHERE FlightID = 36251 AND SeatNumber IN ('1A', '2C', '4D', '7F', '10B');

UPDATE seats
SET Status = 'unavailable'
WHERE FlightID = 36252 AND SeatNumber IN ('1B', '3D', '5A', '8E', '10F');

UPDATE seats
SET Status = 'unavailable'
WHERE FlightID = 36253 AND SeatNumber IN ('2B', '4A', '6F', '9C', '10D');

UPDATE seats
SET Status = 'unavailable'
WHERE FlightID = 10001 AND SeatNumber IN ('1C', '3A', '5E', '8B', '9F');

UPDATE seats
SET Status = 'unavailable'
WHERE FlightID = 10002 AND SeatNumber IN ('2D', '4F', '6A', '7C', '10E');

UPDATE seats
SET Status = 'unavailable'
WHERE FlightID = 10003 AND SeatNumber IN ('1F', '3C', '5B', '7D', '9A');
