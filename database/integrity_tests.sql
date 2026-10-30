-- =====================================================================
-- FIR and Criminal Case Management System (FIR-CMS)
-- Integrity tests: every test tries to break a rule and MUST be rejected.
--
-- Format (read by tools/run_integrity_tests.py):
--   -- T<nn> | rule being tested
--   -- Expect: text that must appear in the error message
--   <one or more statements, run in one session>
--
-- No test may change the database. The runner compares row counts of every
-- table before and after the whole run to prove that.
-- =====================================================================

USE fir_ccms;

-- T01 | An FIR can never be deleted
-- Expect: cannot be deleted
DELETE FROM firs WHERE fir_id = 1;

-- T02 | A closed FIR cannot be re-opened
-- Expect: cannot be re-opened
UPDATE firs SET status = 'Under Investigation' WHERE fir_id = 1;

-- T03 | An FIR must be registered by an officer of the same station
-- Expect: same police station
CALL sp_register_fir(1, 1, NULL, 8, '2026-10-29 10:00:00', 'Test location', 2, 'Test', @f, @n);

-- T04 | The incident cannot be later than the report
-- Expect: chk_firs_times
CALL sp_register_fir(1, 1, NULL, 2, '2031-01-01 10:00:00', 'Test location', 2, 'Test', @f, @n);

-- T05 | An FIR has exactly one complainant (a person or the State)
-- Expect: chk_firs_one_complainant
INSERT INTO firs (station_id, fir_serial, reported_at, complainant_person_id, complainant_officer_id,
                  registered_by, incident_at, incident_location, category_id, description)
VALUES (1, 900, '2026-10-01 10:00:00', 1, 2, 2, '2026-10-01 09:00:00', 'Test', 1, 'Test');

-- T06 | The complainant cannot be the accused
-- Expect: cannot also be its accused
INSERT INTO fir_accused (fir_id, person_id, added_on) VALUES (18, 54, '2026-10-30');

-- T07 | A witness cannot also be the accused in the same FIR
-- Expect: already a victim or witness
INSERT INTO fir_accused (fir_id, person_id, added_on) VALUES (19, 7, '2026-10-30');

-- T08 | A constable cannot be given an investigation
-- Expect: not authorised to investigate
CALL sp_assign_investigator(21, 6, 'Test');

-- T09 | An inactive officer cannot be given an investigation
-- Expect: inactive officer
CALL sp_assign_investigator(21, 28, 'Test');

-- T10 | Only one investigating officer can be active on an FIR
-- Expect: uq_one_active_io
INSERT INTO investigation_assignments (fir_id, officer_id, assigned_on) VALUES (2, 4, '2026-10-30');

-- T11 | Only the assigned investigating officer can write the case diary
-- Expect: Only the investigating officer
INSERT INTO case_diary (fir_id, officer_id, entry_date, entry_text) VALUES (18, 4, '2026-10-30', 'Test');

-- T12 | Digital evidence needs a hash
-- Expect: SHA-256 hash
INSERT INTO evidence (evidence_no, fir_id, type_id, description, collected_by, collected_at, current_custodian_id)
VALUES ('EV-TEST-1', 18, 7, 'Test', 3, '2026-10-30 10:00:00', 3);

-- T13 | A hash must be 64 hex characters
-- Expect: chk_evidence_hash
INSERT INTO evidence (evidence_no, fir_id, type_id, description, collected_by, collected_at, current_custodian_id, hash_sha256)
VALUES ('EV-TEST-2', 18, 7, 'Test', 3, '2026-10-30 10:00:00', 3, 'not-a-real-hash');

-- T14 | Evidence cannot be collected before the incident
-- Expect: before the incident
INSERT INTO evidence (evidence_no, fir_id, type_id, description, collected_by, collected_at, current_custodian_id)
VALUES ('EV-TEST-3', 18, 2, 'Test', 3, '2026-01-01 10:00:00', 3);

-- T15 | New evidence must start with the officer who collected it
-- Expect: must start in the custody
INSERT INTO evidence (evidence_no, fir_id, type_id, description, collected_by, collected_at, current_custodian_id)
VALUES ('EV-TEST-4', 18, 2, 'Test', 3, '2026-10-30 10:00:00', 4);

-- T16 | The hash of an exhibit can never be changed
-- Expect: cannot be changed
UPDATE evidence SET hash_sha256 = REPEAT('a', 64) WHERE evidence_no = 'EV-2026-003';

-- T17 | Destroyed evidence cannot move again
-- Expect: cannot move again
UPDATE evidence SET status = 'In Malkhana' WHERE evidence_no = 'EV-2026-017';

-- T18 | A custody transfer cannot be dated before the previous one
-- Expect: before the previous transfer
SET @as_of = '2026-01-01 10:00:00';
SELECT evidence_id INTO @e FROM evidence WHERE evidence_no = 'EV-2026-031';
CALL sp_transfer_evidence(@e, 3, 'Test', NULL, NULL);

-- T19 | An arrest cannot be earlier than the incident
-- Expect: earlier than the incident
SET @as_of = '2026-08-01 10:00:00';
SELECT fa.fir_accused_id INTO @a FROM fir_accused fa JOIN persons p ON p.person_id = fa.person_id WHERE p.full_name = 'Sikandar Hayat';
CALL sp_register_arrest(@a, 7, 'Test', 1);

-- T20 | A person already in custody cannot be arrested again
-- Expect: already in custody
SELECT fa.fir_accused_id INTO @a FROM fir_accused fa JOIN persons p ON p.person_id = fa.person_id WHERE p.full_name = 'Gulzar Ahmed';
CALL sp_register_arrest(@a, 15, 'Test', 1);

