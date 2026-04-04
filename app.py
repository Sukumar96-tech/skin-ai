

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

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------- EMAIL CONFIG ----------------
EMAIL = "edupluseai0@gmail.com"
APP_PASSWORD = "hlkq zvxr kylq eauy"

# ---------------- LOAD MODEL ----------------
model, device = load_model("model.pth")

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
    try:
        message = f"Subject: OTP Verification\n\nYour OTP is: {otp}"

        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(EMAIL, APP_PASSWORD)
        server.sendmail(EMAIL, email, message)
        server.quit()

        print("✅ OTP sent")

    except Exception as e:
        print("❌ Email failed:", e)

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

             # fallback (show OTP in UI/log)
            print("OTP:", otp)

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

    return render_template("register.html", step="form")
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
#-----------------forgot password----------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    error = None
    step = "email"

    if request.method == "POST":

        # STEP 1 → Send OTP
        if "send_otp" in request.form:
            email = request.form.get("email")

            conn = sqlite3.connect("users.db")
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email=?", (email,))
            if not cur.fetchone():
                conn.close()
                error = "Email not registered ❌"
                return render_template("forgot.html", error=error, step="email")
            conn.close()

            otp = str(random.randint(100000, 999999))
            session["reset_email"] = email
            session["otp"] = otp

            send_otp(email, otp)

            return render_template("forgot.html", step="otp")

        # STEP 2 → Reset Password
        elif "reset_password" in request.form:
            otp = request.form.get("otp")
            new_password = hash_password(request.form.get("password"))

            if otp == session.get("otp"):
                conn = sqlite3.connect("users.db")
                conn.execute(
                    "UPDATE users SET password=? WHERE email=?",
                    (new_password, session["reset_email"])
                )
                conn.commit()
                conn.close()

                return redirect("/login")
            else:
                error = "Invalid OTP ❌"
                return render_template("forgot.html", error=error, step="otp")

    return render_template("forgot.html", step="email")
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
    app.run(debug=True)
