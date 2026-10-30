#!/usr/bin/env python3
"""Build the generated documentation from the LIVE database.

Needs MySQL with fir_ccms loaded, and Graphviz (`dot`) for the picture.
    python3 tools/build_docs.py

Writes:
    docs/DATA_DICTIONARY.md   tables, columns, constraints and triggers
    docs/ERD.md               Mermaid ERD (renders on GitHub)
    docs/erd.svg, docs/erd.png  Graphviz ERD
    docs/QUERY_RESULTS.md     the 27 queries with their real output
    docs/INTEGRITY_TESTS.md   the 45 rule-breaking tests and MySQL's replies
    database/fir_ccms.sql     schema + logic + data in one importable file
"""
import os
import re
import shlex
import subprocess
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MYSQL = shlex.split(os.environ.get("MYSQL_CMD", "mysql"))
DB = os.environ.get("FIR_DB", "fir_ccms")
AS_OF = "2026-10-30 12:00:00"

PURPOSE = {
    "districts": "Districts the force works in, with their province.",
    "police_stations": "Police stations. Each belongs to one district and has a three-letter code used in FIR numbers.",
    "ranks": "Police ranks in order of seniority. The can_investigate flag says which ranks may lead an investigation.",
    "crime_categories": "Broad crime groups used for statistics (person, property, cyber, narcotics and so on).",
    "legal_sections": "Sections of law an FIR can be registered under, with cognizable and bailable flags.",
    "officers": "Police officers. Each is posted at one station and may report to a supervisor (self reference).",
    "roles": "User roles of the system (administrator, SHO, investigating officer and so on).",
    "users": "Login accounts. A user may be linked to an officer.",
    "persons": "Every human who appears in a case. One row per person whatever their role, so a person's history is in one place.",
    "firs": "First Information Reports. The central table of the system.",
    "fir_sections": "Which sections of law an FIR was registered under (many to many).",
    "fir_accused": "Accused persons of an FIR and where each one stands (nominated, arrested, on bail, convicted ...).",
    "fir_parties": "Victims and witnesses of an FIR, with their statements.",
    "fir_status_history": "Audit trail of every FIR status change. Filled by a trigger.",
    "investigation_assignments": "Which officer investigated an FIR, and when. Only one open assignment per FIR.",
    "case_diary": "Day-by-day notes of the investigating officer.",
    "arrests": "Arrests of accused persons, with remand days and release time.",
    "evidence_types": "Kinds of exhibit. The is_digital flag makes the SHA-256 hash mandatory.",
    "evidence": "Exhibits collected for an FIR, their current custodian and status.",
    "evidence_custody_log": "Chain of custody. Every hand-over of an exhibit, written by a trigger.",
    "lab_reports": "Forensic laboratory submissions and findings for an exhibit.",
    "courts": "Courts that hear cases.",
    "judges": "Judges and the court each one sits in.",
    "court_cases": "Cases filed in court on the basis of an FIR.",
    "hearings": "Each court hearing of a case, with the next date fixed.",
    "bail_applications": "Bail applications (before or after arrest) and the court's decision.",
    "verdicts": "Final verdict for each accused person in a case.",
}

# colour of the table header in the picture, by subject area
AREA = {
    "ref": ("#e3e8ec", ["districts", "police_stations", "ranks", "crime_categories", "legal_sections", "evidence_types", "roles"]),
    "people": ("#dbeedd", ["officers", "users", "persons", "judges"]),
    "case": ("#fbe7c6", ["firs", "fir_sections", "fir_accused", "fir_parties", "fir_status_history",
                          "investigation_assignments", "case_diary", "arrests"]),
    "evidence": ("#f6d6d6", ["evidence", "evidence_custody_log", "lab_reports"]),
    "court": ("#d6e2f6", ["courts", "court_cases", "hearings", "bail_applications", "verdicts"]),
}