-- T21 | Police remand cannot exceed 14 days
-- Expect: chk_arrests_remand
SELECT fa.fir_accused_id INTO @a FROM fir_accused fa JOIN persons p ON p.person_id = fa.person_id WHERE p.full_name = 'Sikandar Hayat';
CALL sp_register_arrest(@a, 7, 'Test', 20);

-- T22 | A bail application can be decided only once
-- Expect: already decided
CALL sp_decide_bail(1, 'Rejected', NULL, 'Test');

-- T23 | Granted bail needs a surety amount
-- Expect: chk_bail_surety
UPDATE bail_applications SET surety_amount = NULL WHERE bail_id = 1;

-- T24 | A bail application must be filed as Pending
-- Expect: must be filed as Pending
INSERT INTO bail_applications (fir_accused_id, court_id, bail_type, applied_on, decided_on, decision, surety_amount)
VALUES (1, 1, 'Post-arrest', '2026-10-30', '2026-10-30', 'Granted', 1000);

-- T25 | A case cannot go to court before the investigation
-- Expect: has been investigated
CALL sp_file_court_case(21, 1, 'TEST-1', @c);

-- T26 | A case needs at least one accused
-- Expect: at least one accused
CALL sp_file_court_case(5, 3, 'TEST-2', @c);

-- T27 | A challan needs at least one accused
-- Expect: at least one accused
CALL sp_submit_challan(5);

-- T28 | The judge must sit in the court that holds the case
-- Expect: does not sit in the court
INSERT INTO hearings (case_id, hearing_date, judge_id, purpose)
VALUES ((SELECT case_id FROM court_cases WHERE case_number = 'CY-LHR-2026-0031'), '2026-11-30', 1, 'Evidence');

-- T29 | A decided case cannot receive new hearings
-- Expect: Decided or Withdrawn
INSERT INTO hearings (case_id, hearing_date, judge_id, purpose)
VALUES ((SELECT case_id FROM court_cases WHERE case_number = 'MC-LHR-2026-0114'), '2026-11-01', 1, 'Evidence');

-- T30 | The next hearing must be after this hearing
-- Expect: chk_hearings_next
INSERT INTO hearings (case_id, hearing_date, judge_id, purpose, next_hearing_date)
VALUES ((SELECT case_id FROM court_cases WHERE case_number = 'CY-LHR-2026-0031'), '2026-11-30', 3, 'Evidence', '2026-11-01');

-- T31 | A verdict must be for an accused person of the same FIR
-- Expect: not part of the FIR
SELECT case_id INTO @c FROM court_cases WHERE case_number = 'SC-LHR-2026-0208';
SELECT fa.fir_accused_id INTO @a FROM fir_accused fa JOIN persons p ON p.person_id = fa.person_id WHERE p.full_name = 'Sikandar Hayat';
CALL sp_record_verdict(@c, @a, 'Acquitted', NULL, NULL, 'Test');

-- T32 | A conviction needs a sentence
-- Expect: chk_verdict_sentence
SELECT case_id INTO @c FROM court_cases WHERE case_number = 'SC-LHR-2026-0208';
SELECT fa.fir_accused_id INTO @a FROM fir_accused fa JOIN persons p ON p.person_id = fa.person_id WHERE p.full_name = 'Shahzad Gul';
INSERT INTO verdicts (case_id, fir_accused_id, verdict, verdict_on) VALUES (@c, @a, 'Convicted', '2026-10-30');

-- T33 | A decided case cannot be withdrawn
-- Expect: Pending or Under Trial
CALL sp_withdraw_case((SELECT case_id FROM court_cases WHERE case_number = 'MC-LHR-2026-0114'), 'Test');

-- T34 | The ID card number must have the right format
-- Expect: chk_persons_cnic
INSERT INTO persons (cnic, full_name, gender) VALUES ('12345', 'Test Person', 'Male');

-- T35 | The ID card number must be unique
-- Expect: uq_persons_cnic
INSERT INTO persons (cnic, full_name, gender) VALUES ('00000-0000001-1', 'Test Person', 'Male');

-- T36 | An FIR cannot point to a section that does not exist
-- Expect: foreign key constraint fails
INSERT INTO fir_sections (fir_id, section_id) VALUES (1, 999);

-- T37 | A police station with FIRs cannot be deleted
-- Expect: foreign key constraint fails
DELETE FROM police_stations WHERE station_id = 1;

-- T38 | An officer cannot supervise themselves
-- Expect: cannot supervise themselves
UPDATE officers SET supervisor_id = 5 WHERE officer_id = 5;

-- T39 | Only listed FIR statuses are allowed
-- Expect: Data truncated
UPDATE firs SET status = 'Pending' WHERE fir_id = 21;

-- T40 | Cancelling an FIR needs a written reason
-- Expect: chk_firs_closure
UPDATE firs SET status = 'Cancelled' WHERE fir_id = 21;

-- T41 | An FIR must be investigated before it is closed
-- Expect: must go through investigation
UPDATE firs SET status = 'Closed' WHERE fir_id = 21;

-- T42 | The FIR number cannot be changed
-- Expect: cannot be changed
UPDATE firs SET fir_serial = 99 WHERE fir_id = 1;

-- T43 | User names must follow the naming rule
-- Expect: chk_users_username
INSERT INTO users (username, password_hash, role_id) VALUES ('Bad Name', SHA2('x', 256), 1);

-- T44 | A lab report needs findings once it has a report date
-- Expect: chk_lab_findings
INSERT INTO lab_reports (evidence_id, lab_name, report_type, submitted_on, reported_on)
VALUES (1, 'Test lab', 'Other', '2026-10-01', '2026-10-02');

-- T45 | A user cannot be created without a role
-- Expect: cannot be null
INSERT INTO users (username, password_hash, role_id) VALUES ('norole_user', SHA2('x', 256), NULL);
