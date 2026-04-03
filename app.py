

from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
import random
import smtplib
import hashlib

from model import load_model
from PIL import Image
import torchvision.transforms as transforms
import torch
import json

torch.set_num_threads(1)

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------- EMAIL CONFIG ----------------
EMAIL = "edupluseai0@gmail.com"
APP_PASSWORD = "hlkq zvxr kylq eauy"

# ---------------- LOAD MODEL ----------------
model = None
device = None

def get_model():
    global model, device
    if model is None:
        from model import load_model
        model, device = load_model("model.pth")
    return model, device

with open("labels.json") as f:
    labels = json.load(f)

transform = transforms.Compose([
    transforms.Resize((28, 28)),
    transforms.ToTensor()
])

# ---------------- DISEASE INFO ----------------
disease_info = {
    "akiec": {
        "name": "Actinic Keratosis",
        "medicines": ["Diclofenac Gel 3%", "Fluorouracil Cream 5%"],
        "precautions": [
            "Avoid sun exposure",
            "Use sunscreen SPF 50+",
            "Wear protective clothing"
        ],
        "link": "https://www.1mg.com"
    },

    "bcc": {
        "name": "Basal Cell Carcinoma",
        "medicines": ["Imiquimod Cream 5%", "Fluorouracil 5%"],
        "precautions": [
            "Avoid UV rays",
            "Regular skin checkup",
            "Use sunscreen daily"
        ],
        "link": "https://www.apollopharmacy.in"
    },

    "bkl": {
        "name": "Benign Keratosis",
        "medicines": ["Salicylic Acid Cream 6%", "Cryotherapy"],
        "precautions": [
            "Do not scratch",
            "Maintain hygiene",
            "Consult doctor if irritated"
        ],
        "link": "https://www.netmeds.com"
    },

    "df": {
        "name": "Dermatofibroma",
        "medicines": ["Usually no treatment required"],
        "precautions": [
            "Avoid skin injury",
            "Monitor changes",
            "Consult doctor if painful"
        ],
        "link": "https://www.apollopharmacy.in"
    },

    "nv": {
        "name": "Melanocytic Nevus (Mole)",
        "medicines": ["No medication needed"],
        "precautions": [
            "Monitor size and color",
            "Avoid irritation",
            "Consult doctor if changes occur"
        ],
        "link": "https://www.netmeds.com"
    },

    "vasc": {
        "name": "Vascular Lesion",
        "medicines": ["Laser therapy", "Topical beta blockers"],
        "precautions": [
            "Avoid injury",
            "Keep area clean",
            "Consult specialist if bleeding"
        ],
        "link": "https://www.1mg.com"
    },

    "mel": {
        "name": "Melanoma (Skin Cancer)",
        "medicines": ["Dacarbazine 100mg", "Temozolomide 250mg"],
        "precautions": [
            "Avoid sunlight exposure",
            "Use sunscreen SPF 50+",
            "Immediate medical consultation"
        ],
        "link": "https://www.1mg.com"
    }
}
# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect("users.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            name TEXT,
            email TEXT PRIMARY KEY,
            password TEXT
        )
    """)
    conn.close()

init_db()

# ---------------- HASH ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- SEND OTP ----------------
def send_otp(email, otp):
    message = f"Subject: OTP Verification\n\nYour OTP is: {otp}"

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL, APP_PASSWORD)
    server.sendmail(EMAIL, email, message)
    server.quit()

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("landing.html")
# ---------------- REGISTER (INLINE OTP) ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    step = "form"

    if request.method == "POST":

        if "send_otp" in request.form:
            name = request.form.get("name")
            email = request.form.get("email")
            password = request.form.get("password")
            confirm = request.form.get("confirm")

            if password != confirm:
                error = "Passwords do not match ❌"
                return render_template("register.html", error=error, step="form")

            conn = sqlite3.connect("users.db")
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email=?", (email,))
            if cur.fetchone():
                conn.close()
                error = "Email already registered ❌"
                return render_template("register.html", error=error, step="form")
            conn.close()

            otp = str(random.randint(100000, 999999))

            session["reg_name"] = name
            session["reg_email"] = email
            session["reg_password"] = hash_password(password)
            session["otp"] = otp

            send_otp(email, otp)

            return render_template("register.html", step="otp")

        elif "verify_otp" in request.form:
            user_otp = request.form.get("otp")

            if user_otp == session.get("otp"):
                conn = sqlite3.connect("users.db")
                conn.execute(
                    "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                    (session["reg_name"], session["reg_email"], session["reg_password"])
                )
                conn.commit()
                conn.close()

                return redirect("/login")
            else:
                error = "Invalid OTP ❌"
                return render_template("register.html", error=error, step="otp")

    return render_template("register.html", step="form")# ---------------- LOGIN ----------------


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = hash_password(request.form["password"])

        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        data = cur.fetchone()
        conn.close()

        if data:
            session["user"] = email
            return redirect("/predict")
        else:
            error = "Invalid login details ❌"

    return render_template("login.html", error=error)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- PREDICT ----------------
@app.route("/predict", methods=["GET", "POST"])
def predict():
    if "user" not in session:
        return redirect("/login")

    prediction = None
    confidence = None
    image_path = None
    medicines = []
    precautions = []
    link = "#"

    if request.method == "POST":
        file = request.files["file"]

        if file:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(filepath)

            # ✅ LOAD MODEL HERE (IMPORTANT FIX)
            model, device = get_model()

            image = Image.open(filepath).convert("RGB")
            image = transform(image).unsqueeze(0).to(device)

            with torch.no_grad():
                output = model(image)
                probs = torch.softmax(output, dim=1)
                conf, pred = torch.max(probs, 1)

            key = labels[str(pred.item())].lower()
            info = disease_info.get(key, {})

            prediction = info.get("name", key)
            medicines = info.get("medicines", [])
            precautions = info.get("precautions", [])
            link = info.get("link", "#")

            confidence = round(conf.item() * 100, 2)
            image_path = filepath

    return render_template("index.html",
                           prediction=prediction,
                           confidence=confidence,
                           image_path=image_path,
                           medicines=medicines,
                           precautions=precautions,
                           link=link,
                           user=session["user"])
# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
