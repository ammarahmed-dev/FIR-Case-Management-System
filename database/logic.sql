-- =====================================================================
-- FIR and Criminal Case Management System (FIR-CMS)
-- File 2 of 3: functions, triggers, stored procedures and views
-- Run after schema.sql. Uses DELIMITER, so load it with the mysql client.
--
-- Testing hook: every timestamp the logic writes comes from fn_now().
-- It returns NOW() unless the session variable @as_of is set, which lets
-- the sample data (and the tests) replay history on a controlled clock.
-- =====================================================================

USE fir_ccms;
SET NAMES utf8mb4;

DELIMITER $$

-- ---------------------------------------------------------------------
-- Functions
-- ---------------------------------------------------------------------

CREATE FUNCTION fn_now() RETURNS DATETIME
  NOT DETERMINISTIC NO SQL
BEGIN
  RETURN COALESCE(@as_of, NOW());
END$$

CREATE FUNCTION fn_age(p_dob DATE) RETURNS SMALLINT
  NOT DETERMINISTIC NO SQL
BEGIN
  RETURN TIMESTAMPDIFF(YEAR, p_dob, DATE(fn_now()));
END$$

-- Printable FIR number, e.g. RVS-0007/2026
CREATE FUNCTION fn_fir_number(p_fir_id INT UNSIGNED) RETURNS VARCHAR(20)
  NOT DETERMINISTIC READS SQL DATA
BEGIN
  DECLARE v_number VARCHAR(20);
  SELECT CONCAT(ps.station_code, '-', LPAD(f.fir_serial, 4, '0'), '/', f.fir_year)
    INTO v_number
    FROM firs f JOIN police_stations ps ON ps.station_id = f.station_id
   WHERE f.fir_id = p_fir_id;
  RETURN v_number;
END$$

-- ---------------------------------------------------------------------
-- Triggers: officers
-- ---------------------------------------------------------------------

CREATE TRIGGER trg_officers_bu BEFORE UPDATE ON officers FOR EACH ROW
BEGIN
  IF NEW.supervisor_id IS NOT NULL AND NEW.supervisor_id = NEW.officer_id THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'An officer cannot supervise themselves.';
  END IF;
END$$

-- ---------------------------------------------------------------------
-- Triggers: FIR life cycle
-- ---------------------------------------------------------------------

CREATE TRIGGER trg_firs_bi BEFORE INSERT ON firs FOR EACH ROW
BEGIN
  DECLARE v_station SMALLINT UNSIGNED;
  DECLARE v_active BOOLEAN;
  SELECT station_id, is_active INTO v_station, v_active
    FROM officers WHERE officer_id = NEW.registered_by;
  IF v_station <> NEW.station_id THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'An FIR must be registered by an officer posted at the same police station.';
  END IF;
  IF v_active = FALSE THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The registering officer is not active.';
  END IF;
  IF NEW.status <> 'Registered' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A new FIR must start with the status Registered.';
  END IF;
END$$

CREATE TRIGGER trg_firs_ai AFTER INSERT ON firs FOR EACH ROW
BEGIN
  INSERT INTO fir_status_history (fir_id, old_status, new_status, changed_at, changed_by)
  VALUES (NEW.fir_id, NULL, NEW.status, fn_now(), USER());
END$$

CREATE TRIGGER trg_firs_bu BEFORE UPDATE ON firs FOR EACH ROW
BEGIN
  IF OLD.status IN ('Closed', 'Cancelled') AND NEW.status <> OLD.status THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A Closed or Cancelled FIR cannot be re-opened.';
  END IF;
  IF NEW.status = 'Registered' AND OLD.status <> 'Registered' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'An FIR cannot go back to Registered.';
  END IF;
  IF OLD.status = 'Registered' AND NEW.status IN ('Challaned', 'In Court', 'Closed') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'An FIR must go through investigation before it can be challaned, tried or closed.';
  END IF;
  IF NEW.station_id <> OLD.station_id OR NEW.fir_serial <> OLD.fir_serial
     OR NEW.reported_at <> OLD.reported_at THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'The FIR number and registration time cannot be changed.';
  END IF;
END$$

CREATE TRIGGER trg_firs_au AFTER UPDATE ON firs FOR EACH ROW
BEGIN
  IF NEW.status <> OLD.status THEN
    INSERT INTO fir_status_history (fir_id, old_status, new_status, changed_at, changed_by)
    VALUES (NEW.fir_id, OLD.status, NEW.status, fn_now(), USER());
  END IF;
END$$

CREATE TRIGGER trg_firs_bd BEFORE DELETE ON firs FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'FIRs are permanent records and cannot be deleted. Cancel the FIR instead.';
END$$

