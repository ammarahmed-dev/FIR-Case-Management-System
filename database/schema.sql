-- =====================================================================
-- FIR and Criminal Case Management System (FIR-CMS)
-- File 1 of 3: schema (27 tables, 3NF)
-- Target: MySQL 8.0.16+ (CHECK constraints are enforced from 8.0.16)
-- =====================================================================

DROP DATABASE IF EXISTS fir_ccms;
CREATE DATABASE fir_ccms
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE fir_ccms;
SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- A. Reference data: places, ranks, law
-- ---------------------------------------------------------------------

CREATE TABLE districts (
  district_id   TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name          VARCHAR(60)  NOT NULL,
  province      VARCHAR(40)  NOT NULL,
  PRIMARY KEY (district_id),
  UNIQUE KEY uq_districts_name (name)
) ENGINE=InnoDB;

CREATE TABLE police_stations (
  station_id    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  station_code  CHAR(3)      NOT NULL,
  name          VARCHAR(80)  NOT NULL,
  district_id   TINYINT UNSIGNED NOT NULL,
  address       VARCHAR(150) NOT NULL,
  phone         VARCHAR(20)  NULL,
  PRIMARY KEY (station_id),
  UNIQUE KEY uq_stations_code (station_code),
  UNIQUE KEY uq_stations_name (name),
  KEY ix_stations_district (district_id),
  CONSTRAINT fk_stations_district FOREIGN KEY (district_id) REFERENCES districts (district_id),
  CONSTRAINT chk_stations_code  CHECK (station_code REGEXP '^[A-Z]{3}$'),
  CONSTRAINT chk_stations_phone CHECK (phone IS NULL OR phone REGEXP '^[0-9+() -]{7,20}$')
) ENGINE=InnoDB;

CREATE TABLE ranks (
  rank_id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title            VARCHAR(40)  NOT NULL,
  rank_level       TINYINT UNSIGNED NOT NULL,
  can_investigate  BOOLEAN      NOT NULL DEFAULT FALSE,
  PRIMARY KEY (rank_id),
  UNIQUE KEY uq_ranks_title (title),
  UNIQUE KEY uq_ranks_level (rank_level),
  CONSTRAINT chk_ranks_level CHECK (rank_level BETWEEN 1 AND 10)
) ENGINE=InnoDB;

CREATE TABLE crime_categories (
  category_id   TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name          VARCHAR(60)  NOT NULL,
  description   VARCHAR(200) NULL,
  PRIMARY KEY (category_id),
  UNIQUE KEY uq_categories_name (name)
) ENGINE=InnoDB;

