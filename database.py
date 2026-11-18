import sqlite3, os
from flask import current_app, g
from datetime import datetime, timedelta

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT DEFAULT '',
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reviews(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            source TEXT NOT NULL DEFAULT 'Manual',
            external_id TEXT,
            reviewer TEXT DEFAULT 'Anonymous',
            rating INTEGER,
            review_text TEXT NOT NULL,
            clean_text TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analyses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
            aspect TEXT NOT NULL,
            sentiment TEXT NOT NULL CHECK(sentiment IN ('positive','negative','neutral')),
            confidence REAL NOT NULL DEFAULT 0.5,
            method TEXT NOT NULL DEFAULT 'rule-based'
        );
        CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);
        CREATE INDEX IF NOT EXISTS idx_analyses_review ON analyses(review_id);
        """)
        db.commit()

def seed_demo_data():
    from analyzer import analyze_review, clean_text
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] > 0:
        return
    now = datetime.utcnow()
    products = [
        ("Nova X Smartphone","Electronics","Demo product for review analysis."),
        ("Breeze Wireless Headphones","Electronics","Demo product for review analysis."),
        ("HomeChef Blender","Home Appliances","Demo product for review analysis.")
    ]
    ids = []
    for p in products:
        cur = db.execute("INSERT INTO products(name,category,description,created_at) VALUES(?,?,?,?)",
                         (*p,now.isoformat()))
        ids.append(cur.lastrowid)
    samples = [
        (ids[0],"Amazon","Ada",5,"The battery life is excellent and the screen quality is beautiful, but delivery was slow."),
        (ids[0],"Trustpilot","John",2,"Poor camera quality and terrible customer service. The price is too high."),
        (ids[0],"Amazon","Musa",4,"Great product quality, good packaging and fast delivery."),
        (ids[0],"Trustpilot","Grace",3,"The phone works as expected. The packaging was okay."),
        (ids[1],"Amazon","Tunde",5,"Amazing sound quality and comfortable design. Worth the price."),
        (ids[1],"Trustpilot","Mary",2,"Battery drains quickly and customer support was unhelpful."),
        (ids[1],"Amazon","Peter",4,"Good sound, but the delivery took too long."),
        (ids[2],"Amazon","Chi",5,"Excellent build quality, easy to use and well packaged."),
        (ids[2],"Trustpilot","Sam",2,"The blender is noisy, poor quality and the price is expensive.")
    ]
    for pid,source,reviewer,rating,text in samples:
        cur = db.execute("""INSERT INTO reviews(product_id,source,reviewer,rating,review_text,clean_text,created_at)
                            VALUES(?,?,?,?,?,?,?)""",
                         (pid,source,reviewer,rating,text,clean_text(text),(now-timedelta(days=len(samples))).isoformat()))
        for a in analyze_review(text):
            db.execute("INSERT INTO analyses(review_id,aspect,sentiment,confidence,method) VALUES(?,?,?,?,?)",
                       (cur.lastrowid,a["aspect"],a["sentiment"],a["confidence"],a["method"]))
    db.commit()