-- ---------------------------------------------------------------------
-- Triggers: people attached to an FIR
-- ---------------------------------------------------------------------

CREATE TRIGGER trg_fir_accused_bi BEFORE INSERT ON fir_accused FOR EACH ROW
BEGIN
  DECLARE v_status VARCHAR(20);
  DECLARE v_complainant INT UNSIGNED;
  SELECT status, complainant_person_id INTO v_status, v_complainant
    FROM firs WHERE fir_id = NEW.fir_id;
  IF v_status IN ('Closed', 'Cancelled') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Accused cannot be added to a Closed or Cancelled FIR.';
  END IF;
  IF v_complainant = NEW.person_id THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The complainant of an FIR cannot also be its accused.';
  END IF;
  IF EXISTS (SELECT 1 FROM fir_parties WHERE fir_id = NEW.fir_id AND person_id = NEW.person_id) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'This person is already a victim or witness in the same FIR.';
  END IF;
END$$

CREATE TRIGGER trg_fir_parties_bi BEFORE INSERT ON fir_parties FOR EACH ROW
BEGIN
  IF EXISTS (SELECT 1 FROM fir_accused WHERE fir_id = NEW.fir_id AND person_id = NEW.person_id) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'An accused person cannot also be a victim or witness in the same FIR.';
  END IF;
END$$

-- ---------------------------------------------------------------------
-- Triggers: investigation
-- ---------------------------------------------------------------------

CREATE TRIGGER trg_assign_bi BEFORE INSERT ON investigation_assignments FOR EACH ROW
BEGIN
  DECLARE v_can BOOLEAN;
  DECLARE v_active BOOLEAN;
  DECLARE v_status VARCHAR(20);
  SELECT r.can_investigate, o.is_active INTO v_can, v_active
    FROM officers o JOIN ranks r ON r.rank_id = o.rank_id
   WHERE o.officer_id = NEW.officer_id;
  IF v_can = FALSE THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'This officer''s rank is not authorised to investigate cases.';
  END IF;
  IF v_active = FALSE THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'An inactive officer cannot be assigned a case.';
  END IF;
  SELECT status INTO v_status FROM firs WHERE fir_id = NEW.fir_id;
  IF v_status IN ('Closed', 'Cancelled') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A Closed or Cancelled FIR cannot be assigned for investigation.';
  END IF;
END$$

CREATE TRIGGER trg_diary_bi BEFORE INSERT ON case_diary FOR EACH ROW
BEGIN
  IF NOT EXISTS (SELECT 1 FROM investigation_assignments ia
                  WHERE ia.fir_id = NEW.fir_id AND ia.officer_id = NEW.officer_id
                    AND ia.assigned_on <= NEW.entry_date
                    AND (ia.ended_on IS NULL OR ia.ended_on >= NEW.entry_date)) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Only the investigating officer assigned on that date can write the case diary.';
  END IF;
END$$

CREATE TRIGGER trg_arrests_bi BEFORE INSERT ON arrests FOR EACH ROW
BEGIN
  DECLARE v_incident DATETIME;
  DECLARE v_status VARCHAR(20);
  SELECT f.incident_at, fa.status INTO v_incident, v_status
    FROM fir_accused fa JOIN firs f ON f.fir_id = fa.fir_id
   WHERE fa.fir_accused_id = NEW.fir_accused_id;
  IF NEW.arrested_at < v_incident THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'An arrest cannot be earlier than the incident.';
  END IF;
  IF v_status IN ('Convicted', 'Acquitted', 'Discharged') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The trial of this accused is over; no new arrest allowed.';
  END IF;
  IF EXISTS (SELECT 1 FROM arrests WHERE fir_accused_id = NEW.fir_accused_id AND released_at IS NULL) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This accused is already in custody.';
  END IF;
END$$

CREATE TRIGGER trg_arrests_ai AFTER INSERT ON arrests FOR EACH ROW
BEGIN
  UPDATE fir_accused SET status = 'Arrested' WHERE fir_accused_id = NEW.fir_accused_id;
END$$

-- ---------------------------------------------------------------------
-- Triggers: evidence and chain of custody
-- ---------------------------------------------------------------------

CREATE TRIGGER trg_evidence_bi BEFORE INSERT ON evidence FOR EACH ROW
BEGIN
  DECLARE v_digital BOOLEAN;
  DECLARE v_incident DATETIME;
  DECLARE v_status VARCHAR(20);
  SELECT is_digital INTO v_digital FROM evidence_types WHERE type_id = NEW.type_id;
  SELECT incident_at, status INTO v_incident, v_status FROM firs WHERE fir_id = NEW.fir_id;
  IF v_digital = TRUE AND NEW.hash_sha256 IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Digital evidence must be registered with its SHA-256 hash.';
  END IF;
  IF NEW.collected_at < v_incident THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Evidence cannot be collected before the incident.';
  END IF;
  IF v_status IN ('Closed', 'Cancelled') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Evidence cannot be added to a Closed or Cancelled FIR.';
  END IF;
  IF NEW.current_custodian_id <> NEW.collected_by THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'New evidence must start in the custody of the officer who collected it.';
  END IF;
