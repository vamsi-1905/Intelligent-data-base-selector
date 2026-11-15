-- Intelligent Database Selection Framework: schema only.
-- Catalog data is loaded automatically by the app (database/seed_catalog.py).

-- 1. Candidate database systems
CREATE TABLE database_systems (
    database_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    database_type VARCHAR(50) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Evaluation criteria
CREATE TABLE criteria (
    criterion_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    weight NUMERIC(5,4) NOT NULL
        CHECK (weight >= 0 AND weight <= 1),
    score_direction VARCHAR(10) NOT NULL DEFAULT 'higher'
        CHECK (score_direction IN ('higher', 'lower'))
);

-- 3. Capability scores for each database
CREATE TABLE database_criteria_scores (
    database_id INTEGER NOT NULL
        REFERENCES database_systems(database_id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL
        REFERENCES criteria(criterion_id) ON DELETE CASCADE,
    score NUMERIC(4,2) NOT NULL
        CHECK (score BETWEEN 1 AND 10),
    evidence TEXT,
    reasoning TEXT,
    source_url TEXT,
    origin VARCHAR(20),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (database_id, criterion_id)
);

-- 4. Submitted applications
CREATE TABLE applications (
    application_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    expected_users INTEGER CHECK (expected_users >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. Requirements extracted from user descriptions
CREATE TABLE application_requirements (
    application_id INTEGER NOT NULL
        REFERENCES applications(application_id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL
        REFERENCES criteria(criterion_id) ON DELETE CASCADE,
    importance NUMERIC(4,2) NOT NULL
        CHECK (importance BETWEEN 1 AND 10),
    PRIMARY KEY (application_id, criterion_id)
);

-- 6. Ranked recommendations
CREATE TABLE recommendations (
    recommendation_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id INTEGER NOT NULL
        REFERENCES applications(application_id) ON DELETE CASCADE,
    database_id INTEGER NOT NULL
        REFERENCES database_systems(database_id),
    method VARCHAR(30) NOT NULL
        CHECK (method IN ('WSM', 'TOPSIS', 'ML')),
    score NUMERIC(10,6) NOT NULL,
    rank INTEGER NOT NULL CHECK (rank >= 1),
    explanation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (application_id, method, rank),
    UNIQUE (application_id, method, database_id)
);

-- 7. User feedback
CREATE TABLE feedback (
    feedback_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recommendation_id INTEGER NOT NULL
        REFERENCES recommendations(recommendation_id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_recommendations_application ON recommendations(application_id);
CREATE INDEX idx_feedback_recommendation ON feedback(recommendation_id);