CREATE TABLE legal_sections (
  section_id          SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  act                 VARCHAR(20)  NOT NULL,
  section_no          VARCHAR(12)  NOT NULL,
  title               VARCHAR(150) NOT NULL,
  category_id         TINYINT UNSIGNED NOT NULL,
  punishment_summary  VARCHAR(120) NOT NULL,
  is_cognizable       BOOLEAN      NOT NULL,
  is_bailable         BOOLEAN      NOT NULL,
  PRIMARY KEY (section_id),
  UNIQUE KEY uq_sections_act_no (act, section_no),
  KEY ix_sections_category (category_id),
  CONSTRAINT fk_sections_category FOREIGN KEY (category_id) REFERENCES crime_categories (category_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- B. Police officers and system users
-- ---------------------------------------------------------------------

CREATE TABLE officers (
  officer_id     SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  badge_no       VARCHAR(12)  NOT NULL,
  full_name      VARCHAR(100) NOT NULL,
  rank_id        TINYINT UNSIGNED NOT NULL,
  station_id     SMALLINT UNSIGNED NOT NULL,
  supervisor_id  SMALLINT UNSIGNED NULL,
  phone          VARCHAR(20)  NULL,
  email          VARCHAR(120) NULL,
  joined_on      DATE         NOT NULL,
  is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
  PRIMARY KEY (officer_id),
  UNIQUE KEY uq_officers_badge (badge_no),
  UNIQUE KEY uq_officers_email (email),
  KEY ix_officers_rank (rank_id),
  KEY ix_officers_station (station_id),
  KEY ix_officers_supervisor (supervisor_id),
  CONSTRAINT fk_officers_rank       FOREIGN KEY (rank_id)       REFERENCES ranks (rank_id),
  CONSTRAINT fk_officers_station    FOREIGN KEY (station_id)    REFERENCES police_stations (station_id),
  CONSTRAINT fk_officers_supervisor FOREIGN KEY (supervisor_id) REFERENCES officers (officer_id),
  CONSTRAINT chk_officers_email CHECK (email IS NULL OR email REGEXP '^[^@ ]+@[^@ ]+\\.[^@ ]+$')
) ENGINE=InnoDB;

CREATE TABLE roles (
  role_id       TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  role_name     VARCHAR(40)  NOT NULL,
  description   VARCHAR(200) NOT NULL,
  PRIMARY KEY (role_id),
  UNIQUE KEY uq_roles_name (role_name)
) ENGINE=InnoDB;

CREATE TABLE users (
  user_id        SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username       VARCHAR(40) NOT NULL,
  password_hash  CHAR(64)    NOT NULL,
  role_id        TINYINT UNSIGNED NOT NULL,
  officer_id     SMALLINT UNSIGNED NULL,
  is_active      BOOLEAN     NOT NULL DEFAULT TRUE,
  created_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_users_username (username),
  UNIQUE KEY uq_users_officer (officer_id),
  KEY ix_users_role (role_id),
  CONSTRAINT fk_users_role    FOREIGN KEY (role_id)    REFERENCES roles (role_id),
  CONSTRAINT fk_users_officer FOREIGN KEY (officer_id) REFERENCES officers (officer_id),
  CONSTRAINT chk_users_username CHECK (username REGEXP '^[a-z][a-z0-9_]{3,39}$'),
  CONSTRAINT chk_users_hash     CHECK (password_hash REGEXP '^[0-9a-f]{64}$')
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- C. People involved in cases (one row per human, whatever their role)
-- ---------------------------------------------------------------------

CREATE TABLE persons (
  person_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  cnic           CHAR(15)     NULL,
  full_name      VARCHAR(100) NOT NULL,
  father_name    VARCHAR(100) NULL,
  gender         ENUM('Male','Female','Other') NOT NULL,
  date_of_birth  DATE         NULL,
  phone          VARCHAR(20)  NULL,
  address        VARCHAR(200) NULL,
  district_id    TINYINT UNSIGNED NULL,
  occupation     VARCHAR(60)  NULL,
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (person_id),
  UNIQUE KEY uq_persons_cnic (cnic),
  KEY ix_persons_name (full_name),
  KEY ix_persons_district (district_id),
  CONSTRAINT fk_persons_district FOREIGN KEY (district_id) REFERENCES districts (district_id),
  CONSTRAINT chk_persons_cnic  CHECK (cnic IS NULL OR cnic REGEXP '^[0-9]{5}-[0-9]{7}-[0-9]$'),
  CONSTRAINT chk_persons_phone CHECK (phone IS NULL OR phone REGEXP '^[0-9+() -]{7,20}$')
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- D. FIR and everything attached to it
-- ---------------------------------------------------------------------

CREATE TABLE firs (
  fir_id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
  station_id             SMALLINT UNSIGNED NOT NULL,
  fir_serial             SMALLINT UNSIGNED NOT NULL,
  reported_at            DATETIME     NOT NULL,
  fir_year               SMALLINT     GENERATED ALWAYS AS (YEAR(reported_at)) STORED,
  complainant_person_id  INT UNSIGNED NULL,
  complainant_officer_id SMALLINT UNSIGNED NULL,
  registered_by          SMALLINT UNSIGNED NOT NULL,
  incident_at            DATETIME     NOT NULL,
  incident_location      VARCHAR(200) NOT NULL,
  category_id            TINYINT UNSIGNED NOT NULL,
  description            TEXT         NOT NULL,
  status                 ENUM('Registered','Under Investigation','Challaned','In Court','Closed','Cancelled')
                         NOT NULL DEFAULT 'Registered',
  closure_remarks        VARCHAR(250) NULL,
  created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (fir_id),
  UNIQUE KEY uq_firs_station_year_serial (station_id, fir_year, fir_serial),
  KEY ix_firs_status (status),
  KEY ix_firs_reported (reported_at),
  KEY ix_firs_category (category_id),
  KEY ix_firs_complainant (complainant_person_id),
  KEY ix_firs_complainant_officer (complainant_officer_id),
  KEY ix_firs_registered_by (registered_by),
  CONSTRAINT fk_firs_station      FOREIGN KEY (station_id)             REFERENCES police_stations (station_id),
  CONSTRAINT fk_firs_complainant  FOREIGN KEY (complainant_person_id)  REFERENCES persons (person_id),
  CONSTRAINT fk_firs_comp_officer FOREIGN KEY (complainant_officer_id) REFERENCES officers (officer_id),
  CONSTRAINT fk_firs_registered   FOREIGN KEY (registered_by)          REFERENCES officers (officer_id),
  CONSTRAINT fk_firs_category     FOREIGN KEY (category_id)            REFERENCES crime_categories (category_id),
  CONSTRAINT chk_firs_times       CHECK (incident_at <= reported_at),
  CONSTRAINT chk_firs_one_complainant
    CHECK ((complainant_person_id IS NULL) <> (complainant_officer_id IS NULL)),
  CONSTRAINT chk_firs_closure
    CHECK (status NOT IN ('Cancelled') OR closure_remarks IS NOT NULL)
) ENGINE=InnoDB;

CREATE TABLE fir_sections (
  fir_id      INT UNSIGNED NOT NULL,
  section_id  SMALLINT UNSIGNED NOT NULL,
  PRIMARY KEY (fir_id, section_id),
  KEY ix_fir_sections_section (section_id),
  CONSTRAINT fk_fir_sections_fir     FOREIGN KEY (fir_id)     REFERENCES firs (fir_id),
  CONSTRAINT fk_fir_sections_section FOREIGN KEY (section_id) REFERENCES legal_sections (section_id)
) ENGINE=InnoDB;

CREATE TABLE fir_accused (
  fir_accused_id  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fir_id          INT UNSIGNED NOT NULL,
  person_id       INT UNSIGNED NOT NULL,
  status          ENUM('Nominated','Arrested','On Bail','Absconding','Convicted','Acquitted','Discharged')
                  NOT NULL DEFAULT 'Nominated',
  added_on        DATE NOT NULL,
  PRIMARY KEY (fir_accused_id),
  UNIQUE KEY uq_fir_accused (fir_id, person_id),
  KEY ix_fir_accused_person (person_id),
  KEY ix_fir_accused_status (status),
  CONSTRAINT fk_fir_accused_fir    FOREIGN KEY (fir_id)    REFERENCES firs (fir_id),
  CONSTRAINT fk_fir_accused_person FOREIGN KEY (person_id) REFERENCES persons (person_id)
) ENGINE=InnoDB;

CREATE TABLE fir_parties (
  party_id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fir_id      INT UNSIGNED NOT NULL,
  person_id   INT UNSIGNED NOT NULL,
  party_role  ENUM('Victim','Witness') NOT NULL,
  statement   TEXT NULL,
  PRIMARY KEY (party_id),
  UNIQUE KEY uq_fir_parties (fir_id, person_id, party_role),
  KEY ix_fir_parties_person (person_id),
  CONSTRAINT fk_fir_parties_fir    FOREIGN KEY (fir_id)    REFERENCES firs (fir_id),
  CONSTRAINT fk_fir_parties_person FOREIGN KEY (person_id) REFERENCES persons (person_id)
) ENGINE=InnoDB;

CREATE TABLE fir_status_history (
  history_id  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  fir_id      INT UNSIGNED NOT NULL,
  old_status  VARCHAR(20) NULL,
  new_status  VARCHAR(20) NOT NULL,
  changed_at  DATETIME    NOT NULL,
  changed_by  VARCHAR(80) NOT NULL,
  PRIMARY KEY (history_id),
  KEY ix_status_history_fir (fir_id, changed_at),
  CONSTRAINT fk_status_history_fir FOREIGN KEY (fir_id) REFERENCES firs (fir_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- E. Investigation
-- ---------------------------------------------------------------------

CREATE TABLE investigation_assignments (
  assignment_id  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fir_id         INT UNSIGNED NOT NULL,
  officer_id     SMALLINT UNSIGNED NOT NULL,
  assigned_on    DATE NOT NULL,
  ended_on       DATE NULL,
  reason         VARCHAR(150) NULL,
  -- equals fir_id while the assignment is open, NULL once it ends.
  -- The UNIQUE key below therefore allows only ONE open investigator per FIR.
  active_fir_id  INT UNSIGNED GENERATED ALWAYS AS (IF(ended_on IS NULL, fir_id, NULL)) STORED,
  PRIMARY KEY (assignment_id),
  UNIQUE KEY uq_one_active_io (active_fir_id),
  KEY ix_assign_fir (fir_id),
  KEY ix_assign_officer (officer_id),
  CONSTRAINT fk_assign_fir     FOREIGN KEY (fir_id)     REFERENCES firs (fir_id),
  CONSTRAINT fk_assign_officer FOREIGN KEY (officer_id) REFERENCES officers (officer_id),
  CONSTRAINT chk_assign_dates  CHECK (ended_on IS NULL OR ended_on >= assigned_on)
) ENGINE=InnoDB;

CREATE TABLE case_diary (
  diary_id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fir_id      INT UNSIGNED NOT NULL,
  officer_id  SMALLINT UNSIGNED NOT NULL,
  entry_date  DATE NOT NULL,
  entry_text  TEXT NOT NULL,
  PRIMARY KEY (diary_id),
  KEY ix_diary_fir_date (fir_id, entry_date),
  KEY ix_diary_officer (officer_id),
  CONSTRAINT fk_diary_fir     FOREIGN KEY (fir_id)     REFERENCES firs (fir_id),
  CONSTRAINT fk_diary_officer FOREIGN KEY (officer_id) REFERENCES officers (officer_id)
) ENGINE=InnoDB;

CREATE TABLE arrests (
  arrest_id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fir_accused_id  INT UNSIGNED NOT NULL,
  arrested_by     SMALLINT UNSIGNED NOT NULL,
  arrested_at     DATETIME NOT NULL,
  location        VARCHAR(200) NOT NULL,
  remand_days     TINYINT UNSIGNED NOT NULL DEFAULT 0,
  released_at     DATETIME NULL,
  PRIMARY KEY (arrest_id),
  KEY ix_arrests_accused (fir_accused_id),
  KEY ix_arrests_officer (arrested_by),
  CONSTRAINT fk_arrests_accused FOREIGN KEY (fir_accused_id) REFERENCES fir_accused (fir_accused_id),
  CONSTRAINT fk_arrests_officer FOREIGN KEY (arrested_by)    REFERENCES officers (officer_id),
  CONSTRAINT chk_arrests_remand   CHECK (remand_days <= 14),
  CONSTRAINT chk_arrests_released CHECK (released_at IS NULL OR released_at > arrested_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- F. Evidence, chain of custody and forensic reports
-- ---------------------------------------------------------------------

CREATE TABLE evidence_types (
  type_id     TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name        VARCHAR(50) NOT NULL,
  is_digital  BOOLEAN     NOT NULL DEFAULT FALSE,
  PRIMARY KEY (type_id),
  UNIQUE KEY uq_evidence_types_name (name)
) ENGINE=InnoDB;

CREATE TABLE evidence (
  evidence_id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  evidence_no           VARCHAR(20)  NOT NULL,
  fir_id                INT UNSIGNED NOT NULL,
  type_id               TINYINT UNSIGNED NOT NULL,
  description           VARCHAR(250) NOT NULL,
  collected_by          SMALLINT UNSIGNED NOT NULL,
  collected_at          DATETIME     NOT NULL,
  found_location        VARCHAR(200) NULL,
  current_custodian_id  SMALLINT UNSIGNED NOT NULL,
  storage_location      VARCHAR(100) NULL,
  status                ENUM('In Malkhana','With Investigator','At Forensic Lab','Produced in Court','Returned','Destroyed')
                        NOT NULL DEFAULT 'In Malkhana',
  hash_sha256           CHAR(64) NULL,
  PRIMARY KEY (evidence_id),
  UNIQUE KEY uq_evidence_no (evidence_no),
  KEY ix_evidence_fir (fir_id),
  KEY ix_evidence_type (type_id),
  KEY ix_evidence_collector (collected_by),
  KEY ix_evidence_custodian (current_custodian_id),
  CONSTRAINT fk_evidence_fir       FOREIGN KEY (fir_id)               REFERENCES firs (fir_id),
  CONSTRAINT fk_evidence_type      FOREIGN KEY (type_id)              REFERENCES evidence_types (type_id),
  CONSTRAINT fk_evidence_collector FOREIGN KEY (collected_by)         REFERENCES officers (officer_id),
  CONSTRAINT fk_evidence_custodian FOREIGN KEY (current_custodian_id) REFERENCES officers (officer_id),
  CONSTRAINT chk_evidence_hash CHECK (hash_sha256 IS NULL OR hash_sha256 REGEXP '^[0-9a-f]{64}$')
) ENGINE=InnoDB;

CREATE TABLE evidence_custody_log (
  log_id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  evidence_id      INT UNSIGNED NOT NULL,
  from_officer_id  SMALLINT UNSIGNED NULL,
  to_officer_id    SMALLINT UNSIGNED NOT NULL,
  transferred_at   DATETIME     NOT NULL,
  purpose          VARCHAR(150) NOT NULL,
  PRIMARY KEY (log_id),
  KEY ix_custody_evidence (evidence_id, transferred_at),
  KEY ix_custody_from (from_officer_id),
  KEY ix_custody_to (to_officer_id),
  CONSTRAINT fk_custody_evidence FOREIGN KEY (evidence_id)     REFERENCES evidence (evidence_id),
  CONSTRAINT fk_custody_from     FOREIGN KEY (from_officer_id) REFERENCES officers (officer_id),
  CONSTRAINT fk_custody_to       FOREIGN KEY (to_officer_id)   REFERENCES officers (officer_id),
  CONSTRAINT chk_custody_diff    CHECK (from_officer_id IS NULL OR from_officer_id <> to_officer_id)
) ENGINE=InnoDB;

CREATE TABLE lab_reports (
  report_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  evidence_id   INT UNSIGNED NOT NULL,
  lab_name      VARCHAR(100) NOT NULL,
  report_type   ENUM('Fingerprint','DNA','Ballistics','Chemical','Digital Forensics','Document','Other') NOT NULL,
  submitted_on  DATE NOT NULL,
  reported_on   DATE NULL,
  findings      TEXT NULL,
  PRIMARY KEY (report_id),
  KEY ix_lab_evidence (evidence_id),
  CONSTRAINT fk_lab_evidence FOREIGN KEY (evidence_id) REFERENCES evidence (evidence_id),
  CONSTRAINT chk_lab_dates   CHECK (reported_on IS NULL OR reported_on >= submitted_on),
  CONSTRAINT chk_lab_findings CHECK ((reported_on IS NULL) = (findings IS NULL))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- G. Courts, trials, bail and verdicts
-- ---------------------------------------------------------------------

CREATE TABLE courts (
  court_id     SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name         VARCHAR(100) NOT NULL,
  court_type   ENUM('Magistrate','Sessions','Anti-Terrorism','Special (Cyber)','High Court') NOT NULL,
  district_id  TINYINT UNSIGNED NOT NULL,
  address      VARCHAR(150) NULL,
  PRIMARY KEY (court_id),
  UNIQUE KEY uq_courts_name (name),
  KEY ix_courts_district (district_id),
  CONSTRAINT fk_courts_district FOREIGN KEY (district_id) REFERENCES districts (district_id)
) ENGINE=InnoDB;

CREATE TABLE judges (
  judge_id      SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  full_name     VARCHAR(100) NOT NULL,
  court_id      SMALLINT UNSIGNED NOT NULL,
  appointed_on  DATE NOT NULL,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (judge_id),
  KEY ix_judges_court (court_id),
  CONSTRAINT fk_judges_court FOREIGN KEY (court_id) REFERENCES courts (court_id)
) ENGINE=InnoDB;

CREATE TABLE court_cases (
  case_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  case_number  VARCHAR(30) NOT NULL,
  fir_id       INT UNSIGNED NOT NULL,
  court_id     SMALLINT UNSIGNED NOT NULL,
  filed_on     DATE NOT NULL,
  status       ENUM('Pending','Under Trial','Decided','Withdrawn') NOT NULL DEFAULT 'Pending',
  PRIMARY KEY (case_id),
  UNIQUE KEY uq_case_number (case_number),
  UNIQUE KEY uq_case_fir_court (fir_id, court_id),
  KEY ix_cases_court (court_id),
  KEY ix_cases_status (status),
  CONSTRAINT fk_cases_fir   FOREIGN KEY (fir_id)   REFERENCES firs (fir_id),
  CONSTRAINT fk_cases_court FOREIGN KEY (court_id) REFERENCES courts (court_id)
) ENGINE=InnoDB;

CREATE TABLE hearings (
  hearing_id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  case_id            INT UNSIGNED NOT NULL,
  hearing_date       DATE NOT NULL,
  judge_id           SMALLINT UNSIGNED NOT NULL,
  purpose            ENUM('Charge Framing','Evidence','Witness Examination','Arguments','Judgment','Bail Hearing','Other') NOT NULL,
  outcome            VARCHAR(200) NULL,
  next_hearing_date  DATE NULL,
  PRIMARY KEY (hearing_id),
  UNIQUE KEY uq_hearing_case_date (case_id, hearing_date),
  KEY ix_hearings_judge (judge_id),
  KEY ix_hearings_next (next_hearing_date),
  CONSTRAINT fk_hearings_case  FOREIGN KEY (case_id)  REFERENCES court_cases (case_id),
  CONSTRAINT fk_hearings_judge FOREIGN KEY (judge_id) REFERENCES judges (judge_id),
  CONSTRAINT chk_hearings_next CHECK (next_hearing_date IS NULL OR next_hearing_date > hearing_date)
) ENGINE=InnoDB;

CREATE TABLE bail_applications (
  bail_id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fir_accused_id  INT UNSIGNED NOT NULL,
  court_id        SMALLINT UNSIGNED NOT NULL,
  bail_type       ENUM('Pre-arrest','Post-arrest') NOT NULL,
  applied_on      DATE NOT NULL,
  decided_on      DATE NULL,
  decision        ENUM('Pending','Granted','Rejected','Withdrawn') NOT NULL DEFAULT 'Pending',
  surety_amount   DECIMAL(12,2) NULL,
  remarks         VARCHAR(200) NULL,
  PRIMARY KEY (bail_id),
  KEY ix_bail_accused (fir_accused_id),
  KEY ix_bail_court (court_id),
  CONSTRAINT fk_bail_accused FOREIGN KEY (fir_accused_id) REFERENCES fir_accused (fir_accused_id),
  CONSTRAINT fk_bail_court   FOREIGN KEY (court_id)       REFERENCES courts (court_id),
  CONSTRAINT chk_bail_dates    CHECK (decided_on IS NULL OR decided_on >= applied_on),
  CONSTRAINT chk_bail_decided  CHECK ((decision = 'Pending') = (decided_on IS NULL)),
  CONSTRAINT chk_bail_surety   CHECK (decision <> 'Granted' OR surety_amount IS NOT NULL),
  CONSTRAINT chk_bail_amount   CHECK (surety_amount IS NULL OR surety_amount > 0)
) ENGINE=InnoDB;

CREATE TABLE verdicts (
  verdict_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  case_id         INT UNSIGNED NOT NULL,
  fir_accused_id  INT UNSIGNED NOT NULL,
  verdict         ENUM('Convicted','Acquitted','Discharged') NOT NULL,
  verdict_on      DATE NOT NULL,
  sentence_years  DECIMAL(4,1) NULL,
  fine_amount     DECIMAL(12,2) NOT NULL DEFAULT 0,
  remarks         VARCHAR(200) NULL,
  PRIMARY KEY (verdict_id),
  UNIQUE KEY uq_verdict_case_accused (case_id, fir_accused_id),
  KEY ix_verdict_accused (fir_accused_id),
  CONSTRAINT fk_verdict_case    FOREIGN KEY (case_id)        REFERENCES court_cases (case_id),
  CONSTRAINT fk_verdict_accused FOREIGN KEY (fir_accused_id) REFERENCES fir_accused (fir_accused_id),
  CONSTRAINT chk_verdict_sentence CHECK (
      (verdict = 'Convicted' AND sentence_years IS NOT NULL AND sentence_years > 0)
   OR (verdict <> 'Convicted' AND sentence_years IS NULL AND fine_amount = 0)),
  CONSTRAINT chk_verdict_fine CHECK (fine_amount >= 0)
) ENGINE=InnoDB;
