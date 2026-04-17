"""
app.py — Finanzas Estudiantil Web
Backend Flask que reutiliza la lógica de database.py y patterns.py
"""

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, send_file)
import sqlite3, hashlib, os, json, io
from datetime import date, datetime
import calendar

app = Flask(__name__)
app.secret_key = "finanzas_estudiantil_2025_secreto"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finanzas_web.db")

MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

# ══════════════════════════════════════════════════════
#  BASE DE DATOS
# ══════════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        fecha_registro TEXT DEFAULT (date('now'))
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('ingreso','gasto')),
        icono TEXT DEFAULT '💰',
        color TEXT DEFAULT '#4f8ef7'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS transacciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('ingreso','gasto')),
        categoria_id INTEGER NOT NULL,
        monto REAL NOT NULL,
        descripcion TEXT DEFAULT '',
        fecha TEXT NOT NULL DEFAULT (date('now')),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (categoria_id) REFERENCES categorias(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS presupuesto_global (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER UNIQUE NOT NULL,
        monto_limite REAL NOT NULL,
        mes INTEGER NOT NULL,
        anio INTEGER NOT NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS presupuestos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        categoria_id INTEGER NOT NULL,
        monto_limite REAL NOT NULL,
        mes INTEGER NOT NULL,
        anio INTEGER NOT NULL,
        UNIQUE(usuario_id, categoria_id, mes, anio),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (categoria_id) REFERENCES categorias(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS metas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        monto_objetivo REAL NOT NULL,
        monto_actual REAL DEFAULT 0,
        fecha_limite TEXT,
        completada INTEGER DEFAULT 0,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS suscripciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        monto REAL NOT NULL,
        dia_cobro INTEGER NOT NULL,
        activa INTEGER DEFAULT 1,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    )""")
    cats = [
        ("Mesada","ingreso","💵","#22c55e"),("Beca","ingreso","🎓","#16a34a"),
        ("Salario","ingreso","💼","#15803d"),("Freelance","ingreso","💻","#166534"),
        ("Otro ingreso","ingreso","💰","#14532d"),
        ("Comida (Cafetería)","gasto","☕","#ef4444"),
        ("Comida (Súper)","gasto","🛒","#dc2626"),
        ("Transporte","gasto","🚌","#f97316"),
        ("Fotocopias/Libros","gasto","📚","#a855f7"),
        ("Alquiler/Residencia","gasto","🏠","#7c3aed"),
        ("Servicios","gasto","💡","#eab308"),
        ("Salidas/Ocio","gasto","🎉","#ec4899"),
        ("Suscripciones","gasto","📱","#f43f5e"),
        ("Café/Snacks","gasto","☕","#fb923c"),
        ("Salud","gasto","🏥","#06b6d4"),
        ("Ropa","gasto","👕","#8b5cf6"),
        ("Otro gasto","gasto","📦","#6b7280"),
    ]
    c.executemany("INSERT OR IGNORE INTO categorias (nombre,tipo,icono,color) VALUES (?,?,?,?)", cats)
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════
def uid():
    return session.get("usuario_id")

def resumen_mes(usuario_id, mes, anio):
    conn = get_db()
    row = conn.execute("""
        SELECT
          COALESCE(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE 0 END),0) AS ingresos,
          COALESCE(SUM(CASE WHEN tipo='gasto'   THEN monto ELSE 0 END),0) AS gastos
        FROM transacciones
        WHERE usuario_id=?
          AND CAST(strftime('%m',fecha) AS INTEGER)=?
          AND CAST(strftime('%Y',fecha) AS INTEGER)=?
    """, (usuario_id, mes, anio)).fetchone()
    conn.close()
    ing = row["ingresos"]; gas = row["gastos"]
    return {"ingresos": ing, "gastos": gas, "balance": ing - gas}

def dias_restantes_info(usuario_id, mes, anio):
    hoy = date.today()
    _, dias_mes = calendar.monthrange(anio, mes)
    dias_rest = dias_mes - hoy.day
    conn = get_db()
    pg = conn.execute(
        "SELECT monto_limite FROM presupuesto_global WHERE usuario_id=? AND mes=? AND anio=?",
        (usuario_id, mes, anio)).fetchone()
    conn.close()
    res = resumen_mes(usuario_id, mes, anio)
    disponible = (pg["monto_limite"] - res["gastos"]) if pg else res["balance"]
    diario = disponible / dias_rest if dias_rest > 0 else 0
    return {"disponible": disponible, "dias_restantes": dias_rest, "presupuesto_dia": diario}

def tips_personalizados(usuario_id, mes, anio):
    conn = get_db()
    rows = conn.execute("""
        SELECT c.nombre, SUM(t.monto) AS total
        FROM transacciones t JOIN categorias c ON c.id=t.categoria_id
        WHERE t.usuario_id=? AND t.tipo='gasto'
          AND CAST(strftime('%m',t.fecha) AS INTEGER)=?
          AND CAST(strftime('%Y',t.fecha) AS INTEGER)=?
        GROUP BY c.id ORDER BY total DESC
    """, (usuario_id, mes, anio)).fetchall()
    conn.close()
    res = resumen_mes(usuario_id, mes, anio)
    total = res["gastos"] or 1
    tips = []
    for r in rows:
        pct = r["total"] / total
        if r["nombre"] == "Transporte" and pct > 0.25:
            tips.append("🚌 Gastas mucho en transporte. ¿Consideraste el pase mensual?")
        if r["nombre"] == "Comida (Cafetería)" and pct > 0.20:
            tips.append("🍱 Muchos gastos en cafetería. Preparar almuerzo puede ahorrarte 40%.")
        if r["nombre"] == "Salidas/Ocio" and pct > 0.15:
            tips.append("🎉 El ocio supera el 15% de tus gastos. Busca actividades gratuitas.")
        if r["nombre"] == "Café/Snacks" and pct > 0.10:
            tips.append("☕ Café y snacks superaron el 10% de tu presupuesto semanal.")
    if not tips:
        tips.append("✅ ¡Tus finanzas se ven saludables este mes! Sigue así.")
    return tips

# ══════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════
@app.route("/")
def index():
    if uid():
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/api/register", methods=["POST"])
def register():
    d = request.json
    nombre = d.get("nombre","").strip()
    email  = d.get("email","").strip().lower()
    pwd    = d.get("password","")
    if not all([nombre, email, pwd]) or len(pwd) < 6:
        return jsonify({"ok": False, "msg": "Datos inválidos o contraseña muy corta."})
    try:
        conn = get_db()
        conn.execute("INSERT INTO usuarios (nombre,email,password) VALUES (?,?,?)",
                     (nombre, email, hashlib.sha256(pwd.encode()).hexdigest()))
        conn.commit(); conn.close()
        return jsonify({"ok": True, "msg": "Cuenta creada exitosamente."})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "msg": "Este correo ya está registrado."})

@app.route("/api/login", methods=["POST"])
def login():
    d = request.json
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE email=? AND password=?",
        (d.get("email","").strip().lower(),
         hashlib.sha256(d.get("password","").encode()).hexdigest())
    ).fetchone()
    conn.close()
    if row:
        session["usuario_id"] = row["id"]
        session["nombre"]     = row["nombre"]
        return jsonify({"ok": True})
    return jsonify({"ok": False, "msg": "Correo o contraseña incorrectos."})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ══════════════════════════════════════════════════════
#  PÁGINAS
# ══════════════════════════════════════════════════════
@app.route("/dashboard")
def dashboard():
    if not uid(): return redirect(url_for("index"))
    return render_template("app.html", nombre=session["nombre"], pagina="dashboard")

@app.route("/registrar")
def registrar():
    if not uid(): return redirect(url_for("index"))
    return render_template("app.html", nombre=session["nombre"], pagina="registrar")

@app.route("/historial")
def historial():
    if not uid(): return redirect(url_for("index"))
    return render_template("app.html", nombre=session["nombre"], pagina="historial")

@app.route("/presupuestos")
def presupuestos():
    if not uid(): return redirect(url_for("index"))
    return render_template("app.html", nombre=session["nombre"], pagina="presupuestos")

@app.route("/metas")
def metas():
    if not uid(): return redirect(url_for("index"))
    return render_template("app.html", nombre=session["nombre"], pagina="metas")

@app.route("/graficas")
def graficas():
    if not uid(): return redirect(url_for("index"))
    return render_template("app.html", nombre=session["nombre"], pagina="graficas")

# ══════════════════════════════════════════════════════
#  API — DATOS
# ══════════════════════════════════════════════════════
@app.route("/api/dashboard")
def api_dashboard():
    if not uid(): return jsonify({"error":"no auth"}), 401
    hoy = date.today()
    mes, anio = int(request.args.get("mes", hoy.month)), int(request.args.get("anio", hoy.year))
    res   = resumen_mes(uid(), mes, anio)
    dias  = dias_restantes_info(uid(), mes, anio)
    tips  = tips_personalizados(uid(), mes, anio)

    conn = get_db()
    # Últimas transacciones
    trans = conn.execute("""
        SELECT t.id, t.tipo, t.monto, t.descripcion, t.fecha,
               c.nombre AS categoria, c.icono, c.color
        FROM transacciones t JOIN categorias c ON c.id=t.categoria_id
        WHERE t.usuario_id=? ORDER BY t.fecha DESC, t.id DESC LIMIT 8
    """, (uid(),)).fetchall()
    # Presupuestos
    prests = conn.execute("""
        SELECT p.id, c.nombre, c.icono, c.color, p.monto_limite,
               COALESCE((SELECT SUM(t.monto) FROM transacciones t
                          WHERE t.usuario_id=p.usuario_id AND t.categoria_id=p.categoria_id
                            AND t.tipo='gasto'
                            AND CAST(strftime('%m',t.fecha) AS INTEGER)=p.mes
                            AND CAST(strftime('%Y',t.fecha) AS INTEGER)=p.anio),0) AS gastado
        FROM presupuestos p JOIN categorias c ON c.id=p.categoria_id
        WHERE p.usuario_id=? AND p.mes=? AND p.anio=?
    """, (uid(), mes, anio)).fetchall()
    # Suscripciones próximas
    hoy_dia = hoy.day
    subs = conn.execute(
        "SELECT * FROM suscripciones WHERE usuario_id=? AND activa=1 AND ABS(dia_cobro-?)<=3",
        (uid(), hoy_dia)).fetchall()
    conn.close()

    return jsonify({
        "resumen":      res,
        "dias":         dias,
        "tips":         tips,
        "transacciones":[dict(t) for t in trans],
        "presupuestos": [dict(p) for p in prests],
        "suscripciones":[dict(s) for s in subs],
        "mes": mes, "anio": anio,
        "nombre_mes": MESES[mes-1],
    })

@app.route("/api/categorias")
def api_categorias():
    tipo = request.args.get("tipo")
    conn = get_db()
    q = "SELECT * FROM categorias" + (" WHERE tipo=?" if tipo else "") + " ORDER BY tipo,nombre"
    rows = conn.execute(q, (tipo,) if tipo else ()).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/transacciones", methods=["GET","POST","PUT","DELETE"])
def api_transacciones():
    if not uid(): return jsonify({"error":"no auth"}), 401
    if request.method == "GET":
        conn = get_db()
        q = """SELECT t.*, c.nombre AS categoria, c.icono, c.color
               FROM transacciones t JOIN categorias c ON c.id=t.categoria_id
               WHERE t.usuario_id=?"""
        p = [uid()]
        args = request.args
        if args.get("desde"):  q += " AND t.fecha>=?"; p.append(args["desde"])
        if args.get("hasta"):  q += " AND t.fecha<=?"; p.append(args["hasta"])
        if args.get("tipo"):   q += " AND t.tipo=?";   p.append(args["tipo"])
        q += " ORDER BY t.fecha DESC, t.id DESC"
        rows = conn.execute(q, p).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    if request.method == "POST":
        d = request.json
        conn = get_db()
        conn.execute(
            "INSERT INTO transacciones (usuario_id,tipo,categoria_id,monto,descripcion,fecha) VALUES (?,?,?,?,?,?)",
            (uid(), d["tipo"], d["categoria_id"], float(d["monto"]),
             d.get("descripcion",""), d.get("fecha", str(date.today()))))
        conn.commit(); conn.close()
        return jsonify({"ok": True})

    if request.method == "PUT":
        d = request.json
        conn = get_db()
        conn.execute(
            "UPDATE transacciones SET tipo=?,categoria_id=?,monto=?,descripcion=?,fecha=? WHERE id=? AND usuario_id=?",
            (d["tipo"], d["categoria_id"], float(d["monto"]),
             d.get("descripcion",""), d["fecha"], d["id"], uid()))
        conn.commit(); conn.close()
        return jsonify({"ok": True})

    if request.method == "DELETE":
        tid = request.json.get("id")
        conn = get_db()
        conn.execute("DELETE FROM transacciones WHERE id=? AND usuario_id=?", (tid, uid()))
        conn.commit(); conn.close()
        return jsonify({"ok": True})

@app.route("/api/presupuesto-global", methods=["GET","POST"])
def api_presupuesto_global():
    if not uid(): return jsonify({"error":"no auth"}), 401
    hoy = date.today()
    mes  = int(request.args.get("mes",  hoy.month))
    anio = int(request.args.get("anio", hoy.year))
    if request.method == "GET":
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM presupuesto_global WHERE usuario_id=? AND mes=? AND anio=?",
            (uid(), mes, anio)).fetchone()
        conn.close()
        return jsonify(dict(row) if row else {})
    d = request.json
    conn = get_db()
    conn.execute("""INSERT INTO presupuesto_global (usuario_id,monto_limite,mes,anio) VALUES (?,?,?,?)
                    ON CONFLICT(usuario_id) DO UPDATE SET monto_limite=?,mes=?,anio=?""",
                 (uid(), d["monto"], d["mes"], d["anio"],
                  d["monto"], d["mes"], d["anio"]))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/presupuestos", methods=["GET","POST","DELETE"])
def api_presupuestos():
    if not uid(): return jsonify({"error":"no auth"}), 401
    hoy = date.today()
    mes  = int(request.args.get("mes",  hoy.month))
    anio = int(request.args.get("anio", hoy.year))
    if request.method == "GET":
        conn = get_db()
        rows = conn.execute("""
            SELECT p.id, c.nombre, c.icono, c.color, p.monto_limite,
                   COALESCE((SELECT SUM(t.monto) FROM transacciones t
                              WHERE t.usuario_id=p.usuario_id AND t.categoria_id=p.categoria_id
                                AND t.tipo='gasto'
                                AND CAST(strftime('%m',t.fecha) AS INTEGER)=p.mes
                                AND CAST(strftime('%Y',t.fecha) AS INTEGER)=p.anio),0) AS gastado
            FROM presupuestos p JOIN categorias c ON c.id=p.categoria_id
            WHERE p.usuario_id=? AND p.mes=? AND p.anio=? ORDER BY c.nombre
        """, (uid(), mes, anio)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    if request.method == "POST":
        d = request.json
        conn = get_db()
        conn.execute("""INSERT INTO presupuestos (usuario_id,categoria_id,monto_limite,mes,anio) VALUES (?,?,?,?,?)
                        ON CONFLICT(usuario_id,categoria_id,mes,anio) DO UPDATE SET monto_limite=excluded.monto_limite""",
                     (uid(), d["categoria_id"], float(d["monto"]), d["mes"], d["anio"]))
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    if request.method == "DELETE":
        pid = request.json.get("id")
        conn = get_db()
        conn.execute("DELETE FROM presupuestos WHERE id=? AND usuario_id=?", (pid, uid()))
        conn.commit(); conn.close()
        return jsonify({"ok": True})

@app.route("/api/metas", methods=["GET","POST","PUT","DELETE"])
def api_metas():
    if not uid(): return jsonify({"error":"no auth"}), 401
    if request.method == "GET":
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM metas WHERE usuario_id=? ORDER BY completada, fecha_limite",
            (uid(),)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    if request.method == "POST":
        d = request.json
        conn = get_db()
        conn.execute("INSERT INTO metas (usuario_id,nombre,monto_objetivo,fecha_limite) VALUES (?,?,?,?)",
                     (uid(), d["nombre"], float(d["objetivo"]), d.get("fecha_limite")))
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    if request.method == "PUT":
        d = request.json
        aporte = float(d["aporte"])
        conn = get_db()
        conn.execute("""UPDATE metas SET monto_actual=monto_actual+?,
                        completada=CASE WHEN monto_actual+?>=monto_objetivo THEN 1 ELSE 0 END
                        WHERE id=? AND usuario_id=?""",
                     (aporte, aporte, d["id"], uid()))
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    if request.method == "DELETE":
        conn = get_db()
        conn.execute("DELETE FROM metas WHERE id=? AND usuario_id=?",
                     (request.json.get("id"), uid()))
        conn.commit(); conn.close()
        return jsonify({"ok": True})

@app.route("/api/suscripciones", methods=["GET","POST","DELETE"])
def api_suscripciones():
    if not uid(): return jsonify({"error":"no auth"}), 401
    if request.method == "GET":
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM suscripciones WHERE usuario_id=? AND activa=1 ORDER BY dia_cobro",
            (uid(),)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    if request.method == "POST":
        d = request.json
        conn = get_db()
        conn.execute("INSERT INTO suscripciones (usuario_id,nombre,monto,dia_cobro) VALUES (?,?,?,?)",
                     (uid(), d["nombre"], float(d["monto"]), int(d["dia_cobro"])))
        conn.commit(); conn.close()
        return jsonify({"ok": True})
    if request.method == "DELETE":
        conn = get_db()
        conn.execute("DELETE FROM suscripciones WHERE id=? AND usuario_id=?",
                     (request.json.get("id"), uid()))
        conn.commit(); conn.close()
        return jsonify({"ok": True})

@app.route("/api/graficas")
def api_graficas():
    if not uid(): return jsonify({"error":"no auth"}), 401
    hoy = date.today()
    mes  = int(request.args.get("mes",  hoy.month))
    anio = int(request.args.get("anio", hoy.year))
    conn = get_db()
    # Por categoría
    cats = conn.execute("""
        SELECT c.nombre, c.color, SUM(t.monto) AS total
        FROM transacciones t JOIN categorias c ON c.id=t.categoria_id
        WHERE t.usuario_id=? AND t.tipo='gasto'
          AND CAST(strftime('%m',t.fecha) AS INTEGER)=?
          AND CAST(strftime('%Y',t.fecha) AS INTEGER)=?
        GROUP BY c.id ORDER BY total DESC
    """, (uid(), mes, anio)).fetchall()
    # Evolución
    evol = conn.execute("""
        SELECT strftime('%Y-%m', fecha) AS mes,
               SUM(CASE WHEN tipo='ingreso' THEN monto ELSE 0 END) AS ingresos,
               SUM(CASE WHEN tipo='gasto'   THEN monto ELSE 0 END) AS gastos
        FROM transacciones WHERE usuario_id=?
        GROUP BY mes ORDER BY mes DESC LIMIT 6
    """, (uid(),)).fetchall()
    conn.close()
    return jsonify({
        "por_categoria": [dict(r) for r in cats],
        "evolucion":     list(reversed([dict(r) for r in evol])),
    })

if __name__ == "__main__":
    init_db()
    print("\nFinanzas Estudiantil Web corriendo en:")
    print("http://localhost:5000  (PC)")
    print("http://TU_IP:5000     (celular en la misma red WiFi)\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
