import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

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

# --- ФУНКЦИЯ ОТМЕТКИ ---
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
            sheet.update(f"D{row}", "Отгружено")
            sheet.update(f"E{row}", f"{driver} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            st.success(f"✅ Накладная {barcode} отгружена!")
            st.balloons()
            return True
    else:
        st.error(f"❌ Накладная {barcode} не найдена!")
        return False

# --- СКАНИРОВАНИЕ КАМЕРОЙ ---
st.header("📷 Сканируйте QR-код")

scanner_html = """
<div style="text-align: center;">
    <div id="reader" style="width: 100%; max-width: 500px; margin: 0 auto;"></div>
    <div id="result" style="margin-top: 10px;"></div>
</div>
<script src="https://unpkg.com/html5-qrcode@2.3.8/minified/html5-qrcode.min.js"></script>
<script>
const html5QrCode = new Html5Qrcode("reader");
html5QrCode.start(
    { facingMode: "environment" },
    { fps: 10, qrbox: 250 },
    (decodedText) => {
        document.getElementById('result').innerHTML = '✅ Найдено: ' + decodedText;
        const input = document.createElement('input');
        input.type = 'text';
        input.value = decodedText;
        input.id = 'qr_scanned';
        document.body.appendChild(input);
        input.dispatchEvent(new Event('input'));
        html5QrCode.stop();
    },
    (error) => {}
).catch(err => {
    document.getElementById('result').innerHTML = '❌ Ошибка: ' + err;
});
</script>
"""

from streamlit.components.v1 import html
html(scanner_html, height=400)

if 'qr_scanned' in st.session_state:
    barcode = st.session_state.qr_scanned
    if mark_as_shipped(barcode):
        st.rerun()

# --- РУЧНОЙ ВВОД ---
st.markdown("---")
st.subheader("⌨️ Ручной ввод")

manual_barcode = st.text_input("Номер накладной:")
if st.button("Отгрузить") and manual_barcode:
    mark_as_shipped(manual_barcode)

# --- ПРОГРЕСС ---
st.markdown("---")
progress = done / total if total > 0 else 0
st.progress(progress, text=f"{done} из {total} ({int(progress*100)}%)")

st.subheader("📋 Осталось")
remaining = driver_df[driver_df["Статус"] != "Отгружено"]
if not remaining.empty:
    st.dataframe(remaining[["Номера накладных", "Адрес"]], use_container_width=True)
else:
    st.success("✅ Все отгружено!")
