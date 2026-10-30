-- =====================================================================
-- FIR and Criminal Case Management System (FIR-CMS)
-- 27 report and demonstration queries
--
-- Format: each query starts with a "-- Q<nn> | title" line and a
-- "-- Purpose:" line. tools/build_docs.py reads this file to produce
-- docs/QUERY_RESULTS.md, so keep that format.
--
-- "Today" in the sample data is 30 October 2026. Run SET @as_of = '2026-10-30 12:00:00';
-- first to get the same results as docs/QUERY_RESULTS.md.
-- =====================================================================

USE fir_ccms;

-- Q01 | FIR register
-- Purpose: The daily register. One line per FIR with station, complainant, sections and status. Uses the vw_fir_register view.
SELECT fir_number, station, DATE(reported_at) AS reported_on, category, complainant, sections, status
  FROM vw_fir_register
 ORDER BY reported_at;

-- Q02 | FIRs registered at one station in a date range
-- Purpose: Station-level lookup with a date filter (BETWEEN) and a join to the station table.
SELECT r.fir_number, DATE(r.reported_at) AS reported_on, r.complainant, r.sections, r.status
  FROM vw_fir_register r
  JOIN police_stations ps ON ps.name = r.station
 WHERE ps.station_code = 'RVS'
   AND r.reported_at BETWEEN '2026-01-01' AND '2026-06-30 23:59:59'
 ORDER BY r.reported_at;

-- Q03 | FIRs by status
-- Purpose: How many FIRs are at each stage of the life cycle. GROUP BY with a share-of-total column.
SELECT status,
       COUNT(*) AS firs,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM firs), 1) AS percent_of_total
  FROM firs
 GROUP BY status
 ORDER BY firs DESC;

-- Q04 | Crime by district and category with totals
-- Purpose: GROUP BY ... WITH ROLLUP gives district sub-totals and a grand total in one pass.
SELECT COALESCE(district, 'ALL DISTRICTS') AS district,
       COALESCE(category, 'All categories') AS category,
       SUM(fir_count) AS firs
  FROM vw_crime_by_district_category
 GROUP BY district, category WITH ROLLUP;

-- Q05 | Stations ranked by FIR volume
-- Purpose: Window function RANK() over a grouped result.
SELECT RANK() OVER (ORDER BY COUNT(f.fir_id) DESC) AS volume_rank,
       ps.name AS station, d.name AS district, COUNT(f.fir_id) AS firs
  FROM police_stations ps
  JOIN districts d ON d.district_id = ps.district_id
  LEFT JOIN firs f ON f.station_id = ps.station_id
 GROUP BY ps.station_id, ps.name, d.name
 ORDER BY volume_rank, station;

-- Q06 | Investigating officers with more than one open case
-- Purpose: Workload report. HAVING filters on the aggregate. Uses vw_open_cases_by_officer.
SELECT officer, officer_rank, station, open_cases, longest_days_on_case
  FROM vw_open_cases_by_officer
 WHERE open_cases > 1
 ORDER BY open_cases DESC, officer;

-- Q07 | Repeat accused persons
-- Purpose: People named as accused in more than one FIR. Aggregation with GROUP_CONCAT and HAVING.
SELECT p.full_name, p.cnic, COUNT(*) AS times_accused,
       GROUP_CONCAT(fn_fir_number(fa.fir_id) ORDER BY fa.fir_id SEPARATOR ', ') AS firs
  FROM fir_accused fa
  JOIN persons p ON p.person_id = fa.person_id
 GROUP BY p.person_id, p.full_name, p.cnic
HAVING COUNT(*) > 1;

-- Q08 | Criminal history of one person by CNIC
-- Purpose: What the system knows about a person, found by ID card number. Uses vw_criminal_history.
SELECT full_name, fir_number, DATE(reported_at) AS reported_on, category, sections,
       accused_status, COALESCE(verdict, '(no verdict yet)') AS verdict
  FROM vw_criminal_history
 WHERE cnic = '00000-0000005-5'
 ORDER BY reported_at;