END$$

CREATE TRIGGER trg_evidence_ai AFTER INSERT ON evidence FOR EACH ROW
BEGIN
  INSERT INTO evidence_custody_log (evidence_id, from_officer_id, to_officer_id, transferred_at, purpose)
  VALUES (NEW.evidence_id, NULL, NEW.collected_by, NEW.collected_at, 'Collected at scene');
END$$

CREATE TRIGGER trg_evidence_bu BEFORE UPDATE ON evidence FOR EACH ROW
BEGIN
  DECLARE v_last DATETIME;
  IF NEW.fir_id <> OLD.fir_id OR NEW.evidence_no <> OLD.evidence_no
     OR NEW.collected_by <> OLD.collected_by OR NEW.collected_at <> OLD.collected_at
     OR NOT (NEW.hash_sha256 <=> OLD.hash_sha256) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'The FIR, evidence number, collector, collection time and hash cannot be changed.';
  END IF;
  IF OLD.status IN ('Returned', 'Destroyed') AND
     (NEW.status <> OLD.status OR NEW.current_custodian_id <> OLD.current_custodian_id) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Returned or destroyed evidence cannot move again.';
  END IF;
  IF NEW.current_custodian_id <> OLD.current_custodian_id THEN
    SELECT MAX(transferred_at) INTO v_last FROM evidence_custody_log WHERE evidence_id = OLD.evidence_id;
    IF fn_now() < v_last THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'A custody transfer cannot be dated before the previous transfer.';
    END IF;
  END IF;
END$$

-- Any change of custodian, however it is made, writes the chain-of-custody log.
CREATE TRIGGER trg_evidence_au AFTER UPDATE ON evidence FOR EACH ROW
BEGIN
  IF NEW.current_custodian_id <> OLD.current_custodian_id THEN
    INSERT INTO evidence_custody_log (evidence_id, from_officer_id, to_officer_id, transferred_at, purpose)
    VALUES (NEW.evidence_id, OLD.current_custodian_id, NEW.current_custodian_id, fn_now(),
            COALESCE(@custody_purpose, 'Transfer'));
  END IF;
END$$

-- ---------------------------------------------------------------------
-- Triggers: bail, courts, hearings, verdicts
-- ---------------------------------------------------------------------

CREATE TRIGGER trg_bail_bi BEFORE INSERT ON bail_applications FOR EACH ROW
BEGIN
  DECLARE v_incident DATE;
  SELECT DATE(f.incident_at) INTO v_incident
    FROM fir_accused fa JOIN firs f ON f.fir_id = fa.fir_id
   WHERE fa.fir_accused_id = NEW.fir_accused_id;
  IF NEW.applied_on < v_incident THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bail cannot be applied for before the incident.';
  END IF;
  IF NEW.decision <> 'Pending' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A bail application must be filed as Pending and decided later.';
  END IF;
END$$

-- Granting bail releases the accused and updates the accused status.
CREATE TRIGGER trg_bail_au AFTER UPDATE ON bail_applications FOR EACH ROW
BEGIN
  IF NEW.decision = 'Granted' AND OLD.decision <> 'Granted' THEN
    UPDATE arrests
       SET released_at = GREATEST(TIMESTAMP(NEW.decided_on, '17:00:00'), arrested_at + INTERVAL 1 MINUTE)
     WHERE fir_accused_id = NEW.fir_accused_id AND released_at IS NULL;
    UPDATE fir_accused SET status = 'On Bail'
     WHERE fir_accused_id = NEW.fir_accused_id
       AND status IN ('Nominated', 'Arrested', 'Absconding');
  END IF;
END$$

CREATE TRIGGER trg_cases_bi BEFORE INSERT ON court_cases FOR EACH ROW
BEGIN
  DECLARE v_status VARCHAR(20);
  SELECT status INTO v_status FROM firs WHERE fir_id = NEW.fir_id;
  IF v_status NOT IN ('Under Investigation', 'Challaned', 'In Court') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A court case can only be filed for an FIR that has been investigated.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM fir_accused WHERE fir_id = NEW.fir_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A court case needs at least one accused person.';
  END IF;
END$$

