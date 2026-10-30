#!/usr/bin/env python3
"""Generate database/data.sql for the FIR and Criminal Case Management System.

The sample data is fictional. It is written as a timeline per FIR and replayed
through the real stored procedures (sp_register_fir, sp_register_arrest, ...)
on a simulated clock (@as_of), so triggers, custody logs and status history are
filled by the database itself exactly as they would be in daily use.

Usage:  python3 tools/generate_sample_data.py > database/data.sql
"""
import hashlib
import sys
from collections import defaultdict

out = []


def emit(line=""):
    out.append(line)


def q(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def n(value):
    return "NULL" if value is None else str(value)


# ---------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------
DISTRICTS = [
    ("Lahore", "Punjab"), ("Karachi South", "Sindh"), ("Rawalpindi", "Punjab"),
    ("Peshawar", "Khyber Pakhtunkhwa"), ("Faisalabad", "Punjab"),
    ("Islamabad", "Islamabad Capital Territory"),
]
STATIONS = [  # code, name, district, address, phone
    ("RVS", "Riverside Police Station", 1, "Mill Road, Riverside, Lahore", "042-5550101"),
    ("CNV", "Canal View Police Station", 1, "Canal Bank Road, Lahore", "042-5550102"),
    ("OLD", "Old City Police Station", 2, "Old City Market, Karachi South", "021-5550103"),
    ("SDB", "Saddar Bazaar Police Station", 2, "Saddar Bazaar, Karachi South", "021-5550104"),
    ("CNT", "Cantt Road Police Station", 3, "Cantt Road, Rawalpindi", "051-5550105"),
    ("UNI", "University Town Police Station", 4, "University Road, Peshawar", "091-5550106"),
    ("IND", "Industrial Area Police Station", 5, "Industrial Estate, Faisalabad", "041-5550107"),
    ("ARP", "Airport Road Police Station", 6, "Airport Road, Islamabad", "051-5550108"),
]
RANKS = [  # title, level, can_investigate
    ("Constable", 1, 0), ("Head Constable", 2, 0), ("Assistant Sub-Inspector", 3, 0),
    ("Sub-Inspector", 4, 1), ("Inspector", 5, 1),
    ("Deputy Superintendent of Police", 6, 1), ("Senior Superintendent of Police", 7, 1),
]
CATEGORIES = [
    ("Offences against Person", "Murder, attempt to murder and hurt"),
    ("Offences against Property", "Theft, robbery, burglary and house-breaking"),
    ("Cyber Crime", "Offences under the Prevention of Electronic Crimes Act"),
    ("Narcotics", "Possession and trafficking of controlled substances"),
    ("Fraud and Forgery", "Cheating, breach of trust, dishonoured cheques, forged documents"),
    ("Weapons and Explosives", "Illegal possession of arms and ammunition"),
    ("Negligence and Traffic", "Deaths and injuries caused by negligence"),
]
# act, section, title, category, punishment, cognizable, bailable
SECTIONS = [
    ("PPC", "302", "Qatl-i-amd (intentional murder)", 1, "Death or imprisonment for life", 1, 0),
    ("PPC", "320", "Qatl-i-khata (death by mistake or negligence)", 7, "Diyat; imprisonment may also apply", 1, 0),
    ("PPC", "324", "Attempt to commit qatl-i-amd", 1, "Imprisonment up to 10 years", 1, 0),
    ("PPC", "379", "Theft", 2, "Imprisonment up to 3 years", 1, 0),
    ("PPC", "380", "Theft in a dwelling house", 2, "Imprisonment up to 7 years", 1, 0),
    ("PPC", "392", "Robbery", 2, "Imprisonment up to 10 years", 1, 0),
    ("PPC", "406", "Criminal breach of trust", 5, "Imprisonment up to 3 years", 1, 0),
    ("PPC", "420", "Cheating and dishonestly inducing delivery of property", 5, "Imprisonment up to 7 years", 1, 0),
    ("PPC", "457", "Lurking house-trespass or house-breaking by night", 2, "Imprisonment up to 5 years", 1, 0),
    ("PPC", "489-F", "Dishonestly issuing a cheque", 5, "Imprisonment up to 3 years", 1, 0),
    ("CNSA", "9(b)", "Possession of narcotics (smaller quantity)", 4, "Imprisonment up to 7 years", 1, 0),
    ("CNSA", "9(c)", "Possession of narcotics (larger quantity)", 4, "Long imprisonment or more", 1, 0),
    ("Arms Ord.", "13", "Unlicensed possession of arms or ammunition", 6, "Imprisonment and fine", 1, 0),
    ("PECA", "3", "Unauthorised access to an information system", 3, "Short imprisonment or fine", 0, 1),
    ("PECA", "14", "Unauthorised use of identity information", 3, "Imprisonment up to 3 years", 1, 0),
    ("PECA", "20", "Offences against the dignity of a person", 3, "Imprisonment up to 3 years", 1, 0),
    ("PECA", "24", "Cyber stalking", 3, "Imprisonment up to 3 years", 1, 0),
]
SECTION_ID = {f"{a} {s}": i + 1 for i, (a, s, *_rest) in enumerate(SECTIONS)}

# id, badge, name, rank, station, supervisor, joined, active
OFFICERS = [
    (1, "P-0001", "Aamir Rauf", 6, 1, None, "2008-04-01", 1),
    (2, "P-1001", "Tariq Mehmood", 5, 1, 1, "2010-06-15", 1),
    (3, "P-1002", "Nadia Hussain", 4, 1, 2, "2015-02-10", 1),
    (4, "P-1003", "Faisal Qureshi", 4, 1, 2, "2014-09-01", 1),
    (5, "P-1004", "Imran Shah", 3, 1, 3, "2012-03-20", 1),
    (6, "P-1005", "Bilal Ahmed", 1, 1, 5, "2019-07-01", 1),
    (7, "P-2001", "Rubina Akhtar", 5, 2, 1, "2009-11-05", 1),
    (8, "P-2002", "Kamran Butt", 4, 2, 7, "2013-05-12", 1),
    (9, "P-2003", "Shahid Iqbal", 2, 2, 8, "2011-08-22", 1),
    (10, "P-3001", "Zafar Iqbal", 5, 3, 1, "2008-01-14", 1),
    (11, "P-3002", "Sana Malik", 4, 3, 10, "2016-04-18", 1),
    (12, "P-4001", "Asad Raza", 5, 4, 1, "2007-10-09", 1),
    (13, "P-4002", "Hamza Tariq", 4, 4, 12, "2017-01-30", 1),
    (14, "P-5001", "Farhan Saeed", 5, 5, 1, "2009-03-03", 1),
    (15, "P-5002", "Maryam Aslam", 4, 5, 14, "2016-09-19", 1),
    (16, "P-6001", "Waqar Khan", 5, 6, 1, "2008-12-01", 1),
    (17, "P-6002", "Irfan Yousaf", 4, 6, 16, "2015-06-25", 1),
    (18, "P-7001", "Shazia Noor", 5, 7, 1, "2010-02-17", 1),
    (19, "P-7002", "Adeel Anwar", 4, 7, 18, "2016-11-07", 1),
    (20, "P-8001", "Naveed Ahsan", 5, 8, 1, "2009-07-21", 1),
    (21, "P-8002", "Hina Farooq", 4, 8, 20, "2017-08-14", 1),
    (22, "P-3003", "Ghulam Abbas", 2, 3, 10, "2012-05-30", 1),
    (23, "P-4003", "Rashid Mehmood", 2, 4, 12, "2011-09-12", 1),
    (24, "P-5003", "Aslam Pervaiz", 2, 5, 14, "2010-10-04", 1),
    (25, "P-6003", "Noman Ali", 2, 6, 16, "2013-02-26", 1),
    (26, "P-7003", "Khalid Javed", 2, 7, 18, "2012-12-11", 1),
    (27, "P-8003", "Sajid Hussain", 2, 8, 20, "2014-04-08", 1),
    (28, "P-9001", "Mushtaq Gill", 4, 3, 10, "2005-03-15", 0),
]
ROLES = [
    ("System Administrator", "Manages users, roles and reference data"),
    ("Station House Officer", "Heads a police station; assigns and reviews cases"),
    ("Investigating Officer", "Investigates assigned FIRs and writes the case diary"),
    ("Records Clerk", "Registers persons, FIRs and evidence at the station"),
    ("Court Liaison Officer", "Tracks court cases, hearings and verdicts"),
    ("Auditor", "Read-only access to every record"),
]
USERS = [  # username, role, officer
    ("admin", 1, None), ("sho_riverside", 2, 2), ("sho_canalview", 2, 7),
    ("sho_oldcity", 2, 10), ("io_nadia", 3, 3), ("io_kamran", 3, 8),
    ("clerk_riverside", 4, 6), ("court_liaison", 5, 11), ("auditor", 6, None),
]
EVIDENCE_TYPES = [
    ("Firearm or weapon", 0), ("Document", 0), ("Narcotic substance", 0),
    ("Stolen or recovered property", 0), ("Clothing or biological sample", 0),
    ("Vehicle", 0), ("Digital file or data export", 1),
    ("Mobile phone or computer", 1), ("Other physical item", 0),
]
COURTS = [
    ("Judicial Magistrate Court, Lahore", "Magistrate", 1, "Court Road, Lahore"),
    ("Special Court (Cyber Crime), Lahore", "Special (Cyber)", 1, "Court Road, Lahore"),
    ("Sessions Court, Lahore", "Sessions", 1, "Court Road, Lahore"),
    ("Sessions Court, Karachi South", "Sessions", 2, "Court Complex, Karachi South"),
    ("Judicial Magistrate Court, Karachi South", "Magistrate", 2, "Court Complex, Karachi South"),
    ("Sessions Court, Rawalpindi", "Sessions", 3, "Court Complex, Rawalpindi"),
    ("Sessions Court, Peshawar", "Sessions", 4, "Court Complex, Peshawar"),
    ("Sessions Court, Faisalabad", "Sessions", 5, "Court Complex, Faisalabad"),
    ("Special Court (Cyber Crime), Islamabad", "Special (Cyber)", 6, "Judicial Complex, Islamabad"),
    ("Judicial Magistrate Court, Islamabad", "Magistrate", 6, "Judicial Complex, Islamabad"),
]
JUDGES = [  # name, court, appointed
    ("Rana Mazhar Hayat", 1, "2016-03-01"), ("Saima Gillani", 1, "2019-08-12"),
    ("Khalid Mehmood Warraich", 2, "2017-05-20"), ("Shumaila Anjum", 3, "2014-01-06"),
    ("Tahir Hussain Bokhari", 3, "2012-09-17"), ("Naseem Akhtar Lodhi", 4, "2013-04-22"),
    ("Farrukh Siddiqui", 5, "2018-02-05"), ("Ayesha Qazi", 6, "2015-07-13"),
    ("Imtiaz Ali Khattak", 7, "2011-11-28"), ("Rukhsana Bibi Afridi", 8, "2016-10-10"),
    ("Sajjad Ahmad Cheema", 9, "2018-06-18"), ("Muneeb Ur Rehman", 10, "2020-01-13"),
]

# name, father, gender, date of birth, district, occupation, has CNIC
PERSONS = [
    ("Ahsan Ali", "Liaqat Ali", "Male", "1985-03-12", 1, "Shopkeeper"),
    ("Zeeshan Rafiq", "Muhammad Rafiq", "Male", "1996-08-04", 1, "Salesman"),
    ("Mubashir Ali", "Nazir Ahmed", "Male", "1987-12-01", 1, "Shopkeeper"),
    ("Sadia Parveen", "Muhammad Parvez", "Female", "1990-07-21", 1, "Teacher"),
    ("Adnan Sheikh", "Shabbir Sheikh", "Male", "1989-10-15", 1, "Software Developer"),
    ("Mehwish Rani", "Abdul Rehman", "Female", "1992-02-11", 1, "Teacher"),
    ("Bashir Ahmed", "Nazir Ahmed", "Male", "1978-11-02", 1, "Driver"),
    ("Shahzad Gul", "Gul Muhammad", "Male", "1994-05-18", 1, "Labourer"),
    ("Rehan Lakhani", "Hanif Lakhani", "Male", "1993-09-23", 2, "Unemployed"),
    ("Tariq Aziz", "Aziz Ahmed", "Male", "1982-06-30", 1, "Shopkeeper"),
    ("Javed Iqbal", "Iqbal Hussain", "Male", "1975-06-06", 2, "Trader"),
    ("Tanveer Abbas", "Ghulam Abbas", "Male", "1980-01-09", 2, "Contractor"),
    ("Rahat Jamal", "Jamal Uddin", "Male", "1979-04-22", 2, "Bank Manager"),
    ("Farah Naz", "Naz Muhammad", "Female", "1989-02-28", 2, "Nurse"),
    ("Abdul Qadir", "Abdul Ghani", "Male", "1965-08-08", 2, "Retired Clerk"),
    ("Rizwan Haider", "Ghulam Haider", "Male", "1992-05-30", 1, "Mechanic"),
    ("Kashif Mehmood", "Mehmood Ahmed", "Male", "1988-01-17", 1, "Labourer"),
    ("Waseem Butt", "Nawaz Butt", "Male", "1990-03-03", 1, "Labourer"),
    ("Irfan Malik", "Malik Yousaf", "Male", "1986-07-07", 1, "Tailor"),
    ("Sajida Bibi", "Fazal Din", "Female", "1980-10-10", 1, "Housewife"),
    ("Naseer Ud Din", "Fazal Ud Din", "Male", "1972-09-14", 3, "Farmer"),
    ("Munir Hussain", "Fazal Ud Din", "Male", "1968-02-20", 3, "Farmer"),
    ("Gulzar Ahmed", "Bashir Ahmed", "Male", "1975-11-11", 3, "Farmer"),
    ("Sher Zaman", "Gul Zaman", "Male", "1983-04-04", 3, "Labourer"),
    ("Ilyas Masih", "Masih Din", "Male", "1977-05-05", 3, "Shopkeeper"),
    ("Tahira Perveen", "Perveen Akhtar", "Female", "1981-12-12", 3, "Teacher"),
    ("Dr Anwar Baig", "Baig Muhammad", "Male", "1970-03-03", 3, "Medico-Legal Officer"),
    ("Imran Khokhar", "Khokhar Sultan", "Male", "1991-07-27", 4, "Driver"),
    ("Zahid Afridi", "Afridi Gul", "Male", "1984-09-09", 4, "Shopkeeper"),
    ("Anwar Pervez", "Pervez Ahmed", "Male", "1958-01-30", 5, "Retired Teacher"),
    ("Danish Mirza", "Mirza Akram", "Male", "1995-06-12", 5, "Businessman"),
    ("Hassan Raza", "Raza Hussain", "Male", "1993-02-02", 5, "IT Freelancer"),
    ("Saira Khalid", "Khalid Mehmood", "Female", "1987-08-18", 5, "Bank Officer"),
    ("Mansoor Elahi", "Elahi Bakhsh", "Male", "1980-05-25", 1, "Shopkeeper"),
    ("Samina Mansoor", "Rasheed Ahmed", "Female", "1983-07-14", 1, "Housewife"),
    ("Nasir Mahmood", "Mahmood Ahmed", "Male", "1979-10-01", 1, "Bus Driver"),
    ("Qamar Zaman", "Zaman Ali", "Male", "1990-11-23", 1, "Bus Conductor"),
    ("Bilal Sattar", "Sattar Ahmed", "Male", "1986-04-16", 6, "IT Manager"),
    ("Omer Farooq Malik", "Farooq Malik", "Male", "1994-12-05", 6, "Network Engineer"),
    ("Saad Qureshi", "Qureshi Aslam", "Male", "1991-03-29", 6, "System Administrator"),
    ("Naeem Akhtar", "Akhtar Hussain", "Male", "1970-04-25", 1, "Businessman"),
    ("Jamshed Lodhi", "Lodhi Rasheed", "Male", "1972-09-19", 1, "Businessman"),
    ("Asim Raza", "Raza Ali", "Male", "1985-01-21", 1, "Accountant"),
    ("Mubarak Ali Soomro", "Soomro Khan", "Male", "1969-07-16", 2, "Shopkeeper"),
    ("Fahad Memon", "Memon Yaqoob", "Male", "1996-02-14", 2, "Unemployed"),
    ("Ali Raza Jokhio", "Jokhio Rahim", "Male", "1988-10-30", 2, "Salesman"),
    ("Ghulam Rasool Baloch", "Baloch Murad", "Male", "1984-06-18", 2, "Labourer"),
    ("Parvez Jatoi", "Jatoi Nabi", "Male", "1976-12-02", 2, "Tea Stall Owner"),
    ("Fawad Chaudhry", "Chaudhry Nisar", "Male", "1982-09-27", 3, "Manager"),
    ("Waleed Mushtaq", "Mushtaq Ahmed", "Male", "1997-03-08", 3, "Unemployed"),
    ("Rubab Fatima", "Syed Ali Raza", "Female", "1994-11-09", 4, "Student"),
    ("Hira Batool", "Batool Hussain", "Female", "1996-01-26", 5, "Graphic Designer"),
    ("Lubna Shaheen", "Shaheen Akhtar", "Female", "1993-05-15", 5, "Graphic Designer"),
    ("Sobia Aslam", "Aslam Pervaiz", "Female", "1981-08-24", 1, "Housewife"),
    ("Haji Rafiq", "Rafiq Ahmed", "Male", "1960-02-10", 1, "Property Dealer"),
    ("Ayub Khan", "Khan Muhammad", "Male", "1984-04-13", 2, "Transporter"),
    ("Sikandar Hayat", "Hayat Khan", "Male", "1990-09-05", 2, "Unemployed"),
    ("Taimoor Zaheer", "Zaheer Abbas", "Male", "1998-01-19", 6, "Student"),
    ("Danish Ali", "Ali Hassan", "Male", "2000-06-06", 2, "Student"),
    ("Rukhsana Kausar", "Kausar Ali", "Female", "1975-10-17", 3, "Teacher"),
    ("Adil Bashir", "Bashir Ahmed", "Male", "1981-08-12", 3, "Truck Driver"),
    ("Sadaf Munir", "Munir Ahmed", "Female", "1988-03-21", 4, "Boutique Owner"),
    ("Imtiaz Hussain", "Hussain Ali", "Male", "1971-12-28", 2, "Trader"),
]
PID = {p[0]: i + 1 for i, p in enumerate(PERSONS)}
NO_CNIC = {"Sher Zaman", "Fahad Memon"}   # persons without an ID card on file
DISTRICT_NAME = {i + 1: d[0] for i, d in enumerate(DISTRICTS)}

# ---------------------------------------------------------------------
# FIR timelines
# ---------------------------------------------------------------------
LAB_PHYSICAL = "Provincial Forensic Science Laboratory"
LAB_DIGITAL = "Provincial Digital Forensics Laboratory"
LAB_NARCO = "Narcotics Testing Laboratory"

FIRS = []   # each: dict(reg=..., events=[(ts, kind, args)])


def fir(st, comp, regby, reported, incident, cat, loc, desc, sections):
    f = dict(st=st, comp=comp, regby=regby, reported=reported, incident=incident,
             cat=cat, loc=loc, desc=desc, sections=sections, events=[])
    FIRS.append(f)
    return f


def ev(f, ts, kind, *args):
    f["events"].append((ts, kind, args))


# ---- FIR 1: theft from a cloth shop, ends in conviction -------------------
f = fir(1, "Ahsan Ali", 5, "2026-01-08 09:15", "2026-01-07 23:30", 2,
        "Cloth shop 14, Fruit Market Road, Riverside",
        "Complainant found the shop shutter open in the morning. Cash of Rs 85,000 and two mobile phones kept for repair were missing.",
        ["PPC 379"])
ev(f, "2026-01-08 11:00", "assign", 4, "Assigned by the station house officer")
ev(f, "2026-01-09 10:00", "party", "Mubashir Ali", "Witness", "Saw the shutter open at 7 am and informed the complainant.")
ev(f, "2026-01-09 10:30", "evidence", "EV-2026-001", 7, "CCTV footage from the adjoining shop covering 11 pm to 1 am", 4, "Adjoining shop, Fruit Market Road", None)
ev(f, "2026-01-09 17:00", "transfer", "EV-2026-001", 6, "Deposited in digital vault", "In Malkhana", "Digital Vault DV-01")
ev(f, "2026-01-09 15:00", "diary", 4, "Visited the shop and recorded statements of the complainant and a neighbouring shopkeeper. Collected CCTV footage from the adjoining shop.")
ev(f, "2026-01-15 16:00", "diary", 4, "CCTV shows a former employee opening the shutter with a key. The complainant identified him as Zeeshan Rafiq.")
ev(f, "2026-01-15 16:30", "accused", "Zeeshan Rafiq")
ev(f, "2026-01-18 14:20", "arrest", "Zeeshan Rafiq", 4, "Residence of the accused, Riverside", 2)
ev(f, "2026-01-18 15:30", "evidence", "EV-2026-002", 4, "Two stolen mobile phones recovered from the accused's house", 4, "Residence of the accused", None)
ev(f, "2026-01-18 20:00", "transfer", "EV-2026-002", 6, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf B-3")
ev(f, "2026-01-20 11:00", "diary", 4, "Recovery memo prepared in the presence of two witnesses. Accused remanded to police custody for two days.")
ev(f, "2026-01-22 10:00", "bail_apply", "b1", "Zeeshan Rafiq", 1, "Post-arrest")
ev(f, "2026-01-28 11:00", "bail_decide", "b1", "Granted", 100000, "Granted on surety; recovery already made")
ev(f, "2026-02-05 10:00", "challan")
ev(f, "2026-02-10 10:00", "case", 1, "MC-LHR-2026-0114")
ev(f, "2026-02-17 08:30", "transfer", "EV-2026-002", 4, "Produced in court", "Produced in Court", None)
ev(f, "2026-02-17 10:00", "hearing", 1, "Charge Framing", "Charge framed; accused pleaded not guilty", "2026-03-10")
ev(f, "2026-02-17 16:00", "transfer", "EV-2026-002", 6, "Returned to Malkhana after hearing", "In Malkhana", None)
ev(f, "2026-03-10 10:00", "hearing", 1, "Evidence", "Complainant and one witness examined", "2026-04-14")
ev(f, "2026-04-14 10:00", "hearing", 2, "Judgment", "Judgment announced", None)
ev(f, "2026-04-14 15:00", "verdict", "Zeeshan Rafiq", "Convicted", 1.5, 25000, "Convicted under PPC 379")
ev(f, "2026-04-20 11:00", "transfer", "EV-2026-002", 2, "Released to owner on court order", "Returned", None)

# ---- FIR 2: cyber harassment, trial in progress ------------------------------
f = fir(1, "Sadia Parveen", 3, "2026-01-19 11:00", "2026-01-12 18:00", 3,
        "Online, through a fake social media profile; complainant's residence in Riverside",
        "Since 12 January the complainant has received threatening messages and edited photographs from an anonymous profile.",
        ["PECA 20", "PECA 24"])
ev(f, "2026-01-19 11:30", "party", "Sadia Parveen", "Victim", "Receiving threats and edited photographs from a fake profile since 12 January.")
ev(f, "2026-01-19 12:00", "assign", 3, "Assigned by the station house officer")
ev(f, "2026-01-19 13:00", "evidence", "EV-2026-003", 7, "Screenshots and chat export of the threatening messages", 3, "Complainant's phone", None)
ev(f, "2026-01-19 17:00", "transfer", "EV-2026-003", 6, "Deposited in digital vault", "In Malkhana", "Digital Vault DV-01")
ev(f, "2026-01-20 10:00", "party", "Mehwish Rani", "Witness", "Saw the messages on the complainant's phone on 14 January.")
ev(f, "2026-01-25 10:00", "diary", 3, "Request sent to the platform operator for the subscriber data behind the fake profile.")
ev(f, "2026-02-03 10:00", "diary", 3, "Platform replied. The login address (203.0.113.45) belongs to a broadband connection registered to Adnan Sheikh.")
ev(f, "2026-02-10 12:00", "accused", "Adnan Sheikh")
ev(f, "2026-02-12 16:40", "arrest", "Adnan Sheikh", 3, "Workplace, Riverside", 3)
ev(f, "2026-02-12 18:00", "evidence", "EV-2026-004", 8, "Mobile phone of the accused, forensic image taken at seizure", 3, "Workplace of the accused", None)
ev(f, "2026-02-12 21:00", "transfer", "EV-2026-004", 6, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf C-1")
ev(f, "2026-02-13 09:00", "transfer", "EV-2026-004", 3, "Carried to forensic laboratory", "At Forensic Lab", None)
ev(f, "2026-02-16 10:00", "bail_apply", "b2a", "Adnan Sheikh", 2, "Post-arrest")
ev(f, "2026-02-20 11:00", "bail_decide", "b2a", "Rejected", None, "Digital evidence under examination")
ev(f, "2026-02-28 12:00", "lab", "EV-2026-004", LAB_DIGITAL, "Digital Forensics", "2026-02-13", "2026-02-28", "Recovered the fake profile's app data and the same messages on the device. Image hash verified.")
ev(f, "2026-02-28 15:00", "transfer", "EV-2026-004", 6, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-03-05 10:00", "bail_apply", "b2b", "Adnan Sheikh", 2, "Post-arrest")
ev(f, "2026-03-12 11:00", "bail_decide", "b2b", "Granted", 200000, "Granted after the forensic report was received")
ev(f, "2026-03-20 10:00", "challan")
ev(f, "2026-03-25 10:00", "case", 2, "CY-LHR-2026-0031")
ev(f, "2026-04-08 10:00", "hearing", 3, "Charge Framing", "Charge framed; accused pleaded not guilty", "2026-05-13")
ev(f, "2026-05-13 10:00", "hearing", 3, "Evidence", "Complainant examined", "2026-06-24")
ev(f, "2026-06-24 10:00", "hearing", 3, "Witness Examination", "Colleague witness examined; cross-examination part-heard", "2026-08-05")
ev(f, "2026-08-05 10:00", "hearing", 3, "Witness Examination", "Investigating officer examined", "2026-09-16")
ev(f, "2026-09-16 10:00", "hearing", 3, "Evidence", "Forensic expert summoned", "2026-11-18")

# ---- FIR 3: armed motorcycle snatching ---------------------------------------
f = fir(2, "Bashir Ahmed", 8, "2026-02-02 21:10", "2026-02-02 19:45", 2,
        "Canal Bank Road near the fruit market",
        "Two men on a motorcycle stopped the complainant at gunpoint and took his motorcycle and mobile phone.",
        ["PPC 392", "Arms Ord. 13"])
ev(f, "2026-02-03 09:00", "assign", 8, "Assigned by the station house officer")
ev(f, "2026-02-03 11:00", "party", "Tariq Aziz", "Witness", "Saw two men on a motorcycle force the complainant to stop.")
ev(f, "2026-02-04 11:00", "evidence", "EV-2026-005", 7, "CCTV footage from a petrol pump showing two suspects on one motorcycle", 8, "Petrol pump, Canal Bank Road", None)
ev(f, "2026-02-04 17:00", "transfer", "EV-2026-005", 9, "Deposited in digital vault", "In Malkhana", "Digital Vault DV-02")
ev(f, "2026-02-04 14:00", "diary", 8, "Collected CCTV footage from the petrol pump. Two suspects on one motorcycle, faces partly covered.")
ev(f, "2026-02-10 18:00", "diary", 8, "Informer reports that the suspects are Shahzad Gul and Rehan Lakhani.")
ev(f, "2026-02-10 18:30", "accused", "Shahzad Gul")
ev(f, "2026-02-10 18:35", "accused", "Rehan Lakhani")
ev(f, "2026-02-11 05:30", "arrest", "Shahzad Gul", 8, "Hotel room near the bus terminal", 5)
ev(f, "2026-02-11 06:00", "evidence", "EV-2026-006", 1, "Pistol 30 bore with four live rounds recovered from the accused", 8, "Hotel room near the bus terminal", None)
ev(f, "2026-02-11 07:30", "evidence", "EV-2026-007", 6, "Snatched motorcycle recovered from a garage", 8, "Garage on Canal Bank Road", None)
ev(f, "2026-02-11 12:00", "transfer", "EV-2026-006", 9, "Deposit in Malkhana", "In Malkhana", "Arms Locker A-2")
ev(f, "2026-02-11 12:30", "transfer", "EV-2026-007", 9, "Deposit in Malkhana", "In Malkhana", "Vehicle Yard")
ev(f, "2026-02-12 09:15", "arrest", "Rehan Lakhani", 8, "Residence of the accused, Canal View", 3)
ev(f, "2026-02-13 09:00", "transfer", "EV-2026-006", 8, "Sent for ballistic examination", "At Forensic Lab", None)
ev(f, "2026-02-20 10:00", "bail_apply", "b3a", "Shahzad Gul", 3, "Post-arrest")
ev(f, "2026-02-22 10:00", "bail_apply", "b3b", "Rehan Lakhani", 3, "Post-arrest")
ev(f, "2026-02-24 12:00", "lab", "EV-2026-006", LAB_PHYSICAL, "Ballistics", "2026-02-13", "2026-02-24", "Pistol in working condition; live rounds test-fired successfully.")
ev(f, "2026-02-24 14:00", "transfer", "EV-2026-006", 9, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-02-25 11:00", "diary", 8, "Test identification parade held. The complainant identified both accused.")
ev(f, "2026-02-27 11:00", "bail_decide", "b3a", "Rejected", None, "Weapon recovered from this accused; risk of absconding")
ev(f, "2026-03-06 11:00", "bail_decide", "b3b", "Granted", 300000, "Granted; no recovery from this accused")
ev(f, "2026-03-15 10:00", "challan")
ev(f, "2026-03-20 10:00", "case", 3, "SC-LHR-2026-0208")
ev(f, "2026-04-02 10:00", "hearing", 4, "Charge Framing", "Charge framed against both accused", "2026-05-07")
ev(f, "2026-05-07 10:00", "hearing", 4, "Evidence", "Complainant examined", "2026-06-18")
ev(f, "2026-06-18 10:00", "hearing", 4, "Witness Examination", "Eyewitness examined", "2026-08-20")
ev(f, "2026-08-20 10:00", "hearing", 4, "Arguments", "Prosecution arguments heard", "2026-10-08")
ev(f, "2026-10-08 10:00", "hearing", 4, "Arguments", "Defence arguments part-heard", "2026-12-03")

# ---- FIR 4: dishonoured cheque, settled and withdrawn -------------------------
f = fir(3, "Javed Iqbal", 11, "2026-02-14 12:30", "2026-02-10 10:00", 5,
        "Complainant's office, Old City Market",
        "A cheque of Rs 2,500,000 issued by the accused towards a trade payment was returned by the bank for insufficient funds.",
        ["PPC 489-F"])
ev(f, "2026-02-14 12:45", "accused", "Tanveer Abbas")
ev(f, "2026-02-15 10:00", "assign", 11, "Assigned by the station house officer")
ev(f, "2026-02-15 11:30", "evidence", "EV-2026-008", 2, "Dishonoured cheque for Rs 2,500,000", 11, "Complainant's office", None)
ev(f, "2026-02-15 11:40", "evidence", "EV-2026-009", 2, "Bank return memo for the cheque", 11, "Complainant's bank", None)
ev(f, "2026-02-15 16:00", "transfer", "EV-2026-008", 22, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf A-4")
ev(f, "2026-02-15 16:05", "transfer", "EV-2026-009", 22, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf A-4")
ev(f, "2026-02-16 10:00", "party", "Rahat Jamal", "Witness", "Confirmed that the cheque was returned for insufficient funds.")
ev(f, "2026-02-16 12:00", "diary", 11, "Statement of the bank manager recorded.")
ev(f, "2026-02-20 10:00", "bail_apply", "b4", "Tanveer Abbas", 5, "Pre-arrest")
ev(f, "2026-02-24 12:00", "diary", 11, "Accused joined the inquiry and admitted issuing the cheque.")
ev(f, "2026-02-27 11:00", "bail_decide", "b4", "Granted", 500000, "Interim pre-arrest bail confirmed")
ev(f, "2026-03-12 10:00", "challan")
ev(f, "2026-03-18 10:00", "case", 5, "MC-KHI-2026-0455")
ev(f, "2026-03-30 10:00", "hearing", 7, "Charge Framing", "Charge framed", "2026-05-04")
ev(f, "2026-05-04 10:00", "hearing", 7, "Evidence", "Parties told the court that a settlement was reached", "2026-06-01")
ev(f, "2026-06-01 10:00", "withdraw", "Complaint withdrawn after the amount was paid in full")

# ---- FIR 5: house burglary, untraced ---------------------------------------
f = fir(4, "Farah Naz", 13, "2026-02-27 08:40", "2026-02-26 13:00", 2,
        "House 22, Block C, Saddar Housing Society",
        "The house was locked while the family was away. On return the lock was broken and gold jewellery and cash were missing.",
        ["PPC 380", "PPC 457"])
ev(f, "2026-02-27 09:00", "party", "Farah Naz", "Victim", "Gold jewellery of about 8 tola and Rs 120,000 cash taken.")
ev(f, "2026-02-27 09:10", "party", "Abdul Qadir", "Witness", "Saw an unknown van outside the house on the afternoon of 26 February.")
ev(f, "2026-02-27 10:00", "assign", 13, "Assigned by the station house officer")
ev(f, "2026-02-27 12:00", "evidence", "EV-2026-010", 9, "Fingerprint lifts from the almirah and the broken door lock", 13, "House 22, Block C", None)
ev(f, "2026-02-27 16:00", "transfer", "EV-2026-010", 23, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf D-2")
ev(f, "2026-02-28 11:00", "diary", 13, "Neighbours questioned. No eyewitness to the break-in.")
ev(f, "2026-03-02 09:00", "transfer", "EV-2026-010", 13, "Sent for fingerprint comparison", "At Forensic Lab", None)
ev(f, "2026-03-10 11:00", "diary", 13, "Visited the scene again with the fingerprint expert.")
ev(f, "2026-03-20 12:00", "lab", "EV-2026-010", LAB_PHYSICAL, "Fingerprint", "2026-03-02", "2026-03-20", "Prints are partial; no match found in the automated fingerprint database.")
ev(f, "2026-03-20 15:00", "transfer", "EV-2026-010", 23, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-04-02 11:00", "diary", 13, "Local informers contacted. No lead yet.")

# ---- FIR 6: attempted murder, one convicted and one acquitted --------------------
f = fir(1, "Rizwan Haider", 5, "2026-03-09 22:05", "2026-03-09 20:30", 1,
        "Workshop on Mill Road, Riverside",
        "Two men attacked the complainant with an iron rod over a payment dispute and left him with serious head injuries.",
        ["PPC 324"])
ev(f, "2026-03-09 22:10", "accused", "Kashif Mehmood")
ev(f, "2026-03-09 22:12", "accused", "Waseem Butt")
ev(f, "2026-03-10 09:00", "assign", 4, "Assigned by the station house officer")
ev(f, "2026-03-10 09:30", "party", "Rizwan Haider", "Victim", "Struck on the head with an iron rod by the two accused.")
ev(f, "2026-03-10 09:40", "party", "Irfan Malik", "Witness", "Saw both accused beat the complainant outside the workshop.")
ev(f, "2026-03-10 09:50", "party", "Sajida Bibi", "Witness", "Heard the shouting and saw the accused running away.")
ev(f, "2026-03-10 11:00", "diary", 4, "Medico-legal report obtained. The victim is stable but under observation.")
ev(f, "2026-03-10 12:00", "evidence", "EV-2026-011", 5, "Blood-stained clothes of the victim", 4, "Hospital", None)
ev(f, "2026-03-10 18:00", "transfer", "EV-2026-011", 6, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf B-1")
ev(f, "2026-03-11 08:00", "arrest", "Kashif Mehmood", 4, "Residence of the accused, Mill Road", 4)
ev(f, "2026-03-11 09:00", "transfer", "EV-2026-011", 4, "Sent for DNA and serology", "At Forensic Lab", None)
ev(f, "2026-03-12 07:30", "arrest", "Waseem Butt", 4, "Railway station", 3)
ev(f, "2026-03-12 10:00", "evidence", "EV-2026-012", 1, "Iron rod recovered at the instance of the accused", 4, "Field behind the workshop", None)
ev(f, "2026-03-12 18:00", "transfer", "EV-2026-012", 6, "Deposit in Malkhana", "In Malkhana", "Arms Locker A-1")
ev(f, "2026-03-18 10:00", "bail_apply", "b6a", "Kashif Mehmood", 3, "Post-arrest")
ev(f, "2026-03-20 10:00", "bail_apply", "b6b", "Waseem Butt", 3, "Post-arrest")
ev(f, "2026-03-25 11:00", "diary", 4, "Statements of the eyewitnesses recorded under section 161 CrPC.")
ev(f, "2026-03-30 11:00", "bail_decide", "b6a", "Granted", 150000, "Granted; injury not on a vital part")
ev(f, "2026-04-01 12:00", "lab", "EV-2026-011", LAB_PHYSICAL, "DNA", "2026-03-11", "2026-04-01", "Blood group on the clothes is consistent with the injured person.")
ev(f, "2026-04-01 16:00", "transfer", "EV-2026-011", 6, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-04-03 11:00", "bail_decide", "b6b", "Rejected", None, "Specific role assigned and weapon recovered")
ev(f, "2026-04-15 10:00", "challan")
ev(f, "2026-04-20 10:00", "case", 3, "SC-LHR-2026-0301")
ev(f, "2026-05-05 10:00", "hearing", 5, "Charge Framing", "Charge framed against both accused", "2026-06-02")
ev(f, "2026-06-02 10:00", "hearing", 5, "Evidence", "Medico-legal officer examined", "2026-07-14")
ev(f, "2026-07-14 10:00", "hearing", 5, "Witness Examination", "Two eyewitnesses examined", "2026-08-25")
ev(f, "2026-08-25 10:00", "hearing", 5, "Arguments", "Prosecution arguments concluded", "2026-09-22")
ev(f, "2026-09-22 10:00", "hearing", 5, "Arguments", "Defence arguments concluded", "2026-09-29")
ev(f, "2026-09-29 10:00", "hearing", 5, "Judgment", "Judgment announced", None)
ev(f, "2026-09-29 15:00", "verdict", "Kashif Mehmood", "Convicted", 5.0, 100000, "Convicted under PPC 324")
ev(f, "2026-09-29 15:10", "verdict", "Waseem Butt", "Acquitted", None, None, "Benefit of doubt; role not proved")

# ---- FIR 7: murder, reassigned investigator, trial in progress -----------------
f = fir(5, "Naseer Ud Din", 15, "2026-03-21 07:30", "2026-03-20 18:45", 1,
        "Agricultural land at Chak 14, near Cantt Road",
        "Over a land dispute the accused attacked the complainant's brother with an axe. He died on the way to the hospital.",
        ["PPC 302"])
ev(f, "2026-03-21 07:35", "accused", "Gulzar Ahmed")
ev(f, "2026-03-21 07:36", "accused", "Sher Zaman")
ev(f, "2026-03-21 09:00", "assign", 15, "Assigned by the station house officer")
ev(f, "2026-03-21 09:30", "party", "Munir Hussain", "Victim", None)
ev(f, "2026-03-21 10:00", "evidence", "EV-2026-014", 5, "Clothes of the deceased taken at the hospital", 15, "Hospital mortuary", None)
ev(f, "2026-03-21 18:00", "transfer", "EV-2026-014", 24, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf C-2")
ev(f, "2026-03-22 08:00", "evidence", "EV-2026-013", 1, "Axe recovered from the field channel", 15, "Field channel, Chak 14", None)
ev(f, "2026-03-22 09:00", "party", "Ilyas Masih", "Witness", "Saw the accused strike the deceased with an axe.")
ev(f, "2026-03-22 09:10", "party", "Tahira Perveen", "Witness", "Present at the scene and saw both accused leave together.")
ev(f, "2026-03-22 09:20", "party", "Dr Anwar Baig", "Witness", "Conducted the post-mortem; death caused by a deep wound to the neck.")
ev(f, "2026-03-22 11:00", "diary", 15, "Inquest and post-mortem completed. Statements of the eyewitnesses recorded.")
ev(f, "2026-03-22 14:00", "evidence", "EV-2026-016", 2, "Inquest report and post-mortem report", 15, "Hospital mortuary", None)
ev(f, "2026-03-22 18:00", "transfer", "EV-2026-016", 24, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf C-2")
ev(f, "2026-03-22 20:00", "transfer", "EV-2026-013", 24, "Deposit in Malkhana", "In Malkhana", "Arms Locker A-1")
ev(f, "2026-03-23 09:00", "transfer", "EV-2026-013", 15, "Sent for DNA and serology", "At Forensic Lab", None)
ev(f, "2026-03-25 11:00", "diary", 15, "Site plan prepared and blood-stained earth collected.")
ev(f, "2026-04-01 06:00", "arrest", "Gulzar Ahmed", 15, "Hideout near the canal", 7)
ev(f, "2026-04-02 11:00", "diary", 15, "Raids conducted for the arrest of the second accused.")
ev(f, "2026-04-03 10:00", "evidence", "EV-2026-015", 8, "Mobile phone of Gulzar Ahmed, forensic image taken at seizure", 15, "Hideout near the canal", None)
ev(f, "2026-04-03 15:00", "transfer", "EV-2026-015", 24, "Deposit in Malkhana", "In Malkhana", "Digital Vault DV-05")
ev(f, "2026-04-05 07:00", "arrest", "Sher Zaman", 15, "Bus stand, Cantt Road", 7)
ev(f, "2026-04-10 10:00", "assign", 14, "Case entrusted to an Inspector on instructions of the superintendent")
ev(f, "2026-04-12 11:00", "diary", 14, "Reviewed the file and re-recorded the statements of the eyewitnesses.")
ev(f, "2026-04-18 12:00", "lab", "EV-2026-013", LAB_PHYSICAL, "DNA", "2026-03-23", "2026-04-18", "Blood on the axe matches the deceased.")
ev(f, "2026-04-19 11:00", "transfer", "EV-2026-013", 24, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-04-20 10:00", "bail_apply", "b7a", "Gulzar Ahmed", 6, "Post-arrest")
ev(f, "2026-04-30 11:00", "diary", 14, "Medical board opinion obtained on the weapon and injury.")
ev(f, "2026-05-02 10:00", "bail_apply", "b7b", "Sher Zaman", 6, "Post-arrest")
ev(f, "2026-05-06 11:00", "bail_decide", "b7a", "Rejected", None, "Direct role and recovery of the weapon")
ev(f, "2026-05-15 11:00", "diary", 14, "Statements of the remaining witnesses recorded.")
ev(f, "2026-05-20 11:00", "bail_decide", "b7b", "Rejected", None, "Named with a specific role")
ev(f, "2026-06-05 11:00", "diary", 14, "Investigation complete; challan prepared.")
ev(f, "2026-06-10 10:00", "challan")
ev(f, "2026-06-18 10:00", "case", 6, "SC-RWP-2026-0112")
ev(f, "2026-07-01 08:30", "transfer", "EV-2026-013", 14, "Produced in court", "Produced in Court", None)
ev(f, "2026-07-01 10:00", "hearing", 8, "Charge Framing", "Charge framed against both accused", "2026-07-22")
ev(f, "2026-07-01 15:00", "transfer", "EV-2026-013", 24, "Returned to Malkhana after hearing", "In Malkhana", None)
ev(f, "2026-07-22 10:00", "hearing", 8, "Evidence", "Complainant examined", "2026-08-26")
ev(f, "2026-08-26 10:00", "hearing", 8, "Witness Examination", "First eyewitness examined", "2026-09-23")
ev(f, "2026-09-23 10:00", "hearing", 8, "Witness Examination", "Second eyewitness examined", "2026-10-21")
ev(f, "2026-10-21 10:00", "hearing", 8, "Witness Examination", "Medico-legal officer examined", "2026-11-25")

# ---- FIR 8: narcotics recovery at a checkpoint (police complainant) ------------
f = fir(6, ("officer", 17), 17, "2026-04-03 15:20", "2026-04-03 13:15", 4,
        "Police checkpoint on University Road",
        "At a checkpoint the police recovered 640 g of cannabis resin from the bag of a motorcycle rider.",
        ["CNSA 9(b)"])
ev(f, "2026-04-03 15:25", "accused", "Imran Khokhar")
ev(f, "2026-04-03 15:30", "party", "Zahid Afridi", "Witness", "Private witness to the search and recovery at the checkpoint.")
ev(f, "2026-04-03 15:40", "evidence", "EV-2026-017", 3, "Cannabis resin, 640 g in two packets, sealed at the station", 17, "Bag of the accused at the checkpoint", None)
ev(f, "2026-04-03 16:30", "arrest", "Imran Khokhar", 17, "Police checkpoint, University Road", 0)
ev(f, "2026-04-03 21:00", "transfer", "EV-2026-017", 25, "Deposit in Malkhana", "In Malkhana", "Narcotics Locker N-1")
ev(f, "2026-04-04 09:00", "assign", 16, "Investigation given to the station house officer, not the complainant")
ev(f, "2026-04-04 11:00", "diary", 16, "File examined and the private witness re-interviewed.")
ev(f, "2026-04-06 09:00", "transfer", "EV-2026-017", 17, "Sent for chemical analysis", "At Forensic Lab", None)
ev(f, "2026-04-12 11:00", "diary", 16, "Previous record of the accused checked; none found.")
ev(f, "2026-04-15 10:00", "bail_apply", "b8", "Imran Khokhar", 7, "Post-arrest")
ev(f, "2026-04-20 12:00", "lab", "EV-2026-017", LAB_NARCO, "Chemical", "2026-04-06", "2026-04-20", "Positive for cannabis resin; net weight 640 g.")
ev(f, "2026-04-20 14:00", "transfer", "EV-2026-017", 25, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-04-30 11:00", "bail_decide", "b8", "Rejected", None, "Recovery of narcotics; prima facie case")
ev(f, "2026-05-02 10:00", "challan")
ev(f, "2026-05-08 10:00", "case", 7, "SC-PSH-2026-0099")
ev(f, "2026-05-20 10:00", "hearing", 9, "Charge Framing", "Charge framed", "2026-06-17")
ev(f, "2026-06-17 10:00", "hearing", 9, "Evidence", "Recovery witnesses examined", "2026-07-29")
ev(f, "2026-07-29 10:00", "hearing", 9, "Judgment", "Judgment announced", None)
ev(f, "2026-07-29 15:00", "verdict", "Imran Khokhar", "Convicted", 3.0, 50000, "Convicted under CNSA 9(b)")
ev(f, "2026-08-20 10:00", "transfer", "EV-2026-017", 16, "Destroyed under court order", "Destroyed", None)

# ---- FIR 9: online investment fraud, one accused absconding ---------------------
f = fir(7, "Anwar Pervez", 19, "2026-04-11 10:00", "2026-03-28 12:00", 5,
        "Complainant's home and an online investment portal",
        "The complainant transferred Rs 1,800,000 to an online investment portal that promised monthly returns and then went offline.",
        ["PPC 420", "PECA 14"])
ev(f, "2026-04-11 10:10", "accused", "Danish Mirza")
ev(f, "2026-04-11 10:30", "party", "Anwar Pervez", "Victim", "Transferred Rs 1,800,000 in three instalments to two bank accounts.")
ev(f, "2026-04-12 09:30", "assign", 19, "Assigned by the station house officer")
ev(f, "2026-04-12 12:00", "evidence", "EV-2026-018", 7, "Bank statements of the complainant (PDF export)", 19, "Complainant's bank portal", None)
ev(f, "2026-04-12 17:00", "transfer", "EV-2026-018", 26, "Deposited in digital vault", "In Malkhana", "Digital Vault DV-07")
ev(f, "2026-04-13 10:00", "party", "Saira Khalid", "Witness", "Bank officer who confirmed the transfers and the receiving accounts.")
ev(f, "2026-04-13 11:00", "evidence", "EV-2026-019", 7, "Chat export with the portal's representatives", 19, "Complainant's phone", None)
ev(f, "2026-04-13 14:00", "diary", 19, "Bank records requested for the two receiving accounts.")
ev(f, "2026-04-13 17:00", "transfer", "EV-2026-019", 26, "Deposited in digital vault", "In Malkhana", "Digital Vault DV-07")
ev(f, "2026-04-20 16:00", "accused", "Hassan Raza")
ev(f, "2026-04-25 11:00", "diary", 19, "The receiving accounts belong to Danish Mirza and Hassan Raza.")
ev(f, "2026-05-02 07:00", "arrest", "Danish Mirza", 19, "Residence of the accused, Industrial Area", 4)
ev(f, "2026-05-02 09:00", "evidence", "EV-2026-020", 8, "Laptop of Danish Mirza, forensic image taken at seizure", 19, "Residence of the accused", None)
ev(f, "2026-05-02 14:00", "transfer", "EV-2026-020", 26, "Deposit in Malkhana", "In Malkhana", "Digital Vault DV-07")
ev(f, "2026-05-03 09:00", "transfer", "EV-2026-020", 19, "Carried to forensic laboratory", "At Forensic Lab", None)
ev(f, "2026-05-05 12:00", "absconding", "Hassan Raza")
ev(f, "2026-05-10 10:00", "bail_apply", "b9", "Danish Mirza", 8, "Post-arrest")
ev(f, "2026-05-18 11:00", "bail_decide", "b9", "Granted", 400000, "Granted; documentary evidence already secured")
ev(f, "2026-05-30 12:00", "lab", "EV-2026-020", LAB_DIGITAL, "Digital Forensics", "2026-05-03", "2026-05-30", "Wallet records and chat history on the laptop link the accused to the portal.")
ev(f, "2026-05-30 15:00", "transfer", "EV-2026-020", 26, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-06-15 10:00", "challan")
ev(f, "2026-06-25 10:00", "case", 8, "SC-FSD-2026-0188")
ev(f, "2026-07-14 10:00", "hearing", 10, "Charge Framing", "Charge framed against the present accused; the absconder is to be proceeded against separately", "2026-08-18")
ev(f, "2026-08-18 10:00", "hearing", 10, "Evidence", "Complainant examined", "2026-09-29")
ev(f, "2026-09-29 10:00", "hearing", 10, "Evidence", "Bank officer examined", "2026-11-10")

# ---- FIR 10: fatal bus accident ------------------------------------------------
f = fir(2, "Mansoor Elahi", 8, "2026-04-25 06:45", "2026-04-24 23:20", 7,
        "Canal bridge crossing on the highway",
        "A passenger bus overturned near the canal bridge. A woman passenger died and eleven were injured. The brakes are alleged to have failed.",
        ["PPC 320"])
ev(f, "2026-04-25 06:50", "accused", "Nasir Mahmood")
ev(f, "2026-04-25 08:00", "evidence", "EV-2026-021", 6, "Passenger bus involved in the accident", 8, "Accident site, canal bridge", None)
ev(f, "2026-04-25 09:00", "assign", 8, "Assigned by the station house officer")
ev(f, "2026-04-25 09:30", "party", "Samina Mansoor", "Victim", "Passenger who died in the accident.")
ev(f, "2026-04-25 09:40", "party", "Qamar Zaman", "Witness", "Conductor of the bus; says the driver reported weak brakes earlier that day.")
ev(f, "2026-04-25 10:30", "arrest", "Nasir Mahmood", 8, "Accident site", 2)
ev(f, "2026-04-25 14:00", "transfer", "EV-2026-021", 9, "Deposit in Malkhana", "In Malkhana", "Vehicle Yard")
ev(f, "2026-04-26 11:00", "diary", 8, "Mechanical inspection ordered. Statement of the driver recorded.")
ev(f, "2026-04-28 11:00", "evidence", "EV-2026-022", 2, "Mechanical inspection report noting brake failure", 8, "Motor vehicle examiner's office", None)
ev(f, "2026-04-28 16:00", "transfer", "EV-2026-022", 9, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf A-6")
ev(f, "2026-05-02 10:00", "bail_apply", "b10", "Nasir Mahmood", 3, "Post-arrest")
ev(f, "2026-05-09 11:00", "bail_decide", "b10", "Granted", 250000, "Granted; offence arises from negligence")
ev(f, "2026-05-12 11:00", "diary", 8, "Fitness certificate of the bus obtained from the owner.")
ev(f, "2026-05-20 11:00", "transfer", "EV-2026-021", 7, "Released on superdari to the owner", "Returned", None)
ev(f, "2026-05-30 10:00", "challan")
ev(f, "2026-06-04 10:00", "case", 3, "SC-LHR-2026-0377")
ev(f, "2026-06-25 10:00", "hearing", 4, "Charge Framing", "Charge framed", "2026-08-06")
ev(f, "2026-08-06 10:00", "hearing", 4, "Evidence", "Mechanical examiner examined", "2026-10-15")
ev(f, "2026-10-15 10:00", "hearing", 4, "Evidence", "Complainant examined", "2026-12-10")

# ---- FIR 11: network intrusion, challan submitted --------------------------------
f = fir(8, "Bilal Sattar", 21, "2026-05-06 09:30", "2026-05-04 02:15", 3,
        "Server room of Meridian Textiles, Islamabad (remote intrusion)",
        "An unknown person logged in to the company file server through a stolen administrator password and copied customer data.",
        ["PECA 3", "PECA 14"])
ev(f, "2026-05-07 10:00", "assign", 21, "Assigned by the station house officer")
ev(f, "2026-05-07 11:00", "party", "Saad Qureshi", "Witness", "Company system administrator who found the unusual login.")
ev(f, "2026-05-07 12:00", "evidence", "EV-2026-023", 7, "Server access logs for 3 and 4 May", 21, "Company file server", None)
ev(f, "2026-05-07 16:00", "transfer", "EV-2026-023", 27, "Deposited in digital vault", "In Malkhana", "Digital Vault DV-08")
ev(f, "2026-05-08 11:00", "diary", 21, "The intrusion came through a VPN exit address. Subscriber data requested from the provider.")
ev(f, "2026-05-09 11:00", "evidence", "EV-2026-024", 7, "Forensic disk image of the compromised server", 21, "Company file server", None)
ev(f, "2026-05-09 16:00", "transfer", "EV-2026-024", 27, "Deposited in digital vault", "In Malkhana", "Digital Vault DV-08")
ev(f, "2026-06-18 11:00", "diary", 21, "The provider's reply links the connection to the home of Omer Farooq Malik.")
ev(f, "2026-06-20 12:00", "accused", "Omer Farooq Malik")
ev(f, "2026-06-22 06:30", "arrest", "Omer Farooq Malik", 21, "Residence of the accused, Islamabad", 3)
ev(f, "2026-06-22 09:00", "evidence", "EV-2026-025", 8, "Laptop of Omer Farooq Malik, forensic image taken at seizure", 21, "Residence of the accused", None)
ev(f, "2026-06-22 15:00", "transfer", "EV-2026-025", 27, "Deposit in Malkhana", "In Malkhana", "Digital Vault DV-08")
ev(f, "2026-06-23 09:00", "transfer", "EV-2026-025", 21, "Carried to forensic laboratory", "At Forensic Lab", None)
ev(f, "2026-06-27 10:00", "bail_apply", "b11", "Omer Farooq Malik", 9, "Post-arrest")
ev(f, "2026-07-08 11:00", "bail_decide", "b11", "Granted", 300000, "Granted; evidence is electronic and already secured")
ev(f, "2026-07-20 12:00", "lab", "EV-2026-025", LAB_DIGITAL, "Digital Forensics", "2026-06-23", "2026-07-20", "Intrusion tools and stolen credentials found on the laptop; access logs match the intrusion time.")
ev(f, "2026-07-20 15:00", "transfer", "EV-2026-025", 27, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-08-05 10:00", "challan")

# ---- FIR 12: criminal breach of trust, trial just started ------------------------
f = fir(1, "Naeem Akhtar", 3, "2026-05-18 13:10", "2026-05-15 09:00", 5,
        "Complainant's office, Riverside",
        "The complainant's business partner transferred partnership funds of about Rs 4.6 million to his personal account.",
        ["PPC 406"])
ev(f, "2026-05-18 13:20", "accused", "Jamshed Lodhi")
ev(f, "2026-05-19 10:00", "assign", 4, "Assigned by the station house officer")
ev(f, "2026-05-20 10:00", "party", "Asim Raza", "Witness", "Company accountant who prepared the ledgers.")
ev(f, "2026-05-20 11:00", "evidence", "EV-2026-026", 2, "Partnership deed, ledgers and bank statements", 4, "Complainant's office", None)
ev(f, "2026-05-20 12:00", "diary", 4, "Statements recorded. Audit of the ledgers requested.")
ev(f, "2026-05-20 16:00", "transfer", "EV-2026-026", 6, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf B-5")
ev(f, "2026-05-25 10:00", "bail_apply", "b12", "Jamshed Lodhi", 3, "Pre-arrest")
ev(f, "2026-06-03 11:00", "bail_decide", "b12", "Granted", 1000000, "Interim pre-arrest bail confirmed")
ev(f, "2026-06-05 11:00", "diary", 4, "Audit shows diversion of about Rs 4.6 million.")
ev(f, "2026-07-01 10:00", "challan")
ev(f, "2026-07-10 10:00", "case", 3, "SC-LHR-2026-0431")
ev(f, "2026-08-04 10:00", "hearing", 5, "Charge Framing", "Charge framed", "2026-09-15")
ev(f, "2026-09-15 10:00", "hearing", 5, "Evidence", "Complainant examined", "2026-11-03")

# ---- FIR 13: armed shop robbery by a repeat offender -----------------------------
f = fir(3, "Mubarak Ali Soomro", 11, "2026-05-29 20:30", "2026-05-29 19:10", 2,
        "Mobile phone shop, Old City Bazaar",
        "Two masked men entered the shop at gunpoint and took cash and mobile phones worth about Rs 600,000.",
        ["PPC 392", "Arms Ord. 13"])
ev(f, "2026-05-30 09:00", "assign", 11, "Assigned by the station house officer")
ev(f, "2026-05-30 10:00", "party", "Ali Raza Jokhio", "Witness", "Salesman present in the shop during the robbery.")
ev(f, "2026-05-30 11:00", "evidence", "EV-2026-027", 7, "CCTV footage from the shop", 11, "Mobile phone shop, Old City Bazaar", None)
ev(f, "2026-05-30 15:00", "accused", "Rehan Lakhani")
ev(f, "2026-05-30 15:05", "accused", "Fahad Memon")
ev(f, "2026-05-30 17:00", "transfer", "EV-2026-027", 22, "Deposited in digital vault", "In Malkhana", "Digital Vault DV-03")
ev(f, "2026-05-31 11:00", "diary", 11, "CCTV shows two masked men. One is identified from his build and a tattoo as Rehan Lakhani, who is on bail in another case.")
ev(f, "2026-06-08 05:15", "arrest", "Rehan Lakhani", 11, "Residence of the accused, Old City", 6)
ev(f, "2026-06-08 06:30", "evidence", "EV-2026-028", 1, "Pistol 9 mm recovered from the accused", 11, "Residence of the accused", None)
ev(f, "2026-06-08 12:00", "transfer", "EV-2026-028", 22, "Deposit in Malkhana", "In Malkhana", "Arms Locker A-1")
ev(f, "2026-06-09 11:00", "diary", 11, "Second accused Fahad Memon could not be found at his address.")
ev(f, "2026-06-12 12:00", "absconding", "Fahad Memon")
ev(f, "2026-06-20 10:00", "bail_apply", "b13", "Rehan Lakhani", 4, "Post-arrest")
ev(f, "2026-07-02 11:00", "bail_decide", "b13", "Rejected", None, "Alleged repeat offence while on bail in another case")
ev(f, "2026-07-20 10:00", "challan")
ev(f, "2026-07-28 10:00", "case", 4, "SC-KHI-2026-0560")
ev(f, "2026-08-12 10:00", "hearing", 6, "Charge Framing", "Charge framed against the present accused", "2026-09-30")
ev(f, "2026-09-30 10:00", "hearing", 6, "Evidence", "Complainant examined", "2026-11-18")

# ---- FIR 14: heroin recovery (police complainant), trial in progress -------------
f = fir(4, ("officer", 13), 13, "2026-06-10 17:00", "2026-06-10 15:10", 4,
        "Bus terminal, Saddar Bazaar",
        "On a tip-off the police stopped a man at the bus terminal and recovered 1.8 kg of heroin from a travelling bag.",
        ["CNSA 9(c)"])
ev(f, "2026-06-10 17:05", "accused", "Ghulam Rasool Baloch")
ev(f, "2026-06-10 17:30", "party", "Parvez Jatoi", "Witness", "Tea stall owner who witnessed the search and recovery.")
ev(f, "2026-06-10 18:00", "arrest", "Ghulam Rasool Baloch", 13, "Bus terminal, Saddar Bazaar", 5)
ev(f, "2026-06-10 19:00", "evidence", "EV-2026-029", 3, "Heroin, 1.8 kg in three packets, sealed at the station", 13, "Travelling bag of the accused", None)
ev(f, "2026-06-10 22:30", "transfer", "EV-2026-029", 23, "Deposit in Malkhana", "In Malkhana", "Narcotics Locker N-1")
ev(f, "2026-06-11 09:00", "assign", 12, "Investigation given to the station house officer, not the complainant")
ev(f, "2026-06-12 11:00", "diary", 12, "Private witness re-interviewed. Mobile phone data of the accused requested.")
ev(f, "2026-06-13 09:00", "transfer", "EV-2026-029", 13, "Sent for chemical analysis", "At Forensic Lab", None)
ev(f, "2026-06-25 10:00", "bail_apply", "b14", "Ghulam Rasool Baloch", 4, "Post-arrest")
ev(f, "2026-06-28 11:00", "diary", 12, "Source of supply being traced through the phone records.")
ev(f, "2026-06-30 12:00", "lab", "EV-2026-029", LAB_NARCO, "Chemical", "2026-06-13", "2026-06-30", "Positive for heroin; net weight 1.8 kg.")
ev(f, "2026-06-30 14:00", "transfer", "EV-2026-029", 23, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-07-09 11:00", "bail_decide", "b14", "Rejected", None, "Large quantity recovered; prima facie case")
ev(f, "2026-07-12 10:00", "challan")
ev(f, "2026-07-20 10:00", "case", 4, "SC-KHI-2026-0541")
ev(f, "2026-08-05 10:00", "hearing", 6, "Charge Framing", "Charge framed", "2026-09-16")
ev(f, "2026-09-16 10:00", "hearing", 6, "Evidence", "Recovery witness examined", "2026-10-28")
ev(f, "2026-10-28 10:00", "hearing", 6, "Evidence", "Chemical examiner examined", "2026-12-02")

# ---- FIR 15: vehicle theft, plea of guilty ---------------------------------------
f = fir(5, "Fawad Chaudhry", 15, "2026-06-22 09:00", "2026-06-21 22:00", 2,
        "Parking lot of a shopping plaza on Cantt Road",
        "The complainant's car was stolen from the plaza parking lot between 9 pm and 10 pm.",
        ["PPC 379"])
ev(f, "2026-06-22 11:00", "assign", 15, "Assigned by the station house officer")
ev(f, "2026-06-24 11:00", "diary", 15, "CCTV of the plaza obtained. The car leaves at 10:20 pm with one driver.")
ev(f, "2026-07-03 08:00", "accused", "Waleed Mushtaq")
ev(f, "2026-07-03 10:00", "arrest", "Waleed Mushtaq", 15, "Workshop on Cantt Road", 2)
ev(f, "2026-07-03 11:00", "evidence", "EV-2026-030", 6, "Stolen car recovered from a workshop", 15, "Workshop on Cantt Road", None)
ev(f, "2026-07-03 12:00", "diary", 15, "Car recovered from a workshop on an informer's tip and the accused arrested.")
ev(f, "2026-07-03 16:00", "transfer", "EV-2026-030", 24, "Deposit in Malkhana", "In Malkhana", "Vehicle Yard")
ev(f, "2026-07-10 10:00", "challan")
ev(f, "2026-07-15 10:00", "case", 6, "SC-RWP-2026-0171")
ev(f, "2026-07-29 10:00", "hearing", 8, "Charge Framing", "Charge framed; accused pleaded guilty", "2026-08-19")
ev(f, "2026-08-19 10:00", "hearing", 8, "Judgment", "Plea accepted; judgment announced", None)
ev(f, "2026-08-19 15:00", "verdict", "Waleed Mushtaq", "Convicted", 2.0, 30000, "Plea of guilty accepted")
ev(f, "2026-08-25 11:00", "transfer", "EV-2026-030", 14, "Released on superdari to the owner", "Returned", None)

# ---- FIR 16: false report, cancelled -----------------------------------------------
f = fir(6, "Rubab Fatima", 17, "2026-07-04 11:00", "2026-07-03 21:00", 2,
        "Hostel room, University Town",
        "The complainant reported that her laptop was stolen from her hostel room.",
        ["PPC 379"])
ev(f, "2026-07-05 10:00", "assign", 16, "Assigned by the station house officer")
ev(f, "2026-07-06 11:00", "diary", 16, "Hostel searched. The laptop was found in the complainant's own luggage cupboard.")
ev(f, "2026-07-20 10:00", "cancel", "The complainant admitted that the laptop was misplaced; no offence made out")

# ---- FIR 17: cyber stalking by an accused who is on bail in another FIR --------------
f = fir(7, "Hira Batool", 19, "2026-07-15 14:00", "2026-07-01 09:00", 3,
        "Online, through messaging apps; complainant's residence in the Industrial Area",
        "The complainant has been followed online and sent abusive and threatening messages from several accounts since 1 July.",
        ["PECA 24", "PECA 20"])
ev(f, "2026-07-15 14:20", "party", "Hira Batool", "Victim", "Receiving abusive messages from several accounts since 1 July.")
ev(f, "2026-07-16 10:00", "assign", 19, "Assigned by the station house officer")
ev(f, "2026-07-16 12:00", "evidence", "EV-2026-031", 7, "Screenshots of the messages and call logs", 19, "Complainant's phone", None)
ev(f, "2026-07-16 12:30", "accused", "Adnan Sheikh")
ev(f, "2026-07-16 17:00", "transfer", "EV-2026-031", 26, "Deposited in digital vault", "In Malkhana", "Digital Vault DV-07")
ev(f, "2026-07-17 10:00", "party", "Lubna Shaheen", "Witness", "Colleague who has seen the messages.")
ev(f, "2026-07-17 11:00", "diary", 19, "Statements of the complainant and her colleague recorded.")
ev(f, "2026-08-02 11:00", "diary", 19, "Request sent to the messaging service for the account details.")

# ---- FIR 18: property fraud -------------------------------------------------------------
f = fir(1, "Sobia Aslam", 3, "2026-07-29 12:00", "2026-07-20 10:00", 5,
        "Property dealer's office, Riverside",
        "The complainant paid Rs 3,200,000 for a plot and later found that the seller did not own it.",
        ["PPC 420"])
ev(f, "2026-07-30 10:00", "assign", 3, "Assigned by the station house officer")
ev(f, "2026-07-30 11:00", "party", "Haji Rafiq", "Witness", "Property dealer who arranged the meeting between the parties.")
ev(f, "2026-08-04 11:00", "evidence", "EV-2026-032", 2, "Forged sale agreement and fake ownership documents", 3, "Complainant's residence", None)
ev(f, "2026-08-04 12:00", "diary", 3, "Documents examined. The revenue record shows the plot belongs to a third party.")
ev(f, "2026-08-04 12:30", "accused", "Mubashir Ali")
ev(f, "2026-08-04 16:00", "transfer", "EV-2026-032", 6, "Deposit in Malkhana", "In Malkhana", "Malkhana Shelf B-6")
ev(f, "2026-09-10 11:00", "diary", 3, "Accused called for questioning and denied the allegation.")
ev(f, "2026-10-12 11:00", "diary", 3, "Statement of the revenue officer recorded.")
ev(f, "2026-10-15 10:00", "transfer", "EV-2026-032", 3, "Sent for handwriting examination", "At Forensic Lab", None)
ev(f, "2026-10-15 10:30", "lab", "EV-2026-032", LAB_PHYSICAL, "Document", "2026-10-15", None, None)

# ---- FIR 19: firing, accused absconding ----------------------------------------------------
f = fir(2, "Ayub Khan", 8, "2026-08-12 23:40", "2026-08-12 22:30", 1,
        "Roadside tea stall near the bus stand",
        "A man opened fire at the complainant at a tea stall following an argument over a debt. The complainant was hit in the leg.",
        ["PPC 324"])
ev(f, "2026-08-12 23:45", "accused", "Sikandar Hayat")
ev(f, "2026-08-13 09:00", "assign", 7, "Assigned by the station house officer")
ev(f, "2026-08-13 09:30", "party", "Ayub Khan", "Victim", "Shot in the leg by the accused at the tea stall.")
ev(f, "2026-08-13 09:40", "party", "Bashir Ahmed", "Witness", "Was sitting at the tea stall and saw the firing.")
ev(f, "2026-08-13 10:00", "evidence", "EV-2026-033", 1, "Four empty cartridge cases from the scene", 7, "Tea stall near the bus stand", None)
ev(f, "2026-08-13 16:00", "transfer", "EV-2026-033", 9, "Deposit in Malkhana", "In Malkhana", "Arms Locker A-3")
ev(f, "2026-08-14 09:00", "transfer", "EV-2026-033", 7, "Sent for ballistic examination", "At Forensic Lab", None)
ev(f, "2026-08-14 11:00", "diary", 7, "Injured statement recorded. Raids planned for the accused's addresses.")
ev(f, "2026-08-30 12:00", "absconding", "Sikandar Hayat")
ev(f, "2026-08-30 12:30", "diary", 7, "The accused is absconding. Proclamation proceedings to be moved before the court.")
ev(f, "2026-09-05 12:00", "lab", "EV-2026-033", LAB_PHYSICAL, "Ballistics", "2026-08-14", "2026-09-05", "Cartridge cases were fired from a 9 mm pistol; no weapon is available yet to compare.")
ev(f, "2026-09-05 15:00", "transfer", "EV-2026-033", 9, "Returned from laboratory", "In Malkhana", None)
ev(f, "2026-09-25 11:00", "diary", 7, "Application for proclamation of the accused sent to the court.")

# ---- FIR 20: illegal pistol at a checkpoint (police complainant), challan submitted -----------
f = fir(8, ("officer", 21), 21, "2026-08-25 16:10", "2026-08-25 15:00", 6,
        "Checkpoint near the airport road",
        "During a vehicle check a 9 mm pistol with five rounds was found under the driver's seat. The driver had no licence.",
        ["Arms Ord. 13"])
ev(f, "2026-08-25 16:15", "accused", "Taimoor Zaheer")
ev(f, "2026-08-25 16:30", "arrest", "Taimoor Zaheer", 21, "Checkpoint near the airport road", 2)
ev(f, "2026-08-25 17:00", "evidence", "EV-2026-034", 1, "Pistol 9 mm with five rounds recovered from the car", 21, "Under the driver's seat", None)
ev(f, "2026-08-25 20:00", "transfer", "EV-2026-034", 27, "Deposit in Malkhana", "In Malkhana", "Arms Locker A-2")
ev(f, "2026-08-26 09:00", "assign", 20, "Investigation given to the station house officer, not the complainant")
ev(f, "2026-08-27 11:00", "diary", 20, "Licence verification: no licence on record for the pistol or the accused.")
ev(f, "2026-09-02 10:00", "bail_apply", "b20", "Taimoor Zaheer", 10, "Post-arrest")
ev(f, "2026-09-10 11:00", "bail_decide", "b20", "Granted", 100000, "Granted; weapon already in custody")
ev(f, "2026-09-20 11:00", "diary", 20, "Recovery formalities complete; challan being prepared.")
ev(f, "2026-09-30 10:00", "challan")

# ---- FIR 21 to 24: recent FIRs ---------------------------------------------------------------
f = fir(3, "Danish Ali", 11, "2026-09-05 10:30", "2026-09-04 20:00", 2,
        "Bus stop near Old City Market",
        "Two men on a motorcycle snatched the complainant's mobile phone at the bus stop.", ["PPC 379"])
f = fir(5, "Rukhsana Kausar", 15, "2026-09-18 08:15", "2026-09-17 23:50", 7,
        "Cantt Road crossing",
        "A speeding truck hit the complainant's husband's motorcycle at the crossing. He died at the scene.", ["PPC 320"])
ev(f, "2026-09-18 08:20", "accused", "Adil Bashir")
ev(f, "2026-09-18 10:00", "arrest", "Adil Bashir", 15, "Truck stand, Cantt Road", 1)
ev(f, "2026-09-18 11:00", "evidence", "EV-2026-035", 6, "Truck involved in the accident", 15, "Truck stand, Cantt Road", None)
ev(f, "2026-09-18 16:00", "transfer", "EV-2026-035", 24, "Deposit in Malkhana", "In Malkhana", "Vehicle Yard")
ev(f, "2026-09-19 09:00", "assign", 14, "Assigned by the station house officer")
ev(f, "2026-09-20 11:00", "diary", 14, "Scene inspected and the driver's statement recorded.")
ev(f, "2026-10-05 11:00", "diary", 14, "Mechanical inspection report awaited.")
f = fir(6, "Sadaf Munir", 17, "2026-10-02 12:00", "2026-09-28 09:00", 5,
        "Complainant's boutique, University Town",
        "A cheque of Rs 750,000 given by a customer for goods was returned unpaid.", ["PPC 489-F"])
f = fir(4, "Imtiaz Hussain", 13, "2026-10-20 07:20", "2026-10-19 02:00", 2,
        "House 9, Street 6, Saddar Housing Society",
        "The house was broken into at night while the family was away. Electronic goods were taken.",
        ["PPC 457", "PPC 380"])


# ---------------------------------------------------------------------
# Emit SQL
# ---------------------------------------------------------------------
def sha(evidence_no):
    return hashlib.sha256(f"sample-evidence:{evidence_no}".encode()).hexdigest()


emit("-- =====================================================================")
emit("-- FIR and Criminal Case Management System (FIR-CMS)")
emit("-- File 3 of 3: sample data (all names, numbers and events are fictional)")
emit("-- GENERATED by tools/generate_sample_data.py. Do not edit by hand.")
emit("-- Run after schema.sql and logic.sql. The data is replayed through the real")
emit("-- stored procedures on a simulated clock (@as_of), so triggers, custody logs")
emit("-- and status history are filled by the database itself.")
emit("-- =====================================================================")
emit()
emit("USE fir_ccms;")
emit("SET NAMES utf8mb4;")
emit("SET @as_of = NULL;")
emit()

emit("-- Reference data -------------------------------------------------------")
emit("INSERT INTO districts (name, province) VALUES")
emit(",\n".join(f"  ({q(a)}, {q(b)})" for a, b in DISTRICTS) + ";")
emit()
emit("INSERT INTO police_stations (station_code, name, district_id, address, phone) VALUES")
emit(",\n".join(f"  ({q(c)}, {q(nm)}, {d}, {q(a)}, {q(p)})" for c, nm, d, a, p in STATIONS) + ";")
emit()
emit("INSERT INTO ranks (title, rank_level, can_investigate) VALUES")
emit(",\n".join(f"  ({q(t)}, {l}, {c})" for t, l, c in RANKS) + ";")
emit()
emit("INSERT INTO crime_categories (name, description) VALUES")
emit(",\n".join(f"  ({q(a)}, {q(b)})" for a, b in CATEGORIES) + ";")
emit()
emit("-- Reference data for illustration only; check against the current statutes before real use.")
emit("INSERT INTO legal_sections (act, section_no, title, category_id, punishment_summary, is_cognizable, is_bailable) VALUES")
emit(",\n".join(f"  ({q(a)}, {q(s)}, {q(t)}, {c}, {q(p)}, {cg}, {b})" for a, s, t, c, p, cg, b in SECTIONS) + ";")
emit()
emit("INSERT INTO evidence_types (name, is_digital) VALUES")
emit(",\n".join(f"  ({q(a)}, {b})" for a, b in EVIDENCE_TYPES) + ";")
emit()

emit("-- Officers (supervisors are listed before the officers who report to them) ---")
emit("INSERT INTO officers (officer_id, badge_no, full_name, rank_id, station_id, supervisor_id, phone, email, joined_on, is_active) VALUES")
rows = []
for oid, badge, name, rk, st, sup, joined, active in OFFICERS:
    parts = name.split()
    email = f"{parts[0].lower()}.{parts[-1].lower()}@police.example"
    rows.append(f"  ({oid}, {q(badge)}, {q(name)}, {rk}, {st}, {n(sup)}, {q('0300-5550' + format(oid, '03d'))}, {q(email)}, {q(joined)}, {active})")
emit(",\n".join(rows) + ";")
emit()
emit("INSERT INTO roles (role_name, description) VALUES")
emit(",\n".join(f"  ({q(a)}, {q(b)})" for a, b in ROLES) + ";")
emit()
emit("-- Sample logins only. The hash is SHA-256 of 'demo-<username>'; a real system would use a salted bcrypt or Argon2 hash.")
emit("INSERT INTO users (username, password_hash, role_id, officer_id) VALUES")
emit(",\n".join(f"  ({q(u)}, SHA2({q('demo-' + u)}, 256), {r}, {n(o)})" for u, r, o in USERS) + ";")
emit()
emit("INSERT INTO courts (name, court_type, district_id, address) VALUES")
emit(",\n".join(f"  ({q(a)}, {q(t)}, {d}, {q(ad)})" for a, t, d, ad in COURTS) + ";")
emit()
emit("INSERT INTO judges (full_name, court_id, appointed_on) VALUES")
emit(",\n".join(f"  ({q(a)}, {c}, {q(d)})" for a, c, d in JUDGES) + ";")
emit()

emit("-- Persons (CNIC numbers are fake: 00000-<serial>-<digit>) --------------------")
emit("INSERT INTO persons (person_id, cnic, full_name, father_name, gender, date_of_birth, phone, address, district_id, occupation) VALUES")
rows = []
for i, (name, father, gender, dob, dist, occ) in enumerate(PERSONS, start=1):
    cnic = None if name in NO_CNIC else f"00000-{i:07d}-{i % 10}"
    phone = f"0311-5550{i:03d}"
    addr = f"House {10 + i}, Block {chr(65 + i % 6)}, {DISTRICT_NAME[dist]}"
    rows.append(f"  ({i}, {q(cnic)}, {q(name)}, {q(father)}, {q(gender)}, {q(dob)}, {q(phone)}, {q(addr)}, {dist}, {q(occ)})")
emit(",\n".join(rows) + ";")
emit()

# ---- replay cases -------------------------------------------------------
acc_id = {}       # (fir_no, person name) -> fir_accused_id
ev_id = {}        # evidence_no -> evidence_id
bail_id = {}      # key -> bail_id
case_id = {}      # fir_no -> case_id
counters = defaultdict(int)

emit("-- Cases: every FIR is replayed through the stored procedures ---------------")
emit("-- fir_id values follow the order of registration below (1 to 24).")
emit()

for fir_no, f in enumerate(FIRS, start=1):
    emit(f"-- ------------------------------------------------------------------")
    emit(f"-- FIR {fir_no}: {f['loc']} ({f['reported'][:10]})")
    emit(f"-- ------------------------------------------------------------------")
    events = [(f["reported"], -1, "register", ())]
    for seq, (ts, kind, args) in enumerate(f["events"]):
        events.append((ts, seq, kind, args))
    events.sort(key=lambda e: (e[0], e[1]))

    for ts, _seq, kind, a in events:
        emit(f"SET @as_of = '{ts}:00';")
        if kind == "register":
            comp = f["comp"]
            if isinstance(comp, tuple):
                cp, co = "NULL", str(comp[1])
            else:
                cp, co = str(PID[comp]), "NULL"
            emit(f"CALL sp_register_fir({f['st']}, {cp}, {co}, {f['regby']}, '{f['incident']}:00', {q(f['loc'])}, {f['cat']}, {q(f['desc'])}, @fir_id, @fir_no);")
            sec = ", ".join(f"({fir_no}, {SECTION_ID[s]})" for s in f["sections"])
            emit(f"INSERT INTO fir_sections (fir_id, section_id) VALUES {sec};")
        elif kind == "assign":
            emit(f"CALL sp_assign_investigator({fir_no}, {a[0]}, {q(a[1])});")
        elif kind == "party":
            emit(f"INSERT INTO fir_parties (fir_id, person_id, party_role, statement) VALUES ({fir_no}, {PID[a[0]]}, {q(a[1])}, {q(a[2])});")
        elif kind == "accused":
            counters["accused"] += 1
            acc_id[(fir_no, a[0])] = counters["accused"]
            emit(f"INSERT INTO fir_accused (fir_id, person_id, added_on) VALUES ({fir_no}, {PID[a[0]]}, '{ts[:10]}');")
        elif kind == "absconding":
            emit(f"UPDATE fir_accused SET status = 'Absconding' WHERE fir_accused_id = {acc_id[(fir_no, a[0])]};")
        elif kind == "diary":
            emit(f"INSERT INTO case_diary (fir_id, officer_id, entry_date, entry_text) VALUES ({fir_no}, {a[0]}, '{ts[:10]}', {q(a[1])});")
        elif kind == "evidence":
            no, tid, desc, by, where, _ = a
            counters["evidence"] += 1
            ev_id[no] = counters["evidence"]
            digital = EVIDENCE_TYPES[tid - 1][1]
            h = q(sha(no)) if digital else "NULL"
            emit(f"INSERT INTO evidence (evidence_no, fir_id, type_id, description, collected_by, collected_at, found_location, current_custodian_id, status, hash_sha256) VALUES ({q(no)}, {fir_no}, {tid}, {q(desc)}, {by}, '{ts}:00', {q(where)}, {by}, 'With Investigator', {h});")
        elif kind == "transfer":
            no, to, purpose, status, storage = a
            emit(f"CALL sp_transfer_evidence({ev_id[no]}, {to}, {q(purpose)}, {q(status)}, {q(storage)});")
        elif kind == "lab":
            no, lab, rtype, sub, rep, finding = a
            emit(f"INSERT INTO lab_reports (evidence_id, lab_name, report_type, submitted_on, reported_on, findings) VALUES ({ev_id[no]}, {q(lab)}, {q(rtype)}, {q(sub)}, {q(rep)}, {q(finding)});")
        elif kind == "arrest":
            emit(f"CALL sp_register_arrest({acc_id[(fir_no, a[0])]}, {a[1]}, {q(a[2])}, {a[3]});")
        elif kind == "bail_apply":
            counters["bail"] += 1
            bail_id[a[0]] = counters["bail"]
            emit(f"INSERT INTO bail_applications (fir_accused_id, court_id, bail_type, applied_on) VALUES ({acc_id[(fir_no, a[1])]}, {a[2]}, {q(a[3])}, '{ts[:10]}');")
        elif kind == "bail_decide":
            key, decision, surety, remarks = a
            emit(f"CALL sp_decide_bail({bail_id[key]}, {q(decision)}, {n(None if surety is None else '%.2f' % surety)}, {q(remarks)});")
        elif kind == "challan":
            emit(f"CALL sp_submit_challan({fir_no});")
        elif kind == "case":
            counters["case"] += 1
            case_id[fir_no] = counters["case"]
            emit(f"CALL sp_file_court_case({fir_no}, {a[0]}, {q(a[1])}, @case_id);")
        elif kind == "hearing":
            judge, purpose, outcome, nxt = a
            emit(f"INSERT INTO hearings (case_id, hearing_date, judge_id, purpose, outcome, next_hearing_date) VALUES ({case_id[fir_no]}, '{ts[:10]}', {judge}, {q(purpose)}, {q(outcome)}, {q(nxt)});")
        elif kind == "verdict":
            who, verdict, years, fine, remarks = a
            emit(f"CALL sp_record_verdict({case_id[fir_no]}, {acc_id[(fir_no, who)]}, {q(verdict)}, {n(None if years is None else '%.1f' % years)}, {n(None if fine is None else '%.2f' % fine)}, {q(remarks)});")
        elif kind == "withdraw":
            emit(f"CALL sp_withdraw_case({case_id[fir_no]}, {q(a[0])});")
        elif kind == "cancel":
            emit(f"CALL sp_cancel_fir({fir_no}, {q(a[0])});")
        else:
            raise SystemExit(f"unknown event kind {kind}")
    emit()

emit("SET @as_of = NULL;")
emit("SET @custody_purpose = NULL;")

sys.stdout.write("\n".join(out) + "\n")
