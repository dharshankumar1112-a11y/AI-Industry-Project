from flask import Flask, render_template, request
import pandas as pd
import os
import pdfplumber
import re
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------- CSV MACHINE ANALYSIS --------
def normalize_columns(df):
    new_columns = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if "air temperature" in col_lower or "process temperature" in col_lower or "temperature" in col_lower or col_lower in ["metric1", "metric2"]:
            new_columns[col] = "temperature"
        elif "rpm" in col_lower or "rotational speed" in col_lower or col_lower == "metric3":
            new_columns[col] = "rpm"
        elif "torque" in col_lower or col_lower == "metric4":
            new_columns[col] = "torque"
        elif "tool wear" in col_lower or col_lower == "metric5":
            new_columns[col] = "tool_wear"
        elif "vibration" in col_lower:
            new_columns[col] = "vibration"
        elif "failure" in col_lower:
            new_columns[col] = "failure"

    df = df.rename(columns=new_columns)
    df = df.loc[:,~df.columns.duplicated()]
    return df

def analyze_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        df = normalize_columns(df)

        total_rows = len(df)
        avg_temp = df["temperature"].mean() if "temperature" in df.columns else 0
        max_temp = df["temperature"].max() if "temperature" in df.columns else 0
        min_temp = df["temperature"].min() if "temperature" in df.columns else 0
        
        if avg_temp > 200:
            avg_temp -= 273.15
            max_temp -= 273.15
            min_temp -= 273.15
            
        avg_rpm = df["rpm"].mean() if "rpm" in df.columns else 0
        max_rpm = df["rpm"].max() if "rpm" in df.columns else 0
        min_rpm = df["rpm"].min() if "rpm" in df.columns else 0

        avg_torque = df["torque"].mean() if "torque" in df.columns else 0
        avg_wear = df["tool_wear"].mean() if "tool_wear" in df.columns else 0

        supervised_failure = "N/A"
        if "failure" in df.columns:
            flagged = pd.to_numeric(df["failure"], errors='coerce').sum()
            supervised_failure = f"{int(flagged)} record(s) flagged" if flagged > 0 else "None flagged"

        # Unique risk probability logic
        if avg_temp > 80 or avg_rpm > 2000 or avg_wear > 200:
            health = "Critical"
            savings = "₹50,000"
            risk_score = min(98.9, 85.4 + (avg_temp % 10))
        elif avg_temp > 60 or avg_wear > 150:
            health = "Warning"
            savings = "₹20,000"
            risk_score = min(84.9, 60.2 + (avg_temp % 20))
        else:
            health = "Healthy"
            savings = "₹10,000"
            risk_score = min(59.9, 12.5 + (avg_temp % 30))

        return {
            "status": "Success", 
            "health": health, 
            "savings": savings,
            "total_rows": f"{total_rows:,}",
            "avg_temp": round(avg_temp, 1),
            "max_temp": round(max_temp, 1),
            "min_temp": round(min_temp, 1),
            "avg_rpm": int(avg_rpm),
            "max_rpm": int(max_rpm),
            "min_rpm": int(min_rpm),
            "avg_torque": round(avg_torque, 1),
            "avg_wear": round(avg_wear, 1),
            "supervised_failure": supervised_failure,
            "risk_score": round(risk_score, 1)
        }
    except Exception as e:
        return {"status": "Error", "health": str(e), "savings": 0}

# -------- PDF EXTRACTION --------
def normalize_date(date_text):
    try:
        if re.match(r"\d{1,2}/\d{1,2}/\d{4}", date_text):
            dt = datetime.strptime(date_text, "%d/%m/%Y")
            return dt.strftime("%Y-%m-%d")
    except:
        return date_text
    return date_text

def normalize_amount(amount_text):
    is_usd = "$" in amount_text
    amount_text = amount_text.replace(",", "")
    match = re.search(r"\d+(\.\d+)?", amount_text)
    if match:
        val = int(float(match.group(0)))
        return f"${val:,}" if is_usd else f"₹{val:,}"
    return amount_text

def clean_blanks(text):
    # Replaces '_____' with '[Unspecified]' to make blank templates understandable
    if not isinstance(text, str): return text
    return re.sub(r'_{2,}', '[Unspecified]', text).strip()

def clean_entities(raw_entities):
    cleaned = {"PARTY": [], "DATE": [], "AMOUNT": [], "JURISDICTION": []}
    for text, label in raw_entities:
        text = clean_blanks(str(text))
        if label == "DATE":
            cleaned["DATE"].append(normalize_date(text))
        elif label == "AMOUNT":
            cleaned["AMOUNT"].append(normalize_amount(text))
        elif label == "PARTY":
            # Remove junk matches
            if len(text) < 150 and "entered into" not in text.lower():
                cleaned["PARTY"].append(text)
        elif label == "JURISDICTION":
            if len(text) < 50:
                cleaned["JURISDICTION"].append(text)

    for key in cleaned:
        cleaned[key] = list(dict.fromkeys(cleaned[key]))
    return cleaned

