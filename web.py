import subprocess
import threading
import json
import sqlite3
import os
import hashlib
import random
import string
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# ── Ports ──────────────────────────────────────────────────────────────────────
PHP_PORT = 8080
API_PORT = 9000

# ── Database Setup ─────────────────────────────────────────────────────────────
DB_PATH = "restaurant.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Menu Categories
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        name_ar TEXT,
        icon TEXT,
        color TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    # Menu Items
    c.execute('''CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT NOT NULL,
        name_ar TEXT,
        description TEXT,
        price REAL NOT NULL,
        cost REAL DEFAULT 0,
        image_url TEXT,
        is_available INTEGER DEFAULT 1,
        calories INTEGER,
        prep_time INTEGER DEFAULT 15,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(category_id) REFERENCES categories(id)
    )''')

    # Inventory
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        name_ar TEXT,
        quantity REAL DEFAULT 0,
        unit TEXT DEFAULT 'kg',
        min_quantity REAL DEFAULT 5,
        cost_per_unit REAL DEFAULT 0,
        supplier TEXT,
        last_updated TEXT DEFAULT (datetime('now'))
    )''')

    # Employees
    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT,
        phone TEXT,
        email TEXT,
        salary REAL DEFAULT 0,
        shift TEXT DEFAULT 'morning',
        hire_date TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    # Customers
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE,
        email TEXT,
        points INTEGER DEFAULT 0,
        total_spent REAL DEFAULT 0,
        visit_count INTEGER DEFAULT 0,
        tier TEXT DEFAULT 'bronze',
        birthday TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    # Orders
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        employee_id INTEGER,
        table_number TEXT,
        subtotal REAL DEFAULT 0,
        discount_amount REAL DEFAULT 0,
        discount_code TEXT,
        points_used INTEGER DEFAULT 0,
        points_earned INTEGER DEFAULT 0,
        total REAL DEFAULT 0,
        status TEXT DEFAULT 'pending',
        order_type TEXT DEFAULT 'dine-in',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(employee_id) REFERENCES employees(id)
    )''')

    # Order Items
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        menu_item_id INTEGER,
        quantity INTEGER DEFAULT 1,
        unit_price REAL,
        notes TEXT,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(menu_item_id) REFERENCES menu_items(id)
    )''')

    # Discount Codes
    c.execute('''CREATE TABLE IF NOT EXISTS discount_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        type TEXT DEFAULT 'percentage',
        value REAL NOT NULL,
        min_order REAL DEFAULT 0,
        max_uses INTEGER DEFAULT 100,
        used_count INTEGER DEFAULT 0,
        valid_from TEXT,
        valid_until TEXT,
        is_active INTEGER DEFAULT 1,
        description TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    # Promotions
    c.execute('''CREATE TABLE IF NOT EXISTS promotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        title_ar TEXT,
        description TEXT,
        type TEXT DEFAULT 'discount',
        value REAL DEFAULT 0,
        conditions TEXT,
        valid_from TEXT,
        valid_until TEXT,
        is_active INTEGER DEFAULT 1,
        image_url TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    # Points Transactions
    c.execute('''CREATE TABLE IF NOT EXISTS points_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        order_id INTEGER,
        points INTEGER,
        type TEXT DEFAULT 'earn',
        description TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )''')

    # Seed demo data
    seed_demo_data(c)
    conn.commit()
    conn.close()

def seed_demo_data(c):
    # Check if already seeded
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] > 0:
        return

    # Categories
    cats = [
        (1, "Burgers", "برغر", "🍔", "#FF6B35"),
        (2, "Pizza", "بيتزا", "🍕", "#E74C3C"),
        (3, "Salads", "سلطات", "🥗", "#27AE60"),
        (4, "Drinks", "مشروبات", "🥤", "#3498DB"),
        (5, "Desserts", "حلويات", "🍰", "#9B59B6"),
        (6, "Sandwiches", "سندويشات", "🥪", "#F39C12"),
    ]
    c.executemany("INSERT INTO categories (id,name,name_ar,icon,color) VALUES (?,?,?,?,?)", cats)

    # Menu Items
    items = [
        (1, "Classic Burger", "برغر كلاسيك", "Juicy beef patty with fresh toppings", 35.0, 12.0, 1),
        (2, "Double Smash", "دبل سماش", "Double beef smash burger", 55.0, 18.0, 1),
        (3, "Crispy Chicken Burger", "برغر دجاج كريسبي", "Crispy fried chicken burger", 40.0, 13.0, 1),
        (4, "Margherita Pizza", "بيتزا مارغريتا", "Classic tomato and mozzarella", 45.0, 15.0, 2),
        (5, "BBQ Chicken Pizza", "بيتزا دجاج باربيكيو", "Smoky BBQ chicken pizza", 60.0, 20.0, 2),
        (6, "Caesar Salad", "سلطة سيزر", "Romaine lettuce with caesar dressing", 30.0, 8.0, 3),
        (7, "Pepsi", "بيبسي", "330ml cold Pepsi", 10.0, 3.0, 4),
        (8, "Fresh Lemonade", "ليمون عصير طازج", "Fresh squeezed lemonade", 18.0, 5.0, 4),
        (9, "Chocolate Cake", "كيك شوكولاتة", "Rich chocolate layer cake", 25.0, 7.0, 5),
        (10, "Club Sandwich", "كلوب سندويش", "Triple decker club sandwich", 38.0, 12.0, 6),
    ]
    for it in items:
        c.execute("INSERT INTO menu_items (id,name,name_ar,description,price,cost,category_id) VALUES (?,?,?,?,?,?,?)", it)

    # Inventory
    inv = [
        ("Beef Patties", "باتيز لحم", 50, "kg", 5, 45.0, "Al Ain Farms"),
        ("Chicken Breast", "صدر دجاج", 30, "kg", 5, 28.0, "Al Ain Farms"),
        ("Burger Buns", "خبز برغر", 200, "pieces", 50, 1.5, "Local Bakery"),
        ("Mozzarella Cheese", "جبن موزاريلا", 15, "kg", 3, 60.0, "Dairy Co"),
        ("Tomatoes", "طماطم", 20, "kg", 5, 8.0, "Fresh Market"),
        ("Lettuce", "خس", 10, "kg", 3, 12.0, "Fresh Market"),
        ("Pepsi Cans", "علب بيبسي", 150, "pieces", 30, 3.5, "Pepsi Distributor"),
        ("Flour", "طحين", 25, "kg", 10, 3.0, "Flour Mill"),
        ("Olive Oil", "زيت زيتون", 8, "liters", 2, 35.0, "Import Co"),
        ("Sugar", "سكر", 15, "kg", 5, 4.0, "Local Supplier"),
    ]
    for i in inv:
        c.execute("INSERT INTO inventory (name,name_ar,quantity,unit,min_quantity,cost_per_unit,supplier) VALUES (?,?,?,?,?,?,?)", i)

    # Employees
    emps = [
        ("Ahmed Al Rashid", "Manager", "0501234567", "ahmed@restaurant.com", 8000, "morning"),
        ("Sara Mohammed", "Cashier", "0502345678", "sara@restaurant.com", 4500, "morning"),
        ("Khalid Hassan", "Chef", "0503456789", "khalid@restaurant.com", 6000, "morning"),
        ("Fatima Ali", "Waitress", "0504567890", "fatima@restaurant.com", 3500, "evening"),
        ("Omar Saeed", "Delivery", "0505678901", "omar@restaurant.com", 4000, "evening"),
    ]
    for e in emps:
        c.execute("INSERT INTO employees (name,role,phone,email,salary,shift,hire_date) VALUES (?,?,?,?,?,?,date('now','-'||abs(random()%730)||' days'))", e)

    # Customers
    custs = [
        ("Mohammed Al Farsi", "0511111111", "m.farsi@email.com", 1250, 2500.0, 45, "gold"),
        ("Layla Ibrahim", "0522222222", "layla@email.com", 340, 680.0, 12, "silver"),
        ("Abdullah Nasser", "0533333333", "abd@email.com", 80, 160.0, 3, "bronze"),
        ("Nour Hassan", "0544444444", "nour@email.com", 2100, 4200.0, 78, "platinum"),
        ("Tariq Mansoor", "0555555555", "tariq@email.com", 560, 1120.0, 20, "silver"),
    ]
    for cu in custs:
        c.execute("INSERT INTO customers (name,phone,email,points,total_spent,visit_count,tier) VALUES (?,?,?,?,?,?,?)", cu)

    # Discount Codes
    codes = [
        ("WELCOME20", "percentage", 20, 0, 1000, 45, "2024-01-01", "2025-12-31", "Welcome discount 20%"),
        ("FLAT50", "fixed", 50, 200, 500, 123, "2024-01-01", "2025-12-31", "50 AED off on 200+"),
        ("VIP30", "percentage", 30, 300, 200, 89, "2024-01-01", "2025-12-31", "VIP 30% discount"),
        ("SUMMER15", "percentage", 15, 0, 300, 201, "2025-06-01", "2025-09-30", "Summer special 15%"),
    ]
    for co in codes:
        c.execute("INSERT INTO discount_codes (code,type,value,min_order,max_uses,used_count,valid_from,valid_until,description) VALUES (?,?,?,?,?,?,?,?,?)", co)

    # Promotions
    promos = [
        ("Happy Hour", "ساعة سعيدة", "20% off all drinks 3-5 PM", "percentage", 20, "daily 15:00-17:00", "2025-01-01", "2025-12-31"),
        ("Buy 2 Get 1", "اشتري 2 واحصل على 1", "Buy 2 burgers get 1 free", "bogo", 0, "burgers", "2025-01-01", "2025-12-31"),
        ("Loyalty Double Points", "نقاط مضاعفة", "Earn double points on weekends", "points", 2, "weekends", "2025-01-01", "2025-12-31"),
    ]
    for p in promos:
        c.execute("INSERT INTO promotions (title,title_ar,description,type,value,conditions,valid_from,valid_until) VALUES (?,?,?,?,?,?,?,?)", p)

    # Sample orders
    for i in range(20):
        customer_id = random.randint(1, 5)
        subtotal = round(random.uniform(50, 300), 2)
        discount = round(subtotal * random.uniform(0, 0.2), 2)
        total = subtotal - discount
        points_earned = int(total)
        days_ago = random.randint(0, 30)
        status = random.choice(["completed", "completed", "completed", "pending", "cancelled"])
        c.execute("""INSERT INTO orders (customer_id,employee_id,table_number,subtotal,discount_amount,total,
                     points_earned,status,order_type,created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,datetime('now','-'||?||' days'))""",
                  (customer_id, random.randint(1,5), str(random.randint(1,20)),
                   subtotal, discount, total, points_earned, status,
                   random.choice(["dine-in","takeaway","delivery"]), days_ago))


# ── API Handler ────────────────────────────────────────────────────────────────
class RestaurantHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[API] {format % args}")

    def send_json(self, status: int, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length))
        except:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        conn = get_db()
        c = conn.cursor()

        try:
            # ── Dashboard Stats ────────────────────────────────────────────────
            if path == "/api/dashboard":
                today = datetime.now().strftime("%Y-%m-%d")
                month = datetime.now().strftime("%Y-%m")

                c.execute("SELECT COUNT(*), SUM(total), SUM(discount_amount) FROM orders WHERE status='completed' AND date(created_at)=?", (today,))
                day_row = c.fetchone()
                c.execute("SELECT COUNT(*), SUM(total) FROM orders WHERE status='completed' AND strftime('%Y-%m',created_at)=?", (month,))
                month_row = c.fetchone()
                c.execute("SELECT COUNT(*) FROM customers")
                total_customers = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM menu_items WHERE is_available=1")
                active_items = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM inventory WHERE quantity <= min_quantity")
                low_stock = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
                pending_orders = c.fetchone()[0]

                # Revenue last 7 days
                c.execute("""SELECT date(created_at) as day, SUM(total) as revenue, COUNT(*) as orders
                             FROM orders WHERE status='completed' AND created_at >= date('now','-7 days')
                             GROUP BY day ORDER BY day""")
                weekly = [dict(r) for r in c.fetchall()]

                # Top items
                c.execute("""SELECT mi.name, mi.name_ar, SUM(oi.quantity) as sold, SUM(oi.quantity * oi.unit_price) as revenue
                             FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                             JOIN orders o ON oi.order_id=o.id WHERE o.status='completed'
                             GROUP BY mi.id ORDER BY sold DESC LIMIT 5""")
                top_items = [dict(r) for r in c.fetchall()]

                self.send_json(200, {
                    "today_orders": day_row[0] or 0,
                    "today_revenue": round(day_row[1] or 0, 2),
                    "today_discount": round(day_row[2] or 0, 2),
                    "month_orders": month_row[0] or 0,
                    "month_revenue": round(month_row[1] or 0, 2),
                    "total_customers": total_customers,
                    "active_menu_items": active_items,
                    "low_stock_count": low_stock,
                    "pending_orders": pending_orders,
                    "weekly_revenue": weekly,
                    "top_items": top_items,
                })
                return

            # ── Menu ───────────────────────────────────────────────────────────
            elif path == "/api/menu":
                cat_id = params.get("category", [None])[0]
                if cat_id:
                    c.execute("SELECT * FROM menu_items WHERE category_id=? ORDER BY name", (cat_id,))
                else:
                    c.execute("SELECT mi.*, cat.name as category_name, cat.icon as category_icon FROM menu_items mi LEFT JOIN categories cat ON mi.category_id=cat.id ORDER BY cat.name, mi.name")
                self.send_json(200, [dict(r) for r in c.fetchall()])

            elif path == "/api/categories":
                c.execute("SELECT cat.*, COUNT(mi.id) as item_count FROM categories cat LEFT JOIN menu_items mi ON cat.id=mi.category_id GROUP BY cat.id")
                self.send_json(200, [dict(r) for r in c.fetchall()])

            # ── Inventory ──────────────────────────────────────────────────────
            elif path == "/api/inventory":
                c.execute("SELECT * FROM inventory ORDER BY name")
                items = [dict(r) for r in c.fetchall()]
                for it in items:
                    it["status"] = "critical" if it["quantity"] <= it["min_quantity"] * 0.5 else \
                                   "low" if it["quantity"] <= it["min_quantity"] else "ok"
                self.send_json(200, items)

            # ── Employees ──────────────────────────────────────────────────────
            elif path == "/api/employees":
                c.execute("SELECT * FROM employees WHERE is_active=1 ORDER BY name")
                self.send_json(200, [dict(r) for r in c.fetchall()])

            # ── Customers ──────────────────────────────────────────────────────
            elif path == "/api/customers":
                search = params.get("search", [""])[0]
                if search:
                    c.execute("SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY total_spent DESC",
                              (f"%{search}%", f"%{search}%"))
                else:
                    c.execute("SELECT * FROM customers ORDER BY total_spent DESC")
                self.send_json(200, [dict(r) for r in c.fetchall()])

            elif path.startswith("/api/customers/") and path.count("/") == 3:
                cid = path.split("/")[-1]
                c.execute("SELECT * FROM customers WHERE id=?", (cid,))
                customer = dict(c.fetchone() or {})
                c.execute("SELECT * FROM orders WHERE customer_id=? ORDER BY created_at DESC LIMIT 10", (cid,))
                customer["recent_orders"] = [dict(r) for r in c.fetchall()]
                c.execute("SELECT * FROM points_transactions WHERE customer_id=? ORDER BY created_at DESC LIMIT 20", (cid,))
                customer["points_history"] = [dict(r) for r in c.fetchall()]
                self.send_json(200, customer)

            # ── Orders ─────────────────────────────────────────────────────────
            elif path == "/api/orders":
                status = params.get("status", [None])[0]
                limit = int(params.get("limit", [50])[0])
                if status:
                    c.execute("""SELECT o.*, c.name as customer_name, c.phone as customer_phone
                                 FROM orders o LEFT JOIN customers c ON o.customer_id=c.id
                                 WHERE o.status=? ORDER BY o.created_at DESC LIMIT ?""", (status, limit))
                else:
                    c.execute("""SELECT o.*, c.name as customer_name, c.phone as customer_phone
                                 FROM orders o LEFT JOIN customers c ON o.customer_id=c.id
                                 ORDER BY o.created_at DESC LIMIT ?""", (limit,))
                self.send_json(200, [dict(r) for r in c.fetchall()])

            # ── Discounts ──────────────────────────────────────────────────────
            elif path == "/api/discounts":
                c.execute("SELECT * FROM discount_codes ORDER BY created_at DESC")
                self.send_json(200, [dict(r) for r in c.fetchall()])

            elif path == "/api/discounts/validate":
                code = params.get("code", [""])[0].upper()
                amount = float(params.get("amount", [0])[0])
                c.execute("SELECT * FROM discount_codes WHERE code=? AND is_active=1", (code,))
                dc = c.fetchone()
                if not dc:
                    self.send_json(200, {"valid": False, "message": "Invalid code"})
                elif dc["used_count"] >= dc["max_uses"]:
                    self.send_json(200, {"valid": False, "message": "Code limit reached"})
                elif amount < dc["min_order"]:
                    self.send_json(200, {"valid": False, "message": f"Minimum order {dc['min_order']} AED"})
                else:
                    discount = dc["value"] if dc["type"] == "fixed" else round(amount * dc["value"] / 100, 2)
                    self.send_json(200, {"valid": True, "discount": discount, "type": dc["type"], "value": dc["value"]})

            # ── Promotions ─────────────────────────────────────────────────────
            elif path == "/api/promotions":
                c.execute("SELECT * FROM promotions ORDER BY created_at DESC")
                self.send_json(200, [dict(r) for r in c.fetchall()])

            # ── Marketing ─────────────────────────────────────────────────────
            elif path == "/api/marketing/stats":
                c.execute("SELECT tier, COUNT(*) as count, SUM(total_spent) as revenue FROM customers GROUP BY tier")
                tiers = [dict(r) for r in c.fetchall()]
                c.execute("SELECT SUM(used_count) as total_uses, COUNT(*) as total_codes FROM discount_codes")
                discount_stats = dict(c.fetchone())
                c.execute("""SELECT strftime('%Y-%m',created_at) as month, SUM(total) as revenue, COUNT(*) as orders
                             FROM orders WHERE status='completed' GROUP BY month ORDER BY month DESC LIMIT 12""")
                monthly = [dict(r) for r in c.fetchall()]
                c.execute("""SELECT order_type, COUNT(*) as count, SUM(total) as revenue
                             FROM orders WHERE status='completed' GROUP BY order_type""")
                by_type = [dict(r) for r in c.fetchall()]
                c.execute("SELECT SUM(points) as total_points_issued FROM points_transactions WHERE type='earn'")
                points_issued = c.fetchone()[0] or 0
                c.execute("SELECT SUM(ABS(points)) as total_points_redeemed FROM points_transactions WHERE type='redeem'")
                points_redeemed = c.fetchone()[0] or 0

                self.send_json(200, {
                    "tiers": tiers,
                    "discount_stats": discount_stats,
                    "monthly_revenue": monthly,
                    "orders_by_type": by_type,
                    "points_issued": points_issued,
                    "points_redeemed": points_redeemed,
                })

            else:
                self.send_json(404, {"error": "Endpoint not found"})

        except Exception as e:
            self.send_json(500, {"error": str(e)})
        finally:
            conn.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self.read_body()
        conn = get_db()
        c = conn.cursor()

        try:
            # ── Add Menu Item ──────────────────────────────────────────────────
            if path == "/api/menu":
                c.execute("""INSERT INTO menu_items (category_id,name,name_ar,description,price,cost,calories,prep_time)
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (data.get("category_id"), data["name"], data.get("name_ar"),
                           data.get("description"), data["price"], data.get("cost", 0),
                           data.get("calories"), data.get("prep_time", 15)))
                conn.commit()
                self.send_json(201, {"id": c.lastrowid, "message": "Menu item added"})

            # ── Add Category ───────────────────────────────────────────────────
            elif path == "/api/categories":
                c.execute("INSERT INTO categories (name,name_ar,icon,color) VALUES (?,?,?,?)",
                          (data["name"], data.get("name_ar"), data.get("icon","🍽️"), data.get("color","#666")))
                conn.commit()
                self.send_json(201, {"id": c.lastrowid})

            # ── Add Inventory ──────────────────────────────────────────────────
            elif path == "/api/inventory":
                c.execute("""INSERT INTO inventory (name,name_ar,quantity,unit,min_quantity,cost_per_unit,supplier)
                             VALUES (?,?,?,?,?,?,?)""",
                          (data["name"], data.get("name_ar"), data.get("quantity", 0),
                           data.get("unit", "kg"), data.get("min_quantity", 5),
                           data.get("cost_per_unit", 0), data.get("supplier", "")))
                conn.commit()
                self.send_json(201, {"id": c.lastrowid})

            # ── Add Employee ───────────────────────────────────────────────────
            elif path == "/api/employees":
                c.execute("""INSERT INTO employees (name,role,phone,email,salary,shift,hire_date)
                             VALUES (?,?,?,?,?,?,?)""",
                          (data["name"], data.get("role"), data.get("phone"),
                           data.get("email"), data.get("salary", 0),
                           data.get("shift", "morning"), data.get("hire_date", datetime.now().strftime("%Y-%m-%d"))))
                conn.commit()
                self.send_json(201, {"id": c.lastrowid})

            # ── Add Customer ───────────────────────────────────────────────────
            elif path == "/api/customers":
                c.execute("""INSERT INTO customers (name,phone,email,birthday,notes)
                             VALUES (?,?,?,?,?)""",
                          (data["name"], data.get("phone"), data.get("email"),
                           data.get("birthday"), data.get("notes")))
                conn.commit()
                self.send_json(201, {"id": c.lastrowid})

            # ── Create Order ───────────────────────────────────────────────────
            elif path == "/api/orders":
                c.execute("""INSERT INTO orders (customer_id,employee_id,table_number,subtotal,
                             discount_amount,discount_code,points_used,points_earned,total,order_type,notes)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                          (data.get("customer_id"), data.get("employee_id"), data.get("table_number"),
                           data.get("subtotal", 0), data.get("discount_amount", 0),
                           data.get("discount_code"), data.get("points_used", 0),
                           data.get("points_earned", 0), data.get("total", 0),
                           data.get("order_type", "dine-in"), data.get("notes")))
                order_id = c.lastrowid
                for item in data.get("items", []):
                    c.execute("INSERT INTO order_items (order_id,menu_item_id,quantity,unit_price,notes) VALUES (?,?,?,?,?)",
                              (order_id, item["menu_item_id"], item["quantity"], item["unit_price"], item.get("notes")))
                # Update customer stats
                if data.get("customer_id") and data.get("total"):
                    pts = int(data["total"])
                    c.execute("UPDATE customers SET points=points+?, total_spent=total_spent+?, visit_count=visit_count+1 WHERE id=?",
                              (pts, data["total"], data["customer_id"]))
                    c.execute("INSERT INTO points_transactions (customer_id,order_id,points,type,description) VALUES (?,?,?,'earn','Order #'||?)",
                              (data["customer_id"], order_id, pts, order_id))
                    # Update tier
                    c.execute("SELECT total_spent FROM customers WHERE id=?", (data["customer_id"],))
                    spent = c.fetchone()[0]
                    tier = "bronze" if spent < 500 else "silver" if spent < 2000 else "gold" if spent < 5000 else "platinum"
                    c.execute("UPDATE customers SET tier=? WHERE id=?", (tier, data["customer_id"]))
                conn.commit()
                self.send_json(201, {"id": order_id, "message": "Order created"})

            # ── Add Discount Code ──────────────────────────────────────────────
            elif path == "/api/discounts":
                code = data.get("code", "").upper() or ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                c.execute("""INSERT INTO discount_codes (code,type,value,min_order,max_uses,valid_from,valid_until,description)
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (code, data.get("type","percentage"), data["value"],
                           data.get("min_order", 0), data.get("max_uses", 100),
                           data.get("valid_from"), data.get("valid_until"), data.get("description")))
                conn.commit()
                self.send_json(201, {"id": c.lastrowid, "code": code})

            # ── Add Promotion ──────────────────────────────────────────────────
            elif path == "/api/promotions":
                c.execute("""INSERT INTO promotions (title,title_ar,description,type,value,conditions,valid_from,valid_until)
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (data["title"], data.get("title_ar"), data.get("description"),
                           data.get("type","discount"), data.get("value", 0),
                           data.get("conditions"), data.get("valid_from"), data.get("valid_until")))
                conn.commit()
                self.send_json(201, {"id": c.lastrowid})

            else:
                self.send_json(404, {"error": "Not found"})

        except Exception as e:
            conn.rollback()
            self.send_json(500, {"error": str(e)})
        finally:
            conn.close()

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self.read_body()
        conn = get_db()
        c = conn.cursor()

        try:
            parts = path.split("/")

            if path.startswith("/api/menu/"):
                item_id = parts[-1]
                sets = ", ".join(f"{k}=?" for k in data.keys())
                c.execute(f"UPDATE menu_items SET {sets} WHERE id=?", list(data.values()) + [item_id])
                conn.commit()
                self.send_json(200, {"message": "Updated"})

            elif path.startswith("/api/inventory/"):
                inv_id = parts[-1]
                sets = ", ".join(f"{k}=?" for k in data.keys())
                c.execute(f"UPDATE inventory SET {sets}, last_updated=datetime('now') WHERE id=?",
                          list(data.values()) + [inv_id])
                conn.commit()
                self.send_json(200, {"message": "Updated"})

            elif path.startswith("/api/employees/"):
                emp_id = parts[-1]
                sets = ", ".join(f"{k}=?" for k in data.keys())
                c.execute(f"UPDATE employees SET {sets} WHERE id=?", list(data.values()) + [emp_id])
                conn.commit()
                self.send_json(200, {"message": "Updated"})

            elif path.startswith("/api/orders/") and path.endswith("/status"):
                order_id = parts[-2]
                c.execute("UPDATE orders SET status=? WHERE id=?", (data["status"], order_id))
                conn.commit()
                self.send_json(200, {"message": "Status updated"})

            elif path.startswith("/api/customers/"):
                cid = parts[-1]
                sets = ", ".join(f"{k}=?" for k in data.keys())
                c.execute(f"UPDATE customers SET {sets} WHERE id=?", list(data.values()) + [cid])
                conn.commit()
                self.send_json(200, {"message": "Updated"})

            elif path.startswith("/api/discounts/"):
                did = parts[-1]
                sets = ", ".join(f"{k}=?" for k in data.keys())
                c.execute(f"UPDATE discount_codes SET {sets} WHERE id=?", list(data.values()) + [did])
                conn.commit()
                self.send_json(200, {"message": "Updated"})

            else:
                self.send_json(404, {"error": "Not found"})

        except Exception as e:
            conn.rollback()
            self.send_json(500, {"error": str(e)})
        finally:
            conn.close()

    def do_DELETE(self):
        path = urlparse(self.path).path
        parts = path.split("/")
        conn = get_db()
        c = conn.cursor()
        try:
            if path.startswith("/api/menu/"):
                c.execute("DELETE FROM menu_items WHERE id=?", (parts[-1],))
            elif path.startswith("/api/inventory/"):
                c.execute("DELETE FROM inventory WHERE id=?", (parts[-1],))
            elif path.startswith("/api/employees/"):
                c.execute("UPDATE employees SET is_active=0 WHERE id=?", (parts[-1],))
            elif path.startswith("/api/discounts/"):
                c.execute("DELETE FROM discount_codes WHERE id=?", (parts[-1],))
            elif path.startswith("/api/promotions/"):
                c.execute("DELETE FROM promotions WHERE id=?", (parts[-1],))
            conn.commit()
            self.send_json(200, {"message": "Deleted"})
        except Exception as e:
            self.send_json(500, {"error": str(e)})
        finally:
            conn.close()


# ── Serve static HTML ──────────────────────────────────────────────────────────
class StaticHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            filepath = "index.html"
        else:
            filepath = path.lstrip("/")

        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                content = f.read()
            ctype = "text/html" if filepath.endswith(".html") else \
                    "text/css" if filepath.endswith(".css") else \
                    "application/javascript" if filepath.endswith(".js") else "text/plain"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")


def start_api():
    server = HTTPServer(("0.0.0.0", API_PORT), RestaurantHandler)
    print(f"[API] Restaurant API  → http://localhost:{API_PORT}")
    server.serve_forever()

def start_static():
    server = HTTPServer(("0.0.0.0", PHP_PORT), StaticHandler)
    print(f"[WEB] Frontend        → http://localhost:{PHP_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    print("🍽️  Initializing Restaurant Management System...")
    init_db()
    print("✅  Database ready")

    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    print(f"\n{'='*55}")
    print(f"  🚀 Restaurant Management System is RUNNING")
    print(f"{'='*55}")
    print(f"  🌐 Frontend  → http://localhost:{PHP_PORT}")
    print(f"  📡 API       → http://localhost:{API_PORT}")
    print(f"{'='*55}\n")
    print("Press Ctrl+C to stop.\n")

    start_static()