def sql(query, database=DB, headers=False):
    args = MYSQL + ["--batch", database] + ([] if headers else ["--skip-column-names"])
    proc = subprocess.run(args, input=query, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"MySQL error: {proc.stderr}")
    return [line.split("\t") for line in proc.stdout.rstrip("\n").split("\n")] if proc.stdout.strip() else []


def write(path, text):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote", path)


# ---------------------------------------------------------------------
def load_schema():
    tables = [r[0] for r in sql(
        "SELECT table_name FROM information_schema.tables "
        f"WHERE table_schema='{DB}' AND table_type='BASE TABLE' ORDER BY table_name")]
    cols = defaultdict(list)
    for t, c, typ, null, key, default, extra, pos in sql(
            "SELECT table_name, column_name, column_type, is_nullable, column_key, "
            "IFNULL(column_default,'-'), extra, ordinal_position FROM information_schema.columns "
            f"WHERE table_schema='{DB}' ORDER BY table_name, ordinal_position"):
        cols[t].append(dict(name=c, type=typ, null=null, key=key, default=default, extra=extra))
    fks = []   # child, child_col, parent, parent_col, nullable
    for child, col, parent, pcol in sql(
            "SELECT table_name, column_name, referenced_table_name, referenced_column_name "
            "FROM information_schema.key_column_usage "
            f"WHERE table_schema='{DB}' AND referenced_table_name IS NOT NULL ORDER BY table_name, constraint_name"):
        nullable = next(c["null"] == "YES" for c in cols[child] if c["name"] == col)
        fks.append((child, col, parent, pcol, nullable))
    return tables, cols, fks


# ---------------------------------------------------------------------
def build_dictionary(tables, cols, fks):
    counts = {t: n for t, n in sql(
        "SELECT table_name, table_rows FROM information_schema.tables "
        f"WHERE table_schema='{DB}' AND table_type='BASE TABLE'")}
    exact = {}
    for t in tables:
        exact[t] = sql(f"SELECT COUNT(*) FROM `{t}`")[0][0]
    checks = defaultdict(list)
    for t, name, clause in sql(
            "SELECT tc.table_name, cc.constraint_name, cc.check_clause FROM information_schema.check_constraints cc "
            "JOIN information_schema.table_constraints tc ON tc.constraint_schema = cc.constraint_schema "
            "AND tc.constraint_name = cc.constraint_name AND tc.constraint_type = 'CHECK' "
            f"WHERE cc.constraint_schema='{DB}' ORDER BY tc.table_name, cc.constraint_name"):
        checks[t].append((name, clause))
    uniques = defaultdict(list)
    for t, name, cl in sql(
            "SELECT table_name, index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index) "
            f"FROM information_schema.statistics WHERE table_schema='{DB}' AND non_unique=0 AND index_name<>'PRIMARY' "
            "GROUP BY table_name, index_name ORDER BY table_name, index_name"):
        uniques[t].append((name, cl))
    triggers = defaultdict(list)
    for t, name, timing, event in sql(
            "SELECT event_object_table, trigger_name, action_timing, event_manipulation "
            f"FROM information_schema.triggers WHERE trigger_schema='{DB}' ORDER BY event_object_table, trigger_name"):
        triggers[t].append((name, timing, event))
    fk_by_child = defaultdict(list)
    for child, col, parent, pcol, _n in fks:
        fk_by_child[child].append((col, parent, pcol))

    out = ["# Data dictionary", "",
           f"{len(tables)} tables. Generated from the live database by `python3 tools/build_docs.py`; "
           "do not edit by hand.", "",
           "| Table | Rows (sample data) | Purpose |", "|---|---:|---|"]
    for t in tables:
        out.append(f"| [`{t}`](#{t}) | {exact[t]} | {PURPOSE.get(t, '')} |")
    out.append("")
    for t in tables:
        out += [f"## {t}", "", PURPOSE.get(t, ""), "",
                "| Column | Type | Null | Key | Notes |", "|---|---|---|---|---|"]
        fkcols = {c: f"FK to `{p}.{pc}`" for c, p, pc in fk_by_child[t]}
        for c in cols[t]:
            key = {"PRI": "PK", "UNI": "UNIQUE", "MUL": ""}.get(c["key"], "")
            note = []
            if c["name"] in fkcols:
                note.append(fkcols[c["name"]])
            if "auto_increment" in c["extra"]:
                note.append("auto number")
            if "GENERATED" in c["extra"]:
                note.append("generated column")
            if c["default"] != "-" and c["default"] != "NULL":
                note.append(f"default {c['default']}")
            out.append(f"| `{c['name']}` | {c['type']} | {c['null']} | {key} | {'; '.join(note)} |")
        out.append("")
        if uniques[t]:
            out.append("**Unique keys:** " + "; ".join(f"`{n}` ({c})" for n, c in uniques[t]))
            out.append("")
        if checks[t]:
            out.append("**Check constraints:**")
            out.append("")
            for name, clause in checks[t]:
                clause = clause.replace("|", "\\|")
                out.append(f"- `{name}`: `{clause}`")
            out.append("")
        if triggers[t]:
            out.append("**Triggers:** " + "; ".join(f"`{n}` ({tm} {ev})" for n, tm, ev in triggers[t]))
            out.append("")
    write("docs/DATA_DICTIONARY.md", "\n".join(out) + "\n")


