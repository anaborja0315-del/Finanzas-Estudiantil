# 💸 Finanzas Estudiantil — Versión Web

Aplicación web que funciona en **celular y PC** desde el navegador.

---

## 🚀 Instalación (1 minuto)

```bash
pip install flask
python app.py
```

---

## 📱 Abrir en el celular

1. Ejecuta `python app.py` en tu PC
2. Verás en la consola algo como:
   ```
   → http://localhost:5000       (en tu PC)
   → http://192.168.1.X:5000    (en tu celular)
   ```
3. Conecta tu celular a la **misma red WiFi** que tu PC
4. Abre el navegador del celular y entra a `http://192.168.1.X:5000`
5. En Chrome/Safari: **"Agregar a pantalla de inicio"** para que se vea como app

---

## 📁 Archivos

```
FinanzasWeb/
├── app.py               → Servidor Flask (backend)
├── requirements.txt     → Solo necesitas: flask
├── finanzas_web.db      → Se crea automáticamente
└── templates/
    ├── login.html       → Pantalla de login/registro
    └── app.html         → Aplicación completa (SPA)
```

---

## ✨ Funcionalidades

- ✅ Login y registro de usuarios
- ✅ Dashboard con balance, días restantes y tips
- ✅ Registro rápido de gastos e ingresos (< 5 seg)
- ✅ Historial con filtros
- ✅ Presupuestos globales y por categoría
- ✅ Metas de ahorro con barras de progreso
- ✅ Seguimiento de suscripciones con alertas
- ✅ Gráficas interactivas (torta y barras)
- ✅ Deshacer última acción
- ✅ Diseño responsive: funciona en celular y PC

---

## 🌐 Despliegue en internet (opcional)

Para que cualquier persona acceda desde su celular sin estar en la misma red:

**Opción gratuita — Railway:**
1. Sube el proyecto a GitHub
2. Ve a railway.app → Deploy from GitHub
3. Listo, obtienes una URL pública

**Opción gratuita — Render:**
1. Sube a GitHub
2. Ve a render.com → New Web Service
3. Build: `pip install flask`  |  Start: `python app.py`
