DROP TABLE IF EXISTS user;

CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    date_created TEXT NOT NULL,
    name TEXT,
    position_title TEXT,
    minimum_salary INTEGER,
    job_category TEXT,
    location TEXT,
    organizations TEXT,
    travel TEXT,
    schedule_type TEXT,
    willing_to_relocate TEXT,
    security_clearance TEXT,
    radius INTEGER,
    hiring_path TEXT,
    position_sensitivity TEXT,
    remote TEXT
);

