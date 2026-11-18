import os, csv, io, sqlite3, time
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
from analyzer import analyze_review, clean_text, ASPECTS
from database import init_db, get_db, seed_demo_data

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "instance", "feedback.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
app.config["DB_PATH"] = DB_PATH
init_db(app)
with app.app_context():
    seed_demo_data()

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
if not ADMIN_PASSWORD_HASH:
    ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin123"))

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            flash("Please sign in to access the admin area.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def product_stats(db, product_id):
    rows = db.execute("""
        SELECT a.aspect, a.sentiment, COUNT(*) AS n
        FROM analyses a JOIN reviews r ON r.id=a.review_id
        WHERE r.product_id=? GROUP BY a.aspect, a.sentiment
    """, (product_id,)).fetchall()
    result = {a: {"positive":0,"negative":0,"neutral":0,"total":0} for a in ASPECTS}
    for row in rows:
        if row["aspect"] in result:
            result[row["aspect"]][row["sentiment"]] = row["n"]
            result[row["aspect"]]["total"] += row["n"]
    for a, v in result.items():
        v["positive_pct"] = round(v["positive"] / v["total"] * 100, 1) if v["total"] else 0
        v["negative_pct"] = round(v["negative"] / v["total"] * 100, 1) if v["total"] else 0
        v["neutral_pct"] = round(v["neutral"] / v["total"] * 100, 1) if v["total"] else 0
    return result

@app.route("/")
def index():
    db = get_db()
    total_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_reviews = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    sentiments = {r["sentiment"]: r["n"] for r in db.execute(
        "SELECT sentiment, COUNT(*) n FROM analyses GROUP BY sentiment").fetchall()}
    total_analyses = sum(sentiments.values())
    positive = sentiments.get("positive", 0)
    negative = sentiments.get("negative", 0)
    neutral = sentiments.get("neutral", 0)
    products = db.execute("""
        SELECT p.*, COUNT(DISTINCT r.id) review_count
        FROM products p LEFT JOIN reviews r ON r.product_id=p.id
        GROUP BY p.id ORDER BY p.name
    """).fetchall()
    recent = db.execute("""
        SELECT r.*, p.name product_name FROM reviews r JOIN products p ON p.id=r.product_id
        ORDER BY r.created_at DESC LIMIT 7
    """).fetchall()
    return render_template("dashboard.html", total_products=total_products, total_reviews=total_reviews,
        positive=positive, negative=negative, neutral=neutral, total_analyses=total_analyses,
        products=products, recent=recent)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","")
        password = request.form.get("password","")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["admin"] = True
            flash("Welcome back.", "success")
            return redirect(url_for("index"))
        flash("Incorrect username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "info")
    return redirect(url_for("index"))

@app.route("/products")
def products():
    db = get_db()
    items = db.execute("""
        SELECT p.*, COUNT(DISTINCT r.id) review_count
        FROM products p LEFT JOIN reviews r ON r.product_id=p.id
        GROUP BY p.id ORDER BY p.created_at DESC
    """).fetchall()
    return render_template("products.html", products=items)

@app.route("/products/add", methods=["POST"])
@admin_required
def add_product():
    name = request.form.get("name","").strip()
    category = request.form.get("category","").strip()
    description = request.form.get("description","").strip()
    if not name:
        flash("Product name is required.", "danger")
    else:
        db = get_db()
        try:
            db.execute("INSERT INTO products(name,category,description,created_at) VALUES(?,?,?,?)",
                       (name,category,description,datetime.utcnow().isoformat()))
            db.commit()
            flash("Product added.", "success")
        except sqlite3.IntegrityError:
            flash("A product with that name already exists.", "warning")
    return redirect(url_for("products"))

@app.route("/products/<int:product_id>")
def product_detail(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        return "Product not found", 404
    stats = product_stats(db, product_id)
    reviews = db.execute("""
        SELECT r.*, GROUP_CONCAT(a.aspect || ':' || a.sentiment, ' | ') labels
        FROM reviews r LEFT JOIN analyses a ON a.review_id=r.id
        WHERE r.product_id=? GROUP BY r.id ORDER BY r.created_at DESC LIMIT 100
    """, (product_id,)).fetchall()
    platform_rows = db.execute("""
        SELECT r.source, COUNT(DISTINCT r.id) n,
        SUM(CASE WHEN a.sentiment='positive' THEN 1 ELSE 0 END) positive,
        SUM(CASE WHEN a.sentiment='negative' THEN 1 ELSE 0 END) negative,
        SUM(CASE WHEN a.sentiment='neutral' THEN 1 ELSE 0 END) neutral
        FROM reviews r LEFT JOIN analyses a ON a.review_id=r.id
        WHERE r.product_id=? GROUP BY r.source
    """, (product_id,)).fetchall()
    return render_template("product_detail.html", product=product, stats=stats, reviews=reviews,
                           platform_rows=platform_rows, aspects=ASPECTS)

@app.route("/reviews/add", methods=["GET","POST"])
def add_review():
    db = get_db()
    products = db.execute("SELECT id,name FROM products ORDER BY name").fetchall()
    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        text = request.form.get("review_text","").strip()
        source = request.form.get("source","Manual")
        rating = request.form.get("rating", type=int)
        reviewer = request.form.get("reviewer","Anonymous").strip() or "Anonymous"
        if not product_id or not text or not db.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone():
            flash("Choose a product and enter review text.", "danger")
        elif rating is not None and not 1 <= rating <= 5:
            flash("Rating must be between 1 and 5.", "danger")
        else:
            add_review_record(db, product_id, text, source, rating, reviewer)
            flash("Review saved and analyzed successfully.", "success")
            return redirect(url_for("product_detail", product_id=product_id))
    return render_template("add_review.html", products=products)

def add_review_record(db, product_id, text, source, rating=None, reviewer="Anonymous", external_id=None):
    existing = db.execute("SELECT id FROM reviews WHERE product_id=? AND review_text=? AND source=?",
                          (product_id,text,source)).fetchone()
    if existing:
        return False
    cur = db.execute("""INSERT INTO reviews(product_id,source,external_id,reviewer,rating,review_text,clean_text,created_at)
                        VALUES(?,?,?,?,?,?,?,?)""",
                     (product_id,source,external_id,reviewer,rating,text,clean_text(text),datetime.utcnow().isoformat()))
    review_id = cur.lastrowid
    analyses = analyze_review(text)
    for item in analyses:
        db.execute("""INSERT INTO analyses(review_id,aspect,sentiment,confidence,method)
                      VALUES(?,?,?,?,?)""",
                   (review_id,item["aspect"],item["sentiment"],item["confidence"],item["method"]))
    db.commit()
    return True

@app.route("/reviews/import", methods=["GET","POST"])
@admin_required
def import_reviews():
    db = get_db()
    products = db.execute("SELECT id,name FROM products ORDER BY name").fetchall()
    if request.method == "POST":
        upload = request.files.get("file")
        if not upload or not upload.filename.lower().endswith(".csv"):
            flash("Please upload a CSV file.", "danger")
            return redirect(url_for("import_reviews"))
        try:
            content = upload.stream.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            required = {"product_name","review_text"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError("CSV must contain product_name and review_text columns.")
            added = 0
            for row in reader:
                name = (row.get("product_name") or "").strip()
                text = (row.get("review_text") or "").strip()
                if not name or not text:
                    continue
                product = db.execute("SELECT id FROM products WHERE lower(name)=lower(?)", (name,)).fetchone()
                if not product:
                    cur = db.execute("INSERT INTO products(name,category,description,created_at) VALUES(?,?,?,?)",
                                     (name,(row.get("category") or "Imported").strip(),"Imported from CSV",datetime.utcnow().isoformat()))
                    product_id = cur.lastrowid
                else:
                    product_id = product["id"]
                rating = None
                try:
                    if row.get("rating"): rating = int(float(row["rating"]))
                except ValueError:
                    rating = None
                added += int(add_review_record(db, product_id, text, (row.get("source") or "CSV").strip(),
                                               rating, (row.get("reviewer") or "CSV Import").strip(),
                                               (row.get("external_id") or "").strip() or None))
            flash(f"Import completed: {added} new reviews added. Duplicate rows were skipped.", "success")
        except Exception as exc:
            db.rollback()
            flash(f"Import failed: {exc}", "danger")
        return redirect(url_for("import_reviews"))
    return render_template("import_reviews.html", products=products)

@app.route("/api/summary")
def api_summary():
    db = get_db()
    rows = db.execute("SELECT sentiment, COUNT(*) n FROM analyses GROUP BY sentiment").fetchall()
    return jsonify({r["sentiment"]:r["n"] for r in rows})

@app.route("/evaluation")
@admin_required
def evaluation():
    db = get_db()
    rows = db.execute("SELECT sentiment, COUNT(*) n FROM analyses GROUP BY sentiment").fetchall()
    totals = {r["sentiment"]:r["n"] for r in rows}
    count = sum(totals.values())
    return render_template("evaluation.html", totals=totals, count=count)

@app.route("/export/reviews.csv")
@admin_required
def export_reviews():
    db = get_db()
    rows = db.execute("""SELECT p.name product_name,r.source,r.reviewer,r.rating,r.review_text,r.created_at
                         FROM reviews r JOIN products p ON p.id=r.product_id ORDER BY r.created_at DESC""").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["product_name","source","reviewer","rating","review_text","created_at"])
    for row in rows:
        writer.writerow(list(row))
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=customer_reviews.csv"})

@app.route("/health")
def health():
    return jsonify({"status":"ok","service":"Customer Feedback Analyzer"})

@app.errorhandler(413)
def too_large(_):
    flash("File is too large. Maximum upload size is 5 MB.", "danger")
    return redirect(url_for("import_reviews"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=os.environ.get("FLASK_DEBUG")=="1")
