DROP TABLE users;
DROP TABLE semester;
DROP TABLE fach;
DROP TABLE note;


CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);

CREATE TABLE semester (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    user_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE fach (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fachname VARCHAR(100) NOT NULL,
    lehrer VARCHAR(100),
    fachgewichtung FLOAT,
    semester_id INT NOT NULL,
    user_id INT NOT NULL,
    FOREIGN KEY (semester_id) REFERENCES semester(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE note (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titel VARCHAR(100),
    notenwert FLOAT NOT NULL,
    gewichtung FLOAT NOT NULL,
    datum DATE NOT NULL,
    fach_id INT NOT NULL,
    FOREIGN KEY (fach_id) REFERENCES fach(id) ON DELETE CASCADE
);