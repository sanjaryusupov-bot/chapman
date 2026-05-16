import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
from PIL import Image
import io
import cv2
import numpy as np

# Пытаемся импортировать pyzbar с обработкой ошибок
try:
    from pyzbar.pyzbar import decode
    PYZBAR_AVAILABLE = True
except Exception as e:
    PYZBAR_AVAILABLE = False
    st.warning(f"⚠️ Библиотека распознавания не загружена. Будет использован ручной ввод.")

st.set_page_config(layout="wide")

# --- GOOGLE SHEETS ---
creds_dict = st.secrets["gcp_service_account"]

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1soHrN7Iqd3jk9iLGdUGK9APxVfRBwWXHxoI8x2Hsh1o"
).worksheet("Отгрузка")

df = pd.DataFrame(sheet.get_all_records())

st.title("🚚 Отгрузка со сканером")

# --- выбор водителя ---
driver = st.selectbox("🚛 Выберите машину", df["Номер Машины"].dropna().unique())
driver_df = df[df["Номер Машины"] == driver]

total = len(driver_df)
done = len(driver_df[driver_df["Статус"] == "Отгружено"])

col1, col2, col3 = st.columns(3)
col1.metric("📦 Всего", total)
col2.metric("✅ Отгружено", done)
col3.metric("⏳ Осталось", total - done)

# --- функция для отметки отгрузки ---
def mark_as_shipped(barcode):
    # Очищаем штрихкод
    barcode = str(barcode).strip()
    
    # Ищем накладную
    match = df[df["Номера накладных"].astype(str).str.strip() == barcode]
    
    if not match.empty:
        row = match.index[0] + 2
        current_status = sheet.acell(f"D{row}").value
        
        if current_status == "Отгружено":
            st.warning(f"⚠️ Накладная {barcode} уже отгружена!")
            return False
        else:
            # Обновляем статус
            sheet.update(f"D{row}", "Отгружено")
            sheet.update(f"E{row}", f"{driver} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            st.success(f"✅ Накладная {barcode} отгружена!")
            return True
    else:
        st.error(f"❌ Накладная {barcode} не найдена!")
        return False

# --- СКАНИРОВАНИЕ КАМЕРОЙ ---
st.header("📷 Сканирование штрихкода камерой")

# Используем HTML5 камеру через JavaScript (работает на телефонах)
camera_html = """
<div style="text-align: center; padding: 20px;">
    <video id="video" width="100%" height="auto" autoplay playsinline style="border: 2px solid #ccc; border-radius: 10px;"></video>
    <canvas id="canvas" style="display: none;"></canvas>
    <div style="margin-top: 10px;">
        <button id="capture" style="padding: 10px 20px; font-size: 18px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer;">📸 Сделать фото</button>
    </div>
    <div id="result" style="margin-top: 10px; font-size: 16px;"></div>
</div>

<script>
let video = document.getElementById('video');
let canvas = document.getElementById('canvas');
let captureBtn = document.getElementById('capture');
let resultDiv = document.getElementById('result');

// Запуск камеры
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        video.srcObject = stream;
    } catch(err) {
        resultDiv.innerHTML = '❌ Ошибка доступа к камере: ' + err.message;
        resultDiv.style.color = 'red';
    }
}

// Захват фото
captureBtn.addEventListener('click', () => {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Конвертируем в base64
    let imageData = canvas.toDataURL('image/jpeg', 0.8);
    
    // Отправляем в Streamlit
    const input = document.createElement('input');
    input.type = 'hidden';
    input.id = 'captured_image';
    input.value = imageData;
    document.body.appendChild(input);
    
    // Обновляем Streamlit
    const event = new Event('input');
    input.dispatchEvent(event);
    
    resultDiv.innerHTML = '📷 Фото сделано! Обработка...';
});

startCamera();
</script>
"""

# Показываем камеру
st.components.v1.html(camera_html, height=400)

# Обработка фото из камеры
if 'captured_image' in st.session_state:
    image_data = st.session_state.captured_image
    if image_data:
        # Конвертируем base64 в изображение
        import base64
        image_bytes = base64.b64decode(image_data.split(',')[1])
        image = Image.open(io.BytesIO(image_bytes))
        
        # Конвертируем PIL Image в numpy array для OpenCV
        img_array = np.array(image)
        
        # Распознаем штрихкод
        if PYZBAR_AVAILABLE:
            decoded_objects = decode(img_array)
            
            if decoded_objects:
                barcode_data = decoded_objects[0].data.decode('utf-8')
                st.info(f"🔍 Найден штрихкод: {barcode_data}")
                
                # Отмечаем как отгруженный
                if mark_as_shipped(barcode_data):
                    st.balloons()
                    st.rerun()
            else:
                st.warning("❌ Штрихкод не распознан. Попробуйте еще раз или используйте ручной ввод.")
        else:
            st.error("⚠️ Библиотека распознавания недоступна. Используйте ручной ввод.")

# --- АЛЬТЕРНАТИВНЫЙ ВАРИАНТ: РУЧНОЙ ВВОД ---
st.header("⌨️ Ручной ввод (альтернатива)")

col1, col2 = st.columns([3, 1])
with col1:
    manual_barcode = st.text_input("Введите номер накладной:", key="manual_input")
with col2:
    if st.button("✅ Отгрузить"):
        if manual_barcode:
            if mark_as_shipped(manual_barcode):
                st.rerun()
        else:
            st.warning("Введите номер накладной")

# --- ОСТАВШИЕСЯ НАКЛАДНЫЕ ---
st.subheader("📦 Осталось отгрузить")
remaining = driver_df[driver_df["Статус"] != "Отгружено"]
if not remaining.empty:
    # Показываем только нужные колонки
    display_cols = ["Номера накладных", "Адрес"] if "Адрес" in remaining.columns else ["Номера накладных"]
    st.dataframe(remaining[display_cols], use_container_width=True, height=300)
else:
    st.success("🎉 Поздравляем! Все накладные отгружены!")

# --- МАРШРУТ ---
if "Адрес" in df.columns:
    st.subheader("🗺️ Маршрут")
    route = driver_df[driver_df["Статус"] != "Отгружено"].groupby("Адрес").size().reset_index(name="Количество накладных")
    if not route.empty:
        st.dataframe(route, use_container_width=True)
    else:
        st.info("🚚 Маршрут завершен!")

# --- ПРОГРЕСС-БАР ---
progress = done / total if total > 0 else 0
st.progress(progress, text=f"Прогресс: {done}/{total} ({int(progress*100)}%)")

# --- ОБНОВЛЕНИЕ ДАННЫХ ---
if st.button("🔄 Обновить данные"):
    st.rerun()
