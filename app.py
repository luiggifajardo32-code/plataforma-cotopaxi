import os
import sqlite3
import re
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, make_response
from datetime import datetime

app = Flask(__name__)
app.secret_key = "clave_secreta_sesion_cotopaxi"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, "cotopaxi.db")
CARPETA_FOTOS = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(CARPETA_FOTOS, exist_ok=True)

CLAVE_ADMIN = "cotopaxi2026"
CLAVE_DOCENTE = "docente2026"
EXTENSIONES_PERMITIDAS = {"png", "jpg", "jpeg", "gif", "webp"}

PALABRAS_PROHIBIDAS = [
    "puta", "puto", "verga", "chucha", "mamerto", "idiota", "estupido",
    "estúpido", "imbecil", "imbécil", "pendejo", "cabron", "cabrón",
    "mierda", "carajo", "culero", "maricon", "maricón", "perra",
    "zorra", "bastardo", "hijueputa", "hp", "ctm", "ptm", "hdp",
    "tonto", "menso", "baboso", "burla", "payaso", "inutil", "inútil"
]

def contiene_groserias(texto):
    texto_limpio = texto.lower()
    for palabra in PALABRAS_PROHIBIDAS:
        if re.search(r'\b' + re.escape(palabra) + r'\b', texto_limpio):
            return True
    return False

def foto_valida(nombre_archivo):
    return "." in nombre_archivo and nombre_archivo.rsplit(".", 1)[1].lower() in EXTENSIONES_PERMITIDAS

def iniciar_bd():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comunicados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            autor TEXT NOT NULL,
            fecha TEXT NOT NULL,
            contenido TEXT NOT NULL,
            token_dispositivo TEXT NOT NULL,
            foto TEXT
        )
    """)
    conexion.commit()
    conexion.close()

iniciar_bd()

@app.route("/")
def inicio():
    token_actual = request.cookies.get("token_usuario")
    es_moderador = session.get("rol") in ("admin", "docente")
    rol_actual = session.get("rol", "")

    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM comunicados ORDER BY id DESC")
    comunicados = cursor.fetchall()
    conexion.close()

    respuesta = make_response(render_template(
        "index.html",
        comunicados=comunicados,
        token_actual=token_actual,
        es_moderador=es_moderador,
        rol_actual=rol_actual
    ))

    if not token_actual:
        nuevo_token = str(uuid.uuid4())
        respuesta.set_cookie("token_usuario", nuevo_token, max_age=60*60*24*365)

    return respuesta

@app.route("/publicar", methods=["GET", "POST"])
def publicar():
    error_filtro = None
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        categoria = request.form.get("categoria", "").strip()
        autor = request.form.get("autor", "").strip()
        contenido = request.form.get("contenido", "").strip()

        if contiene_groserias(titulo) or contiene_groserias(contenido) or contiene_groserias(autor):
            error_filtro = "⚠️ Publicación bloqueada: Se detectó lenguaje ofensivo, groserías o contenido de burla."
            return render_template("publicar.html", error_filtro=error_filtro)

        if len(titulo) < 4 or len(contenido) < 10:
            error_filtro = "⚠️ La noticia es demasiado corta. Escriba un título y un detalle claro."
            return render_template("publicar.html", error_filtro=error_filtro)

        nombre_foto_guardada = None
        archivo = request.files.get("foto")
        if archivo and archivo.filename != "":
            if foto_valida(archivo.filename):
                ext = archivo.filename.rsplit(".", 1)[1].lower()
                nombre_foto_guardada = f"{uuid.uuid4().hex}.{ext}"
                archivo.save(os.path.join(CARPETA_FOTOS, nombre_foto_guardada))
            else:
                error_filtro = "⚠️ Formato de imagen no válido. Use JPG, PNG o WEBP."
                return render_template("publicar.html", error_filtro=error_filtro)

        token_actual = request.cookies.get("token_usuario") or str(uuid.uuid4())
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")

        conexion = sqlite3.connect(DB_NAME)
        cursor = conexion.cursor()
        cursor.execute(
            "INSERT INTO comunicados (titulo, categoria, autor, fecha, contenido, token_dispositivo, foto) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (titulo, categoria, autor, fecha, contenido, token_actual, nombre_foto_guardada)
        )
        conexion.commit()
        conexion.close()

        respuesta = make_response(redirect(url_for("inicio")))
        respuesta.set_cookie("token_usuario", token_actual, max_age=60*60*24*365)
        return respuesta

    return render_template("publicar.html", error_filtro=error_filtro)

@app.route("/eliminar/<int:id>", methods=["POST"])
def eliminar(id):
    token_actual = request.cookies.get("token_usuario")
    es_moderador = session.get("rol") in ("admin", "docente")

    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("SELECT token_dispositivo, foto FROM comunicados WHERE id = ?", (id,))
    fila = cursor.fetchone()

    if fila:
        token_dueno, foto_archivo = fila[0], fila[1]
        if es_moderador or (token_actual and token_actual == token_dueno):
            if foto_archivo:
                ruta_foto = os.path.join(CARPETA_FOTOS, foto_archivo)
                if os.path.exists(ruta_foto):
                    os.remove(ruta_foto)
            cursor.execute("DELETE FROM comunicados WHERE id = ?", (id,))
            conexion.commit()

    conexion.close()
    return redirect(url_for("inicio"))

@app.route("/acceso", methods=["POST"])
def acceso():
    clave = request.form.get("clave", "").strip()
    if clave == CLAVE_ADMIN:
        session["rol"] = "admin"
    elif clave == CLAVE_DOCENTE:
        session["rol"] = "docente"
    return redirect(url_for("inicio"))

@app.route("/salir")
def salir():
    session.pop("rol", None)
    return redirect(url_for("inicio"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)