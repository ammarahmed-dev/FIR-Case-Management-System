# Data dictionary

27 tables. Generated from the live database by `python3 tools/build_docs.py`; do not edit by hand.

| Table | Rows (sample data) | Purpose |
|---|---:|---|
| [`arrests`](#arrests) | 17 | Arrests of accused persons, with remand days and release time. |
| [`bail_applications`](#bail_applications) | 18 | Bail applications (before or after arrest) and the court's decision. |
| [`case_diary`](#case_diary) | 51 | Day-by-day notes of the investigating officer. |
| [`court_cases`](#court_cases) | 13 | Cases filed in court on the basis of an FIR. |
| [`courts`](#courts) | 10 | Courts that hear cases. |
| [`crime_categories`](#crime_categories) | 7 | Broad crime groups used for statistics (person, property, cyber, narcotics and so on). |
| [`districts`](#districts) | 6 | Districts the force works in, with their province. |
| [`evidence`](#evidence) | 35 | Exhibits collected for an FIR, their current custodian and status. |
| [`evidence_custody_log`](#evidence_custody_log) | 99 | Chain of custody. Every hand-over of an exhibit, written by a trigger. |
| [`evidence_types`](#evidence_types) | 9 | Kinds of exhibit. The is_digital flag makes the SHA-256 hash mandatory. |
| [`fir_accused`](#fir_accused) | 24 | Accused persons of an FIR and where each one stands (nominated, arrested, on bail, convicted ...). |
| [`fir_parties`](#fir_parties) | 28 | Victims and witnesses of an FIR, with their statements. |
| [`fir_sections`](#fir_sections) | 32 | Which sections of law an FIR was registered under (many to many). |
| [`fir_status_history`](#fir_status_history) | 79 | Audit trail of every FIR status change. Filled by a trigger. |
| [`firs`](#firs) | 24 | First Information Reports. The central table of the system. |
| [`hearings`](#hearings) | 44 | Each court hearing of a case, with the next date fixed. |
| [`investigation_assignments`](#investigation_assignments) | 22 | Which officer investigated an FIR, and when. Only one open assignment per FIR. |
| [`judges`](#judges) | 12 | Judges and the court each one sits in. |
| [`lab_reports`](#lab_reports) | 11 | Forensic laboratory submissions and findings for an exhibit. |
| [`legal_sections`](#legal_sections) | 17 | Sections of law an FIR can be registered under, with cognizable and bailable flags. |
| [`officers`](#officers) | 28 | Police officers. Each is posted at one station and may report to a supervisor (self reference). |
| [`persons`](#persons) | 63 | Every human who appears in a case. One row per person whatever their role, so a person's history is in one place. |
| [`police_stations`](#police_stations) | 8 | Police stations. Each belongs to one district and has a three-letter code used in FIR numbers. |
| [`ranks`](#ranks) | 7 | Police ranks in order of seniority. The can_investigate flag says which ranks may lead an investigation. |
| [`roles`](#roles) | 6 | User roles of the system (administrator, SHO, investigating officer and so on). |
| [`users`](#users) | 9 | Login accounts. A user may be linked to an officer. |
| [`verdicts`](#verdicts) | 5 | Final verdict for each accused person in a case. |

## arrests

Arrests of accused persons, with remand days and release time.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `arrest_id` | int unsigned | NO | PK | auto number |
| `fir_accused_id` | int unsigned | NO |  | FK to `fir_accused.fir_accused_id` |
| `arrested_by` | smallint unsigned | NO |  | FK to `officers.officer_id` |
| `arrested_at` | datetime | NO |  |  |
| `location` | varchar(200) | NO |  |  |
| `remand_days` | tinyint unsigned | NO |  | default 0 |
| `released_at` | datetime | YES |  |  |

**Check constraints:**

- `chk_arrests_released`: `((`released_at` is null) or (`released_at` > `arrested_at`))`
- `chk_arrests_remand`: `(`remand_days` <= 14)`

**Triggers:** `trg_arrests_ai` (AFTER INSERT); `trg_arrests_bi` (BEFORE INSERT)

## bail_applications

Bail applications (before or after arrest) and the court's decision.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `bail_id` | int unsigned | NO | PK | auto number |
| `fir_accused_id` | int unsigned | NO |  | FK to `fir_accused.fir_accused_id` |
| `court_id` | smallint unsigned | NO |  | FK to `courts.court_id` |
| `bail_type` | enum('Pre-arrest','Post-arrest') | NO |  |  |
| `applied_on` | date | NO |  |  |
| `decided_on` | date | YES |  |  |
| `decision` | enum('Pending','Granted','Rejected','Withdrawn') | NO |  | default Pending |
| `surety_amount` | decimal(12,2) | YES |  |  |
| `remarks` | varchar(200) | YES |  |  |

**Check constraints:**

- `chk_bail_amount`: `((`surety_amount` is null) or (`surety_amount` > 0))`
- `chk_bail_dates`: `((`decided_on` is null) or (`decided_on` >= `applied_on`))`
- `chk_bail_decided`: `((`decision` = _utf8mb4\\'Pending\\') = (`decided_on` is null))`
- `chk_bail_surety`: `((`decision` <> _utf8mb4\\'Granted\\') or (`surety_amount` is not null))`

**Triggers:** `trg_bail_au` (AFTER UPDATE); `trg_bail_bi` (BEFORE INSERT)

## case_diary

Day-by-day notes of the investigating officer.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `diary_id` | int unsigned | NO | PK | auto number |
| `fir_id` | int unsigned | NO |  | FK to `firs.fir_id` |
| `officer_id` | smallint unsigned | NO |  | FK to `officers.officer_id` |
| `entry_date` | date | NO |  |  |
| `entry_text` | text | NO |  |  |

**Triggers:** `trg_diary_bi` (BEFORE INSERT)

## court_cases

Cases filed in court on the basis of an FIR.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `case_id` | int unsigned | NO | PK | auto number |
| `case_number` | varchar(30) | NO | UNIQUE |  |
| `fir_id` | int unsigned | NO |  | FK to `firs.fir_id` |
| `court_id` | smallint unsigned | NO |  | FK to `courts.court_id` |
| `filed_on` | date | NO |  |  |
| `status` | enum('Pending','Under Trial','Decided','Withdrawn') | NO |  | default Pending |

**Unique keys:** `uq_case_fir_court` (fir_id,court_id); `uq_case_number` (case_number)

**Triggers:** `trg_cases_bi` (BEFORE INSERT)

## courts

Courts that hear cases.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `court_id` | smallint unsigned | NO | PK | auto number |
| `name` | varchar(100) | NO | UNIQUE |  |
| `court_type` | enum('Magistrate','Sessions','Anti-Terrorism','Special (Cyber)','High Court') | NO |  |  |
| `district_id` | tinyint unsigned | NO |  | FK to `districts.district_id` |
| `address` | varchar(150) | YES |  |  |

**Unique keys:** `uq_courts_name` (name)

## crime_categories

Broad crime groups used for statistics (person, property, cyber, narcotics and so on).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `category_id` | tinyint unsigned | NO | PK | auto number |
| `name` | varchar(60) | NO | UNIQUE |  |
| `description` | varchar(200) | YES |  |  |

**Unique keys:** `uq_categories_name` (name)

## districts

Districts the force works in, with their province.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `district_id` | tinyint unsigned | NO | PK | auto number |
| `name` | varchar(60) | NO | UNIQUE |  |
| `province` | varchar(40) | NO |  |  |

**Unique keys:** `uq_districts_name` (name)

## evidence

Exhibits collected for an FIR, their current custodian and status.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `evidence_id` | int unsigned | NO | PK | auto number |
| `evidence_no` | varchar(20) | NO | UNIQUE |  |
| `fir_id` | int unsigned | NO |  | FK to `firs.fir_id` |
| `type_id` | tinyint unsigned | NO |  | FK to `evidence_types.type_id` |
| `description` | varchar(250) | NO |  |  |
| `collected_by` | smallint unsigned | NO |  | FK to `officers.officer_id` |
| `collected_at` | datetime | NO |  |  |
| `found_location` | varchar(200) | YES |  |  |
| `current_custodian_id` | smallint unsigned | NO |  | FK to `officers.officer_id` |
| `storage_location` | varchar(100) | YES |  |  |
| `status` | enum('In Malkhana','With Investigator','At Forensic Lab','Produced in Court','Returned','Destroyed') | NO |  | default In Malkhana |
| `hash_sha256` | char(64) | YES |  |  |

**Unique keys:** `uq_evidence_no` (evidence_no)

**Check constraints:**

- `chk_evidence_hash`: `((`hash_sha256` is null) or regexp_like(`hash_sha256`,_utf8mb4\\'^[0-9a-f]{64}$\\'))`

**Triggers:** `trg_evidence_ai` (AFTER INSERT); `trg_evidence_au` (AFTER UPDATE); `trg_evidence_bi` (BEFORE INSERT); `trg_evidence_bu` (BEFORE UPDATE)

## evidence_custody_log

Chain of custody. Every hand-over of an exhibit, written by a trigger.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `log_id` | bigint unsigned | NO | PK | auto number |
| `evidence_id` | int unsigned | NO |  | FK to `evidence.evidence_id` |
| `from_officer_id` | smallint unsigned | YES |  | FK to `officers.officer_id` |
| `to_officer_id` | smallint unsigned | NO |  | FK to `officers.officer_id` |
| `transferred_at` | datetime | NO |  |  |
| `purpose` | varchar(150) | NO |  |  |

**Check constraints:**

- `chk_custody_diff`: `((`from_officer_id` is null) or (`from_officer_id` <> `to_officer_id`))`

## evidence_types

Kinds of exhibit. The is_digital flag makes the SHA-256 hash mandatory.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `type_id` | tinyint unsigned | NO | PK | auto number |
| `name` | varchar(50) | NO | UNIQUE |  |
| `is_digital` | tinyint(1) | NO |  | default 0 |

**Unique keys:** `uq_evidence_types_name` (name)

## fir_accused

Accused persons of an FIR and where each one stands (nominated, arrested, on bail, convicted ...).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `fir_accused_id` | int unsigned | NO | PK | auto number |
| `fir_id` | int unsigned | NO |  | FK to `firs.fir_id` |
| `person_id` | int unsigned | NO |  | FK to `persons.person_id` |
| `status` | enum('Nominated','Arrested','On Bail','Absconding','Convicted','Acquitted','Discharged') | NO |  | default Nominated |
| `added_on` | date | NO |  |  |

**Unique keys:** `uq_fir_accused` (fir_id,person_id)

**Triggers:** `trg_fir_accused_bi` (BEFORE INSERT)

## fir_parties

Victims and witnesses of an FIR, with their statements.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `party_id` | int unsigned | NO | PK | auto number |
| `fir_id` | int unsigned | NO |  | FK to `firs.fir_id` |
| `person_id` | int unsigned | NO |  | FK to `persons.person_id` |
| `party_role` | enum('Victim','Witness') | NO |  |  |
| `statement` | text | YES |  |  |

**Unique keys:** `uq_fir_parties` (fir_id,person_id,party_role)

**Triggers:** `trg_fir_parties_bi` (BEFORE INSERT)

## fir_sections

Which sections of law an FIR was registered under (many to many).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `fir_id` | int unsigned | NO | PK | FK to `firs.fir_id` |
| `section_id` | smallint unsigned | NO | PK | FK to `legal_sections.section_id` |

## fir_status_history

Audit trail of every FIR status change. Filled by a trigger.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `history_id` | bigint unsigned | NO | PK | auto number |
| `fir_id` | int unsigned | NO |  | FK to `firs.fir_id` |
| `old_status` | varchar(20) | YES |  |  |
| `new_status` | varchar(20) | NO |  |  |
| `changed_at` | datetime | NO |  |  |
| `changed_by` | varchar(80) | NO |  |  |

## firs

First Information Reports. The central table of the system.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `fir_id` | int unsigned | NO | PK | auto number |
| `station_id` | smallint unsigned | NO |  | FK to `police_stations.station_id` |
| `fir_serial` | smallint unsigned | NO |  |  |
| `reported_at` | datetime | NO |  |  |
| `fir_year` | smallint | YES |  | generated column |
| `complainant_person_id` | int unsigned | YES |  | FK to `persons.person_id` |
| `complainant_officer_id` | smallint unsigned | YES |  | FK to `officers.officer_id` |
| `registered_by` | smallint unsigned | NO |  | FK to `officers.officer_id` |
| `incident_at` | datetime | NO |  |  |
| `incident_location` | varchar(200) | NO |  |  |
| `category_id` | tinyint unsigned | NO |  | FK to `crime_categories.category_id` |
| `description` | text | NO |  |  |
| `status` | enum('Registered','Under Investigation','Challaned','In Court','Closed','Cancelled') | NO |  | default Registered |
| `closure_remarks` | varchar(250) | YES |  |  |
| `created_at` | datetime | NO |  | generated column; default CURRENT_TIMESTAMP |

**Unique keys:** `uq_firs_station_year_serial` (station_id,fir_year,fir_serial)

**Check constraints:**

- `chk_firs_closure`: `((`status` <> _utf8mb4\\'Cancelled\\') or (`closure_remarks` is not null))`
- `chk_firs_one_complainant`: `((`complainant_person_id` is null) <> (`complainant_officer_id` is null))`
- `chk_firs_times`: `(`incident_at` <= `reported_at`)`

**Triggers:** `trg_firs_ai` (AFTER INSERT); `trg_firs_au` (AFTER UPDATE); `trg_firs_bd` (BEFORE DELETE); `trg_firs_bi` (BEFORE INSERT); `trg_firs_bu` (BEFORE UPDATE)

## hearings

Each court hearing of a case, with the next date fixed.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `hearing_id` | int unsigned | NO | PK | auto number |
| `case_id` | int unsigned | NO |  | FK to `court_cases.case_id` |
| `hearing_date` | date | NO |  |  |
| `judge_id` | smallint unsigned | NO |  | FK to `judges.judge_id` |
| `purpose` | enum('Charge Framing','Evidence','Witness Examination','Arguments','Judgment','Bail Hearing','Other') | NO |  |  |
| `outcome` | varchar(200) | YES |  |  |
| `next_hearing_date` | date | YES |  |  |

**Unique keys:** `uq_hearing_case_date` (case_id,hearing_date)

**Check constraints:**

- `chk_hearings_next`: `((`next_hearing_date` is null) or (`next_hearing_date` > `hearing_date`))`

**Triggers:** `trg_hearings_ai` (AFTER INSERT); `trg_hearings_bi` (BEFORE INSERT)

## investigation_assignments

Which officer investigated an FIR, and when. Only one open assignment per FIR.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `assignment_id` | int unsigned | NO | PK | auto number |
| `fir_id` | int unsigned | NO |  | FK to `firs.fir_id` |
| `officer_id` | smallint unsigned | NO |  | FK to `officers.officer_id` |
| `assigned_on` | date | NO |  |  |
| `ended_on` | date | YES |  |  |
| `reason` | varchar(150) | YES |  |  |
| `active_fir_id` | int unsigned | YES | UNIQUE | generated column |

**Unique keys:** `uq_one_active_io` (active_fir_id)

**Check constraints:**

- `chk_assign_dates`: `((`ended_on` is null) or (`ended_on` >= `assigned_on`))`

**Triggers:** `trg_assign_bi` (BEFORE INSERT)

## judges

Judges and the court each one sits in.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `judge_id` | smallint unsigned | NO | PK | auto number |
| `full_name` | varchar(100) | NO |  |  |
| `court_id` | smallint unsigned | NO |  | FK to `courts.court_id` |
| `appointed_on` | date | NO |  |  |
| `is_active` | tinyint(1) | NO |  | default 1 |

## lab_reports

Forensic laboratory submissions and findings for an exhibit.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `report_id` | int unsigned | NO | PK | auto number |
| `evidence_id` | int unsigned | NO |  | FK to `evidence.evidence_id` |
| `lab_name` | varchar(100) | NO |  |  |
| `report_type` | enum('Fingerprint','DNA','Ballistics','Chemical','Digital Forensics','Document','Other') | NO |  |  |
| `submitted_on` | date | NO |  |  |
| `reported_on` | date | YES |  |  |
| `findings` | text | YES |  |  |

**Check constraints:**

- `chk_lab_dates`: `((`reported_on` is null) or (`reported_on` >= `submitted_on`))`
- `chk_lab_findings`: `((`reported_on` is null) = (`findings` is null))`

## legal_sections

Sections of law an FIR can be registered under, with cognizable and bailable flags.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `section_id` | smallint unsigned | NO | PK | auto number |
| `act` | varchar(20) | NO |  |  |
| `section_no` | varchar(12) | NO |  |  |
| `title` | varchar(150) | NO |  |  |
| `category_id` | tinyint unsigned | NO |  | FK to `crime_categories.category_id` |
| `punishment_summary` | varchar(120) | NO |  |  |
| `is_cognizable` | tinyint(1) | NO |  |  |
| `is_bailable` | tinyint(1) | NO |  |  |

**Unique keys:** `uq_sections_act_no` (act,section_no)

## officers

Police officers. Each is posted at one station and may report to a supervisor (self reference).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `officer_id` | smallint unsigned | NO | PK | auto number |
| `badge_no` | varchar(12) | NO | UNIQUE |  |
| `full_name` | varchar(100) | NO |  |  |
| `rank_id` | tinyint unsigned | NO |  | FK to `ranks.rank_id` |
| `station_id` | smallint unsigned | NO |  | FK to `police_stations.station_id` |
| `supervisor_id` | smallint unsigned | YES |  | FK to `officers.officer_id` |
| `phone` | varchar(20) | YES |  |  |
| `email` | varchar(120) | YES | UNIQUE |  |
| `joined_on` | date | NO |  |  |
| `is_active` | tinyint(1) | NO |  | default 1 |

**Unique keys:** `uq_officers_badge` (badge_no); `uq_officers_email` (email)

**Check constraints:**

- `chk_officers_email`: `((`email` is null) or regexp_like(`email`,_utf8mb4\\'^[^@ ]+@[^@ ]+\\\\\\\\.[^@ ]+$\\'))`

**Triggers:** `trg_officers_bu` (BEFORE UPDATE)

## persons

Every human who appears in a case. One row per person whatever their role, so a person's history is in one place.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `person_id` | int unsigned | NO | PK | auto number |
| `cnic` | char(15) | YES | UNIQUE |  |
| `full_name` | varchar(100) | NO |  |  |
| `father_name` | varchar(100) | YES |  |  |
| `gender` | enum('Male','Female','Other') | NO |  |  |
| `date_of_birth` | date | YES |  |  |
| `phone` | varchar(20) | YES |  |  |
| `address` | varchar(200) | YES |  |  |
| `district_id` | tinyint unsigned | YES |  | FK to `districts.district_id` |
| `occupation` | varchar(60) | YES |  |  |
| `created_at` | datetime | NO |  | generated column; default CURRENT_TIMESTAMP |

**Unique keys:** `uq_persons_cnic` (cnic)

**Check constraints:**

- `chk_persons_cnic`: `((`cnic` is null) or regexp_like(`cnic`,_utf8mb4\\'^[0-9]{5}-[0-9]{7}-[0-9]$\\'))`
- `chk_persons_phone`: `((`phone` is null) or regexp_like(`phone`,_utf8mb4\\'^[0-9+() -]{7,20}$\\'))`

## police_stations

Police stations. Each belongs to one district and has a three-letter code used in FIR numbers.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `station_id` | smallint unsigned | NO | PK | auto number |
| `station_code` | char(3) | NO | UNIQUE |  |
| `name` | varchar(80) | NO | UNIQUE |  |
| `district_id` | tinyint unsigned | NO |  | FK to `districts.district_id` |
| `address` | varchar(150) | NO |  |  |
| `phone` | varchar(20) | YES |  |  |

**Unique keys:** `uq_stations_code` (station_code); `uq_stations_name` (name)

**Check constraints:**

- `chk_stations_code`: `regexp_like(`station_code`,_utf8mb4\\'^[A-Z]{3}$\\')`
- `chk_stations_phone`: `((`phone` is null) or regexp_like(`phone`,_utf8mb4\\'^[0-9+() -]{7,20}$\\'))`

## ranks

Police ranks in order of seniority. The can_investigate flag says which ranks may lead an investigation.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `rank_id` | tinyint unsigned | NO | PK | auto number |
| `title` | varchar(40) | NO | UNIQUE |  |
| `rank_level` | tinyint unsigned | NO | UNIQUE |  |
| `can_investigate` | tinyint(1) | NO |  | default 0 |

**Unique keys:** `uq_ranks_level` (rank_level); `uq_ranks_title` (title)

**Check constraints:**

- `chk_ranks_level`: `(`rank_level` between 1 and 10)`

## roles

User roles of the system (administrator, SHO, investigating officer and so on).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `role_id` | tinyint unsigned | NO | PK | auto number |
| `role_name` | varchar(40) | NO | UNIQUE |  |
| `description` | varchar(200) | NO |  |  |

**Unique keys:** `uq_roles_name` (role_name)

## users

Login accounts. A user may be linked to an officer.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `user_id` | smallint unsigned | NO | PK | auto number |
| `username` | varchar(40) | NO | UNIQUE |  |
| `password_hash` | char(64) | NO |  |  |
| `role_id` | tinyint unsigned | NO |  | FK to `roles.role_id` |
| `officer_id` | smallint unsigned | YES | UNIQUE | FK to `officers.officer_id` |
| `is_active` | tinyint(1) | NO |  | default 1 |
| `created_at` | datetime | NO |  | generated column; default CURRENT_TIMESTAMP |

**Unique keys:** `uq_users_officer` (officer_id); `uq_users_username` (username)

**Check constraints:**

- `chk_users_hash`: `regexp_like(`password_hash`,_utf8mb4\\'^[0-9a-f]{64}$\\')`
- `chk_users_username`: `regexp_like(`username`,_utf8mb4\\'^[a-z][a-z0-9_]{3,39}$\\')`

## verdicts

Final verdict for each accused person in a case.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `verdict_id` | int unsigned | NO | PK | auto number |
| `case_id` | int unsigned | NO |  | FK to `court_cases.case_id` |
| `fir_accused_id` | int unsigned | NO |  | FK to `fir_accused.fir_accused_id` |
| `verdict` | enum('Convicted','Acquitted','Discharged') | NO |  |  |
| `verdict_on` | date | NO |  |  |
| `sentence_years` | decimal(4,1) | YES |  |  |
| `fine_amount` | decimal(12,2) | NO |  | default 0.00 |
| `remarks` | varchar(200) | YES |  |  |

**Unique keys:** `uq_verdict_case_accused` (case_id,fir_accused_id)

**Check constraints:**

- `chk_verdict_fine`: `(`fine_amount` >= 0)`
- `chk_verdict_sentence`: `(((`verdict` = _utf8mb4\\'Convicted\\') and (`sentence_years` is not null) and (`sentence_years` > 0)) or ((`verdict` <> _utf8mb4\\'Convicted\\') and (`sentence_years` is null) and (`fine_amount` = 0)))`

**Triggers:** `trg_verdicts_ai` (AFTER INSERT); `trg_verdicts_bi` (BEFORE INSERT)