CREATE TRIGGER trg_hearings_bi BEFORE INSERT ON hearings FOR EACH ROW
BEGIN
  DECLARE v_filed DATE;
  DECLARE v_status VARCHAR(20);
  DECLARE v_court SMALLINT UNSIGNED;
  DECLARE v_judge_court SMALLINT UNSIGNED;
  SELECT filed_on, status, court_id INTO v_filed, v_status, v_court
    FROM court_cases WHERE case_id = NEW.case_id;
  SELECT court_id INTO v_judge_court FROM judges WHERE judge_id = NEW.judge_id;
  IF NEW.hearing_date < v_filed THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A hearing cannot be earlier than the date the case was filed.';
  END IF;
  IF v_status IN ('Decided', 'Withdrawn') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No hearings can be added to a Decided or Withdrawn case.';
  END IF;
  IF v_judge_court <> v_court THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The judge does not sit in the court that holds this case.';
  END IF;
END$$

CREATE TRIGGER trg_hearings_ai AFTER INSERT ON hearings FOR EACH ROW
BEGIN
  IF NEW.purpose <> 'Bail Hearing' THEN
    UPDATE court_cases SET status = 'Under Trial' WHERE case_id = NEW.case_id AND status = 'Pending';
  END IF;
END$$

CREATE TRIGGER trg_verdicts_bi BEFORE INSERT ON verdicts FOR EACH ROW
BEGIN
  DECLARE v_case_fir INT UNSIGNED;
  DECLARE v_accused_fir INT UNSIGNED;
  DECLARE v_filed DATE;
  DECLARE v_status VARCHAR(20);
  SELECT fir_id, filed_on, status INTO v_case_fir, v_filed, v_status
    FROM court_cases WHERE case_id = NEW.case_id;
  SELECT fir_id INTO v_accused_fir FROM fir_accused WHERE fir_accused_id = NEW.fir_accused_id;
  IF v_case_fir <> v_accused_fir THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This accused person is not part of the FIR behind this case.';
  END IF;
  IF v_status = 'Withdrawn' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A withdrawn case cannot receive a verdict.';
  END IF;
  IF NEW.verdict_on < v_filed THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A verdict cannot be earlier than the filing date.';
  END IF;
END$$

CREATE TRIGGER trg_verdicts_ai AFTER INSERT ON verdicts FOR EACH ROW
BEGIN
  UPDATE fir_accused SET status = NEW.verdict WHERE fir_accused_id = NEW.fir_accused_id;
END$$

-- ---------------------------------------------------------------------
-- Stored procedures: business transactions
-- ---------------------------------------------------------------------

-- Register an FIR. The serial number is allocated inside the transaction.
CREATE PROCEDURE sp_register_fir(
  IN  p_station_id             SMALLINT UNSIGNED,
  IN  p_complainant_person_id  INT UNSIGNED,
  IN  p_complainant_officer_id SMALLINT UNSIGNED,
  IN  p_registered_by          SMALLINT UNSIGNED,
  IN  p_incident_at            DATETIME,
  IN  p_incident_location      VARCHAR(200),
  IN  p_category_id            TINYINT UNSIGNED,
  IN  p_description            TEXT,
  OUT p_fir_id                 INT UNSIGNED,
  OUT p_fir_number             VARCHAR(20))
BEGIN
  DECLARE v_now DATETIME;
  DECLARE v_serial SMALLINT UNSIGNED;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET v_now = fn_now();
  START TRANSACTION;
    SELECT COALESCE(MAX(fir_serial), 0) + 1 INTO v_serial
      FROM firs WHERE station_id = p_station_id AND fir_year = YEAR(v_now) FOR UPDATE;

    INSERT INTO firs (station_id, fir_serial, reported_at, complainant_person_id, complainant_officer_id,
                      registered_by, incident_at, incident_location, category_id, description)
    VALUES (p_station_id, v_serial, v_now, p_complainant_person_id, p_complainant_officer_id,
            p_registered_by, p_incident_at, p_incident_location, p_category_id, p_description);
    SET p_fir_id = LAST_INSERT_ID();
    SET p_fir_number = fn_fir_number(p_fir_id);
  COMMIT;
END$$

-- Hand a case to an investigating officer. Closes the previous assignment (if any)
-- and moves a freshly registered FIR to Under Investigation.
CREATE PROCEDURE sp_assign_investigator(
  IN p_fir_id     INT UNSIGNED,
  IN p_officer_id SMALLINT UNSIGNED,
  IN p_reason     VARCHAR(150))
BEGIN
  DECLARE v_today DATE;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET v_today = DATE(fn_now());
  START TRANSACTION;
    UPDATE investigation_assignments SET ended_on = v_today
     WHERE fir_id = p_fir_id AND ended_on IS NULL;
    INSERT INTO investigation_assignments (fir_id, officer_id, assigned_on, reason)
    VALUES (p_fir_id, p_officer_id, v_today, p_reason);
    UPDATE firs SET status = 'Under Investigation'
     WHERE fir_id = p_fir_id AND status = 'Registered';
  COMMIT;
