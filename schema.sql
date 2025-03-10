DROP TABLE IF EXISTS user;

CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    date_created TEXT NOT NULL,
    name TEXT,
    position_title TEXT,
    minimum_salary TEXT,
    location TEXT,
    travel TEXT,
    schedule_type TEXT,
    willing_to_relocate TEXT,
    security_clearance TEXT,
    radius TEXT,
    hiring_path TEXT,
    position_sensitivity TEXT,
    remote TEXT
);

