# FIR and Criminal Case Management System: Requirements Specification

| | |
|---|---|
| **Project** | FIR and Criminal Case Management System |
| **Field** | Criminology and Criminal Justice |
| **Course** | Database Management Systems |
| **Version** | 1.0 |

---

## 1. Purpose

This document lists what the database must do (functional requirements), how well it must do it (non-functional requirements) and the rules it enforces. Each requirement points to the table, constraint, trigger, procedure or view that implements it, so a reader can check any claim in the source files.

## 2. Scope

**In scope**
- The relational database: schema, constraints, triggers, stored procedures, views, sample data.
- Report queries and tests that show the database works.
- Documentation: ERD, data dictionary, project report.

**Out of scope**
- A graphical front end or web application.
- Biometric data (fingerprints, photographs), prison records, warrants, SMS or e-mail sending.
- Real personal data. All sample data is fictional.

---

## 3. Software and hardware

| Item | Requirement | Notes |
|---|---|---|
| Database server | **MySQL Community Server 8.0.16 or newer** | CHECK constraints are enforced from 8.0.16. Window functions and CTEs need 8.0. Tested on 8.0.46 |
| Storage engine | InnoDB | Foreign keys and transactions |
| Character set | utf8mb4 / utf8mb4_0900_ai_ci | Full Unicode for names |
| Client | `mysql` command line or MySQL Workbench 8.0 | The scripts use `DELIMITER` |
| Python 3 and Graphviz | Optional | Only to regenerate the sample data and documents |
| Docker | Optional | `docker compose up -d` starts a ready database |
| Hardware | 2 CPU cores, 2 GB RAM, 1 GB disk | The sample database is under 5 MB |
| Privileges | A user with `CREATE`, `DROP`, `CREATE ROUTINE`, `TRIGGER` | `root` is fine for development. If binary logging is on, trigger and function creation needs `SUPER` or `log_bin_trust_function_creators=1` for non-root users |

---

## 4. Users and roles

| Role | Main tasks |
|---|---|
| System Administrator | Manages users, roles and reference data |
| Station House Officer (SHO) | Heads a station, assigns investigating officers, watches workload and stale cases |
| Investigating Officer | Investigates assigned FIRs, writes the case diary, arrests, collects evidence |
| Records Clerk | Registers FIRs, persons and exhibits at the station |
| Court Liaison Officer | Files cases, records hearings, bail decisions and verdicts |
| Auditor | Read-only access to every record |

The roles are rows of the `roles` table and are linked to people through `users.role_id`. Database-level privileges for each role are listed in the report, section 7.6.

---

## 5. Functional requirements

Priority: **M** must have, **S** should have, **C** could have.

### 5.1 Reference data

| ID | Requirement | Pri | Implemented by |
|---|---|---|---|
| FR-01 | Store districts, police stations (with a unique three-letter code) and courts | M | `districts`, `police_stations`, `courts`, `chk_stations_code` |
| FR-02 | Store police ranks in order of seniority and mark which may investigate | M | `ranks.rank_level`, `ranks.can_investigate` |
| FR-03 | Store sections of law with cognizable and bailable flags, grouped by crime category | M | `legal_sections`, `crime_categories` |
| FR-04 | Store officers with rank, station, unique badge number, unique e-mail and a supervisor | M | `officers`, `fk_officers_supervisor`, `uq_officers_badge` |
| FR-05 | Deactivate an officer without deleting their history | M | `officers.is_active` |
| FR-06 | Store user accounts with a role, optionally linked to an officer | S | `users`, `roles` |

### 5.2 People

| ID | Requirement | Pri | Implemented by |
|---|---|---|---|
| FR-07 | Store each person once, whatever their role in any case | M | `persons` |
| FR-08 | ID card number has a fixed format and is unique | M | `chk_persons_cnic`, `uq_persons_cnic` |
| FR-09 | Show everything known about a person by ID number or name | M | `sp_person_profile`, `vw_criminal_history` |

### 5.3 FIR registration

