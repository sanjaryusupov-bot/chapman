import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

st.title("🚚 Отгрузка товаров")

# --- ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ---
try:
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(credentials)
    
    # Открываем таблицу
    spreadsheet = client.open_by_url(
        "https://docs.google.com/spreadsheets/d/1soHrN7Iqd3jk9iLGdUGK9APxVfRBwWXHxoI8x2Hsh1o"
    )
    
    # Пробуем найти лист "Отгрузка" или берем первый
    try:
        sheet = spreadsheet.worksheet("Отгрузка")
    except:
        sheet = spreadsheet.get_worksheet(0)
        st.info(f"Используется лист: {sheet.title}")
    
    # Загружаем данные
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    st.success("✅ Подключено к Google Sheets")
    
except Exception as e:
    st.error(f"❌ Ошибка: {e}")
    st.stop()

# --- ВЫБОР МАШИНЫ ---
if "Номер Машины" in df.columns:
    driver = st.selectbox("Выберите машину", df["Номер Машины"].dropna().unique())
    driver_df = df[df["Номер Машины"] == driver]
    
    total = len(driver_df)
    done = len(driver_df[driver_df["Статус"] == "Отгружено"])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Всего", total)
    col2.metric("Отгружено", done)
    col3.metric("Осталось", total - done)
else:
    st.error("Нет колонки 'Номер Машины'")
    st.stop()

# --- ФУНКЦИЯ ДЛЯ ОБНОВЛЕНИЯ СТАТУСА ---
def update_status(barcode):
    try:
        # Ищем строку с таким номером накладной
        for i, row in enumerate(data, start=2):
            if str(row.get("Номера накладных", "")).strip() == str(barcode).strip():
                # Проверяем текущий статус
                current = sheet.cell(i, 4).value  # Колонка D
                
                if current == "Отгружено":
                    st.warning(f"⚠️ {barcode} уже отгружен")
                    return False
                else:
                    # Обновляем статус
                    sheet.update_cell(i, 4, "Отгружено")  # Колонка D
                    sheet.update_cell(i, 5, f"{driver} | {datetime.now()}")  # Колонка E
                    st.success(f"✅ {barcode} отгружен!")
                    st.balloons()
                    return True
        
        st.error(f"❌ {barcode} не найден")
        return False
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return False

# --- РУЧНОЙ ВВОД (РАБОТАЕТ ВСЕГДА) ---
st.header("⌨️ Ручной ввод")

col1, col2 = st.columns([3, 1])
with col1:
    barcode_input = st.text_input("Введите номер накладной:", key="manual")
with col2:
    if st.button("Отгрузить", type="primary"):
        if barcode_input:
            if update_status(barcode_input):
                st.rerun()

# --- КАМЕРА (ПРОСТОЙ ВАРИАНТ) ---
st.header("📷 Или отсканируйте")

# HTML камера с кнопкой
camera_html = """
<div style="text-align: center; padding: 20px;">
    <video id="video" autoplay playsinline style="width: 100%; max-width: 400px; border-radius: 10px; border: 2px solid #ddd;"></video>
    <br><br>
    <button onclick="takePhoto()" style="background-color: #4CAF50; color: white; padding: 12px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer;">
        📸 Сделать фото
    </button>
    <canvas id="canvas" style="display: none;"></canvas>
    <div id="result" style="margin-top: 10px;"></div>
</div>

<script>
let video = document.getElementById('video');
let canvas = document.getElementById('canvas');
let stream = null;

// Запуск камеры
navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
    .then(function(s) {
        stream = s;
        video.srcObject = stream;
    })
    .catch(function(err) {
        document.getElementById('result').innerHTML = '❌ Ошибка: ' + err.message;
    });

function takePhoto() {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    
    // Конвертируем в base64
    let imageData = canvas.toDataURL('image/jpeg', 0.8);
    
    // Отправляем в Streamlit
    const input = document.createElement('input');
    input.type = 'text';
    input.value = imageData;
    input.id = 'photo_data';
    document.body.appendChild(input);
    input.dispatchEvent(new Event('input'));
    
    document.getElementById('result').innerHTML = '📷 Фото сделано!';
}
</script>
"""

from streamlit.components.v1 import html
html(camera_html, height=400)

# Обработка фото
if 'photo_data' in st.session_state:
    photo_data = st.session_state.photo_data
    st.info("📷 Фото получено! Введите номер накладной вручную (распознавание пока не работает)")
    # Для распознавания нужно API, пока предлагаем ручной ввод
    del st.session_state.photo_data

# --- ОСТАВШИЕСЯ НАКЛАДНЫЕ ---
st.subheader("📦 Осталось отгрузить")

remaining = driver_df[driver_df["Статус"] != "Отгружено"]
if not remaining.empty:
    # Показываем таблицу
    cols_to_show = []
    if "Номера накладных" in remaining.columns:
        cols_to_show.append("Номера накладных")
    if "Адрес" in remaining.columns:
        cols_to_show.append("Адрес")
    
    if cols_to_show:
        st.dataframe(remaining[cols_to_show], use_container_width=True)
    else:
        st.dataframe(remaining, use_container_width=True)
else:
    st.success("🎉 Все отгружено!")

# --- ПРОГРЕСС ---
if total > 0:
    progress = done / total
    st.progress(progress, text=f"{int(progress*100)}% выполнено")

# --- КНОПКА ОБНОВЛЕНИЯ ---
if st.button("🔄 Обновить"):
    st.rerun()
