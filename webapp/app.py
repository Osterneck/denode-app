import os
import sys
import json
import stripe
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from datetime import datetime, date
from decimal import Decimal
import sqlite3
from functools import wraps

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.schema_extractor import extract_schema
from db.query_log_analyzer import parse_query_logs, analyze_query_patterns
from engine.heuristics import recommend_changes
from engine.plan_generator import generate_sql
from engine.benchmark import PerformanceBenchmark
from storage.metadata_store import MetadataStore

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("denode-webapp")

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "denode-dev-key-change-in-prod")

# Stripe
stripe.api_key              = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY      = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_PRICE_ID             = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET       = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access DEnode."
login_manager.login_message_category = "warning"

METADATA_BASE = os.environ.get("METADATA_PATH", "./metadata")
USERS_DB_PATH = os.path.join(METADATA_BASE, "users.db")

def get_users_db():
    os.makedirs(METADATA_BASE, exist_ok=True)
    conn = sqlite3.connect(USERS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_users_db():
    conn = get_users_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            email                  TEXT    UNIQUE NOT NULL,
            password               TEXT    NOT NULL,
            plan                   TEXT    NOT NULL DEFAULT 'free',
            stripe_customer_id     TEXT,
            stripe_subscription_id TEXT,
            schema_count           INTEGER NOT NULL DEFAULT 0,
            created_at             TEXT    NOT NULL
        );
    ''')
    conn.commit()
    conn.close()

init_users_db()

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, list, dict)):
            return list(obj)
        return super().default(obj)

app.json_encoder = CustomJSONEncoder


# ── User model ────────────────────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, id, email, plan, schema_count,
                 stripe_customer_id=None, stripe_subscription_id=None):
        self.id                    = id
        self.email                 = email
        self.plan                  = plan
        self.schema_count          = schema_count
        self.stripe_customer_id    = stripe_customer_id
        self.stripe_subscription_id = stripe_subscription_id

    @property
    def is_pro(self):
        return self.plan == "pro"

    @property
    def can_add_schema(self):
        return self.is_pro or self.schema_count < 1

    @staticmethod
    def get(user_id):
        conn = get_users_db()
        row  = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if row:
            return User(row["id"], row["email"], row["plan"], row["schema_count"],
                        row["stripe_customer_id"], row["stripe_subscription_id"])
        return None

    @staticmethod
    def get_by_email(email):
        conn = get_users_db()
        row  = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if row:
            return User(row["id"], row["email"], row["plan"], row["schema_count"],
                        row["stripe_customer_id"], row["stripe_subscription_id"])
        return None


@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))


def get_store():
    user_path = os.path.join(METADATA_BASE, f"user_{current_user.id}")
    return MetadataStore(base_path=user_path)


def pro_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        if not current_user.is_pro:
            flash("This feature requires a Pro plan.", "warning")
            return redirect(url_for("pricing"))
        return f(*args, **kwargs)
    return decorated


# ═════════════════════════════════════════════════════════════════════════════
# AUTH
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")
        if not email or not password:
            error = "Email and password are required."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif User.get_by_email(email):
            error = "An account with that email already exists."
        else:
            conn = get_users_db()
            conn.execute(
                "INSERT INTO users (email, password, plan, schema_count, created_at) VALUES (?,?,?,?,?)",
                (email, generate_password_hash(password), "free", 0, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            user = User.get_by_email(email)
            login_user(user)
            flash("Welcome to DEnode! You're on the Free plan — 1 schema analysis included.", "success")
            return redirect(url_for("index"))
    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_users_db()
        row  = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if row and check_password_hash(row["password"], password):
            user = User(row["id"], row["email"], row["plan"], row["schema_count"],
                        row["stripe_customer_id"], row["stripe_subscription_id"])
            login_user(user)
            return redirect(request.args.get("next") or url_for("index"))
        error = "Invalid email or password."
    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("login"))


# ═════════════════════════════════════════════════════════════════════════════
# PRICING & STRIPE
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/pricing")
def pricing():
    return render_template("pricing.html",
                           stripe_publishable_key=STRIPE_PUBLISHABLE_KEY,
                           stripe_price_id=STRIPE_PRICE_ID)


@app.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    try:
        conn        = get_users_db()
        row         = conn.execute("SELECT stripe_customer_id FROM users WHERE id = ?",
                                   (current_user.id,)).fetchone()
        customer_id = row["stripe_customer_id"] if row else None
        conn.close()

        if not customer_id:
            customer    = stripe.Customer.create(email=current_user.email,
                                                 metadata={"user_id": current_user.id})
            customer_id = customer.id
            conn = get_users_db()
            conn.execute("UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                         (customer_id, current_user.id))
            conn.commit()
            conn.close()

        checkout = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=url_for("payment_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("pricing", _external=True),
        )
        return redirect(checkout.url, code=303)
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        flash("Payment error — please try again or contact support.", "danger")
        return redirect(url_for("pricing"))


@app.route("/payment-success")
@login_required
def payment_success():
    flash("Welcome to DEnode Pro! Unlimited schema analyses are now unlocked.", "success")
    return redirect(url_for("index"))


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload    = request.data
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 400

    if event["type"] == "checkout.session.completed":
        sess    = event["data"]["object"]
        cust_id = sess.get("customer")
        sub_id  = sess.get("subscription")
        conn = get_users_db()
        conn.execute("UPDATE users SET plan='pro', stripe_subscription_id=? WHERE stripe_customer_id=?",
                     (sub_id, cust_id))
        conn.commit()
        conn.close()

    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        sub     = event["data"]["object"]
        cust_id = sub.get("customer")
        conn = get_users_db()
        conn.execute("UPDATE users SET plan='free' WHERE stripe_customer_id=?", (cust_id,))
        conn.commit()
        conn.close()

    return jsonify({"status": "ok"})


@app.route("/manage-billing")
@login_required
def manage_billing():
    if not current_user.stripe_customer_id:
        flash("No billing account found.", "warning")
        return redirect(url_for("pricing"))
    portal = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=url_for("index", _external=True)
    )
    return redirect(portal.url)


# ═════════════════════════════════════════════════════════════════════════════
# CORE APP ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/")
@login_required
def index():
    databases = get_store().list_databases()
    return render_template("index.html", databases=databases)


@app.route("/extract", methods=["GET", "POST"])
@login_required
def extract():
    result  = None
    error   = None
    db_type = None

    if request.method == "POST":
        if not current_user.can_add_schema:
            flash("Free plan limit reached (1 schema). Upgrade to Pro for unlimited analyses.", "warning")
            return redirect(url_for("pricing"))
        try:
            db_url  = request.form.get("db_url")
            db_name = request.form.get("db_name")
            if not db_url:
                error = "Database URL is required."
            elif not db_name:
                error = "Database name identifier is required."
            else:
                from db.schema_extractor import detect_database_type
                db_type = detect_database_type(db_url)
                result  = extract_schema(db_url)
                store   = get_store()
                if store.save_schema(result, db_name):
                    conn = get_users_db()
                    conn.execute("UPDATE users SET schema_count = schema_count + 1 WHERE id = ?",
                                 (current_user.id,))
                    conn.commit()
                    conn.close()
                    flash(f"Schema extracted and saved for '{db_name}'.", "success")
                    session["current_db"] = db_name
                    session["db_type"]    = db_type
                    return redirect(url_for("analyze", db_name=db_name))
        except Exception as e:
            logger.error(f"Schema extraction error: {e}")
            error = f"Error extracting schema: {e}"

    return render_template("extract.html", result=result, error=error, db_type=db_type)


@app.route("/analyze", methods=["GET", "POST"])
@app.route("/analyze/<path:db_name>", methods=["GET", "POST"])
@login_required
def analyze(db_name=None):
    result        = None
    error         = None
    db_name       = request.args.get("db_name", session.get("current_db"))
    store         = get_store()
    schema        = None
    schema_loaded = False

    if db_name:
        schema = store.load_latest_schema(db_name)
        if schema:
            schema_loaded = True

    if request.method == "POST":
        try:
            use_sample = request.form.get("use_sample_log") == "yes"
            db_name    = request.form.get("db_name", db_name)
            if not db_name:
                error = "Database name identifier is required."
            elif use_sample:
                result = parse_query_logs("./data/query_log_sample.sql")
                if schema:
                    result["advanced_analysis"] = analyze_query_patterns(result, schema)
                if store.save_query_analysis(result, db_name):
                    flash(f"Query analysis completed for '{db_name}'.", "success")
                    session["current_db"] = db_name
                    return redirect(url_for("recommendations", db_name=db_name))
            else:
                if "log_file" not in request.files:
                    error = "No log file uploaded."
                else:
                    log_file = request.files["log_file"]
                    if not log_file.filename:
                        error = "No log file selected."
                    else:
                        log_path = f"/tmp/{log_file.filename}"
                        log_file.save(log_path)
                        result = parse_query_logs(log_path)
                        if schema:
                            result["advanced_analysis"] = analyze_query_patterns(result, schema)
                        if store.save_query_analysis(result, db_name):
                            flash(f"Query analysis saved for '{db_name}'.", "success")
                            session["current_db"] = db_name
                            return redirect(url_for("recommendations", db_name=db_name))
                        os.remove(log_path)
        except Exception as e:
            logger.error(f"Analyze error: {e}")
            error = f"Error analyzing queries: {e}"

    return render_template("analyze.html", db_name=db_name, schema_loaded=schema_loaded,
                           result=result, error=error, db_type=session.get("db_type"))


@app.route("/recommendations", methods=["GET", "POST"])
@app.route("/recommendations/<path:db_name>", methods=["GET", "POST"])
@login_required
def recommendations(db_name=None):
    db_name = request.args.get("db_name", session.get("current_db"))
    store   = get_store()
    schema  = recs = query_analysis = None
    error   = None

    if db_name:
        schema         = store.load_latest_schema(db_name)
        query_analysis = store.load_latest_query_analysis(db_name)
        recs           = store.load_latest_recommendations(db_name)

    if request.method == "POST":
        try:
            if not schema:
                error = "No schema available. Please extract the schema first."
            elif not query_analysis:
                error = "No query analysis available. Please analyze query logs first."
            else:
                recs = recommend_changes(schema, query_analysis)
                if store.save_recommendations(recs, db_name):
                    flash(f"Generated {len(recs)} recommendations for '{db_name}'.", "success")
        except Exception as e:
            logger.error(f"Recommendations error: {e}")
            error = f"Error generating recommendations: {e}"

    if recs:
        session["current_recommendations"] = recs

    return render_template("recommendations.html", db_name=db_name,
                           recommendations=recs, error=error)


@app.route("/generate_sql/<path:db_name>/<table>/<action>")
@login_required
def generate_sql_page(db_name, table, action):
    try:
        from urllib.parse import unquote
        name  = unquote(db_name)
        store = get_store()
        schema = store.load_latest_schema(name)
        if not schema:
            return render_template("error.html", error=f"Schema not found for '{name}'",
                                   title="Schema Not Found", db_name=name)
        recs = session.get("current_recommendations") or store.load_latest_recommendations(name)
        if not recs:
            return render_template("error.html", error="Recommendations not found.",
                                   title="Recommendations Not Found", db_name=name)
        rec = next((r for r in recs if r["table"] == table and r["action"] == action), None)
        if not rec:
            return render_template("error.html",
                                   error=f"No recommendation for table '{table}' / action '{action}'.",
                                   title="Recommendation Not Found", db_name=name)
        return render_template("sql_plan.html", db_name=name, plan=generate_sql(rec, schema))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/benchmark", methods=["GET", "POST"])
@login_required
def benchmark():
    result  = None
    error   = None
    db_name = request.args.get("db_name", session.get("current_db"))
    mode    = request.args.get("mode", "quick")
    db_url  = os.environ.get("DATABASE_URL", "")
    query   = "SELECT 1"

    if request.method == "POST":
        try:
            db_url = request.form.get("db_url")
            mode   = request.args.get("mode", "quick")
            if not db_url:
                error = "Database connection URL is required."
            else:
                b = PerformanceBenchmark(db_url)
                if mode == "quick":
                    query  = request.form.get("query", "SELECT 1")
                    result = b.time_query(query,
                                          iterations=int(request.form.get("iterations", 5)),
                                          warmup=int(request.form.get("warmup", 1)))
                elif mode == "compare":
                    q1 = request.form.get("query1", "SELECT 1")
                    q2 = request.form.get("query2", "SELECT 1")
                    itr = int(request.form.get("iterations", 3))
                    r1 = b.time_query(q1, iterations=itr)
                    r2 = b.time_query(q2, iterations=itr)
                    result = {"before": r1, "after": r2,
                              "percent_improvement": (r1["avg"] - r2["avg"]) / r1["avg"] * 100,
                              "absolute_improvement_ms": r1["avg"] - r2["avg"]}
                    query = q1
                elif mode == "throughput":
                    query  = request.form.get("query", "SELECT 1")
                    result = b.run_throughput_test(query,
                                                   duration=int(request.form.get("duration", 5)),
                                                   concurrent_clients=int(request.form.get("clients", 5)))
                flash("Benchmark completed.", "success")
        except Exception as e:
            logger.error(f"Benchmark error: {e}")
            error = f"Error running benchmark: {e}"

    return render_template("benchmark.html", db_name=db_name, db_url=db_url,
                           query=query, mode=mode, result=result, error=error)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/schemas/<path:db_name>")
@login_required
def api_get_schema(db_name):
    try:
        from urllib.parse import unquote
        s = get_store().load_latest_schema(unquote(db_name))
        return jsonify(s) if s else (jsonify({"error": "Schema not found"}), 404)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/analysis/<path:db_name>")
@login_required
def api_get_analysis(db_name):
    try:
        from urllib.parse import unquote
        a = get_store().load_latest_query_analysis(unquote(db_name))
        return jsonify(a) if a else (jsonify({"error": "Analysis not found"}), 404)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/recommendations/<path:db_name>")
@login_required
def api_get_recommendations(db_name):
    try:
        from urllib.parse import unquote
        r = get_store().load_latest_recommendations(unquote(db_name))
        return jsonify(r) if r else (jsonify({"error": "Recommendations not found"}), 404)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sql_plan", methods=["POST"])
@login_required
def api_generate_sql():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        db_name, table, action = data.get("db_name"), data.get("table"), data.get("action")
        if not all([db_name, table, action]):
            return jsonify({"error": "Missing required parameters"}), 400
        store  = get_store()
        schema = store.load_latest_schema(db_name)
        recs   = store.load_latest_recommendations(db_name)
        if not schema:
            return jsonify({"error": "Schema not found"}), 404
        if not recs:
            return jsonify({"error": "Recommendations not found"}), 404
        rec = next((r for r in recs if r["table"] == table and r["action"] == action), None)
        if not rec:
            return jsonify({"error": "Recommendation not found"}), 404
        return jsonify(generate_sql(rec, schema))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
