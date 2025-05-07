DROP TABLE IF EXISTS user;

CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    date_created TEXT NOT NULL,
    position_title TEXT,
    minimum_salary TEXT,
    location TEXT,
    hiring_path TEXT,
    remote TEXT
);

