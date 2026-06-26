#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    pass
import hashlib
import hmac
import base64
import time
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 8000))
DATABASE_URL = os.environ.get("DATABASE_URL")
USING_POSTGRES = bool(DATABASE_URL)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "erp.db")
SECRET_KEY = b"AM_ERP_SECURE_HMAC_SECRET_KEY_2026_DM"

# =====================================================================
# 1. DATABASE SETUP & INITIAL PRESETS
# =====================================================================
class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
    def execute(self, query, params=()):
        if USING_POSTGRES:
            query = query.replace('?', '%s')
        self.cursor.execute(query, params)
    def fetchall(self):
        return self.cursor.fetchall()
    def fetchone(self):
        return self.cursor.fetchone()
    @property
    def rowcount(self):
        return self.cursor.rowcount

class DBWrapper:
    def __init__(self):
        if USING_POSTGRES:
            self.conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        else:
            self.conn = sqlite3.connect(DB_FILE)
            self.conn.row_factory = sqlite3.Row
    def cursor(self):
        return CursorWrapper(self.conn.cursor())
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()

def get_db():
    return DBWrapper()


def hash_password(password, salt=None):
    if not salt:
        salt = base64.b64encode(os.urandom(16)).decode('utf-8')
    # PBKDF2-HMAC SHA-256 for secure hashing (100,000 iterations)
    pwd_bytes = password.encode('utf-8')
    salt_bytes = salt.encode('utf-8')
    hashed = hashlib.pbkdf2_hmac('sha256', pwd_bytes, salt_bytes, 100000)
    return base64.b64encode(hashed).decode('utf-8'), salt