| ID | Requirement | Pri | Implemented by |
|---|---|---|---|
| FR-10 | Register an FIR with station, times, location, category, description and one or more sections | M | `firs`, `fir_sections`, `sp_register_fir` |
| FR-11 | Give every FIR a number unique within station and year (for example `RVS-0007/2026`) | M | `firs.fir_serial`, `uq_firs_station_year_serial`, `fn_fir_number` |
| FR-12 | The complainant is either a person or the State (a police officer), never both or neither | M | `chk_firs_one_complainant` |
| FR-13 | The incident cannot be later than the report | M | `chk_firs_times` |
| FR-14 | An FIR is registered by an officer of the same station | M | `trg_firs_bi` |
| FR-15 | Record victims and witnesses with their statements | M | `fir_parties` |
| FR-16 | Record accused persons and their position (nominated, arrested, on bail, absconding, convicted, acquitted, discharged) | M | `fir_accused.status` |
| FR-17 | Keep a history of every change of FIR status | M | `fir_status_history`, `trg_firs_ai`, `trg_firs_au` |
| FR-18 | Cancel a false or mistaken FIR with a written reason | S | `sp_cancel_fir`, `chk_firs_closure` |

### 5.4 Investigation

| ID | Requirement | Pri | Implemented by |
|---|---|---|---|
| FR-19 | Assign an investigating officer and keep the history of re-assignments | M | `investigation_assignments`, `sp_assign_investigator` |
| FR-20 | Only one investigating officer may be active on an FIR | M | generated column `active_fir_id` with `uq_one_active_io` |
| FR-21 | Only authorised ranks and active officers may investigate | M | `ranks.can_investigate`, `trg_assign_bi` |
| FR-22 | Keep a case diary written only by the assigned officer | M | `case_diary`, `trg_diary_bi` |
| FR-23 | Record arrests with remand days (at most 14) and release time | M | `arrests`, `chk_arrests_remand`, `sp_register_arrest` |
| FR-24 | Arrest updates the accused status; a person in custody cannot be arrested again | M | `trg_arrests_ai`, `trg_arrests_bi` |
| FR-25 | List investigations with no diary entry for more than 30 days | S | `vw_stale_investigations` |
| FR-26 | Report the workload of each investigating officer | S | `vw_open_cases_by_officer`, `sp_officer_caseload` |

### 5.5 Evidence

| ID | Requirement | Pri | Implemented by |
|---|---|---|---|
| FR-27 | Register exhibits with type, collector, time, place and storage | M | `evidence`, `evidence_types` |
| FR-28 | Digital evidence must carry a valid SHA-256 hash, and the hash can never change | M | `chk_evidence_hash`, `trg_evidence_bi`, `trg_evidence_bu` |
| FR-29 | Log every hand-over of an exhibit automatically, in time order | M | `evidence_custody_log`, `trg_evidence_ai`, `trg_evidence_au`, `sp_transfer_evidence` |
| FR-30 | Returned or destroyed exhibits cannot move again | M | `trg_evidence_bu` |
| FR-31 | Record forensic lab submissions and findings | S | `lab_reports`, `chk_lab_findings` |
| FR-32 | Show where each exhibit is and how often it has moved | S | `vw_evidence_custody_status` |

### 5.6 Courts

| ID | Requirement | Pri | Implemented by |
|---|---|---|---|
| FR-33 | Submit the challan (police report) for an investigated FIR with at least one accused | M | `sp_submit_challan` |
| FR-34 | File a case with a court; the FIR moves to In Court | M | `court_cases`, `sp_file_court_case`, `trg_cases_bi` |
| FR-35 | Record hearings with judge, purpose, outcome and next date | M | `hearings`, `trg_hearings_bi`, `chk_hearings_next` |
| FR-36 | The judge must sit in the court that holds the case | M | `trg_hearings_bi` |
| FR-37 | The first non-bail hearing moves a case from Pending to Under Trial | S | `trg_hearings_ai` |
| FR-38 | Record bail applications (before or after arrest) and the court's decision | M | `bail_applications`, `sp_decide_bail` |
| FR-39 | Granting bail needs a surety, releases the accused and updates the status | M | `chk_bail_surety`, `trg_bail_au` |
| FR-40 | Record a verdict for each accused; the last verdict closes the case and the FIR | M | `verdicts`, `sp_record_verdict` |
| FR-41 | A conviction needs a sentence; an acquittal or discharge cannot have one | M | `chk_verdict_sentence` |
| FR-42 | Withdraw a case (for example after settlement) and close the FIR | S | `sp_withdraw_case` |
| FR-43 | Show the court calendar of next hearing dates | S | `vw_cause_list` |

### 5.7 Reports