END$$

-- Move evidence from one officer to another. The trigger writes the custody log.
CREATE PROCEDURE sp_transfer_evidence(
  IN p_evidence_id INT UNSIGNED,
  IN p_to_officer  SMALLINT UNSIGNED,
  IN p_purpose     VARCHAR(150),
  IN p_new_status  VARCHAR(30),
  IN p_storage     VARCHAR(100))
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    SET @custody_purpose = NULL;
    ROLLBACK;
    RESIGNAL;
  END;

  SET @custody_purpose = p_purpose;
  START TRANSACTION;
    UPDATE evidence
       SET current_custodian_id = p_to_officer,
           status = COALESCE(p_new_status, status),
           storage_location = COALESCE(p_storage, storage_location)
     WHERE evidence_id = p_evidence_id;
    IF ROW_COUNT() = 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Evidence not found or nothing to change.';
    END IF;
  COMMIT;
  SET @custody_purpose = NULL;
END$$

CREATE PROCEDURE sp_register_arrest(
  IN p_fir_accused_id INT UNSIGNED,
  IN p_officer_id     SMALLINT UNSIGNED,
  IN p_location       VARCHAR(200),
  IN p_remand_days    TINYINT UNSIGNED)
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
    INSERT INTO arrests (fir_accused_id, arrested_by, arrested_at, location, remand_days)
    VALUES (p_fir_accused_id, p_officer_id, fn_now(), p_location, p_remand_days);
  COMMIT;
END$$

CREATE PROCEDURE sp_decide_bail(
  IN p_bail_id  INT UNSIGNED,
  IN p_decision VARCHAR(10),
  IN p_surety   DECIMAL(12,2),
  IN p_remarks  VARCHAR(200))
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
    UPDATE bail_applications
       SET decision = p_decision, decided_on = DATE(fn_now()),
           surety_amount = p_surety, remarks = p_remarks
     WHERE bail_id = p_bail_id AND decision = 'Pending';
    IF ROW_COUNT() = 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bail application not found or already decided.';
    END IF;
  COMMIT;
END$$

-- Investigation finished: submit the challan (police report) to the court.
CREATE PROCEDURE sp_submit_challan(IN p_fir_id INT UNSIGNED)
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
    IF NOT EXISTS (SELECT 1 FROM fir_accused WHERE fir_id = p_fir_id) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A challan needs at least one accused person.';
    END IF;
    UPDATE firs SET status = 'Challaned' WHERE fir_id = p_fir_id AND status = 'Under Investigation';
    IF ROW_COUNT() = 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only an FIR that is Under Investigation can be challaned.';
    END IF;
  COMMIT;
END$$

-- Register the case with a court and mark the FIR In Court.
CREATE PROCEDURE sp_file_court_case(
  IN  p_fir_id      INT UNSIGNED,
  IN  p_court_id    SMALLINT UNSIGNED,
  IN  p_case_number VARCHAR(30),
  OUT p_case_id     INT UNSIGNED)
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
    INSERT INTO court_cases (case_number, fir_id, court_id, filed_on)
    VALUES (p_case_number, p_fir_id, p_court_id, DATE(fn_now()));
    SET p_case_id = LAST_INSERT_ID();
    UPDATE firs SET status = 'In Court' WHERE fir_id = p_fir_id AND status <> 'In Court';
  COMMIT;
END$$

-- Record one accused person's verdict. When every accused who can be tried has a
-- verdict, the case is Decided and the FIR is Closed, all in the same transaction.
CREATE PROCEDURE sp_record_verdict(
  IN p_case_id        INT UNSIGNED,
  IN p_fir_accused_id INT UNSIGNED,
  IN p_verdict        VARCHAR(12),
  IN p_sentence_years DECIMAL(4,1),
  IN p_fine           DECIMAL(12,2),
  IN p_remarks        VARCHAR(200))
BEGIN
  DECLARE v_fir_id INT UNSIGNED;
  DECLARE v_open INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
    SELECT fir_id INTO v_fir_id FROM court_cases WHERE case_id = p_case_id FOR UPDATE;

    INSERT INTO verdicts (case_id, fir_accused_id, verdict, verdict_on, sentence_years, fine_amount, remarks)
    VALUES (p_case_id, p_fir_accused_id, p_verdict, DATE(fn_now()), p_sentence_years, COALESCE(p_fine, 0), p_remarks);

    SELECT COUNT(*) INTO v_open
      FROM fir_accused fa
     WHERE fa.fir_id = v_fir_id
       AND fa.status <> 'Absconding'
       AND NOT EXISTS (SELECT 1 FROM verdicts v
                        WHERE v.case_id = p_case_id AND v.fir_accused_id = fa.fir_accused_id);
    IF v_open = 0 THEN
      UPDATE court_cases SET status = 'Decided' WHERE case_id = p_case_id;
      UPDATE firs SET status = 'Closed' WHERE fir_id = v_fir_id AND status <> 'Closed';
    END IF;
  COMMIT;
