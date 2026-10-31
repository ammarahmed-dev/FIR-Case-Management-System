/* FIR Case Management front end.
   Reads data.json, an export of the MySQL database fir_ccms made by tools/export_web_data.py,
   and draws every screen from it. No server code, no build step. */
(function () {
  "use strict";

  var D = null;           // the exported database
  var BY_FIR = {};        // fir_id -> fir
  var PEOPLE = {};        // person_id -> person with involvement list
  var main = document.getElementById("main");

  /* ------------------------------------------------------------ helpers */
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function date(s) {
    if (!s) return "";
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    return m ? parseInt(m[3], 10) + " " + MONTHS[parseInt(m[2], 10) - 1] + " " + m[1] : esc(s);
  }
  function dt(s) {
    if (!s) return "";
    var t = /(\d{2}:\d{2})$/.exec(s);
    return date(s) + (t && t[1] !== "00:00" ? ", " + t[1] : "");
  }
  function money(n) { return n == null ? "" : "Rs " + Number(n).toLocaleString("en-US"); }
  var STATUS_CLASS = {
    "Registered": "c-reg", "Under Investigation": "c-inv", "Challaned": "c-chal", "In Court": "c-court",
    "Closed": "c-closed", "Cancelled": "c-cancel"
  };
  function chip(text, cls) { return '<span class="chip ' + (cls || STATUS_CLASS[text] || "") + '">' + esc(text) + "</span>"; }
  function outcomeChip(s) {
    var good = { "Granted": "c-good", "Convicted": "c-bad", "Acquitted": "c-good", "Discharged": "c-good", "Rejected": "c-bad",
      "On Bail": "c-warn", "Absconding": "c-bad", "Arrested": "c-inv", "Nominated": "c-reg", "Pending": "c-reg",
      "Decided": "c-closed", "Under Trial": "c-court", "Withdrawn": "c-cancel" };
    return chip(s, good[s] || "");
  }
  function firLink(f) { return '<a class="mono" href="#/fir/' + f.fir_id + '">' + esc(f.fir_number) + "</a>"; }
  function personLink(id, name) { return id ? '<a href="#/person/' + id + '">' + esc(name) + "</a>" : esc(name); }
  function table(head, rows, opts) {
    opts = opts || {};
    if (!rows.length) return '<div class="empty">' + esc(opts.empty || "Nothing to show.") + "</div>";
    return '<div class="tablewrap"><table><thead><tr>' + head.map(function (h) {
      return "<th" + (h.num ? ' class="num"' : "") + ">" + esc(h.t || h) + "</th>";
    }).join("") + "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
  }
  function setTitle(t) { document.title = t + " | FIR Case Management"; }

  /* ------------------------------------------------------------ data prep */
  function prepare() {
    D.firs.forEach(function (f) { BY_FIR[f.fir_id] = f; });
    D.persons.forEach(function (p) { p.involvement = []; PEOPLE[p.person_id] = p; });
    D.firs.forEach(function (f) {
      if (f.complainant_person_id && PEOPLE[f.complainant_person_id]) {
        PEOPLE[f.complainant_person_id].involvement.push({ fir: f, role: "Complainant", detail: "" });
      }
      f.parties.forEach(function (p) {
        PEOPLE[p.person_id].involvement.push({ fir: f, role: p.role, detail: p.statement || "" });
      });
      f.accused.forEach(function (a) {
        var verdict = null;
        f.cases.forEach(function (c) {
          c.verdicts.forEach(function (v) { if (v.name === a.name) verdict = v; });
        });
        PEOPLE[a.person_id].involvement.push({ fir: f, role: "Accused", status: a.status, verdict: verdict, detail: "" });
      });
    });
  }

  /* ------------------------------------------------------------ screens */
  function home() {
    setTitle("Overview");
    var f = D.firs, n = f.length;
    function c(fn) { return f.filter(fn).length; }
    var open = c(function (x) { return x.status === "Registered" || x.status === "Under Investigation"; });
    var inCourt = c(function (x) { return x.status === "In Court"; });
    var closed = c(function (x) { return x.status === "Closed"; });
    var absconding = 0, exLab = 0;
    f.forEach(function (x) {
      x.accused.forEach(function (a) { if (a.status === "Absconding") absconding++; });
      x.evidence.forEach(function (e) { if (e.status === "At Forensic Lab") exLab++; });
    });
    var soon = D.cause_list.filter(function (h) { return h.days_until >= 0 && h.days_until <= 60; });

    var statuses = ["Registered", "Under Investigation", "Challaned", "In Court", "Closed", "Cancelled"];
    var max = 1, counts = {};
    statuses.forEach(function (s) { counts[s] = c(function (x) { return x.status === s; }); max = Math.max(max, counts[s]); });
    var bars = statuses.map(function (s) {
      var color = { "Registered": "#8b9aa6", "Under Investigation": "#d08a1f", "Challaned": "#7b63c4", "In Court": "#1f5fa8", "Closed": "#2a9560", "Cancelled": "#c4605b" }[s];
      return '<div class="bar"><span>' + esc(s) + '</span><i style="width:' + Math.round(100 * counts[s] / max) + "%;background:" + color + '"></i><b>' + counts[s] + "</b></div>";
    }).join("");

    var perMonth = {};
    f.forEach(function (x) {
      var k = x.reported_at.slice(0, 7);
      perMonth[k] = perMonth[k] || { conv: 0, cyber: 0 };
      if (x.category === "Cyber Crime") perMonth[k].cyber++; else perMonth[k].conv++;
    });
    var keys = Object.keys(perMonth).sort();
    var pmax = Math.max.apply(null, keys.map(function (k) { return perMonth[k].conv + perMonth[k].cyber; }));
    var months = keys.map(function (k) {
      var m = perMonth[k], u = 100 / pmax * 0.78;
      return '<div class="month" title="' + MONTHS[parseInt(k.slice(5), 10) - 1] + ": " + (m.conv + m.cyber) + ' FIRs"><div class="stack"><i class="seg-cyber" style="height:' + Math.round(m.cyber * u * 1.2) + 'px"></i><i class="seg-conv" style="height:' + Math.round(m.conv * u * 1.2) + 'px"></i></div><span>' + MONTHS[parseInt(k.slice(5), 10) - 1] + "</span></div>";
    }).join("");

    var unassigned = f.filter(function (x) { return x.assignments.length === 0 && x.status === "Registered"; });
    var absc = [];
    f.forEach(function (x) { x.accused.forEach(function (a) { if (a.status === "Absconding") absc.push({ f: x, a: a }); }); });

    main.innerHTML =
      '<div class="eyebrow">Overview</div><h1>Case overview</h1>' +
      '<p class="sub">Every number on this page is counted from the sample data in the MySQL database. "Today" is ' + date(D.meta.as_of) + ".</p>" +
      '<div class="kpis">' +
      '<a class="kpi" href="#/firs"><b>' + n + "</b><span>FIRs registered</span></a>" +
      '<a class="kpi" href="#/firs?status=Under%20Investigation"><b>' + open + "</b><span>being investigated or waiting</span></a>" +
      '<a class="kpi" href="#/firs?status=In%20Court"><b>' + inCourt + "</b><span>in court</span></a>" +
      '<a class="kpi" href="#/firs?status=Closed"><b>' + closed + "</b><span>closed</span></a>" +
      '<a class="kpi" href="#/people"><b>' + absconding + "</b><span>accused absconding</span></a>" +
      '<a class="kpi" href="#/evidence"><b>' + exLab + "</b><span>exhibit at the lab now</span></a>" +
      "</div>" +
      '<div class="grid g2">' +
      '<div class="card"><h3>FIRs by stage</h3><div class="bars">' + bars + "</div></div>" +
      '<div class="card"><h3>FIRs registered per month</h3><div class="months">' + months + '</div><div class="legend"><span><i style="background:#9db6d0"></i>Conventional crime</span><span><i style="background:var(--brass)"></i>Cyber crime</span></div></div>' +
      "</div>" +
      "<h2>Needs attention</h2>" +
      '<div class="grid g3">' +
      '<div class="card"><h3>No investigating officer yet (' + unassigned.length + ")</h3><ul class='list'>" +
      (unassigned.map(function (x) { return "<li><div class='row'>" + firLink(x) + "<span class='muted small'>" + esc(x.station) + "</span></div><span class='small muted'>" + esc(x.category) + ", reported " + date(x.reported_at) + "</span></li>"; }).join("") || "<li class='muted'>None</li>") +
      "</ul></div>" +
      '<div class="card"><h3>Investigations gone quiet (' + D.stale.length + ")</h3><ul class='list'>" +
      D.stale.map(function (s) { return "<li><div class='row'><a class='mono' href='#/fir/" + s.fir_id + "'>" + esc(s.fir_number) + "</a>" + chip(s.days_idle + " days idle", "c-warn") + "</div><span class='small muted'>" + esc(s.investigating_officer) + "</span></li>"; }).join("") +
      "</ul></div>" +
      '<div class="card"><h3>Absconding accused (' + absc.length + ")</h3><ul class='list'>" +
      absc.map(function (r) { return "<li><div class='row'>" + personLink(r.a.person_id, r.a.name) + "<a class='mono small' href='#/fir/" + r.f.fir_id + "'>" + esc(r.f.fir_number) + "</a></div><span class='small muted'>IO: " + esc(r.f.investigating_officer || "none") + "</span></li>"; }).join("") +
      "</ul></div></div>" +
      "<h2>Court dates in the next 60 days (" + soon.length + ")</h2>" +
      table(["Date", "In", "Court", "Case", "FIR", "Last stage"], soon.map(function (h) {
        return "<tr><td class='nowrap'>" + date(h.next_hearing_date) + "</td><td class='nowrap'>" + h.days_until + " days</td><td>" + esc(h.court) + "</td><td class='mono'>" + esc(h.case_number) + "</td><td>" + firLinkByNumber(h.fir_number) + "</td><td>" + esc(h.last_purpose) + "</td></tr>";
      }), { empty: "No hearings in the next 60 days." });
  }

  function firLinkByNumber(num) {
    var f = D.firs.filter(function (x) { return x.fir_number === num; })[0];
    return f ? firLink(f) : esc(num);
  }

  function firs(params) {
    setTitle("FIR register");
    var statuses = [], stations = [], cats = [];
    D.firs.forEach(function (f) {
      if (statuses.indexOf(f.status) < 0) statuses.push(f.status);
      if (stations.indexOf(f.station) < 0) stations.push(f.station);
      if (cats.indexOf(f.category) < 0) cats.push(f.category);
    });
    function opts(list, sel) { return list.sort().map(function (x) { return "<option" + (x === sel ? " selected" : "") + ">" + esc(x) + "</option>"; }).join(""); }
    main.innerHTML =
      '<div class="eyebrow">FIR register</div><h1>First Information Reports</h1>' +
      '<p class="sub">The daily register. Open any FIR to see its whole case file: people, investigation, evidence, bail and court.</p>' +
      '<div class="filters"><input type="search" id="fq" placeholder="Search number, person, officer, section..." aria-label="Search FIRs" value="' + esc(params.q || "") + '">' +
      '<select id="fs" aria-label="Status"><option value="">All statuses</option>' + opts(statuses, params.status) + "</select>" +
      '<select id="fst" aria-label="Station"><option value="">All stations</option>' + opts(stations, params.station) + "</select>" +
      '<select id="fc" aria-label="Category"><option value="">All categories</option>' + opts(cats, params.category) + "</select>" +
      '<span class="count" id="fcount"></span></div><div id="ftable"></div>';
    function draw() {
      var q = document.getElementById("fq").value.toLowerCase().trim();
      var s = document.getElementById("fs").value, st = document.getElementById("fst").value, c = document.getElementById("fc").value;
      var rows = D.firs.filter(function (f) {
        if (s && f.status !== s) return false;
        if (st && f.station !== st) return false;
        if (c && f.category !== c) return false;
        if (!q) return true;
        var hay = [f.fir_number, f.complainant, f.investigating_officer, f.sections, f.station, f.category, f.incident_location]
          .concat(f.accused.map(function (a) { return a.name; })).join(" ").toLowerCase();
        return hay.indexOf(q) >= 0;
      }).map(function (f) {
        return "<tr><td class='nowrap'>" + firLink(f) + "</td><td class='nowrap'>" + date(f.reported_at) + "</td><td>" + esc(f.station.replace(" Police Station", "")) + "</td><td>" + esc(f.category) + "</td><td>" + esc(f.complainant) + "</td><td>" + esc(f.sections) + "</td><td>" + chip(f.status) + "</td><td>" + esc(f.investigating_officer || "") + "</td></tr>";
      });
      document.getElementById("fcount").textContent = rows.length + " of " + D.firs.length + " FIRs";
      document.getElementById("ftable").innerHTML = table(["FIR no.", "Reported", "Station", "Category", "Complainant", "Sections", "Status", "Investigating officer"], rows, { empty: "No FIR matches these filters." });
    }
    ["fq", "fs", "fst", "fc"].forEach(function (id) { document.getElementById(id).addEventListener("input", draw); });
    draw();
  }

  function flags(s) {
    return '<span class="flag">' + (s.cognizable ? "Cognizable" : "Non-cognizable") + '</span><span class="flag">' + (s.bailable ? "Bailable" : "Non-bailable") + "</span>";
  }

  function fir(id) {
    var f = BY_FIR[id];
    if (!f) { main.innerHTML = '<p class="empty">No such FIR.</p>'; return; }
    setTitle(f.fir_number);
    var ids = D.firs.map(function (x) { return x.fir_id; }), i = ids.indexOf(f.fir_id);
    var prev = i > 0 ? BY_FIR[ids[i - 1]] : null, next = i < ids.length - 1 ? BY_FIR[ids[i + 1]] : null;
    var victims = f.parties.filter(function (p) { return p.role === "Victim"; });
    var witnesses = f.parties.filter(function (p) { return p.role === "Witness"; });
    var compLink = f.complainant_person_id ? personLink(f.complainant_person_id, f.complainant) : esc(f.complainant);

    function sect(title, body) { return "<h2>" + title + "</h2>" + body; }

    var people = '<div class="grid g2">' +
      '<div class="card"><h3>Complainant</h3><p style="margin:0">' + compLink + "</p></div>" +
      '<div class="card"><h3>Accused (' + f.accused.length + ")</h3>" + (f.accused.length ? "<ul class='list'>" + f.accused.map(function (a) {
        return "<li><div class='row'>" + personLink(a.person_id, a.name) + outcomeChip(a.status) + "</div><span class='small muted mono'>" + esc(a.cnic || "no CNIC on file") + ", named " + date(a.added_on) + "</span></li>";
      }).join("") + "</ul>" : "<p class='muted' style='margin:0'>No accused person named yet.</p>") + "</div>" +
      '<div class="card"><h3>Victims (' + victims.length + ")</h3>" + (victims.length ? "<ul class='list'>" + victims.map(function (p) { return "<li>" + personLink(p.person_id, p.name) + (p.statement ? "<span class='small muted'>" + esc(p.statement) + "</span>" : "") + "</li>"; }).join("") + "</ul>" : "<p class='muted' style='margin:0'>None recorded.</p>") + "</div>" +
      '<div class="card"><h3>Witnesses (' + witnesses.length + ")</h3>" + (witnesses.length ? "<ul class='list'>" + witnesses.map(function (p) { return "<li>" + personLink(p.person_id, p.name) + (p.statement ? "<span class='small muted'>" + esc(p.statement) + "</span>" : "") + "</li>"; }).join("") + "</ul>" : "<p class='muted' style='margin:0'>None recorded.</p>") + "</div></div>";

    var invest = '<div class="grid g2"><div class="card"><h3>Investigating officers</h3>' +
      (f.assignments.length ? "<ul class='timeline'>" + f.assignments.map(function (a) {
        return "<li class='" + (a.ended_on ? "" : "hot") + "'><span class='when'>" + date(a.assigned_on) + " to " + (a.ended_on ? date(a.ended_on) : "now") + "</span><b>" + esc(a.officer) + "</b><span class='small muted'>" + esc(a.rank_title) + ". " + esc(a.reason || "") + "</span></li>";
      }).join("") + "</ul>" : "<p class='muted' style='margin:0'>No officer assigned yet.</p>") + "</div>" +
      '<div class="card"><h3>Case diary (' + f.diary.length + ")</h3>" +
      (f.diary.length ? "<ul class='timeline'>" + f.diary.map(function (d) {
        return "<li><span class='when'>" + date(d.date) + ", " + esc(d.officer) + "</span><span class='small'>" + esc(d.text) + "</span></li>";
      }).join("") + "</ul>" : "<p class='muted' style='margin:0'>No diary entries.</p>") + "</div></div>";

    var evid = f.evidence.length ? '<div class="grid">' + f.evidence.map(exhibitCard).join("") + "</div>" : "<p class='muted'>No exhibits collected.</p>";

    var custodyRows = f.arrests.map(function (a) {
      return "<tr><td>Arrest</td><td>" + esc(a.name) + "</td><td class='nowrap'>" + dt(a.arrested_at) + "</td><td>" + esc(a.officer) + ", " + esc(a.location) + ". Remand " + a.remand_days + " day(s)" + (a.released_at ? ". Released " + dt(a.released_at) : ". In custody") + "</td></tr>";
    }).concat(f.bail.map(function (b) {
      return "<tr><td>Bail (" + esc(b.bail_type.toLowerCase()) + ")</td><td>" + esc(b.name) + "</td><td class='nowrap'>" + date(b.applied_on) + "</td><td>" + esc(b.court) + ". " + outcomeChip(b.decision) + (b.decided_on ? " on " + date(b.decided_on) : "") + (b.surety_amount ? ", surety " + money(b.surety_amount) : "") + (b.remarks ? ". <span class='muted'>" + esc(b.remarks) + "</span>" : "") + "</td></tr>";
    }));
    var arrestBail = table(["Event", "Person", "Date", "Details"], custodyRows, { empty: "No arrests or bail applications." });

    var courts = f.cases.length ? f.cases.map(function (c) {
      return '<div class="card" style="margin-bottom:12px"><div class="filehead" style="margin-bottom:8px"><h3 style="margin:0" class="mono">' + esc(c.case_number) + "</h3>" + outcomeChip(c.status) + '<span class="muted small">' + esc(c.court) + ", filed " + date(c.filed_on) + "</span></div>" +
        table(["Hearing", "Judge", "Stage", "Outcome", "Next date"], c.hearings.map(function (h) {
          return "<tr><td class='nowrap'>" + date(h.date) + "</td><td>" + esc(h.judge) + "</td><td>" + esc(h.purpose) + "</td><td>" + esc(h.outcome || "") + "</td><td class='nowrap'>" + date(h.next) + "</td></tr>";
        }), { empty: "No hearings yet." }) +
        (c.verdicts.length ? "<h3 style='margin-top:14px'>Verdicts</h3>" + table(["Accused", "Verdict", "Date", "Sentence", "Fine", "Remarks"], c.verdicts.map(function (v) {
          return "<tr><td>" + esc(v.name) + "</td><td>" + outcomeChip(v.verdict) + "</td><td class='nowrap'>" + date(v.date) + "</td><td>" + (v.sentence_years ? v.sentence_years + " years" : "") + "</td><td>" + (v.fine_amount ? money(v.fine_amount) : "") + "</td><td>" + esc(v.remarks || "") + "</td></tr>";
        })) : "") + "</div>";
    }).join("") : "<p class='muted'>Not in court.</p>";

    main.innerHTML =
      '<div class="crumbs"><a href="#/firs">FIR register</a> / ' + esc(f.fir_number) + "</div>" +
      '<div class="filehead"><h1>' + esc(f.fir_number) + "</h1>" + chip(f.status) + "</div>" +
      '<p class="sub" style="margin-bottom:0">' + esc(f.station) + ", " + esc(f.district) + ". " + esc(f.category) + ".</p>" +
      '<dl class="facts">' +
      "<div><dt>Incident</dt><dd>" + dt(f.incident_at) + "</dd></div>" +
      "<div><dt>FIR registered</dt><dd>" + dt(f.reported_at) + "</dd></div>" +
      "<div><dt>Reporting delay</dt><dd>" + f.reporting_delay_hours + " hours</dd></div>" +
      "<div><dt>Complainant</dt><dd>" + compLink + "</dd></div>" +
      "<div><dt>Investigating officer</dt><dd>" + esc(f.investigating_officer || "Not assigned") + "</dd></div>" +
      "<div><dt>Place</dt><dd>" + esc(f.incident_location) + "</dd></div></dl>" +
      '<div class="story"><div class="eyebrow">What was reported</div>' + esc(f.description) + (f.closure_remarks ? "<br><b>Closing remarks:</b> " + esc(f.closure_remarks) : "") + "</div>" +
      sect("Sections of law", table(["Section", "Offence", "Punishment", "Nature"], f.sectionList.map(function (s) {
        return "<tr><td class='mono nowrap'>" + esc(s.section) + "</td><td>" + esc(s.title) + "</td><td>" + esc(s.punishment) + "</td><td>" + flags(s) + "</td></tr>";
      }))) +
      sect("Status history", '<div class="card"><ul class="timeline">' + f.history.map(function (h) {
        return "<li class='hot'><span class='when'>" + dt(h.changed_at) + "</span><span>" + (h.old_status ? esc(h.old_status) + " &rarr; " : "") + "<b>" + esc(h.new_status) + "</b></span></li>";
      }).join("") + '</ul><p class="small muted" style="margin:12px 0 0">Written by a database trigger on every status change, so it cannot be skipped.</p></div>') +
      sect("People", people) +
      sect("Investigation", invest) +
      sect("Evidence (" + f.evidence.length + ")", evid) +
      sect("Arrests and bail", arrestBail) +
      sect("Court", courts) +
      '<div class="filters" style="margin-top:28px">' + (prev ? '<a href="#/fir/' + prev.fir_id + '">&larr; ' + esc(prev.fir_number) + "</a>" : "") + '<span class="count">' + (next ? '<a href="#/fir/' + next.fir_id + '">' + esc(next.fir_number) + " &rarr;</a>" : "") + "</span></div>";
  }

  function exhibitCard(e) {
    var chain = "<ul class='timeline'>" + e.custody.map(function (c) {
      return "<li><span class='when'>" + dt(c.at) + "</span><span class='small'>" + (c.from_officer ? esc(c.from_officer) + " &rarr; " : "") + "<b>" + esc(c.to_officer) + "</b>. " + esc(c.purpose) + "</span></li>";
    }).join("") + "</ul>";
    var labs = e.lab.map(function (l) {
      return "<p class='small' style='margin:6px 0 0'><b>" + esc(l.type) + " report</b>, " + esc(l.lab) + ", submitted " + date(l.submitted_on) + (l.reported_on ? ", reported " + date(l.reported_on) + ". " + esc(l.findings) : ". <i>Report awaited.</i>") + "</p>";
    }).join("");
    return '<div class="card exhibit"><div class="top"><div><b class="mono">' + esc(e.evidence_no) + "</b> " + esc(e.type) + (e.digital ? ' <span class="flag">Digital, hash required</span>' : "") + "</div>" + chip(e.status, e.status === "At Forensic Lab" ? "c-warn" : e.status === "Destroyed" ? "c-cancel" : e.status === "Returned" ? "c-closed" : "c-reg") + "</div>" +
      "<div>" + esc(e.description) + "</div>" +
      "<div class='small muted'>Collected " + dt(e.collected_at) + " by " + esc(e.collected_by) + (e.found_location ? ", " + esc(e.found_location) : "") + ". Now with <b>" + esc(e.custodian) + "</b>" + (e.storage_location ? " (" + esc(e.storage_location) + ")" : "") + ".</div>" +
      (e.hash ? '<div class="hash" title="SHA-256 recorded at seizure. The database refuses any change to it.">SHA-256 ' + esc(e.hash) + "</div>" : "") +
      '<details><summary><b>Chain of custody</b><span class="muted small">' + e.custody.length + " entries, written by a trigger</span></summary><div class='inner'>" + chain + "</div></details>" + labs + "</div>";
  }

  function people(params) {
    setTitle("People");
    main.innerHTML =
      '<div class="eyebrow">People</div><h1>Persons in the system</h1>' +
      '<p class="sub">One row per human, whatever their role. The same person can be complainant, witness and accused in different FIRs, which is how repeat offenders are found.</p>' +
      '<div class="filters"><input type="search" id="pq" placeholder="Search name or CNIC..." aria-label="Search people" value="' + esc(params.q || "") + '">' +
      '<select id="pr" aria-label="Filter by role"><option value="">Everyone</option><option value="Accused">Accused in any FIR</option><option value="repeat">Repeat accused</option><option value="multi">More than one role</option><option value="Witness">Witnesses</option><option value="Victim">Victims</option></select><span class="count" id="pcount"></span></div><div id="ptable"></div>';
    function draw() {
      var q = document.getElementById("pq").value.toLowerCase().trim(), r = document.getElementById("pr").value;
      var rows = D.persons.filter(function (p) {
        var roles = p.involvement.map(function (i) { return i.role; });
        var accusedCount = roles.filter(function (x) { return x === "Accused"; }).length;
        if (r === "repeat" && accusedCount < 2) return false;
        if (r === "multi") { var uniq = roles.filter(function (x, i) { return roles.indexOf(x) === i; }); if (uniq.length < 2) return false; }
        if (r && r !== "repeat" && r !== "multi" && roles.indexOf(r) < 0) return false;
        return !q || (p.name + " " + (p.cnic || "")).toLowerCase().indexOf(q) >= 0;
      }).map(function (p) {
        var acc = p.involvement.filter(function (i) { return i.role === "Accused"; }).length;
        return "<tr><td><a href='#/person/" + p.person_id + "'>" + esc(p.name) + "</a></td><td class='mono nowrap'>" + esc(p.cnic || "none") + "</td><td>" + esc(p.district || "") + "</td><td>" + esc(p.occupation || "") + "</td><td class='num'>" + p.involvement.length + "</td><td class='num'>" + (acc > 1 ? chip(acc + " FIRs", "c-bad") : acc) + "</td></tr>";
      });
      document.getElementById("pcount").textContent = rows.length + " of " + D.persons.length + " people";
      document.getElementById("ptable").innerHTML = table(["Name", "CNIC (fake)", "District", "Occupation", { t: "FIRs involved", num: 1 }, { t: "As accused", num: 1 }], rows, { empty: "Nobody matches." });
    }
    document.getElementById("pq").addEventListener("input", draw);
    document.getElementById("pr").addEventListener("input", draw);
    draw();
  }

  function person(id) {
    var p = PEOPLE[id];
    if (!p) { main.innerHTML = '<p class="empty">No such person.</p>'; return; }
    setTitle(p.name);
    var acc = p.involvement.filter(function (i) { return i.role === "Accused"; });
    var roles = p.involvement.map(function (i) { return i.role; }).filter(function (x, i, a) { return a.indexOf(x) === i; });
    var rows = p.involvement.slice().sort(function (a, b) { return a.fir.reported_at < b.fir.reported_at ? -1 : 1; }).map(function (i) {
      var outcome = i.role === "Accused" ? outcomeChip(i.status) + (i.verdict ? " " + outcomeChip(i.verdict.verdict) + (i.verdict.sentence_years ? " " + i.verdict.sentence_years + " yrs" : "") : "") : "";
      return "<tr><td>" + firLink(i.fir) + "</td><td class='nowrap'>" + date(i.fir.reported_at) + "</td><td>" + (i.role === "Accused" ? chip(i.role, "c-bad") : chip(i.role)) + "</td><td>" + esc(i.fir.category) + "</td><td>" + esc(i.fir.sections) + "</td><td>" + outcome + "</td></tr>";
    });
    main.innerHTML =
      '<div class="crumbs"><a href="#/people">People</a> / ' + esc(p.name) + "</div>" +
      '<div class="filehead"><h1 style="font-family:var(--sans)">' + esc(p.name) + "</h1>" + (acc.length > 1 ? chip("Repeat accused, " + acc.length + " FIRs", "c-bad") : "") + (roles.length > 1 ? chip(roles.length + " different roles", "c-warn") : "") + "</div>" +
      '<dl class="facts">' +
      "<div><dt>CNIC (fake)</dt><dd class='mono'>" + esc(p.cnic || "none on file") + "</dd></div>" +
      "<div><dt>Father</dt><dd>" + esc(p.father || "") + "</dd></div>" +
      "<div><dt>Gender, age</dt><dd>" + esc(p.gender) + ", " + (p.age == null ? "unknown" : p.age) + "</dd></div>" +
      "<div><dt>Occupation</dt><dd>" + esc(p.occupation || "") + "</dd></div>" +
      "<div><dt>Address</dt><dd>" + esc(p.address || "") + "</dd></div></dl>" +
      "<h2>Involvement in FIRs</h2>" +
      table(["FIR", "Reported", "Role", "Category", "Sections", "Outcome"], rows, { empty: "Not named in any FIR." }) +
      '<p class="small muted" style="margin-top:14px">Same data as the <code>vw_criminal_history</code> view and the <code>sp_person_profile</code> procedure.</p>';
  }

  function evidence(params) {
    setTitle("Evidence");
    var all = [];
    D.firs.forEach(function (f) { f.evidence.forEach(function (e) { e.fir = f; all.push(e); }); });
    var statuses = all.map(function (e) { return e.status; }).filter(function (x, i, a) { return a.indexOf(x) === i; }).sort();
    main.innerHTML =
      '<div class="eyebrow">Evidence</div><h1>Exhibits and chain of custody</h1>' +
      '<p class="sub">Every exhibit, where it is now and every hand it has passed through. The custody log is written by a database trigger, so an exhibit cannot move without leaving a trace.</p>' +
      '<div class="filters"><input type="search" id="eq" placeholder="Search exhibits..." aria-label="Search exhibits">' +
      '<select id="es" aria-label="Status"><option value="">All statuses</option>' + statuses.map(function (s) { return "<option>" + esc(s) + "</option>"; }).join("") + "</select>" +
      '<select id="ed" aria-label="Kind"><option value="">Physical and digital</option><option value="1">Digital only</option><option value="0">Physical only</option></select><span class="count" id="ecount"></span></div><div id="elist" class="grid"></div>';
    function draw() {
      var q = document.getElementById("eq").value.toLowerCase().trim(), s = document.getElementById("es").value, d = document.getElementById("ed").value;
      var rows = all.filter(function (e) {
        if (s && e.status !== s) return false;
        if (d !== "" && String(e.digital ? 1 : 0) !== d) return false;
        return !q || (e.evidence_no + " " + e.description + " " + e.type + " " + e.custodian + " " + e.fir.fir_number).toLowerCase().indexOf(q) >= 0;
      });
      document.getElementById("ecount").textContent = rows.length + " of " + all.length + " exhibits";
      document.getElementById("elist").innerHTML = rows.length ? rows.map(function (e) {
        return "<div>" + "<div class='small muted' style='margin:0 0 4px'>FIR " + firLink(e.fir) + "</div>" + exhibitCard(e) + "</div>";
      }).join("") : '<div class="empty">No exhibit matches.</div>';
    }
    ["eq", "es", "ed"].forEach(function (id) { document.getElementById(id).addEventListener("input", draw); });
    draw();
  }

  function courts() {
    setTitle("Courts");
    var cases = [];
    D.firs.forEach(function (f) { f.cases.forEach(function (c) { c.fir = f; cases.push(c); }); });
    main.innerHTML =
      '<div class="eyebrow">Courts</div><h1>Court calendar and cases</h1>' +
      '<p class="sub">The calendar is the <code>vw_cause_list</code> view: the next hearing date fixed in every open case.</p>' +
      "<h2>Next hearings</h2>" +
      table(["Date", "In", "Court", "Case", "FIR", "Last stage", "Last judge"], D.cause_list.map(function (h) {
        return "<tr><td class='nowrap'>" + date(h.next_hearing_date) + "</td><td class='nowrap'>" + (h.days_until < 0 ? chip("passed", "c-bad") : h.days_until + " days") + "</td><td>" + esc(h.court) + "</td><td class='mono'>" + esc(h.case_number) + "</td><td>" + firLinkByNumber(h.fir_number) + "</td><td>" + esc(h.last_purpose) + "</td><td>" + esc(h.last_judge) + "</td></tr>";
      })) +
      "<h2>All court cases (" + cases.length + ")</h2>" +
      table(["Case", "Court", "FIR", "Filed", "Status", "Hearings", "Verdicts"], cases.map(function (c) {
        return "<tr><td class='mono nowrap'>" + esc(c.case_number) + "</td><td>" + esc(c.court) + "</td><td>" + firLink(c.fir) + "</td><td class='nowrap'>" + date(c.filed_on) + "</td><td>" + outcomeChip(c.status) + "</td><td class='num'>" + c.hearings.length + "</td><td>" + (c.verdicts.map(function (v) { return esc(v.name) + ": " + v.verdict; }).join("<br>") || "<span class='muted'>none yet</span>") + "</td></tr>";
      }));
  }

  function stations() {
    setTitle("Stations and officers");
    var byStation = {};
    D.officers.forEach(function (o) { (byStation[o.station] = byStation[o.station] || []).push(o); });
    main.innerHTML =
      '<div class="eyebrow">Stations and officers</div><h1>Stations and officers</h1>' +
      '<p class="sub">Station scorecard from <code>vw_station_performance</code>, officer workload from <code>vw_open_cases_by_officer</code>, and the chain of command.</p>' +
      "<h2>Station scorecard</h2>" +
      table(["Station", "District", { t: "FIRs", num: 1 }, { t: "Investigating", num: 1 }, { t: "With courts", num: 1 }, { t: "Closed", num: 1 }, { t: "Cancelled", num: 1 }, { t: "Convictions", num: 1 }, { t: "Acquitted or discharged", num: 1 }], D.stations.map(function (s) {
        return "<tr><td>" + esc(s.station) + "</td><td>" + esc(s.district) + "</td><td class='num'>" + s.total_firs + "</td><td class='num'>" + s.in_investigation + "</td><td class='num'>" + s.with_courts + "</td><td class='num'>" + s.closed + "</td><td class='num'>" + s.cancelled + "</td><td class='num'>" + s.convictions + "</td><td class='num'>" + s.acquittals_or_discharges + "</td></tr>";
      })) +
      "<h2>Officer workload</h2>" +
      table(["Officer", "Rank", "Station", { t: "Open cases", num: 1 }, { t: "Longest on a case", num: 1 }], D.workload.map(function (w) {
        return "<tr><td>" + esc(w.officer) + "</td><td>" + esc(w.officer_rank) + "</td><td>" + esc(w.station) + "</td><td class='num'>" + w.open_cases + "</td><td class='num'>" + w.longest_days_on_case + " days</td></tr>";
      })) +
      "<h2>Officers by station</h2>" +
      '<div class="grid g2">' + Object.keys(byStation).sort().map(function (st) {
        return '<div class="card"><h3>' + esc(st) + "</h3><ul class='list'>" + byStation[st].map(function (o) {
          return "<li><div class='row'><span>" + esc(o.name) + (o.active ? "" : " " + chip("retired", "c-cancel")) + "</span><span class='muted small'>" + esc(o.rank_title) + "</span></div><span class='small muted mono'>" + esc(o.badge_no) + (o.supervisor ? ", reports to " + esc(o.supervisor) : "") + "</span></li>";
        }).join("") + "</ul></div>";
      }).join("") + "</div>";
  }

  function queries(qid) {
    setTitle("Query explorer");
    var cur = D.queries.filter(function (q) { return q.id === qid; })[0] || D.queries[8];
    var res = cur.rows.length ? '<div class="tablewrap"><table><thead><tr>' + cur.columns.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") + "</tr></thead><tbody>" +
      cur.rows.map(function (r) { return "<tr>" + r.map(function (v) { return "<td>" + (v == null ? "<span class='muted'>NULL</span>" : esc(v)) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>" : '<div class="empty">The query returns no rows.</div>';
    main.innerHTML =
      '<div class="eyebrow">Query explorer</div><h1>The SQL behind the screens</h1>' +
      '<p class="sub">The 27 report queries of the project. Each result below was produced by MySQL when this page was built.</p>' +
      '<div class="qlayout"><nav class="qlist" aria-label="Queries">' + D.queries.map(function (q) {
        return '<a href="#/queries/' + q.id + '"' + (q.id === cur.id ? ' class="on"' : "") + "><span>" + q.id + "</span><span>" + esc(q.title) + "</span></a>";
      }).join("") + "</nav><div><h2 style='margin-top:0'>" + cur.id + ". " + esc(cur.title) + "</h2><p class='muted' style='margin-top:0'>" + esc(cur.purpose) + "</p><pre class='sqlbox'>" + esc(cur.sql) + "</pre><p class='small muted' style='margin:12px 0 8px'>" + cur.rows.length + " row(s)</p>" + res + "</div></div>";
  }

  function rules() {
    setTitle("Rules and tests");
    var ok = D.tests.filter(function (t) { return t.rejected; }).length;
    main.innerHTML =
      '<div class="eyebrow">Rules and tests</div><h1>What the database refuses</h1>' +
      '<p class="sub">Each test tries to break a rule of criminal procedure and must be rejected by MySQL itself. ' + ok + " of " + D.tests.length + " were rejected, and the row count of every table was identical before and after the run.</p>" +
      '<div class="filters"><input type="search" id="rq" placeholder="Filter rules..." aria-label="Filter rules"><span class="count" id="rcount"></span></div><div id="rlist" class="grid" style="gap:8px"></div>';
    function draw() {
      var q = document.getElementById("rq").value.toLowerCase().trim();
      var rows = D.tests.filter(function (t) { return !q || (t.rule + " " + t.message + " " + t.sql).toLowerCase().indexOf(q) >= 0; });
      document.getElementById("rcount").textContent = rows.length + " of " + D.tests.length;
      document.getElementById("rlist").innerHTML = rows.map(function (t) {
        return "<details><summary><span class='mono' style='color:var(--brass)'>" + esc(t.id) + "</span><b>" + esc(t.rule) + "</b>" + chip(t.rejected ? "Rejected" : "NOT rejected", t.rejected ? "c-good" : "c-bad") + "</summary><div class='inner'><p class='small muted' style='margin:10px 0 6px'>The attempt:</p><pre class='sqlbox'>" + esc(t.sql) + "</pre><p class='small muted' style='margin:12px 0 6px'>MySQL answered:</p><pre class='sqlbox' style='color:#ffb4ae'>" + esc(t.message) + "</pre></div></details>";
      }).join("") || '<div class="empty">No rule matches.</div>';
    }
    document.getElementById("rq").addEventListener("input", draw);
    draw();
  }

  function about() {
    setTitle("About");
    var m = D.meta;
    main.innerHTML =
      '<div class="eyebrow">About</div><h1>FIR and Criminal Case Management System</h1>' +
      '<p class="sub">A relational database for First Information Reports, investigations, evidence, courts and verdicts. This site is its front end. The database design and the SQL are the project; this site lets you look inside it.</p>' +
      '<div class="kpis"><div class="kpi"><b>' + m.tables + "</b><span>tables (3NF)</span></div><div class=\"kpi\"><b>" + m.triggers + "</b><span>triggers</span></div><div class=\"kpi\"><b>" + (m.procedures + m.functions) + "</b><span>procedures and functions</span></div><div class=\"kpi\"><b>" + m.views + "</b><span>views</span></div><div class=\"kpi\"><b>" + m.queries + "</b><span>report queries</span></div><div class=\"kpi\"><b>" + m.tests_passed + "/" + m.tests + "</b><span>rules enforced in tests</span></div></div>" +
      '<div class="note"><b>How this site works.</b> It shows a read-only snapshot of the sample data, exported from MySQL ' + esc(m.mysql_version.split("-")[0]) + " on " + esc(m.generated_at) + ". Every table, case file, query result and test result here came out of that database. The people, FIRs and events are fictional. To run the live, writable database yourself, use <code>docker compose up -d</code> from the repository.</div>" +
      "<h2>Entity relationship diagram</h2>" +
      '<a href="erd.png"><img class="erd" src="erd.png" alt="Entity relationship diagram of the 27 tables" loading="lazy"></a>' +
      "<h2>Links</h2><ul class='list' style='max-width:620px'>" +
      "<li><a href='https://github.com/ammarahmed-dev/hospital-management-system' target='_blank' rel='noopener'>Source repository on GitHub</a><span class='small muted'>SQL scripts, tests, docker setup</span></li>" +
      "<li><a href='https://github.com/ammarahmed-dev/hospital-management-system/blob/claude/gifted-hopper-vpfrca/docs/PROJECT_REPORT.md' target='_blank' rel='noopener'>Project report</a><span class='small muted'>Requirements, design, normalization, testing</span></li>" +
      "<li><a href='https://github.com/ammarahmed-dev/hospital-management-system/blob/claude/gifted-hopper-vpfrca/docs/DATA_DICTIONARY.md' target='_blank' rel='noopener'>Data dictionary</a><span class='small muted'>Every table, column, constraint and trigger</span></li></ul>";
  }

  /* ------------------------------------------------------------ router */
  function parseHash() {
    var h = location.hash.replace(/^#\/?/, ""), qs = {}, i = h.indexOf("?");
    if (i >= 0) {
      h.slice(i + 1).split("&").forEach(function (kv) { var p = kv.split("="); qs[decodeURIComponent(p[0])] = decodeURIComponent((p[1] || "").replace(/\+/g, " ")); });
      h = h.slice(0, i);
    }
    var parts = h.split("/");
    return { name: parts[0] || "home", arg: parts[1], q: qs };
  }
  function route() {
    if (!D) return;
    var r = parseHash();
    var nav = { home: "home", firs: "firs", fir: "firs", people: "people", person: "people", evidence: "evidence", courts: "courts", stations: "stations", queries: "queries", rules: "rules", about: "about" }[r.name] || "home";
    Array.prototype.forEach.call(document.querySelectorAll("#nav a"), function (a) { a.classList.toggle("on", a.getAttribute("data-route") === nav); });
    switch (r.name) {
      case "firs": firs(r.q); break;
      case "fir": fir(parseInt(r.arg, 10)); break;
      case "people": people(r.q); break;
      case "person": person(parseInt(r.arg, 10)); break;
      case "evidence": evidence(r.q); break;
      case "courts": courts(); break;
      case "stations": stations(); break;
      case "queries": queries(r.arg); break;
      case "rules": rules(); break;
      case "about": about(); break;
      default: home();
    }
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);

  fetch("data.json").then(function (r) { return r.json(); }).then(function (d) {
    D = d;
    prepare();
    document.getElementById("banner").innerHTML =
      "<b>Read-only demo.</b> A front end for the MySQL database <code>fir_ccms</code>. Data exported " + esc(D.meta.generated_at) + ". All names and cases are fictional. \"Today\" is " + date(D.meta.as_of) + ".";
    route();
  }).catch(function (e) {
    main.innerHTML = '<p class="empty">Could not load data.json. ' + esc(e.message) + "</p>";
  });
})();