-- Q09 | Chain of custody of one exhibit
-- Purpose: Every hand-over of the axe in FIR CNT-0001/2026, with the time since the previous hand-over. LAG() window function.
SELECT l.transferred_at,
       COALESCE(fo.full_name, '(collected at scene)') AS from_officer,
       t.full_name AS to_officer,
       l.purpose,
       TIMESTAMPDIFF(HOUR, LAG(l.transferred_at) OVER (ORDER BY l.transferred_at, l.log_id), l.transferred_at) AS hours_since_previous
  FROM evidence_custody_log l
  JOIN evidence e       ON e.evidence_id = l.evidence_id
  LEFT JOIN officers fo ON fo.officer_id = l.from_officer_id
  JOIN officers t       ON t.officer_id = l.to_officer_id
 WHERE e.evidence_no = 'EV-2026-013'
 ORDER BY l.transferred_at, l.log_id;

-- Q10 | Evidence at the forensic laboratory
-- Purpose: Exhibits that are out for examination and how long they have been away.
SELECT evidence_no, fir_number, evidence_type, description, current_custodian,
       DATEDIFF(DATE(fn_now()), DATE(last_moved_at)) AS days_at_lab
  FROM vw_evidence_custody_status
 WHERE status = 'At Forensic Lab';

-- Q11 | Digital evidence and its hashes
-- Purpose: Cyber-crime exhibits. The SHA-256 hash is stored at seizure so tampering can be detected later.
SELECT evidence_no, fir_number, evidence_type, status, CONCAT(LEFT(hash_sha256, 16), '...') AS hash_start
  FROM vw_evidence_custody_status
 WHERE is_digital = 1
 ORDER BY evidence_no;

-- Q12 | Reporting delay by station
-- Purpose: Average hours between the incident and the FIR. TIMESTAMPDIFF and AVG over a view.
SELECT station, COUNT(*) AS firs,
       ROUND(AVG(reporting_delay_hours), 1) AS avg_delay_hours,
       MAX(reporting_delay_hours) AS longest_delay_hours
  FROM vw_fir_register
 GROUP BY station
 ORDER BY avg_delay_hours DESC;

-- Q13 | Time from FIR to verdict for closed cases
-- Purpose: How long decided cases took, per FIR. Joins FIR, court case and the last verdict.
SELECT r.fir_number, r.category, DATE(r.reported_at) AS reported_on,
       MAX(v.verdict_on) AS decided_on,
       DATEDIFF(MAX(v.verdict_on), DATE(r.reported_at)) AS days_to_decision
  FROM vw_fir_register r
  JOIN court_cases cc ON cc.fir_id = r.fir_id AND cc.status = 'Decided'
  JOIN verdicts v     ON v.case_id = cc.case_id
 GROUP BY r.fir_id, r.fir_number, r.category, r.reported_at
 ORDER BY days_to_decision;

-- Q14 | Conviction rate by crime category
-- Purpose: Conditional aggregation with CASE. Only accused who have a verdict are counted.
SELECT cc.name AS category,
       COUNT(*) AS verdicts,
       SUM(v.verdict = 'Convicted') AS convictions,
       ROUND(100 * SUM(v.verdict = 'Convicted') / COUNT(*), 1) AS conviction_rate_percent
  FROM verdicts v
  JOIN court_cases c       ON c.case_id = v.case_id
  JOIN firs f              ON f.fir_id = c.fir_id
  JOIN crime_categories cc ON cc.category_id = f.category_id
 GROUP BY cc.category_id, cc.name
 ORDER BY conviction_rate_percent DESC;

-- Q15 | Court calendar for the next 60 days
-- Purpose: Upcoming hearings from the cause-list view, soonest first.
SELECT next_hearing_date, days_until, court, case_number, fir_number, last_purpose, listing_status
  FROM vw_cause_list
 WHERE days_until BETWEEN 0 AND 60
 ORDER BY next_hearing_date, court;