END$$

-- A case dropped by the complainant or the prosecution.
CREATE PROCEDURE sp_withdraw_case(
  IN p_case_id INT UNSIGNED,
  IN p_reason  VARCHAR(250))
BEGIN
  DECLARE v_fir_id INT UNSIGNED;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
    SELECT fir_id INTO v_fir_id FROM court_cases WHERE case_id = p_case_id FOR UPDATE;
    UPDATE court_cases SET status = 'Withdrawn' WHERE case_id = p_case_id AND status IN ('Pending', 'Under Trial');
    IF ROW_COUNT() = 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only a Pending or Under Trial case can be withdrawn.';
    END IF;
    UPDATE fir_accused SET status = 'Discharged'
     WHERE fir_id = v_fir_id AND status IN ('Nominated', 'Arrested', 'On Bail');
    UPDATE firs SET status = 'Closed', closure_remarks = p_reason WHERE fir_id = v_fir_id;
  COMMIT;
END$$

-- Cancel an FIR (for example a false report). Needs a written reason.
CREATE PROCEDURE sp_cancel_fir(
  IN p_fir_id INT UNSIGNED,
  IN p_reason VARCHAR(250))
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
    UPDATE investigation_assignments SET ended_on = DATE(fn_now())
     WHERE fir_id = p_fir_id AND ended_on IS NULL;
    UPDATE firs SET status = 'Cancelled', closure_remarks = p_reason
     WHERE fir_id = p_fir_id AND status IN ('Registered', 'Under Investigation');
    IF ROW_COUNT() = 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only a Registered or Under Investigation FIR can be cancelled.';
    END IF;
  COMMIT;
END$$

-- ---------------------------------------------------------------------
-- Stored procedures: read-only lookups used by the desk and the courts
-- ---------------------------------------------------------------------

-- The complete case file of one FIR in seven result sets.
CREATE PROCEDURE sp_fir_dossier(IN p_fir_id INT UNSIGNED)
BEGIN
  SELECT * FROM vw_fir_register WHERE fir_id = p_fir_id;

  SELECT CONCAT(ls.act, ' ', ls.section_no) AS section, ls.title, ls.punishment_summary,
         IF(ls.is_cognizable, 'Yes', 'No') AS cognizable, IF(ls.is_bailable, 'Yes', 'No') AS bailable
    FROM fir_sections fs JOIN legal_sections ls ON ls.section_id = fs.section_id
   WHERE fs.fir_id = p_fir_id;

  SELECT fp.party_role, p.full_name, p.cnic, fp.statement
    FROM fir_parties fp JOIN persons p ON p.person_id = fp.person_id
   WHERE fp.fir_id = p_fir_id ORDER BY fp.party_role, p.full_name;

  SELECT p.full_name, p.cnic, fa.status, fa.added_on
    FROM fir_accused fa JOIN persons p ON p.person_id = fa.person_id
   WHERE fa.fir_id = p_fir_id ORDER BY fa.added_on, p.full_name;

  SELECT o.full_name AS investigating_officer, ia.assigned_on, ia.ended_on, ia.reason
    FROM investigation_assignments ia JOIN officers o ON o.officer_id = ia.officer_id
   WHERE ia.fir_id = p_fir_id ORDER BY ia.assigned_on, ia.assignment_id;

  SELECT e.evidence_no, et.name AS type, e.description, e.status, o.full_name AS custodian
    FROM evidence e JOIN evidence_types et ON et.type_id = e.type_id
                    JOIN officers o ON o.officer_id = e.current_custodian_id
   WHERE e.fir_id = p_fir_id ORDER BY e.evidence_no;

  SELECT cc.case_number, c.name AS court, h.hearing_date, h.purpose, h.outcome, h.next_hearing_date
    FROM court_cases cc JOIN courts c ON c.court_id = cc.court_id
                        LEFT JOIN hearings h ON h.case_id = cc.case_id
   WHERE cc.fir_id = p_fir_id ORDER BY cc.case_number, h.hearing_date;
END$$

-- Everything the system knows about one person, found by CNIC or by name.
CREATE PROCEDURE sp_person_profile(IN p_search VARCHAR(100))
BEGIN
  SELECT person_id, cnic, full_name, father_name, gender, fn_age(date_of_birth) AS age, address, occupation
    FROM persons
   WHERE cnic = p_search OR full_name LIKE CONCAT('%', p_search, '%')
   ORDER BY full_name;

  SELECT h.*
    FROM vw_criminal_history h JOIN persons p ON p.person_id = h.person_id
   WHERE p.cnic = p_search OR p.full_name LIKE CONCAT('%', p_search, '%')
   ORDER BY h.reported_at;
