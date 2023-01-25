CREATE SCHEMA IF NOT EXISTS reviews;

CREATE TABLE IF NOT EXISTS reviews.cursors (
  owner     TEXT NOT NULL,
  repo      TEXT NOT NULL,
  cursor    TEXT NOT NULL,
  PRIMARY KEY(owner, repo)
);

CREATE TABLE IF NOT EXISTS reviews.cursors_history (
  owner     TEXT NOT NULL,
  repo      TEXT NOT NULL,
  number    INTEGER NOT NULL,
  cursor    TEXT NOT NULL,
  merged_at TIMESTAMPTZ,
  PRIMARY KEY(owner, repo, number)
);

CREATE TABLE IF NOT EXISTS reviews.processed_prs (
  owner     TEXT NOT NULL,
  repo      TEXT NOT NULL,
  number    INTEGER NOT NULL,
  event_at  TIMESTAMPTZ,
  PRIMARY KEY(owner, repo, number)
);

CREATE TABLE IF NOT EXISTS reviews.review_stats (
  owner     TEXT NOT NULL,
  repo      TEXT NOT NULL,
  number    INTEGER NOT NULL,
  reviewer  TEXT NOT NULL,
  minutes   INTEGER NOT NULL,
  review_at TIMESTAMPTZ,
  event_at  TIMESTAMPTZ DEFAULT NOW() AT TIME ZONE 'UTC',
  PRIMARY KEY(owner, repo, number, review_at)
);

CREATE INDEX IF NOT EXISTS idx_stats_by_reviewers ON reviews.review_stats (reviewer, event_at);

CREATE TABLE IF NOT EXISTS reviews.key_value (
  key       TEXT PRIMARY KEY,
  value     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews.users_logins (
  staff_login     TEXT PRIMARY KEY,
  telegram_login  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS reviews.users_telegrams (
  telegram_login  TEXT PRIMARY KEY,
  chat_id         INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS reviews.users_settings (
  staff_login            TEXT PRIMARY KEY,
  review_notify_hours    INTEGER[] NOT NULL DEFAULT '{}',
  review_notify_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
  my_prs                 BOOLEAN NOT NULL DEFAULT TRUE,
  wip_prs                BOOLEAN NOT NULL DEFAULT TRUE,
  startrek               BOOLEAN NOT NULL DEFAULT TRUE
  -- timezone_offset        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews.cache_gaps (
  staff_login   TEXT PRIMARY KEY,
  gaps          JSONB NOT NULL DEFAULT '[]'::JSONB
);

CREATE TABLE IF NOT EXISTS reviews.subordinated (
  staff_login   TEXT PRIMARY KEY,
  nearest       TEXT[],
  all           TEXT[]
);

CREATE TABLE IF NOT EXISTS reviews.nda_links (
  url    TEXT PRIMARY KEY,
  nda    TEXT
);

