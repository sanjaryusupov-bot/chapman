import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
from PIL import Image
import io
import base64
import json

st.set_page_config(layout="wide")

# --- ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS (ИСПРАВЛЕНО) ---
# Получаем credentials из secrets
creds_dict = dict(st.secrets["gcp_service_account"])

# Создаем credentials правильно
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Используем google.oauth2 вместо oauth2client
credentials = Credentials.from_service_account_info(
    creds_dict,
    scopes=scope
)

client = gspread.authorize(credentials)

# Открываем таблицу
sheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1soHrN7Iqd3jk9iLGdUGK9APxVfRBwWXHxoI8x2Hsh1o"
).worksheet("Отгрузка")

df = pd.DataFrame(sheet.get_all_records())

st.title("🚚 Отгрузка со сканером")

# --- ВЫБОР МАШИНЫ ---
if "Номер Машины" in df.columns:
    driver = st.selectbox("🚛 Выберите машину", df["Номер Машины"].dropna().unique())
    driver_df = df[df["Номер Машины"] == driver]

    total = len(driver_df)
    done = len(driver_df[driver_df["Статус"] == "Отгружено"])

    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Всего", total)
    col2.metric("✅ Отгружено", done)
    col3.metric("⏳ Осталось", total - done)
else:
    st.error("❌ В таблице нет колонки 'Номер Машины'")
    st.stop()

# --- ФУНКЦИЯ ОТМЕТКИ ОТГРУЗКИ ---
def mark_as_shipped(barcode):
    barcode = str(barcode).strip()
    
    # Ищем накладную
    if "Номера накладных" not in df.columns:
        st.error("❌ В таблице нет колонки 'Номера накладных'")
        return False
        
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
            st.balloons()
            return True
    else:
        st.error(f"❌ Накладная {barcode} не найдена!")
        return False

# --- СКАНИРОВАНИЕ КАМЕРОЙ ТЕЛЕФОНА ---
st.header("📷 Сканирование штрихкода")

# JavaScript для захвата фото с камеры телефона
camera_html = """
<div style="text-align: center; padding: 10px;">
    <video id="video" width="100%" autoplay playsinline style="border: 2px solid #ddd; border-radius: 10px; max-width: 500px;"></video>
    <div style="margin-top: 10px;">
        <button id="capture" style="padding: 12px 24px; font-size: 18px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer;">📸 Сканировать</button>
    </div>
    <div id="result" style="margin-top: 10px; font-size: 14px; color: #666;"></div>
</div>

<script>
let video = document.getElementById('video');
let captureBtn = document.getElementById('capture');
let resultDiv = document.getElementById('result');

// Запуск камеры
navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
    .then(function(stream) {
        video.srcObject = stream;
        resultDiv.innerHTML = '✅ Камера готова';
        resultDiv.style.color = 'green';
    })
    .catch(function(err) {
        resultDiv.innerHTML = '❌ Ошибка доступа к камере: ' + err.message;
        resultDiv.style.color = 'red';
    });

// Функция захвата и отправки фото
captureBtn.addEventListener('click', function() {
    let canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    let ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Получаем base64 изображения
    let imageData = canvas.toDataURL('image/jpeg', 0.8);
    
    // Отправляем в Streamlit
    const input = document.createElement('input');
    input.type = 'text';
    input.id = 'scanned_image';
    input.value = imageData;
    document.body.appendChild(input);
    input.dispatchEvent(new Event('input'));
    
    resultDiv.innerHTML = '📷 Обработка...';
});
</script>
"""

# Отображаем компонент камеры
from streamlit.components.v1 import html
html(camera_html, height=450)

# Обработка полученного изображения
if 'scanned_image' in st.session_state:
    image_data = st.session_state.scanned_image
    if image_data:
        st.info("🔍 Распознаем штрихкод...")
        
        # Здесь нужен сервис распознавания штрихкодов
        # Пока используем ручной ввод
        st.warning("⚠️ Для распознавания штрихкодов нужно подключить API (например, Google Vision)")
        st.info("💡 Используйте поле ручного ввода ниже")

# --- РУЧНОЙ ВВОД (ОСНОВНОЙ СПОСОБ) ---
st.header("⌨️ Ввод номера накладной")

col1, col2 = st.columns([3, 1])
with col1:
    manual_barcode = st.text_input("Введите или отсканируйте номер накладной:", key="manual_input", placeholder="Например: INV-001")
with col2:
    if st.button("✅ Отгрузить", type="primary"):
        if manual_barcode:
            if mark_as_shipped(manual_barcode):
                st.rerun()
        else:
            st.warning("Введите номер накладной")

# --- ПРОГРЕСС ОТГРУЗКИ ---
st.subheader("📦 Прогресс отгрузки")

progress = done / total if total > 0 else 0
st.progress(progress, text=f"Выполнено: {done} из {total} ({int(progress*100)}%)")

# --- ОСТАВШИЕСЯ НАКЛАДНЫЕ ---
st.subheader("📋 Осталось отгрузить")

remaining = driver_df[driver_df["Статус"] != "Отгружено"]
if not remaining.empty:
    # Выбираем колонки для отображения
    display_cols = []
    if "Номера накладных" in remaining.columns:
        display_cols.append("Номера накладных")
    if "Адрес" in remaining.columns:
        display_cols.append("Адрес")
    
    if display_cols:
        st.dataframe(remaining[display_cols], use_container_width=True, height=300)
    else:
        st.dataframe(remaining, use_container_width=True, height=300)
else:
    st.success("🎉 Поздравляем! Все накладные отгружены!")

# --- МАРШРУТ ---
if "Адрес" in df.columns:
    st.subheader("🗺️ Маршрут")
    route = driver_df[driver_df["Статус"] != "Отгружено"].groupby("Адрес").size().reset_index(name="Количество")
    if not route.empty:
        st.dataframe(route, use_container_width=True)
    else:
        st.info("🚚 Маршрут завершен!")

# --- КНОПКА ОБНОВЛЕНИЯ ---
if st.button("🔄 Обновить данные"):
    st.rerun()

# --- СТАТИСТИКА ---
st.subheader("📊 Статистика по всем машинам")
if "Номер Машины" in df.columns:
    all_stats = df.groupby("Номер Машины").agg({
        "Номера накладных": "count",
        "Статус": lambda x: (x == "Отгружено").sum()
    }).reset_index()
    all_stats.columns = ["Машина", "Всего", "Отгружено"]
    all_stats["Осталось"] = all_stats["Всего"] - all_stats["Отгружено"]
    st.dataframe(all_stats, use_container_width=True)