END$$

CREATE PROCEDURE sp_officer_caseload(IN p_officer_id SMALLINT UNSIGNED)
BEGIN
  SELECT r.fir_number, r.station, r.category, r.status, ia.assigned_on,
         DATEDIFF(DATE(fn_now()), ia.assigned_on) AS days_on_case
    FROM investigation_assignments ia JOIN vw_fir_register r ON r.fir_id = ia.fir_id
   WHERE ia.officer_id = p_officer_id AND ia.ended_on IS NULL
   ORDER BY ia.assigned_on;
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- Views: ready-made reports
-- ---------------------------------------------------------------------

-- The FIR register: one line per FIR with everything an officer asks first.
CREATE OR REPLACE VIEW vw_fir_register AS
SELECT f.fir_id,
       CONCAT(ps.station_code, '-', LPAD(f.fir_serial, 4, '0'), '/', f.fir_year) AS fir_number,
       ps.name AS station,
       d.name  AS district,
       f.reported_at,
       f.incident_at,
       TIMESTAMPDIFF(HOUR, f.incident_at, f.reported_at) AS reporting_delay_hours,
       cc.name AS category,
       COALESCE(p.full_name, CONCAT('State (', co.full_name, ')')) AS complainant,
       (SELECT GROUP_CONCAT(CONCAT(ls.act, ' ', ls.section_no) ORDER BY ls.act, ls.section_no SEPARATOR ', ')
          FROM fir_sections fs JOIN legal_sections ls ON ls.section_id = fs.section_id
         WHERE fs.fir_id = f.fir_id) AS sections,
       f.status,
       (SELECT o.full_name FROM investigation_assignments ia JOIN officers o ON o.officer_id = ia.officer_id
         WHERE ia.fir_id = f.fir_id AND ia.ended_on IS NULL) AS investigating_officer
  FROM firs f
  JOIN police_stations ps ON ps.station_id = f.station_id
  JOIN districts d        ON d.district_id = ps.district_id
  JOIN crime_categories cc ON cc.category_id = f.category_id
  LEFT JOIN persons p     ON p.person_id = f.complainant_person_id
  LEFT JOIN officers co   ON co.officer_id = f.complainant_officer_id;

-- Active investigations per officer, with the age of the oldest file.
CREATE OR REPLACE VIEW vw_open_cases_by_officer AS
SELECT o.officer_id, o.full_name AS officer, r.title AS officer_rank, ps.name AS station,
       COUNT(*) AS open_cases,
       MIN(ia.assigned_on) AS oldest_assignment,
       MAX(DATEDIFF(DATE(fn_now()), ia.assigned_on)) AS longest_days_on_case
  FROM investigation_assignments ia
  JOIN firs f            ON f.fir_id = ia.fir_id AND f.status = 'Under Investigation'
  JOIN officers o        ON o.officer_id = ia.officer_id
  JOIN ranks r           ON r.rank_id = o.rank_id
  JOIN police_stations ps ON ps.station_id = o.station_id
 WHERE ia.ended_on IS NULL
 GROUP BY o.officer_id, o.full_name, r.title, ps.name;

-- Number of FIRs per district and crime category.
CREATE OR REPLACE VIEW vw_crime_by_district_category AS
SELECT d.name AS district, cc.name AS category, COUNT(*) AS fir_count
  FROM firs f
  JOIN police_stations ps  ON ps.station_id = f.station_id
  JOIN districts d         ON d.district_id = ps.district_id
  JOIN crime_categories cc ON cc.category_id = f.category_id
 WHERE f.status <> 'Cancelled'
 GROUP BY d.name, cc.name;

-- Criminal history: every time a person was named as accused, and how it ended.
CREATE OR REPLACE VIEW vw_criminal_history AS
SELECT p.person_id, p.cnic, p.full_name,
       f.fir_id,
       CONCAT(ps.station_code, '-', LPAD(f.fir_serial, 4, '0'), '/', f.fir_year) AS fir_number,
       f.reported_at,
       cc.name AS category,
       (SELECT GROUP_CONCAT(CONCAT(ls.act, ' ', ls.section_no) ORDER BY ls.act, ls.section_no SEPARATOR ', ')
          FROM fir_sections fs JOIN legal_sections ls ON ls.section_id = fs.section_id
         WHERE fs.fir_id = f.fir_id) AS sections,
       fa.status AS accused_status,
       v.verdict, v.verdict_on, v.sentence_years, v.fine_amount
  FROM fir_accused fa
  JOIN persons p           ON p.person_id = fa.person_id
  JOIN firs f              ON f.fir_id = fa.fir_id
  JOIN police_stations ps  ON ps.station_id = f.station_id
  JOIN crime_categories cc ON cc.category_id = f.category_id
  LEFT JOIN verdicts v     ON v.fir_accused_id = fa.fir_accused_id;

