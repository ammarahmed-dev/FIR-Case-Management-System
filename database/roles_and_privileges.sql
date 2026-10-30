-- =====================================================================
-- FIR and Criminal Case Management System (FIR-CMS)
-- Optional: MySQL roles and least-privilege grants (MySQL 8.0 roles)
--
-- Idea: people get NO direct write access to the important tables.
-- They get EXECUTE on the stored procedures, which run with the rights of
-- the procedure owner (SQL SECURITY DEFINER) and apply all the rules.
-- Only plain look-up tables and notes are written directly.
--
-- Run as an administrator after fir_ccms.sql:  mysql -u root -p < roles_and_privileges.sql
-- =====================================================================

USE fir_ccms;

CREATE ROLE IF NOT EXISTS 'fir_admin', 'fir_sho', 'fir_investigator', 'fir_clerk', 'fir_court', 'fir_auditor';

-- Auditor: read everything, change nothing.
GRANT SELECT ON fir_ccms.* TO 'fir_auditor';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_fir_dossier    TO 'fir_auditor';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_person_profile TO 'fir_auditor';

-- Everyone who works cases can read and use the look-up procedures.
GRANT SELECT ON fir_ccms.* TO 'fir_clerk', 'fir_investigator', 'fir_sho', 'fir_court';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_fir_dossier     TO 'fir_clerk', 'fir_investigator', 'fir_sho', 'fir_court';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_person_profile  TO 'fir_clerk', 'fir_investigator', 'fir_sho', 'fir_court';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_officer_caseload TO 'fir_investigator', 'fir_sho';

-- Records clerk: registers persons and FIRs, adds sections, victims and witnesses.
GRANT INSERT, UPDATE ON fir_ccms.persons       TO 'fir_clerk';
GRANT INSERT          ON fir_ccms.fir_sections TO 'fir_clerk';
GRANT INSERT          ON fir_ccms.fir_parties  TO 'fir_clerk';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_register_fir TO 'fir_clerk';

-- Investigating officer: case diary, accused, evidence, lab reports, arrests, challan.
GRANT INSERT ON fir_ccms.case_diary     TO 'fir_investigator';
GRANT INSERT ON fir_ccms.fir_accused    TO 'fir_investigator';
GRANT INSERT ON fir_ccms.fir_parties    TO 'fir_investigator';
GRANT INSERT ON fir_ccms.evidence       TO 'fir_investigator';
GRANT INSERT ON fir_ccms.lab_reports    TO 'fir_investigator';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_register_arrest   TO 'fir_investigator';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_transfer_evidence TO 'fir_investigator';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_submit_challan    TO 'fir_investigator';

-- Station house officer: everything an investigator and a clerk can do, plus
-- assigning investigators and cancelling FIRs.
GRANT 'fir_investigator', 'fir_clerk' TO 'fir_sho';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_assign_investigator TO 'fir_sho';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_cancel_fir          TO 'fir_sho';

-- Court liaison officer: bail, cases, hearings and verdicts.
GRANT INSERT ON fir_ccms.hearings          TO 'fir_court';
GRANT INSERT ON fir_ccms.bail_applications TO 'fir_court';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_decide_bail     TO 'fir_court';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_file_court_case TO 'fir_court';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_record_verdict  TO 'fir_court';
GRANT EXECUTE ON PROCEDURE fir_ccms.sp_withdraw_case   TO 'fir_court';

-- Administrator: full control of the database.
GRANT ALL PRIVILEGES ON fir_ccms.* TO 'fir_admin';

-- Example of giving a role to a person (uncomment and change the password):
-- CREATE USER 'nadia'@'localhost' IDENTIFIED BY 'change-me-please';
-- GRANT 'fir_investigator' TO 'nadia'@'localhost';
-- SET DEFAULT ROLE 'fir_investigator' TO 'nadia'@'localhost';