# ---------------------------------------------------------------------
def build_mermaid(tables, cols, fks):
    fk_cols = defaultdict(set)
    for child, col, *_ in fks:
        fk_cols[child].add(col)
    out = ["# Entity Relationship Diagram", "",
           "![Entity relationship diagram](erd.png)", "",
           "The picture above is [`erd.svg`](erd.svg) (scalable) and [`erd.png`](erd.png). "
           "The same model as a Mermaid diagram follows; GitHub draws it in the browser.", "",
           "Colours in the picture: grey is reference data, green is people, orange is the FIR and its "
           "investigation, red is evidence, blue is courts.", "",
           "```mermaid", "erDiagram"]
    for child, col, parent, pcol, nullable in fks:
        card = "|o--o{" if nullable else "||--o{"
        out.append(f"    {parent} {card} {child} : \"{col}\"")
    for t in tables:
        out.append(f"    {t} {{")
        for c in cols[t]:
            typ = re.match(r"[a-z]+", c["type"]).group(0)
            marks = []
            if c["key"] == "PRI":
                marks.append("PK")
            if c["name"] in fk_cols[t]:
                marks.append("FK")
            out.append(f"        {typ} {c['name']}" + (f" {','.join(marks)}" if marks else ""))
        out.append("    }")
    out += ["```", ""]
    write("docs/ERD.md", "\n".join(out))


def build_graphviz(tables, cols, fks):
    fk_cols = defaultdict(set)
    for child, col, *_ in fks:
        fk_cols[child].add(col)
    colour = {}
    for _area, (hex_, members) in AREA.items():
        for m in members:
            colour[m] = hex_
    dot = ['digraph erd {', '  graph [rankdir=LR, splines=true, nodesep=0.28, ranksep=1.1, fontname="Helvetica", pad=0.3, bgcolor="white"];',
           '  node [shape=plain, fontname="Helvetica", fontsize=10];',
           '  edge [color="#55636b", arrowsize=0.7, dir=both, penwidth=1.0];']
    for t in tables:
        rows = []
        shown = [c for c in cols[t] if c["key"] == "PRI" or c["name"] in fk_cols[t]]
        others = [c for c in cols[t] if c not in shown]
        extra_rows = others[:2]
        hidden = len(others) - len(extra_rows)
        for c in shown + extra_rows:
            tag = "PK " if c["key"] == "PRI" else ("FK " if c["name"] in fk_cols[t] else "")
            bold = "<B>" if c["key"] == "PRI" else ""
            endbold = "</B>" if c["key"] == "PRI" else ""
            rows.append(f'<TR><TD ALIGN="LEFT" PORT="{c["name"]}">{bold}{tag}{c["name"]}{endbold}</TD></TR>')
        if hidden > 0:
            rows.append(f'<TR><TD ALIGN="LEFT"><I>+ {hidden} more</I></TD></TR>')
        dot.append(f'  {t} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" COLOR="#8a99a2">'
                   f'<TR><TD BGCOLOR="{colour[t]}"><B>{t}</B></TD></TR>{"".join(rows)}</TABLE>>];')
    for child, col, parent, pcol, nullable in fks:
        tail = "crowodot" if nullable else "crow"
        dot.append(f'  {child}:{col} -> {parent} [arrowtail={tail}, arrowhead=tee];')
    dot.append("}")
    path = os.path.join(ROOT, "docs", "erd.dot")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(dot) + "\n")
    for fmt in ("svg", "png"):
        extra = ["-Gdpi=110"] if fmt == "png" else []
        subprocess.run(["dot", f"-T{fmt}", *extra, path, "-o", os.path.join(ROOT, "docs", f"erd.{fmt}")], check=True)
        print("wrote docs/erd." + fmt)