-- Where every piece of evidence is right now and how often it has changed hands.
CREATE OR REPLACE VIEW vw_evidence_custody_status AS
SELECT e.evidence_id, e.evidence_no,
       fn_fir_number(e.fir_id) AS fir_number,
       et.name AS evidence_type, et.is_digital,
       e.description, e.status,
       o.full_name AS current_custodian,
       e.storage_location,
       (SELECT COUNT(*) FROM evidence_custody_log l WHERE l.evidence_id = e.evidence_id) - 1 AS transfers,
       (SELECT MAX(l.transferred_at) FROM evidence_custody_log l WHERE l.evidence_id = e.evidence_id) AS last_moved_at,
       e.hash_sha256
  FROM evidence e
  JOIN evidence_types et ON et.type_id = e.type_id
  JOIN officers o        ON o.officer_id = e.current_custodian_id;

-- Investigations with no diary entry for more than 30 days.
CREATE OR REPLACE VIEW vw_stale_investigations AS
SELECT r.fir_id, r.fir_number, r.station, r.category, r.investigating_officer,
       COALESCE((SELECT MAX(cd.entry_date) FROM case_diary cd WHERE cd.fir_id = r.fir_id),
                (SELECT ia.assigned_on FROM investigation_assignments ia
                  WHERE ia.fir_id = r.fir_id AND ia.ended_on IS NULL)) AS last_activity,
       DATEDIFF(DATE(fn_now()),
                COALESCE((SELECT MAX(cd.entry_date) FROM case_diary cd WHERE cd.fir_id = r.fir_id),
                         (SELECT ia.assigned_on FROM investigation_assignments ia
                           WHERE ia.fir_id = r.fir_id AND ia.ended_on IS NULL))) AS days_idle
  FROM vw_fir_register r
 WHERE r.status = 'Under Investigation'
HAVING days_idle > 30;

-- One line per police station: workload and outcome.
CREATE OR REPLACE VIEW vw_station_performance AS
SELECT ps.station_id, ps.name AS station, d.name AS district,
       COUNT(f.fir_id) AS total_firs,
       SUM(f.status IN ('Registered', 'Under Investigation')) AS in_investigation,
       SUM(f.status IN ('Challaned', 'In Court')) AS with_courts,
       SUM(f.status = 'Closed') AS closed,
       SUM(f.status = 'Cancelled') AS cancelled,
       (SELECT COUNT(*) FROM verdicts v JOIN court_cases cc ON cc.case_id = v.case_id
          JOIN firs f2 ON f2.fir_id = cc.fir_id
         WHERE f2.station_id = ps.station_id AND v.verdict = 'Convicted') AS convictions,
       (SELECT COUNT(*) FROM verdicts v JOIN court_cases cc ON cc.case_id = v.case_id
          JOIN firs f2 ON f2.fir_id = cc.fir_id
         WHERE f2.station_id = ps.station_id AND v.verdict <> 'Convicted') AS acquittals_or_discharges
  FROM police_stations ps
  JOIN districts d ON d.district_id = ps.district_id
  LEFT JOIN firs f ON f.station_id = ps.station_id
 GROUP BY ps.station_id, ps.name, d.name;

-- Court calendar: the next date fixed in each open case.
CREATE OR REPLACE VIEW vw_cause_list AS
WITH ranked AS (
  SELECT h.*, ROW_NUMBER() OVER (PARTITION BY h.case_id ORDER BY h.hearing_date DESC, h.hearing_id DESC) AS rn
    FROM hearings h
)
SELECT cc.case_id, cc.case_number, c.name AS court, j.full_name AS last_judge,
       fn_fir_number(cc.fir_id) AS fir_number,
       rk.purpose AS last_purpose, rk.next_hearing_date,
       DATEDIFF(rk.next_hearing_date, DATE(fn_now())) AS days_until,
       IF(rk.next_hearing_date < DATE(fn_now()), 'Date passed, update needed', 'Scheduled') AS listing_status
  FROM ranked rk
  JOIN court_cases cc ON cc.case_id = rk.case_id
  JOIN courts c       ON c.court_id = cc.court_id
  JOIN judges j       ON j.judge_id = rk.judge_id
 WHERE rk.rn = 1 AND cc.status IN ('Pending', 'Under Trial') AND rk.next_hearing_date IS NOT NULL;