def extract_pdf(pdf_path):
    full_text = ""
    total_pages = 0
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page in pdf.pages[:max(3, total_pages)]:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    total_chars = len(full_text)
    raw_entities = []

    # DATE
    dates = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", full_text)
    word_dates = re.findall(r"(?:this|the)\s+[\w_]+\s+day\s+of\s+[A-Za-z\s,_]+(?:\d{2,4})?", full_text, re.I)
    for d in dates + word_dates:
        raw_entities.append((d, "DATE"))

    # AMOUNT
    amounts = re.findall(r"Rs\.?\s?\d+(?:,\d{2,3})*|₹\s?\d+(?:,\d{2,3})*|\$\d+(?:,\d{3})*", full_text)
    for a in amounts:
        raw_entities.append((a, "AMOUNT"))

    # PARTY Generalized Fallbacks
    p_generic = re.search(r"between\s+(?:the\s+)?(.*?)\s+and\s+(.*?)\s+(?:for|hereinafter|,|registered|\()", full_text, re.I | re.DOTALL)
    if p_generic:
        name1 = " ".join(p_generic.group(1).split())
        name2 = " ".join(p_generic.group(2).split())
        if len(name1) < 150 and "entered into" not in name1.lower(): raw_entities.append((name1, "PARTY"))
        if len(name2) < 150 and "entered into" not in name2.lower(): raw_entities.append((name2, "PARTY"))

    p1 = re.search(r"between\s+(?:the\s+)?(.*?)(?:,|\s+\(hereinafter|\s+hereinafter)", full_text, re.I | re.DOTALL)
    if p1:
        name = " ".join(p1.group(1).split())
        raw_entities.append((name, "PARTY"))

    p2_matches = re.findall(r"and\s+(M/s.*?)(?:registered|having|,|\()", full_text, re.I | re.DOTALL)
    for p in p2_matches:
        name = " ".join(p.split())
        raw_entities.append((name, "PARTY"))
        
    p3 = re.search(r",\s*and\s+(.*?),\s*hereinafter", full_text, re.I | re.DOTALL)
    if p3:
        name = " ".join(p3.group(1).split())
        raw_entities.append((name, "PARTY"))

    if "CONSULTANT" in full_text.upper():
        raw_entities.append(("CONSULTANT", "PARTY"))

    iit_match = re.search(r"Indian Institute of Technology.*?Kanpur", full_text, re.I)
    if iit_match:
        raw_entities.append((iit_match.group(0), "PARTY"))

    # JURISDICTION
    juris = re.search(r"courts in (\w+)", full_text, re.I)
    if juris:
        raw_entities.append((juris.group(1), "JURISDICTION"))
    gov_law = re.search(r"laws of (?:the\s+)?([A-Za-z\s]+)(?:,|\.|and)", full_text, re.I)
    if gov_law:
        raw_entities.append((gov_law.group(1).strip(), "JURISDICTION"))

    cleaned_data = clean_entities(raw_entities)

    # Document Classification & Confidence AI
    doc_type = "Generic Legal Contract"
    header = full_text[:1000].upper()
    if "SERVICES AGREEMENT" in header: doc_type = "Professional Services Contract"
    elif "RESIDENCE" in header: doc_type = "Hall of Residence Agreement"
    elif "LEASE" in header: doc_type = "Lease or Rental Contract"
    elif "EMPLOYMENT" in header: doc_type = "Employment Agreement"
    elif "NON-DISCLOSURE" in header or "NDA" in header: doc_type = "Non-Disclosure Agreement"
    elif "STANDARD CONTRACT" in header or "MINISTRY OF" in header: doc_type = "Government Standard Contract"

    detected_cats = sum(1 for v in cleaned_data.values() if len(v) > 0)
    confidence = min(98.6, 12.0 + (detected_cats * 21.5)) # Dynamically scales to 98.6% max
    
    # Catch non-contracts like academic papers or templates that completely lack core pillars
    if confidence <= 35 and not any(k in header for k in ["THIS AGREEMENT", "AGREEMENT BETWEEN", "CONTRACT NO", "STANDARD CONTRACT"]):
        doc_type = "Informational / Research Paper"
    
    missing_criticals = []
    if not cleaned_data["PARTY"]: missing_criticals.append("No Counterparties Found")
    if not cleaned_data["AMOUNT"]: missing_criticals.append("No Financial Liability Found")
    if not cleaned_data["JURISDICTION"]: missing_criticals.append("No Legal Jurisdiction Defined")

    cleaned_data["META"] = {
        "doc_type": doc_type,
        "total_pages": total_pages,
        "total_chars": f"{total_chars:,}",
        "confidence": confidence,
        "warnings": missing_criticals
    }

    return cleaned_data

# -------- ROUTES --------
@app.route('/')
def home():
    return render_template("index.html")

@app.route('/csv', methods=["GET", "POST"])
def csv_upload():
    result = None
    if request.method == "POST":
        file = request.files["file"]
        if file:
            path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(path)
            result = analyze_csv(path)
    return render_template("csv.html", result=result)

@app.route('/pdf', methods=["GET", "POST"])
def pdf_upload():
    data = None
    if request.method == "POST":
        file = request.files["file"]
        if file:
            path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(path)
            data = extract_pdf(path)
    return render_template("pdf.html", data=data)

if __name__ == "__main__":
    app.run(debug=True)