# ---------------------------------------------------------------------
def md_table(rows):
    if not rows:
        return "_The query returns no rows._"
    head, body = rows[0], rows[1:]
    esc = lambda v: v.replace("|", "\\|")
    lines = ["| " + " | ".join(esc(h) for h in head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for r in body:
        lines.append("| " + " | ".join(esc(v) for v in r) + " |")
    return "\n".join(lines)


def build_query_results():
    text = open(os.path.join(ROOT, "database", "queries.sql"), encoding="utf-8").read()
    blocks = re.split(r"^-- (Q\d+) \| (.*)$", text, flags=re.M)[1:]
    out = ["# Query results", "",
           f"The 27 queries of [`database/queries.sql`](../database/queries.sql) with their real output. "
           f"Generated by `python3 tools/build_docs.py` with the clock fixed at {AS_OF} (`SET @as_of`), so "
           "'today' is 30 October 2026 and the results are repeatable.", ""]
    for i in range(0, len(blocks), 3):
        qid, title, body = blocks[i], blocks[i + 1].strip(), blocks[i + 2]
        purpose = re.search(r"-- Purpose: (.*)", body).group(1).strip()
        query = "\n".join(l for l in body.strip().splitlines() if not l.startswith("-- Purpose:")).strip()
        rows = sql(f"SET @as_of = '{AS_OF}';\n{query}", headers=True)
        out += [f"## {qid}. {title}", "", purpose, "", "```sql", query, "```", "",
                md_table(rows), "", f"_{max(len(rows) - 1, 0)} row(s)_", ""]
    write("docs/QUERY_RESULTS.md", "\n".join(out))


def build_combined():
    parts = []
    for name in ("schema.sql", "logic.sql", "data.sql"):
        parts.append(open(os.path.join(ROOT, "database", name), encoding="utf-8").read().rstrip() + "\n")
    banner = ("-- =====================================================================\n"
              "-- FIR-CMS complete build: schema.sql + logic.sql + data.sql in one file.\n"
              "-- Load with the mysql client:   mysql -u root -p < fir_ccms.sql\n"
              "-- GENERATED by tools/build_docs.py. Edit the three source files instead.\n"
              "-- =====================================================================\n\n")
    write("database/fir_ccms.sql", banner + "\n".join(parts))


def main():
    tables, cols, fks = load_schema()
    build_dictionary(tables, cols, fks)
    build_mermaid(tables, cols, fks)
    build_graphviz(tables, cols, fks)
    build_query_results()
    build_combined()
    subprocess.run(["python3", os.path.join(ROOT, "tools", "run_integrity_tests.py"),
                    "--markdown", "docs/INTEGRITY_TESTS.md"], check=True, stdout=subprocess.DEVNULL)
    print("wrote docs/INTEGRITY_TESTS.md")


if __name__ == "__main__":
    main()
