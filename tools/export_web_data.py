#!/usr/bin/env python3
"""Export the live fir_ccms database to web/data.json for the web front end.

Needs: MySQL with fir_ccms loaded, and `pip install pymysql`.
    python3 tools/export_web_data.py

Connection (defaults suit a local server reached by socket as root):
    MYSQL_SOCKET=/var/run/mysqld/mysqld.sock
    or MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD
"""
import datetime
import decimal
import json
import os
import re
import subprocess
from collections import defaultdict

import pymysql
import pymysql.cursors

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AS_OF = "2026-10-30 12:00:00"   # "today" in the sample data; same clock as docs/QUERY_RESULTS.md


def connect():
    kw = dict(user=os.environ.get("MYSQL_USER", "root"), password=os.environ.get("MYSQL_PASSWORD", ""),
              database="fir_ccms", charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    if os.environ.get("MYSQL_HOST"):
        kw.update(host=os.environ["MYSQL_HOST"], port=int(os.environ.get("MYSQL_PORT", "3306")))
    else:
        kw["unix_socket"] = os.environ.get("MYSQL_SOCKET", "/var/run/mysqld/mysqld.sock")
    return pymysql.connect(**kw)


def clean(v):
    if isinstance(v, (datetime.datetime,)):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return v


def main():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SET @as_of = %s", (AS_OF,))

    def q(sql, args=None):
        cur.execute(sql, args)
        return [{k: clean(v) for k, v in row.items()} for row in cur.fetchall()]

    def group(rows, key="fir_id"):
        out = defaultdict(list)
        for r in rows:
            out[r[key]].append(r)
        return out

    firs = q("""SELECT r.fir_id, r.fir_number, r.station, r.district, r.reported_at, r.incident_at,
                       r.reporting_delay_hours, r.category, r.complainant, r.sections, r.status,
                       r.investigating_officer, f.incident_location, f.description, f.closure_remarks,
                       f.complainant_person_id
                  FROM vw_fir_register r JOIN firs f ON f.fir_id = r.fir_id ORDER BY r.fir_id""")

    sections = group(q("""SELECT fs.fir_id, CONCAT(ls.act,' ',ls.section_no) AS section, ls.title, ls.punishment_summary AS punishment,
                                 ls.is_cognizable AS cognizable, ls.is_bailable AS bailable
                            FROM fir_sections fs JOIN legal_sections ls ON ls.section_id = fs.section_id
                           ORDER BY fs.fir_id, ls.act, ls.section_no"""))
    parties = group(q("""SELECT fp.fir_id, fp.party_role AS role, p.person_id, p.full_name AS name, p.cnic, fp.statement
                           FROM fir_parties fp JOIN persons p ON p.person_id = fp.person_id ORDER BY fp.fir_id, fp.party_id"""))
    accused = group(q("""SELECT fa.fir_id, fa.fir_accused_id AS accused_id, p.person_id, p.full_name AS name, p.cnic, fa.status, fa.added_on
                           FROM fir_accused fa JOIN persons p ON p.person_id = fa.person_id ORDER BY fa.fir_id, fa.fir_accused_id"""))
    assignments = group(q("""SELECT ia.fir_id, o.full_name AS officer, r.title AS rank_title, ia.assigned_on, ia.ended_on, ia.reason
                               FROM investigation_assignments ia JOIN officers o ON o.officer_id = ia.officer_id
                               JOIN ranks r ON r.rank_id = o.rank_id ORDER BY ia.fir_id, ia.assigned_on, ia.assignment_id"""))
    diary = group(q("""SELECT cd.fir_id, cd.entry_date AS date, o.full_name AS officer, cd.entry_text AS text
                         FROM case_diary cd JOIN officers o ON o.officer_id = cd.officer_id ORDER BY cd.fir_id, cd.entry_date, cd.diary_id"""))
    history = group(q("""SELECT fir_id, old_status, new_status, changed_at FROM fir_status_history ORDER BY fir_id, changed_at, history_id"""))
    custody = group(q("""SELECT l.evidence_id, l.transferred_at AS at, fo.full_name AS from_officer, t.full_name AS to_officer, l.purpose
                           FROM evidence_custody_log l LEFT JOIN officers fo ON fo.officer_id = l.from_officer_id
                           JOIN officers t ON t.officer_id = l.to_officer_id ORDER BY l.evidence_id, l.transferred_at, l.log_id"""),
                   "evidence_id")
    labs = group(q("""SELECT evidence_id, lab_name AS lab, report_type AS type, submitted_on, reported_on, findings FROM lab_reports ORDER BY report_id"""),
                 "evidence_id")
    evidence = q("""SELECT e.evidence_id, e.evidence_no, e.fir_id, et.name AS type, et.is_digital AS digital, e.description,
                           e.collected_at, o.full_name AS collected_by, e.found_location, c.full_name AS custodian,
                           e.storage_location, e.status, e.hash_sha256 AS hash
                      FROM evidence e JOIN evidence_types et ON et.type_id = e.type_id
                      JOIN officers o ON o.officer_id = e.collected_by JOIN officers c ON c.officer_id = e.current_custodian_id
                     ORDER BY e.evidence_no""")
    for e in evidence:
        e["custody"] = custody.get(e["evidence_id"], [])
        e["lab"] = labs.get(e["evidence_id"], [])
    evidence_by_fir = group(evidence)
    arrests = group(q("""SELECT fa.fir_id, p.full_name AS name, o.full_name AS officer, a.arrested_at, a.location, a.remand_days, a.released_at
                           FROM arrests a JOIN fir_accused fa ON fa.fir_accused_id = a.fir_accused_id
                           JOIN persons p ON p.person_id = fa.person_id JOIN officers o ON o.officer_id = a.arrested_by
                          ORDER BY fa.fir_id, a.arrested_at"""))
    bail = group(q("""SELECT fa.fir_id, p.full_name AS name, c.name AS court, b.bail_type, b.applied_on, b.decided_on, b.decision,
                             b.surety_amount, b.remarks
                        FROM bail_applications b JOIN fir_accused fa ON fa.fir_accused_id = b.fir_accused_id
                        JOIN persons p ON p.person_id = fa.person_id JOIN courts c ON c.court_id = b.court_id
                       ORDER BY fa.fir_id, b.applied_on, b.bail_id"""))
    hearings = group(q("""SELECT h.case_id, h.hearing_date AS date, j.full_name AS judge, h.purpose, h.outcome, h.next_hearing_date AS next
                            FROM hearings h JOIN judges j ON j.judge_id = h.judge_id ORDER BY h.case_id, h.hearing_date"""), "case_id")
    verdicts = group(q("""SELECT v.case_id, p.full_name AS name, v.verdict, v.verdict_on AS date, v.sentence_years, v.fine_amount, v.remarks
                            FROM verdicts v JOIN fir_accused fa ON fa.fir_accused_id = v.fir_accused_id
                            JOIN persons p ON p.person_id = fa.person_id ORDER BY v.case_id, v.verdict_id"""), "case_id")
    cases = group(q("""SELECT cc.case_id, cc.fir_id, cc.case_number, c.name AS court, c.court_type, cc.filed_on, cc.status
                         FROM court_cases cc JOIN courts c ON c.court_id = cc.court_id ORDER BY cc.fir_id, cc.case_id"""))
    for rows in cases.values():
        for cs in rows:
            cs["hearings"] = hearings.get(cs["case_id"], [])
            cs["verdicts"] = verdicts.get(cs["case_id"], [])

    for f in firs:
        i = f["fir_id"]
        f["sectionList"] = sections.get(i, [])
        f["parties"] = parties.get(i, [])
        f["accused"] = accused.get(i, [])
        f["assignments"] = assignments.get(i, [])
        f["diary"] = diary.get(i, [])
        f["history"] = history.get(i, [])
        f["evidence"] = evidence_by_fir.get(i, [])
        f["arrests"] = arrests.get(i, [])
        f["bail"] = bail.get(i, [])
        f["cases"] = cases.get(i, [])

    persons = q("""SELECT p.person_id, p.cnic, p.full_name AS name, p.father_name AS father, p.gender, p.date_of_birth AS dob,
                          fn_age(p.date_of_birth) AS age, p.address, d.name AS district, p.occupation
                     FROM persons p LEFT JOIN districts d ON d.district_id = p.district_id ORDER BY p.full_name""")
    officers = q("""SELECT o.officer_id, o.badge_no, o.full_name AS name, r.title AS rank_title, r.rank_level, ps.name AS station,
                           s.full_name AS supervisor, o.is_active AS active
                      FROM officers o JOIN ranks r ON r.rank_id = o.rank_id JOIN police_stations ps ON ps.station_id = o.station_id
                      LEFT JOIN officers s ON s.officer_id = o.supervisor_id ORDER BY r.rank_level DESC, o.full_name""")
    stations = q("SELECT * FROM vw_station_performance ORDER BY total_firs DESC, station")
    cause_list = q("SELECT * FROM vw_cause_list ORDER BY next_hearing_date, court")
    stale = q("SELECT * FROM vw_stale_investigations ORDER BY days_idle DESC")
    workload = q("SELECT * FROM vw_open_cases_by_officer ORDER BY open_cases DESC, officer")

    # the 27 documented queries and their live results
    text = open(os.path.join(ROOT, "database", "queries.sql"), encoding="utf-8").read()
    blocks = re.split(r"^-- (Q\d+) \| (.*)$", text, flags=re.M)[1:]
    queries = []
    for i in range(0, len(blocks), 3):
        qid, title, body = blocks[i], blocks[i + 1].strip(), blocks[i + 2]
        purpose = re.search(r"-- Purpose: (.*)", body).group(1).strip()
        sql = "\n".join(l for l in body.strip().splitlines() if not l.startswith("-- Purpose:")).strip()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [[clean(row[c]) for c in cols] for row in cur.fetchall()]
        queries.append(dict(id=qid, title=title, purpose=purpose, sql=sql, columns=cols, rows=rows))

    # the 45 integrity tests, run now against the same database
    tests_path = "/tmp/fir_cms_tests.json"
    subprocess.run(["python3", os.path.join(ROOT, "tools", "run_integrity_tests.py"), "--json", tests_path],
                   check=True, stdout=subprocess.DEVNULL)
    tests = json.load(open(tests_path, encoding="utf-8"))

    def count(sql):
        cur.execute(sql)
        return list(cur.fetchone().values())[0]

    meta = dict(
        generated_at=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        as_of=AS_OF[:10],
        mysql_version=count("SELECT VERSION()"),
        tables=count("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='fir_ccms' AND table_type='BASE TABLE'"),
        triggers=count("SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema='fir_ccms'"),
        procedures=count("SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='fir_ccms' AND routine_type='PROCEDURE'"),
        functions=count("SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='fir_ccms' AND routine_type='FUNCTION'"),
        views=count("SELECT COUNT(*) FROM information_schema.views WHERE table_schema='fir_ccms'"),
        queries=len(queries), tests=len(tests), tests_passed=sum(1 for t in tests if t["rejected"]),
        custody_rows=count("SELECT COUNT(*) FROM evidence_custody_log"),
        history_rows=count("SELECT COUNT(*) FROM fir_status_history"),
    )

    data = dict(meta=meta, firs=firs, persons=persons, officers=officers, stations=stations,
                cause_list=cause_list, stale=stale, workload=workload, queries=queries, tests=tests)
    out = os.path.join(ROOT, "web", "data.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote web/data.json ({os.path.getsize(out) // 1024} KB): {len(firs)} FIRs, {len(persons)} persons, "
          f"{len(evidence)} exhibits, {len(queries)} queries, {len(tests)} tests")


if __name__ == "__main__":
    main()