def init_db():
    if USING_POSTGRES:
        return
    conn = get_db()
    c = conn.cursor()
    
    # Create Tables
    c.execute("""
    CREATE TABLE IF NOT EXISTS tenants (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL, -- 'activo', 'suspendido'
        plan TEXT NOT NULL,   -- 'Basico', 'Gold', 'Premium'
        created_at TEXT NOT NULL
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL,   -- 'admin', 'cajero', 'produccion'
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        allowed_pages TEXT,
        base_salary REAL DEFAULT 0.0,
        FOREIGN KEY(tenant_id) REFERENCES tenants(id),
        UNIQUE(tenant_id, username)
    )
    """)
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN allowed_pages TEXT")
    except Exception:
        pass
        
    try:
        c.execute("ALTER TABLE users ADD COLUMN base_salary REAL DEFAULT 0.0")
    except Exception:
        pass
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS tenant_data (
        tenant_id TEXT PRIMARY KEY,
        json_data TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(tenant_id) REFERENCES tenants(id)
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        username TEXT NOT NULL,
        role TEXT NOT NULL,
        module TEXT NOT NULL,
        action TEXT NOT NULL,
        impact TEXT NOT NULL,
        FOREIGN KEY(tenant_id) REFERENCES tenants(id)
    )
    """)
    
    conn.commit()
    
    # Check if empty to load default companies/users
    c.execute("SELECT COUNT(*) as count FROM tenants")
    if c.fetchone()["count"] == 0:
        print("🌱 Base de datos vacía. Insertando presets de demostración de A&M ERP...")
        
        # 1. Tenants
        tenants_presets = [
            ("MigaMiga", "A&M ERP", "activo", "Premium", "2026-05-27T00:00:00Z"),
            ("DulceTentacion", "Dulce Tentación", "activo", "Gold", "2026-05-27T00:00:00Z"),
            ("SweetHouse", "Sweet House", "suspendido", "Basico", "2026-05-27T00:00:00Z")
        ]
        for tid, name, status, plan, cat in tenants_presets:
            c.execute("INSERT INTO tenants VALUES (?, ?, ?, ?, ?)", (tid, name, status, plan, cat))
            
        # 2. Users
        users_presets = [
            ("MigaMiga", "admin", "admin123", "admin", "Sofía Rodríguez", 50000),
            ("MigaMiga", "cajero", "cajera123", "cajero", "Camila Reyes", 25000),
            ("MigaMiga", "chef", "chef123", "produccion", "Chef de Producción", 35000),
            ("DulceTentacion", "admin", "admin123", "admin", "Admin Dulce", 50000),
            ("SweetHouse", "admin", "admin123", "admin", "Admin Sweet", 50000)
        ]
        for tid, username, password, role, name, base_salary in users_presets:
            p_hash, salt = hash_password(password)
            uid = f"{tid}_{username}_{int(time.time())}"
            
            allowed = []
            if role == "admin":
                allowed = ["dashboard-page", "pos-page", "caja-page", "inventario-page", "recetario-page", "produccion-page", "crm-page", "settings-page", "finanzas-page"]
            elif role == "cajero":
                allowed = ["pos-page", "caja-page", "crm-page"]
            else:
                allowed = ["inventario-page", "recetario-page", "produccion-page"]
                
            c.execute("INSERT INTO users (id, tenant_id, username, password_hash, salt, role, name, created_at, allowed_pages, base_salary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (uid, tid, username, p_hash, salt, role, name, "2026-05-27T00:00:00Z", json.dumps(allowed), base_salary))
            
        # 3. Default Tenant Data for MigaMiga
        default_migamiga_data = {
            "inventory": [
                {"id": "inv_harina", "name": "Harina Blanquita", "category": "Ingredientes", "stock": 5000, "unit": "g", "cost": 0.08, "minStock": 2000},
                {"id": "inv_azucar", "name": "Azúcar Crema", "category": "Ingredientes", "stock": 3000, "unit": "g", "cost": 0.05, "minStock": 1000},
                {"id": "inv_mantequilla", "name": "Mantequilla Rica", "category": "Ingredientes", "stock": 2500, "unit": "g", "cost": 0.45, "minStock": 800},
                {"id": "inv_cacao", "name": "Cacao en Polvo Munné", "category": "Ingredientes", "stock": 1500, "unit": "g", "cost": 0.35, "minStock": 500},
                {"id": "inv_huevos", "name": "Huevos Kikiriki", "category": "Ingredientes", "stock": 60, "unit": "u", "cost": 8.0, "minStock": 24},
                {"id": "inv_leche", "name": "Leche Entera Milex", "category": "Líquidos", "stock": 4000, "unit": "ml", "cost": 0.12, "minStock": 1000},
                {"id": "inv_nutella", "name": "Crema de Nutella", "category": "Ingredientes", "stock": 2000, "unit": "g", "cost": 0.65, "minStock": 500},
                {"id": "inv_caja_brownie", "name": "Caja Kraft Brownie", "category": "Empaques", "stock": 120, "unit": "u", "cost": 15.0, "minStock": 30},
                {"id": "inv_caja_pastel", "name": "Caja Alta para Pastel", "category": "Empaques", "stock": 40, "unit": "u", "cost": 45.0, "minStock": 10}
            ],
            "recipes": [
                {
                    "id": "rec_brownie",
                    "name": "Brownie Premium MigaMiga",
                    "category": "Brownies",
                    "yield": 27,
                    "unit": "u",
                    "laborCost": 150,
                    "overheadCost": 50,
                    "packagingCost": 80,
                    "wastePercent": 5,
                    "targetMargin": 50,
                    "priceSet": 95,
                    "ingredients": [
                        {"id": "inv_harina", "qty": 400, "unit": "g"},
                        {"id": "inv_mantequilla", "qty": 300, "unit": "g"},
                        {"id": "inv_azucar", "qty": 350, "unit": "g"},
                        {"id": "inv_cacao", "qty": 180, "unit": "g"},
                        {"id": "inv_huevos", "qty": 6, "unit": "u"},
                        {"id": "inv_nutella", "qty": 150, "unit": "g"}
                    ],
                    "steps": "Fundir mantequilla con cacao, agregar azúcar, huevos uno a uno, harina tamizada e incorporar Nutella. Hornear a 180C por 25 minutos."
                }
            ],
            "products": [
                {"id": "prod_brownie", "name": "Brownie Premium MigaMiga", "category": "Reposteria", "stock": 27, "price": 95, "cost": 45.5, "recipeId": "rec_brownie"}
            ],
            "sales": [],
            "caja": {
                "active": None,
                "history": []
            },
            "clients": [
                {"id": "cli_pedro", "name": "Pedro Martínez", "phone": "8095551234", "debt": 0, "limit": 5000, "rank": "Bronce"},
                {"id": "cli_maria", "name": "María Almonte", "phone": "8294445678", "debt": 1200, "limit": 8000, "rank": "Plata"},
                {"id": "cli_sofia", "name": "Sofía Guerrero", "phone": "8492223333", "debt": 0, "limit": 15000, "rank": "Oro"}
            ],
            "orders": []
        }
        c.execute("INSERT INTO tenant_data VALUES (?, ?, ?)",
                  ("MigaMiga", json.dumps(default_migamiga_data), "2026-05-27T00:00:00Z"))
        
        # Default empty structures for others
        empty_structure = {"inventory": [], "recipes": [], "products": [], "sales": [], "caja": {"active": None, "history": []}, "clients": [], "orders": []}
        c.execute("INSERT INTO tenant_data VALUES (?, ?, ?)", ("DulceTentacion", json.dumps(empty_structure), "2026-05-27T00:00:00Z"))
        c.execute("INSERT INTO tenant_data VALUES (?, ?, ?)", ("SweetHouse", json.dumps(empty_structure), "2026-05-27T00:00:00Z"))
        
        conn.commit()
    
    conn.close()

# =====================================================================
# 2. CRYPTOGRAPHIC SESSION SIGNING (HMAC-SHA256 Session Tokens)
# =====================================================================
def sign_token(payload_dict):
    payload_str = json.dumps(payload_dict)
    payload_b64 = base64.urlsafe_b64encode(payload_str.encode()).decode().rstrip("=")
    
    sig = hmac.new(SECRET_KEY, payload_b64.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    
    return f"{payload_b64}.{sig_b64}"

def verify_token(token_str):
    if not token_str or "." not in token_str:
        return None
    try:
        parts = token_str.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts[0], parts[1]
        
        # Verify Signature
        expected_sig = hmac.new(SECRET_KEY, payload_b64.encode(), hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        
        if not hmac.compare_digest(sig_b64.encode(), expected_sig_b64.encode()):
            return None
            
        # Decode and check expiry
        missing_padding = len(payload_b64) % 4
        if missing_padding:
            payload_b64 += "=" * (4 - missing_padding)
        payload_str = base64.urlsafe_b64decode(payload_b64).decode()
        payload = json.loads(payload_str)
        
        if payload.get("exp", 0) < time.time():
            return None # Expired
            
        return payload
    except Exception as e:
        print(f"Error al verificar token: {e}")
        return None

# =====================================================================
# 3. SECURE CUSTOM REQUEST HANDLER
# =====================================================================
class SecureERPRequestHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        try:
            with open(os.path.join(SCRIPT_DIR, "requests.log"), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}\n")
        except Exception:
            pass

    def send_json(self, data, status=200):
        try:
            with open(os.path.join(SCRIPT_DIR, "requests.log"), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Response status={status} - Data: {json.dumps(data)}\n")
        except Exception:
            pass
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.end_headers()

    def get_authorized_user(self):
        auth_header = self.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        token = auth_header.split(" ")[1]
        return verify_token(token)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # --- API ENDPOINTS ---
        if path == "/api/tenant/data":
            user = self.get_authorized_user()
            if not user:
                return self.send_json({"error": "No autorizado. Sesión inválida o expirada."}, 401)
                
            conn = get_db()
            c = conn.cursor()
            # Double check tenant status
            c.execute("SELECT status FROM tenants WHERE id = ?", (user["tenant_id"],))
            t_row = c.fetchone()
            if not t_row or t_row["status"] == "suspendido":
                conn.close()
                return self.send_json({"error": "Empresa suspendida por falta de pago."}, 403)
                
            c.execute("SELECT json_data FROM tenant_data WHERE tenant_id = ?", (user["tenant_id"],))
            data_row = c.fetchone()
            conn.close()
            
            if data_row:
                return self.send_json(json.loads(data_row["json_data"]))
            else:
                return self.send_json({"error": "No se encontraron datos para la empresa."}, 404)
                
        elif path == "/api/audit-logs":
            user = self.get_authorized_user()
            if not user:
                return self.send_json({"error": "No autorizado."}, 401)
                
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT timestamp, username, role, module, action, impact FROM audit_logs WHERE tenant_id = ? ORDER BY id DESC LIMIT 100", (user["tenant_id"],))
            logs = [dict(r) for r in c.fetchall()]
            conn.close()
            return self.send_json(logs)
            
        elif path == "/api/users/list":
            user = self.get_authorized_user()
            if not user:
                return self.send_json({"error": "No autorizado."}, 401)
                
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT username, role, name, allowed_pages, base_salary FROM users WHERE tenant_id = ?", (user["tenant_id"],))
            rows = c.fetchall()
            conn.close()
            
            users_list = []
            for r in rows:
                allowed = []
                if r["allowed_pages"]:
                    try:
                        allowed = json.loads(r["allowed_pages"])
                    except Exception:
                        pass
                else:
                    # Fallback standard roles
                    if r["role"] == "admin":
                        allowed = ["dashboard-page", "pos-page", "caja-page", "inventario-page", "recetario-page", "produccion-page", "crm-page", "settings-page"]
                    elif r["role"] == "cajero":
                        allowed = ["pos-page", "caja-page", "crm-page"]
                    else:
                        allowed = ["inventario-page", "recetario-page", "produccion-page"]
                        
                users_list.append({
                    "username": r["username"],
                    "role": r["role"],
                    "name": r["name"],
                    "status": "Activo",
                    "allowedPages": allowed,
                    "baseSalary": r["base_salary"]
                })
            return self.send_json(users_list)
            
        elif path == "/api/backup/download":
            user = self.get_authorized_user()
            if not user or user["role"] != "admin":
                return self.send_json({"error": "No autorizado. Solo administradores pueden descargar respaldos."}, 401)
                
            try:
                with open(DB_FILE, "rb") as f:
                    db_data = f.read()
                
                self.send_response(200)
                self.send_header("Content-Type", "application/x-sqlite3")
                self.send_header("Content-Disposition", f"attachment; filename=respaldo_erp_{user['tenant_id']}_{time.strftime('%Y%m%d_%H%M%S')}.db")
                self.send_header("Content-Length", str(len(db_data)))
                self.end_headers()
                self.wfile.write(db_data)
                return
            except Exception as e:
                return self.send_json({"error": f"Error al generar respaldo: {e}"}, 500)
            
        elif path == "/api/tenants/list":
            # Public/SaaS tenant list for login dropdown selector
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id, name, status, plan FROM tenants")
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return self.send_json(rows)

        # --- STATIC FILE SERVING ---
        else:
            if path == "/":
                path = "/index.html"
            
            # Sanitize path to prevent Directory Traversal
            normalized_path = os.path.normpath(path.lstrip("/"))
            if normalized_path.startswith("..") or os.path.isabs(normalized_path):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Acceso Prohibido")
                return
                
            local_file_path = os.path.join(SCRIPT_DIR, normalized_path)
            if os.path.exists(local_file_path) and os.path.isfile(local_file_path):
                # Set mime types
                mime_type = "text/html"
                if local_file_path.endswith(".css"):
                    mime_type = "text/css"
                elif local_file_path.endswith(".js"):
                    mime_type = "application/javascript"
                elif local_file_path.endswith(".png"):
                    mime_type = "image/png"
                elif local_file_path.endswith(".jpg") or local_file_path.endswith(".jpeg"):
                    mime_type = "image/jpeg"
                elif local_file_path.endswith(".svg"):
                    mime_type = "image/svg+xml"
                
                try:
                    with open(local_file_path, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("X-Frame-Options", "DENY")
                    self.send_header("Content-Security-Policy", "default-src 'self' https:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: https://images.unsplash.com https://images.pexels.com; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;")
                    self.end_headers()
                    self.wfile.write(content)
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f"Error Interno del Servidor: {e}".encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Archivo No Encontrado")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        try:
            with open(os.path.join(SCRIPT_DIR, "requests.log"), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] POST {path} - Headers: {dict(self.headers)} - Body: {post_data}\n")
        except Exception:
            pass
            
        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            return self.send_json({"error": "Cuerpo de petición JSON inválido."}, 400)
            
        # --- LOGIN ENDPOINT ---
        if path == "/api/auth/login":
            username = body.get("username")
            password = body.get("password")
            
            if not username or not password:
                return self.send_json({"error": "Completa todos los campos obligatorios."}, 400)
                
            conn = get_db()
            c = conn.cursor()
            
            # Find a matching user across all tenants
            c.execute("SELECT * FROM users WHERE username = ?", (username,))
            candidate_users = c.fetchall()
            
            matched_user = None
            for u in candidate_users:
                stored_hash = u["password_hash"]
                stored_salt = u["salt"]
                computed_hash, _ = hash_password(password, stored_salt)
                if computed_hash == stored_hash:
                    matched_user = u
                    break
                    
            if not matched_user:
                # Log failed attempt
                c.execute("INSERT INTO audit_logs (tenant_id, timestamp, username, role, module, action, impact) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          ("global", time.strftime("%Y-%m-%dT%H:%M:%SZ"), username, "Desconocido", "Seguridad", "Intento Fallido de Acceso", "Credenciales incorrectas"))
                conn.commit()
                conn.close()
                return self.send_json({"error": "Credenciales incorrectas. Intento de acceso rechazado."}, 401)
                
            # Check Tenant Status
            tenant_id = matched_user["tenant_id"]
            c.execute("SELECT status, name FROM tenants WHERE id = ?", (tenant_id,))
            t_row = c.fetchone()
            if not t_row:
                conn.close()
                return self.send_json({"error": "La empresa asociada al usuario no existe."}, 404)
                
            if t_row["status"] == "suspendido":
                conn.close()
                return self.send_json({"error": "El acceso a esta empresa está suspendido por falta de pago."}, 403)
                
            # Successful Login - Generate Token expiring in 24 hours
            token_payload = {
                "tenant_id": tenant_id,
                "username": username,
                "role": matched_user["role"],
                "name": matched_user["name"],
                "exp": time.time() + 86400
            }
            token = sign_token(token_payload)
            
            # Log audit success
            c.execute("INSERT INTO audit_logs (tenant_id, timestamp, username, role, module, action, impact) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (tenant_id, time.strftime("%Y-%m-%dT%H:%M:%SZ"), username, matched_user["role"], "Seguridad", "Inicio de Sesión Exitoso", "Acceso concedido al sistema"))
            conn.commit()
            conn.close()
            
            allowed_pages = []
            if matched_user["allowed_pages"]:
                try:
                    allowed_pages = json.loads(matched_user["allowed_pages"])
                except Exception:
                    pass
            else:
                # Fallback standard
                if matched_user["role"] == "admin":
                    allowed_pages = ["dashboard-page", "pos-page", "caja-page", "inventario-page", "recetario-page", "produccion-page", "crm-page", "settings-page"]
                elif matched_user["role"] == "cajero":
                    allowed_pages = ["pos-page", "caja-page", "crm-page"]
                else:
                    allowed_pages = ["inventario-page", "recetario-page", "produccion-page"]
 
            return self.send_json({
                "message": "Autenticación exitosa",
                "token": token,
                "user": {
                    "username": username,
                    "name": matched_user["name"],
                    "role": matched_user["role"],
                    "tenantName": t_row["name"],
                    "allowedPages": allowed_pages
                }
            })
            
        # --- REGISTER TENANT (Superadmin / SaaS Registration) ---
        elif path == "/api/auth/register-tenant":
            user = self.get_authorized_user()
            if not user or user["role"] != "admin":
                return self.send_json({"error": "No autorizado. Solo administradores de plataforma pueden dar de alta inquilinos."}, 401)
                
            tenant_id = body.get("tenant_id")
            name = body.get("name")
            plan = body.get("plan", "Basico")
            admin_username = body.get("admin_username")
            admin_password = body.get("admin_password")
            admin_fullname = body.get("admin_fullname", "Administrador Principal")
            
            if not tenant_id or not name or not admin_username or not admin_password:
                return self.send_json({"error": "Faltan parámetros obligatorios de registro."}, 400)
                
            conn = get_db()
            c = conn.cursor()
            
            # Check if tenant exists
            c.execute("SELECT id FROM tenants WHERE id = ?", (tenant_id,))
            if c.fetchone():
                conn.close()
                return self.send_json({"error": "Este identificador de empresa ya está registrado."}, 409)
                
            try:
                # Insert Tenant
                c.execute("INSERT INTO tenants VALUES (?, ?, ?, ?, ?)",
                          (tenant_id, name, "activo", plan, time.strftime("%Y-%m-%dT%H:%M:%SZ")))
                
                # Insert Admin User
                p_hash, salt = hash_password(admin_password)
                uid = f"{tenant_id}_{admin_username}_{int(time.time())}"
                c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (uid, tenant_id, admin_username, p_hash, salt, "admin", admin_fullname, time.strftime("%Y-%m-%dT%H:%M:%SZ")))
                
                # Initialize Empty Tenant Data structure
                empty_structure = {
                    "inventory": [], "recipes": [], "products": [], "sales": [],
                    "caja": {"active": None, "history": []}, "clients": [], "orders": []
                }
                c.execute("INSERT INTO tenant_data VALUES (?, ?, ?)",
                          (tenant_id, json.dumps(empty_structure), time.strftime("%Y-%m-%dT%H:%M:%SZ")))
                
                # Audit trail
                c.execute("INSERT INTO audit_logs (tenant_id, timestamp, username, role, module, action, impact) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (user["tenant_id"], time.strftime("%Y-%m-%dT%H:%M:%SZ"), user["username"], user["role"], "SaaS Admin", f"Nueva Empresa Creada: {name}", f"ID: {tenant_id} | Plan: {plan}"))
                
                conn.commit()
                conn.close()
                return self.send_json({"message": f"Empresa '{name}' registrada exitosamente."})
            except Exception as e:
                conn.rollback()
                conn.close()
                return self.send_json({"error": f"Error al procesar alta: {e}"}, 500)

        # --- REGISTER EMPLOYEE USER ---
        elif path == "/api/auth/register-user":
            user = self.get_authorized_user()
            if not user or user["role"] != "admin":
                return self.send_json({"error": "No autorizado. Solo el Administrador de la empresa puede crear nuevos usuarios."}, 401)
                
            username = body.get("username")
            password = body.get("password")
            role = body.get("role")
            fullname = body.get("name")
            allowed_pages = body.get("allowedPages", [])
            base_salary = float(body.get("baseSalary", 0.0))
            
            if not username or not password or not role or not fullname:
                return self.send_json({"error": "Completa todos los campos obligatorios del empleado."}, 400)
                
            conn = get_db()
            c = conn.cursor()
            
            # Check if user already exists
            c.execute("SELECT id FROM users WHERE tenant_id = ? AND username = ?", (user["tenant_id"], username))
            if c.fetchone():
                conn.close()
                return self.send_json({"error": "Este nombre de usuario ya está registrado en tu empresa."}, 409)
                
            try:
                p_hash, salt = hash_password(password)
                uid = f"{user['tenant_id']}_{username}_{int(time.time())}"
                c.execute("INSERT INTO users (id, tenant_id, username, password_hash, salt, role, name, created_at, allowed_pages, base_salary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (uid, user["tenant_id"], username, p_hash, salt, role, fullname, time.strftime("%Y-%m-%dT%H:%M:%SZ"), json.dumps(allowed_pages), base_salary))
                
                # Audit Log
                c.execute("INSERT INTO audit_logs (tenant_id, timestamp, username, role, module, action, impact) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (user["tenant_id"], time.strftime("%Y-%m-%dT%H:%M:%SZ"), user["username"], user["role"], "Configuración", "Creación de Cuenta de Personal", f"Nuevo Usuario: {username} | Rol: {role}"))
                
                conn.commit()
                conn.close()
                return self.send_json({"message": f"Usuario '{username}' registrado con éxito."})
            except Exception as e:
                conn.rollback()
                conn.close()
                return self.send_json({"error": f"Error al registrar usuario: {e}"}, 500)

        # --- DELETE EMPLOYEE USER ---
        elif path == "/api/auth/delete-user":
            user = self.get_authorized_user()
            if not user or user["role"] != "admin":
                return self.send_json({"error": "No autorizado. Solo el Administrador puede eliminar personal."}, 401)
                
            username_to_delete = body.get("username")
            if not username_to_delete:
                return self.send_json({"error": "Falta el nombre de usuario a eliminar."}, 400)
                
            if username_to_delete == "admin":
                return self.send_json({"error": "No puedes eliminar la cuenta de administrador principal."}, 400)
                
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE tenant_id = ? AND username = ?", (user["tenant_id"], username_to_delete))
            
            # Audit log
            c.execute("INSERT INTO audit_logs (tenant_id, timestamp, username, role, module, action, impact) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (user["tenant_id"], time.strftime("%Y-%m-%dT%H:%M:%SZ"), user["username"], user["role"], "Configuración", "Eliminación de Cuenta de Personal", f"Usuario eliminado: {username_to_delete}"))
            
            conn.commit()
            conn.close()
            return self.send_json({"message": f"Usuario '{username_to_delete}' eliminado con éxito."})

        # --- POST AUDIT TRAIL LOG RECORD ---
        elif path == "/api/audit-logs":
            user = self.get_authorized_user()
            if not user:
                return self.send_json({"error": "No autorizado."}, 401)
                
            module = body.get("module", "General")
            action = body.get("action", "Acción")
            impact = body.get("impact", "N/A")
            
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO audit_logs (tenant_id, timestamp, username, role, module, action, impact) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (user["tenant_id"], time.strftime("%Y-%m-%dT%H:%M:%SZ"), user["username"], user["role"], module, action, impact))
            conn.commit()
            conn.close()
            return self.send_json({"message": "Registro de auditoría guardado con éxito."})
            
        else:
            return self.send_json({"error": "Endpoint no encontrado."}, 404)

    def do_PUT(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            return self.send_json({"error": "Cuerpo de petición JSON inválido."}, 400)
            
        # --- SYNC OPERATIONAL DATA ---
        if path == "/api/tenant/data":
            user = self.get_authorized_user()
            if not user:
                return self.send_json({"error": "No autorizado."}, 401)
                
            conn = get_db()
            c = conn.cursor()
            
            # Double check tenant status
            c.execute("SELECT status FROM tenants WHERE id = ?", (user["tenant_id"],))
            t_row = c.fetchone()
            if not t_row or t_row["status"] == "suspendido":
                conn.close()
                return self.send_json({"error": "Empresa suspendida por falta de pago."}, 403)
                
            try:
                c.execute("UPDATE tenant_data SET json_data = ?, updated_at = ? WHERE tenant_id = ?",
                          (json.dumps(body), time.strftime("%Y-%m-%dT%H:%M:%SZ"), user["tenant_id"]))
                conn.commit()
                conn.close()
                return self.send_json({"message": "Datos de la empresa sincronizados con éxito en la nube."})
            except Exception as e:
                conn.rollback()
                conn.close()
                return self.send_json({"error": f"Error de base de datos durante sincronización: {e}"}, 500)
        else:
            return self.send_json({"error": "Endpoint no encontrado."}, 404)

# =====================================================================
# 4. INITIALIZATION & SERVER START
# =====================================================================
def run():
    print("🔒 Inicializando servidor seguro A&M ERP...")
    init_db()
    
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, SecureERPRequestHandler)
    print(f"🚀 ¡A&M ERP SaaS está listo y 100% seguro en línea!")
    print(f"👉 Abre tu navegador e ingresa a: http://localhost:{PORT}")
    print("Press Ctrl+C to terminate...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Apagando el servidor seguro A&M ERP.")
        sys.exit(0)

if __name__ == "__main__":
    run()