| ID | Requirement | Pri | Implemented by |
|---|---|---|---|
| FR-44 | FIR register with station, complainant, sections, status and investigator | M | `vw_fir_register` |
| FR-45 | Complete case file of one FIR in a single call | S | `sp_fir_dossier` |
| FR-46 | Crime statistics by district and category | S | `vw_crime_by_district_category`, Q04 |
| FR-47 | Station scorecard: workload and outcomes | S | `vw_station_performance`, Q27 |
| FR-48 | Repeat offenders, absconding accused, people in more than one role | C | Q07, Q18, Q24 |

---

## 6. Business rules

| ID | Rule | Enforced by |
|---|---|---|
| BR-01 | An FIR can never be deleted. Wrong ones are cancelled with a reason | `trg_firs_bd`, `sp_cancel_fir` |
| BR-02 | A Closed or Cancelled FIR cannot be re-opened, and an FIR cannot return to Registered | `trg_firs_bu` |
| BR-03 | An FIR must be investigated before it is challaned, tried or closed | `trg_firs_bu` |
| BR-04 | The FIR number and registration time cannot be changed | `trg_firs_bu` |
| BR-05 | The complainant cannot be an accused person of the same FIR | `trg_fir_accused_bi` |
| BR-06 | An accused person cannot also be a victim or witness of the same FIR (checked in both directions) | `trg_fir_accused_bi`, `trg_fir_parties_bi` |
| BR-07 | A case needs at least one accused before it is challaned or filed | `sp_submit_challan`, `trg_cases_bi` |
| BR-08 | Evidence cannot be collected before the incident, and new evidence is held by its collector | `trg_evidence_bi` |
| BR-09 | A custody transfer cannot be dated before the previous one | `trg_evidence_bu` |
| BR-10 | An arrest cannot be earlier than the incident | `trg_arrests_bi` |
| BR-11 | Bail is filed as Pending and decided once | `trg_bail_bi`, `sp_decide_bail` |
| BR-12 | No hearing, verdict or withdrawal on a case that is already Decided or Withdrawn | `trg_hearings_bi`, `trg_verdicts_bi`, `sp_withdraw_case` |
| BR-13 | A verdict can only be given to an accused person of the FIR behind the case | `trg_verdicts_bi` |
| BR-14 | An officer cannot supervise themselves | `trg_officers_bu` |

Each rule has at least one test in `database/integrity_tests.sql`; the results are in [INTEGRITY_TESTS.md](INTEGRITY_TESTS.md).

---

## 7. Non-functional requirements

| ID | Requirement | How it is met |
|---|---|---|
| NFR-01 | **Integrity.** Invalid data must be rejected by the database, whichever program sends it | 44 foreign keys, 25 CHECK constraints, 24 UNIQUE keys, 23 triggers |
| NFR-02 | **Consistency of multi-step actions.** Registering an FIR, assigning an officer, recording a verdict and similar steps are all or nothing | Write procedures use `START TRANSACTION` with an exit handler that rolls back and re-raises the error |
| NFR-03 | **Normalization.** No repeated facts; third normal form | One `persons` table; lookup tables for stations, ranks, sections, courts; link tables `fir_sections`, `fir_parties`; no stored totals that can drift |
| NFR-04 | **Traceability.** It must be possible to see who held an exhibit and how an FIR changed status | `evidence_custody_log`, `fir_status_history` filled by triggers, so they cannot be skipped |
| NFR-05 | **Performance.** Common look-ups must not scan whole tables | Indexes on every foreign key, on `persons.full_name`, `firs.status` and `firs.reported_at` |
| NFR-06 | **Repeatability.** Anyone can rebuild the database and get the same results | One script (`database/fir_ccms.sql`), Docker support, and a fixed-clock mode (`@as_of`) for the documented results |
| NFR-07 | **Testability.** The rules must be checked automatically | `tools/run_integrity_tests.py` and a GitHub Actions workflow run all 45 tests on every push |
| NFR-08 | **Privacy of sample data.** No real person may appear | All names are invented and ID numbers are fake (`00000-...`) |
| NFR-09 | **Security basics.** Passwords are never stored in clear text; access follows roles | `users.password_hash` (CHECK for a 64-character hash), `roles`, least-privilege accounts in the report |

---

## 8. Assumptions

1. One police station registers an FIR for incidents it handles; transfer of an FIR between stations is not modelled.
2. An FIR can lead to more than one court case (one per court), but the sample data uses one.
3. An accused person who is absconding is not waited for: the case can be decided when everyone else has a verdict.
4. Legal section data is illustrative and must be checked against current statutes before real use.
5. Dates and times are stored without a time zone (local time of the police station).
