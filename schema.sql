use dbms_proj;
-- User table combining all user information
CREATE TABLE User (
    User_ID VARCHAR(255) PRIMARY KEY,
    First_Name VARCHAR(255) NOT NULL,
    Second_Name VARCHAR(255),
    Email_ID VARCHAR(255) UNIQUE,
    Phone_No VARCHAR(20)
);

-- Device table with ownership information
CREATE TABLE Device (
    Device_ID VARCHAR(255) PRIMARY KEY,
    User_ID VARCHAR(255) NOT NULL,
    MAC_Address VARCHAR(17) UNIQUE NOT NULL,
    Device_Name VARCHAR(255) NOT NULL,
    Device_Type VARCHAR(255) NOT NULL,
    FOREIGN KEY (User_ID) REFERENCES User(User_ID) ON DELETE CASCADE
);

-- Network table
CREATE TABLE Network (
    Network_ID VARCHAR(255) PRIMARY KEY,
    SSID VARCHAR(255) NOT NULL
);

-- Connection log table
CREATE TABLE Connection_Log (
    Log_ID VARCHAR(255) PRIMARY KEY,
    Network_ID VARCHAR(255) NOT NULL,
    Device_ID VARCHAR(255) NOT NULL,
    Timestamp TIMESTAMP NOT NULL,
    IP_Address VARCHAR(15) NOT NULL,
    FOREIGN KEY (Network_ID) REFERENCES Network(Network_ID) ON DELETE CASCADE,
    FOREIGN KEY (Device_ID) REFERENCES Device(Device_ID) ON DELETE CASCADE
);

-- Data usage table
CREATE TABLE Data_Usage (
    Usage_ID VARCHAR(255) PRIMARY KEY,
    Log_ID VARCHAR(255) NOT NULL,
    Data_Downloaded FLOAT NOT NULL DEFAULT 0,
    Data_Uploaded FLOAT NOT NULL DEFAULT 0,
    FOREIGN KEY (Log_ID) REFERENCES Connection_Log(Log_ID) ON DELETE CASCADE
);

-- Connection between devices and networks
CREATE TABLE Connects (
    Device_ID VARCHAR(255) NOT NULL,
    Network_ID VARCHAR(255) NOT NULL,
    PRIMARY KEY (Device_ID, Network_ID),
    FOREIGN KEY (Device_ID) REFERENCES Device(Device_ID) ON DELETE CASCADE,
    FOREIGN KEY (Network_ID) REFERENCES Network(Network_ID) ON DELETE CASCADE
);




-- Insert Records into the User Table
INSERT INTO User (User_ID, First_Name, Second_Name, Email_ID, Phone_No) VALUES
('U001', 'Mithun', 'Prabhu', 'mithun.prabhu@example.com', '1234567890'),
('U002', 'Jeeva', 'Praveen', 'jeeva.praveen@example.com', '0987654321'),
('U003', 'Meharnaz', 'Kiran', 'meharnaz.kiran@example.com', '1122334455'),
('U004', 'Madhumithra', 'RR', 'madhumithra.rr@example.com', '2233445566'),
('U005', 'David', 'Wilson', 'david.wilson@example.com', '3344556677');

-- Insert Records into the Device Table
INSERT INTO Device (Device_ID, User_ID, MAC_Address, Device_Name, Device_Type) VALUES
('D001', 'U001', '00:1A:2B:3C:4D:5E', 'iPhone', 'Smartphone'),
('D002', 'U002', '00:1A:2B:3C:4D:5F', 'Galaxy Tab', 'Tablet'),
('D003', 'U003', '00:1A:2B:3C:4D:5G', 'Dell Laptop', 'Laptop'),
('D004', 'U004', '00:1A:2B:3C:4D:5H', 'HP Printer', 'Printer'),
('D005', 'U005', '00:1A:2B:3C:4D:5I', 'Samsung TV', 'Smart TV');

-- Insert Records into the Network Table with College Context
INSERT INTO Network (Network_ID, SSID) VALUES
('N001', 'GH_1'),  -- Gentlemen's Hostel
('N002', 'LH_1'),  -- Ladies' Hostel
('N003', 'AB_1'),  -- Academic Block 1
('N004', 'AB_2'),  -- Academic Block 2
('N005', 'Rishabs'), -- Canteen
('N006', 'GH_2'),  -- Gentlemen's Hostel 2
('N007', 'LH_2'),  -- Ladies' Hostel 2
('N008', 'GH_5');  -- Gentlemen's Hostel 5

-- Insert Records into the Connection_Log Table
INSERT INTO Connection_Log (Log_ID, Network_ID, Device_ID, Timestamp, IP_Address) VALUES
('L001', 'N001', 'D001', '2025-08-18 10:00:00', '192.168.1.2'),
('L002', 'N002', 'D002', '2025-08-18 11:00:00', '192.168.1.3'),
('L003', 'N003', 'D003', '2025-08-18 12:00:00', '192.168.1.4'),
('L004', 'N004', 'D004', '2025-08-18 13:00:00', '192.168.1.5'),
('L005', 'N005', 'D005', '2025-08-18 14:00:00', '192.168.1.6');

-- Insert Records into the Data_Usage Table
INSERT INTO Data_Usage (Usage_ID, Log_ID, Data_Downloaded, Data_Uploaded) VALUES
('U001', 'L001', 150.5, 50.2),
('U002', 'L002', 200.0, 75.0),
('U003', 'L003', 100.0, 25.0),
('U004', 'L004', 300.0, 100.0),
('U005', 'L005', 250.0, 80.0);

-- Insert Records into the Connects Table
INSERT INTO Connects (Device_ID, Network_ID) VALUES
('D001', 'N001'),
('D002', 'N002'),
('D003', 'N003'),
('D004', 'N004'),
('D005', 'N005'),
('D001', 'N006'),
('D002', 'N007'),
('D003', 'N008');


USE dbms_proj;

ALTER TABLE User
ADD COLUMN Password_Hash VARCHAR(255) NOT NULL;


-- Update existing users with hashed passwords (example hashes)

UPDATE User SET Password_Hash = 'pbkdf2:sha256:1000000$Q0MrOdtLBypJijm7$7c244b5ae0e05edd572e0032b9487ffb735ad904c356566c721f77277c1bdc21' WHERE User_ID = 'U001';

UPDATE User SET Password_Hash = 'pbkdf2:sha256:1000000$Q0MrOdtLBypJijm7$7c244b5ae0e05edd572e0032b9487ffb735ad904c356566c721f77277c1bdc21' WHERE User_ID = 'U002';

UPDATE User SET Password_Hash = 'pbkdf2:sha256:1000000$Q0MrOdtLBypJijm7$7c244b5ae0e05edd572e0032b9487ffb735ad904c356566c721f77277c1bdc21' WHERE User_ID = 'U003';

UPDATE User SET Password_Hash = 'pbkdf2:sha256:1000000$Q0MrOdtLBypJijm7$7c244b5ae0e05edd572e0032b9487ffb735ad904c356566c721f77277c1bdc21' WHERE User_ID = 'U004';

UPDATE User SET Password_Hash = 'pbkdf2:sha256:1000000$Q0MrOdtLBypJijm7$7c244b5ae0e05edd572e0032b9487ffb735ad904c356566c721f77277c1bdc21' WHERE User_ID = 'U005';