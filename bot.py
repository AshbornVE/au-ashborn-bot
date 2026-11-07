os = __import__('os')
time = __import__('time')
requests = __import__('requests')
from pypdf import PdfReader
from flask import Flask
import threading

# Leemos el Token de forma segura desde las variables de entorno de la nube
TOKEN = os.environ.get("TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

print("🤖 Preparando bot para la nube...")

# Servidor Flask para mantener el servicio activo 24/7 en Render
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "¡El bot universitario de la UNA está activo 24/7 en la nube! 🚀"

def correr_web():
    # Render asigna un puerto automático mediante la variable 'PORT'
    puerto = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=puerto)

# Memoria temporal y base de datos base
USUARIOS_TEXTOS = {}

PLAN_ESTUDIOS_BASE = {
    "sem_I": {
        "titulo": "📚 Semestre I",
        "materias": [
            {"codigo": "107", "nombre": "Lógica", "uc": "3", "prelacion": "Ninguna"},
            {"codigo": "115", "nombre": "Lengua y Comunicación", "uc": "3", "prelacion": "Ninguna"},
            {"codigo": "116", "nombre": "Introducción a la Informática", "uc": "3", "prelacion": "Ninguna"},
            {"codigo": "177", "nombre": "Matemática I", "uc": "5", "prelacion": "Ninguna"},
            {"codigo": "327", "nombre": "Introducción a la Ingeniería de Sistemas", "uc": "3", "prelacion": "Ninguna"}
        ]
    },
    "sem_II": {
        "titulo": "📚 Semestre II",
        "materias": [
            {"codigo": "119", "nombre": "Temas de Ética", "uc": "2", "prelacion": "Ninguna"},
            {"codigo": "121", "nombre": "Problemática del Desarrollo Venezolano", "uc": "2", "prelacion": "Ninguna"},
            {"codigo": "179", "nombre": "Matemática II", "uc": "5", "prelacion": "177"},
            {"codigo": "323", "nombre": "Computación I", "uc": "4", "prelacion": "116 y 177"}
        ]
    },
    "sem_III": {
        "titulo": "📚 Semestre III",
        "materias": [
            {"codigo": "117", "nombre": "Ambiente y Desarrollo Sostenible", "uc": "3", "prelacion": "Ninguna"},
            {"codigo": "300", "nombre": "Física General I", "uc": "4", "prelacion": "179"},
            {"codigo": "324", "nombre": "Computación II", "uc": "4", "prelacion": "323"},
            {"codigo": "641", "nombre": "Teoría Económica I", "uc": "4", "prelacion": "Ninguna"},
            {"codigo": "733", "nombre": "Matemática III", "uc": "5", "prelacion": "179"}
        ]
    },
    "sem_IV": {
        "titulo": "📚 Semestre IV",
        "materias": [
            {"codigo": "315", "nombre": "Investigación de Operaciones I", "uc": "4", "prelacion": "Ninguna"},
            {"codigo": "326", "nombre": "Física General II", "uc": "4", "prelacion": "300"},
            {"codigo": "330", "nombre": "Procesamiento de Datos", "uc": "4", "prelacion": "324"},
            {"codigo": "735", "nombre": "Matemática IV", "uc": "5", "prelacion": "733"},
            {"codigo": "737", "nombre": "Introducción a la Probabilidad", "uc": "4", "prelacion": "733"}
        ]
    }
}

def extraer_texto_pdf(ruta_archivo):
    try:
        lector = PdfReader(ruta_archivo)
        texto_completo = ""
        for pagina in lector.pages:
            t = pagina.extract_text()
            if t:
                texto_completo += "\n" + t
        return texto_completo
    except Exception as e:
        return f"Error leyendo el PDF: {e}"

def enviar_o_editar_mensaje(chat_id, message_id, texto, teclado=None):
    if message_id:
        url = f"{BASE_URL}/editMessageText"
        payload = {"chat_id": chat_id, "message_id": message_id, "text": texto, "parse_mode": "Markdown"}
        if teclado: payload["reply_markup"] = teclado
        res = requests.post(url, json=payload)
        if res.status_code != 200: enviar_mensaje_nuevo(chat_id, texto, teclado)
    else:
        enviar_mensaje_nuevo(chat_id, texto, teclado)

