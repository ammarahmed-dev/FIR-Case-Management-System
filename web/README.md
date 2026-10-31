# Web front end

A read-only front end for the FIR-CMS MySQL database. It is plain HTML, CSS and JavaScript with no build step.

- `data.json` is an export of the live database, made by `python3 tools/export_web_data.py`
  (every FIR case file, custody chain, the 27 query results and the 45 rule tests).
- `index.html`, `styles.css`, `app.js` draw the screens from that file.

Run it locally:

```bash
cd web && python3 -m http.server 8000     # then open http://localhost:8000
```

Refresh the data after changing the database: `python3 tools/export_web_data.py` (needs `pip install pymysql`).