-- Q16 | Court workload
-- Purpose: Cases, open cases and hearings per court, including courts with no cases (LEFT JOIN).
SELECT c.name AS court, c.court_type,
       COUNT(DISTINCT cc.case_id) AS cases,
       COUNT(DISTINCT CASE WHEN cc.status IN ('Pending', 'Under Trial') THEN cc.case_id END) AS open_cases,
       COUNT(h.hearing_id) AS hearings_held
  FROM courts c
  LEFT JOIN court_cases cc ON cc.court_id = c.court_id
  LEFT JOIN hearings h     ON h.case_id = cc.case_id
 GROUP BY c.court_id, c.name, c.court_type
 ORDER BY cases DESC, court;

-- Q17 | Accused currently on bail
-- Purpose: Who is out on bail, in which court, and with what surety. Sub-select picks the granted application.
SELECT p.full_name, fn_fir_number(fa.fir_id) AS fir_number, b.bail_type,
       c.name AS court, b.decided_on, b.surety_amount
  FROM fir_accused fa
  JOIN persons p ON p.person_id = fa.person_id
  JOIN bail_applications b ON b.fir_accused_id = fa.fir_accused_id AND b.decision = 'Granted'
  JOIN courts c ON c.court_id = b.court_id
 WHERE fa.status = 'On Bail'
 ORDER BY b.decided_on;

-- Q18 | Absconding accused
-- Purpose: Persons the police are looking for, with the officer who holds the case.
SELECT p.full_name, p.father_name, fn_fir_number(fa.fir_id) AS fir_number,
       r.sections, r.investigating_officer, DATEDIFF(DATE(fn_now()), fa.added_on) AS days_since_named
  FROM fir_accused fa
  JOIN persons p       ON p.person_id = fa.person_id
  JOIN vw_fir_register r ON r.fir_id = fa.fir_id
 WHERE fa.status = 'Absconding'
 ORDER BY days_since_named DESC;

-- Q19 | FIRs with no investigating officer
-- Purpose: Anti-join. LEFT JOIN ... IS NULL finds FIRs that nobody has been assigned to yet.
SELECT r.fir_number, r.station, r.category, r.status, DATE(r.reported_at) AS reported_on,
       DATEDIFF(DATE(fn_now()), DATE(r.reported_at)) AS days_waiting
  FROM vw_fir_register r
  LEFT JOIN investigation_assignments ia ON ia.fir_id = r.fir_id
 WHERE ia.assignment_id IS NULL
 ORDER BY days_waiting DESC;

-- Q20 | Stale investigations
-- Purpose: Open investigations with no case-diary entry for more than 30 days (vw_stale_investigations).
SELECT fir_number, station, category, investigating_officer, last_activity, days_idle
  FROM vw_stale_investigations
 ORDER BY days_idle DESC;

-- Q21 | Monthly FIR trend
-- Purpose: CTE plus LAG() to show FIRs per month and the change from the previous month.
WITH monthly AS (
  SELECT DATE_FORMAT(reported_at, '%Y-%m') AS month, COUNT(*) AS firs
    FROM firs
   GROUP BY DATE_FORMAT(reported_at, '%Y-%m')
)
SELECT month, firs,
       LAG(firs) OVER (ORDER BY month) AS previous_month,
       firs - LAG(firs) OVER (ORDER BY month) AS difference
  FROM monthly
 ORDER BY month;

-- Q22 | FIRs charged under non-bailable sections
-- Purpose: Join through the many-to-many table fir_sections and aggregate the sections of each FIR.
SELECT fn_fir_number(f.fir_id) AS fir_number,
       GROUP_CONCAT(CONCAT(ls.act, ' ', ls.section_no) ORDER BY ls.act, ls.section_no SEPARATOR ', ') AS sections,
       SUM(ls.is_bailable = 0) AS non_bailable_sections
  FROM firs f
  JOIN fir_sections fs    ON fs.fir_id = f.fir_id
  JOIN legal_sections ls  ON ls.section_id = fs.section_id
 GROUP BY f.fir_id