def enviar_mensaje_nuevo(chat_id, texto, teclado=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    if teclado: payload["reply_markup"] = teclado
    requests.post(url, json=payload)

def responder_callback(callback_query_id, texto=""):
    url = f"{BASE_URL}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id, "text": texto}
    requests.post(url, json=payload)

def obtener_teclado_semestres():
    return {
        "inline_keyboard": [
            [{"text": "Semestre I", "callback_data": "ver_sem_I"}, {"text": "Semestre II", "callback_data": "ver_sem_II"}],
            [{"text": "Semestre III", "callback_data": "ver_sem_III"}, {"text": "Semestre IV", "callback_data": "ver_sem_IV"}]
        ]
    }

def crear_teclado_materias(semestre_key):
    datos = PLAN_ESTUDIOS_BASE.get(semestre_key)
    if not datos: return None
    teclado = []
    for mat in datos["materias"]:
        teclado.append([{"text": f"📖 {mat['nombre']} ({mat['uc']} UC)", "callback_data": f"mat_{mat['codigo']}"}])
    teclado.append([{"text": "⬅️ Volver a Semestres", "callback_data": "menu_principal"}])
    return {"inline_keyboard": teclado}

def buscar_materia_por_codigo(codigo):
    for sem_key, info in PLAN_ESTUDIOS_BASE.items():
        for mat in info["materias"]:
            if mat["codigo"] == codigo: return mat
    return None

def procesar_actualizaciones(offset=None):
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 30, "offset": offset}
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        return None

def main():
    # Iniciamos el servidor Flask en un hilo secundario para cumplir con Render
    hilo = threading.Thread(target=correr_web)
    hilo.daemon = True
    hilo.start()
    print("🌐 Servidor web secundario iniciado para Render.")

    offset = None
    while True:
        data = procesar_actualizaciones(offset)
        if data and "result" in data:
            for update in data["result"]:
                offset = update["update_id"] + 1
                
                if "callback_query" in update:
                    cq = update["callback_query"]
                    chat_id = cq["message"]["chat"]["id"]
                    message_id = cq["message"]["message_id"]
                    callback_id = cq["id"]
                    data_accion = cq["data"]
                    
                    responder_callback(callback_id)
                    
                    if data_accion == "menu_principal":
                        texto = "🎓 *Menú Principal*\n\nSelecciona el semestre que deseas consultar:"
                        enviar_o_editar_mensaje(chat_id, message_id, texto, obtener_teclado_semestres())
                    elif data_accion.startswith("ver_sem_"):
                        sem_key = data_accion.replace("ver_", "")
                        info_sem = PLAN_ESTUDIOS_BASE.get(sem_key)
                        if info_sem:
                            texto = f"📋 *{info_sem['titulo']}*\n\nSelecciona una asignatura para ver sus detalles:"
                            enviar_o_editar_mensaje(chat_id, message_id, texto, crear_teclado_materias(sem_key))
                    elif data_accion.startswith("mat_"):
                        codigo_mat = data_accion.replace("mat_", "")
                        materia = buscar_m_por_codigo_seguro = buscar_materia_por_codigo(codigo_mat)
                        if materia:
                            texto = (
                                f"📌 *FICHA DE ASIGNATURA*\n\n"
                                f"🔹 *Asignatura:* {materia['nombre']}\n"
                                f"🔢 *Código:* `{materia['codigo']}`\n"
                                f"🎯 *Unidades Crédito:* {materia['uc']} UC\n"
                                f"🔗 *Prelación:* {materia['prelacion']}\n\n"
                                f"📅 *Evaluaciones y Plazos:* \n"
                                f"*(Próximamente aquí aparecerán las fechas y alarmas de 20 y 5 días)*"
                            )
                            teclado_volver = {"inline_keyboard": [[{"text": "⬅️ Volver al listado", "callback_data": "menu_principal"}]]}
                            enviar_o_editar_mensaje(chat_id, message_id, texto, teclado_volver)
                
                elif "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    
                    if "document" in msg:
                        doc = msg["document"]
                        file_name = doc["file_name"]
                        if file_name.endswith(".pdf"):
                            enviar_mensaje_nuevo(chat_id, f"📥 He recibido el archivo *{file_name}* correctamente en la nube...")
                            file_id = doc["file_id"]
                            file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
                            file_path = file_info["result"]["file_path"]
                            pdf_bytes = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{file_path}").content
                            
                            local_pdf = "temp_evaluacion.pdf"
                            with open(local_pdf, "wb") as f: f.write(pdf_bytes)
                            USUARIOS_TEXTOS[chat_id] = extraer_texto_pdf(local_pdf)
                            if os.path.exists(local_pdf): os.remove(local_pdf)
                            
                            enviar_mensaje_nuevo(chat_id, f"✅ *¡Documento analizado en la nube!*", obtener_teclado_semestres())
                        else:
                            enviar_mensaje_nuevo(chat_id, "⚠️ Envía un archivo **PDF** válido.")
                    elif "text" in msg:
                        texto_usuario = msg["text"]
                        if texto_usuario.startswith("/start"):
                            enviar_o_editar_mensaje(chat_id, None, "¡Hola desde la nube! 🎓\n\nSelecciona el semestre:", obtener_teclado_semestres())
                        else:
                            enviar_o_editar_mensaje(chat_id, None, "Usa el menú o envíame tu PDF:", obtener_teclado_semestres())
            time.sleep(1)

if __name__ == "__main__":
    main()