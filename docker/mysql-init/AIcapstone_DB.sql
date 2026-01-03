CREATE DATABASE IF NOT EXISTS AIcapstone;
USE AIcapstone;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),
    email VARCHAR(50)
);

CREATE TABLE requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    original_query TEXT,
    extracted_fields JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE recommendations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    dish_name VARCHAR(100),
    dish_type VARCHAR(50),
    ingredient TEXT,
    option_json JSON,
    recommended_options JSON,
    score FLOAT,
    explaination TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES requests(id)
);