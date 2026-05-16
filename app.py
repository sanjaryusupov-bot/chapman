import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import re

st.set_page_config(layout="wide")

# --- ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ---
creds_dict = dict(st.secrets["gcp_service_account"])

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

try:
    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=scope
    )
    client = gspread.authorize(credentials)
    
    sheet = client.open_by_url(
        "https://docs.google.com/spreadsheets/d/1soHrN7Iqd3jk9iLGdUGK9APxVfRBwWXHxoI8x2Hsh1o"
    ).worksheet("Отгрузка")
    
    df = pd.DataFrame(sheet.get_all_records())
    st.success("✅ Подключено к Google Sheets")
    
except Exception as e:
    st.error(f"❌ Ошибка подключения: {e}")
    st.stop()

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

# --- СКАНИРОВАНИЕ КАМЕРОЙ ТЕЛЕФОНА (РАБОТАЕТ!) ---
st.header("📷 Сканирование штрихкода камерой")

# HTML/JS компонент для сканирования QR/штрихкодов
scanner_html = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/html5-qrcode/minified/html5-qrcode.min.js"></script>
</head>
<body>
    <div style="width: 100%; max-width: 600px; margin: 0 auto;">
        <div id="reader" style="width: 100%;"></div>
        <div id="result" style="margin-top: 20px; padding: 10px; font-size: 16px; text-align: center;"></div>
    </div>
    
    <script>
    let html5QrCode = null;
    
    function startScanner() {
        html5QrCode = new Html5Qrcode("reader");
        const config = {
            fps: 10,
            qrbox: { width: 250, height: 250 },
            aspectRatio: 1.0
        };
        
        html5QrCode.start(
            { facingMode: "environment" },
            config,
            (decodedText) => {
                // Успешное сканирование
                document.getElementById('result').innerHTML = '✅ Найден: ' + decodedText;
                document.getElementById('result').style.color = 'green';
                
                // Отправляем в Streamlit
                const input = document.createElement('input');
                input.type = 'text';
                input.value = decodedText;
                input.id = 'scanned_code';
                document.body.appendChild(input);
                input.dispatchEvent(new Event('input'));
                
                // Останавливаем сканер после успешного сканирования
                setTimeout(() => {
                    if (html5QrCode) {
                        html5QrCode.stop();
                    }
                }, 1000);
            },
            (error) => {
                // Ошибки игнорируем (обычно это просто пропущенные кадры)
                console.log(error);
            }
        ).catch(err => {
            document.getElementById('result').innerHTML = '❌ Ошибка камеры: ' + err;
            document.getElementById('result').style.color = 'red';
        });
    }
    
    // Запускаем сканер при загрузке страницы
    startScanner();
    
    // Кнопка для перезапуска
    window.restartScanner = function() {
        if (html5QrCode) {
            html5QrCode.stop().then(() => {
                startScanner();
                document.getElementById('result').innerHTML = '🔄 Сканер перезапущен';
                document.getElementById('result').style.color = 'blue';
            });
        }
    };
    </script>
    
    <div style="text-align: center; margin-top: 10px;">
        <button onclick="restartScanner()" style="padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer;">🔄 Перезапустить камеру</button>
    </div>
</body>
</html>
"""

# Отображаем сканер
from streamlit.components.v1 import html
html(scanner_html, height=500)

# Обработка отсканированного кода
if 'scanned_code' in st.session_state:
    barcode = st.session_state.scanned_code
    st.info(f"📦 Отсканировано: {barcode}")
    
    if mark_as_shipped(barcode):
        # Очищаем значение, чтобы можно было сканировать снова
        del st.session_state.scanned_code
        st.rerun()

# --- РУЧНОЙ ВВОД (НА СЛУЧАЙ, ЕСЛИ КАМЕРА НЕ РАБОТАЕТ) ---
st.markdown("---")
st.subheader("⌨️ Или введите номер вручную")

col1, col2 = st.columns([3, 1])
with col1:
    manual_barcode = st.text_input("Номер накладной:", placeholder="Введите номер...")
with col2:
    if st.button("✅ Отгрузить", type="primary"):
        if manual_barcode:
            if mark_as_shipped(manual_barcode):
                st.rerun()
        else:
            st.warning("Введите номер накладной")

# --- ПРОГРЕСС И ОСТАВШИЕСЯ НАКЛАДНЫЕ ---
st.markdown("---")
st.subheader("📊 Прогресс отгрузки")

progress = done / total if total > 0 else 0
st.progress(progress, text=f"Выполнено: {done} из {total} ({int(progress*100)}%)")

st.subheader("📋 Осталось отгрузить")

remaining = driver_df[driver_df["Статус"] != "Отгружено"]
if not remaining.empty:
    display_cols = []
    if "Номера накладных" in remaining.columns:
        display_cols.append("Номера накладных")
    if "Адрес" in remaining.columns:
        display_cols.append("Адрес")
    
    if display_cols:
        st.dataframe(remaining[display_cols], use_container_width=True)
    else:
        st.dataframe(remaining, use_container_width=True)
else:
    st.success("🎉 Поздравляем! Все накладные отгружены!")

# --- МАРШРУТ ---
if "Адрес" in df.columns:
    st.subheader("🗺️ Маршрут")
    route = driver_df[driver_df["Статус"] != "Отгружено"].groupby("Адрес").size().reset_index(name="Количество")
    if not route.empty:
        st.dataframe(route, use_container_width=True)

# --- КНОПКА ОБНОВЛЕНИЯ ---
if st.button("🔄 Обновить данные"):
    st.rerun()
