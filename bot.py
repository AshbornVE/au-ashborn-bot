import os
import threading
import time
import requests
from flask import Flask, request
from pypdf import PdfReader

app = Flask(__name__)

# Token obtenido desde las variables de entorno de Render
TOKEN = os.environ.get("TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

# Diccionario global para almacenar el pensum/cronograma de cada usuario por su chat_id
user_pensums = {}

@app.route("/")
def home():
    return "¡El bot de la UNA para Ingeniería en Sistemas está vivo y activo en la nube! 🚀"

def send_message(chat_id, text, reply_markup=None):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

def parse_pdf_text(extracted_text):
    """
    Función inteligente para analizar el texto del PDF y organizarlo en semestres y materias.
    Busca palabras clave como 'Semestre', 'Trimestre' o 'Año' y agrupa las líneas siguientes.
    """
    structure = {}
    current_section = "General"
    structure[current_section] = []

    lines = extracted_text.split('\n')
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        
        # Detectar si la línea marca un semestre o bloque nuevo
        lower_line = line_clean.lower()
        if "semestre" in lower_line or "trayecto" in lower_line or "periodo" in lower_line or "ciclo" in lower_line:
            current_section = line_clean
            if current_section not in structure:
                structure[current_section] = []
        else:
            # Evitar agregar líneas demasiado cortas o encabezados repetitivos
            if len(line_clean) > 3:
                structure[current_section].append(line_clean)
                
    # Filtrar secciones vacías por seguridad
    structure = {k: v for k, v in structure.items() if v}
    if not structure:
        structure["Plan de Estudios"] = [line.strip() for line in lines if line.strip()][:30]
        
    return structure

def handle_update(update):
    chat_id = update["message"]["chat"]["id"]
    msg = update["message"]
    text = msg.get("text", "")
    document = msg.get("document")

    # 1. Si el usuario envía un archivo PDF
    if document:
        file_name = document.get("file_name", "")
        if file_name.lower().endswith(".pdf"):
            send_message(chat_id, "📥 Archivo PDF recibido. Procesando tu cronograma al vuelo...")
            file_id = document["file_id"]
            
            # Obtener la ruta de descarga de Telegram
            file_info_res = requests.get(f"{TELEGRAM_API}/getFile?file_id={file_id}").json()
            if not file_info_res.get("ok"):
                send_message(chat_id, "❌ Hubo un error al obtener el archivo de los servidores de Telegram.")
                return
                
            file_path = file_info_res["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
            
            # Descargar bytes del PDF
            pdf_bytes = requests.get(download_url).content
            temp_filename = f"temp_{chat_id}.pdf"
            
            with open(temp_filename, "wb") as f:
                f.write(pdf_bytes)
                
            try:
                # Extraer texto con pypdf
                reader = PdfReader(temp_filename)
                full_text = ""
                for page in reader.pages:
                    full_text += (page.extract_text() or "") + "\n"
                
                # Procesar y guardar el pensum específico de este usuario
                user_pensums[chat_id] = parse_pdf_text(full_text)
                
                send_message(chat_id, "✅ ¡Cronograma procesado con éxito!\n\nEscribe /start para ver tu menú interactivo personalizado.")
            except Exception as e:
                send_message(chat_id, f"❌ Ocurrió un error al leer el PDF: {str(e)}")
            finally:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
        else:
            send_message(chat_id, "⚠️ Por favor, asegúrate de enviar un archivo con formato **PDF**.")
        return

    # 2. Comando /start
    if text == "/start":
        if chat_id not in user_pensums:
            send_message(chat_id, 
                "👋 ¡Bienvenido al Bot Académico Global para Ingeniería en Sistemas (UNA)!\n\n"
                "Para comenzar, **envíame tu cronograma o plan de estudios en formato PDF** adjunto en este chat. "
                "A partir de él, generaré tu menú de estudio personalizado."
            )
        else:
            # Mostrar los semestres/secciones extraídos de su PDF
            sections = list(user_pensums[chat_id].keys())
            keyboard_inline = {
                "inline_keyboard": [
                    [{"text": sec, "callback_data": f"sec_{i}"}] for i, sec in enumerate(sections)
                ]
            }
            send_message(chat_id, "📚 **Menú Principal de Estudio**\nSelecciona el semestre o sección de tu cronograma:", reply_markup=keyboard_inline)
        return

    # 3. Manejar texto común
    if chat_id not in user_pensums:
        send_message(chat_id, "📌 Aún no has cargado ningún PDF. Por favor, envíame tu cronograma universitario en PDF para comenzar.")
    else:
        send_message(chat_id, "💡 Usa /start para ver las opciones de tu menú interactivo.")

def handle_callback(callback_query):
    chat_id = callback_query["message"]["chat"]["id"]
    data = callback_query["data"]
    query_id = callback_query["id"]
    
    # Responder al callback para quitar el estado de carga en el botón
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": query_id})
    
    if chat_id in user_pensums and data.startswith("sec_"):
        try:
            index = int(data.split("_")[1])
            sections = list(user_pensums[chat_id].keys())
            selected_section = sections[index]
            subjects = user_pensums[chat_id][selected_section]
            
            response_text = f"📖 **{selected_section}**:\n\n" + "\n".join([f"• {sub}" for sub in subjects])
            send_message(chat_id, response_text)
        except Exception:
            send_message(chat_id, "⚠️ Ocurrió un error al cargar los datos de esta sección.")

def telegram_polling():
    """Bucle en segundo plano para escuchar actualizaciones de Telegram mediante Long Polling"""
    offset = 0
    print("🤖 Hilo de Telegram Polling iniciado correctamente.")
    while True:
        try:
            url = f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=30"
            res = requests.get(url, timeout=35).json()
            if res.get("ok"):
                for update in res.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        threading.Thread(target=handle_update, args=(update,)).invoke = handle_update(update) # ejecución directa segura
                    elif "callback_query" in update:
                        threading.Thread(target=handle_callback, args=(update["callback_query"],)).start()
        except Exception as e:
            print(f"Error en polling: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Iniciar el hilo de Telegram en segundo plano
    t = threading.Thread(target=telegram_polling, daemon=True)
    t.start()
    
    # Iniciar el servidor Flask para cumplir con el puerto web de Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)