HAVING SUM(ls.is_bailable = 0) >= 2
 ORDER BY f.fir_id;

-- Q23 | Chain of command
-- Purpose: Recursive CTE that walks the officers table from the DSP down through every reporting line.
WITH RECURSIVE chain AS (
  SELECT o.officer_id, o.full_name, r.title AS officer_rank, o.supervisor_id, 0 AS depth,
         CAST(o.full_name AS CHAR(300)) AS path
    FROM officers o JOIN ranks r ON r.rank_id = o.rank_id
   WHERE o.supervisor_id IS NULL
  UNION ALL
  SELECT o.officer_id, o.full_name, r.title, o.supervisor_id, c.depth + 1,
         CONCAT(c.path, ' > ', o.full_name)
    FROM officers o
    JOIN ranks r  ON r.rank_id = o.rank_id
    JOIN chain c  ON c.officer_id = o.supervisor_id
)
SELECT CONCAT(REPEAT('    ', depth), full_name) AS officer, officer_rank, depth
  FROM chain
 WHERE depth <= 2
 ORDER BY path;

-- Q24 | People who appear in more than one role
-- Purpose: Persons who are a witness or victim in one FIR and accused in another. EXISTS sub-queries.
SELECT p.full_name, p.cnic,
       (SELECT GROUP_CONCAT(DISTINCT CONCAT(fp.party_role, ' in ', fn_fir_number(fp.fir_id)) SEPARATOR '; ')
          FROM fir_parties fp WHERE fp.person_id = p.person_id) AS as_witness_or_victim,
       (SELECT GROUP_CONCAT(DISTINCT CONCAT('Accused in ', fn_fir_number(fa.fir_id)) SEPARATOR '; ')
          FROM fir_accused fa WHERE fa.person_id = p.person_id) AS as_accused
  FROM persons p
 WHERE EXISTS (SELECT 1 FROM fir_parties fp WHERE fp.person_id = p.person_id)
   AND EXISTS (SELECT 1 FROM fir_accused fa WHERE fa.person_id = p.person_id);

-- Q25 | Cyber versus conventional crime by month
-- Purpose: Pivot with CASE: one row per month, one column per type of crime.
SELECT DATE_FORMAT(f.reported_at, '%Y-%m') AS month,
       SUM(cc.name = 'Cyber Crime') AS cyber,
       SUM(cc.name <> 'Cyber Crime') AS conventional,
       COUNT(*) AS total
  FROM firs f
  JOIN crime_categories cc ON cc.category_id = f.category_id
 GROUP BY DATE_FORMAT(f.reported_at, '%Y-%m')
 ORDER BY month;

-- Q26 | FIRs reported later than the station average
-- Purpose: Correlated sub-query comparing each FIR with the average of its own station.
SELECT r.fir_number, r.station, r.reporting_delay_hours,
       ROUND((SELECT AVG(r2.reporting_delay_hours) FROM vw_fir_register r2 WHERE r2.station = r.station), 1) AS station_avg_hours
  FROM vw_fir_register r
 WHERE r.reporting_delay_hours > (SELECT AVG(r2.reporting_delay_hours) FROM vw_fir_register r2 WHERE r2.station = r.station)
 ORDER BY r.reporting_delay_hours DESC;

-- Q27 | Station performance scorecard
-- Purpose: The vw_station_performance view with a conviction share calculated on top.
SELECT station, district, total_firs, in_investigation, with_courts, closed, cancelled,
       convictions, acquittals_or_discharges,
       IF(convictions + acquittals_or_discharges = 0, NULL,
          ROUND(100 * convictions / (convictions + acquittals_or_discharges), 1)) AS conviction_percent
  FROM vw_station_performance
 ORDER BY total_firs DESC, station;
