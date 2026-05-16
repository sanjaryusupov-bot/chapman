import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import av
from pyzbar import pyzbar

# --- CONFIG ---
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

data = sheet.get_all_records()
df = pd.DataFrame(data)

st.title("🚚 Система отгрузки (WMS Lite)")

# --- ВЫБОР ВОДИТЕЛЯ ---
drivers = df["Номер Машины"].dropna().unique()
driver = st.selectbox("Выбери машину", drivers)

driver_df = df[df["Номер Машины"] == driver]

# --- МЕТРИКИ ---
total = len(driver_df)
done = len(driver_df[driver_df["Статус"] == "Отгружено"])

col1, col2, col3 = st.columns(3)
col1.metric("Всего", total)
col2.metric("Отгружено", done)
col3.metric("Осталось", total - done)

# --- ЗВУК ---
st.markdown("""
<audio id="success_sound" src="https://www.soundjay.com/buttons/sounds/button-3.mp3"></audio>
<script>
function playSound(){
    document.getElementById("success_sound").play();
}
</script>
""", unsafe_allow_html=True)

# --- ФУНКЦИЯ ОБНОВЛЕНИЯ ---
def mark_shipment(barcode):
    global df

    match = df[df["Номера накладных"].astype(str) == barcode]

    if not match.empty:
        row = match.index[0] + 2
        current_status = sheet.acell(f"D{row}").value

        if current_status == "Отгружено":
            st.warning(f"⚠️ Уже отгружено: {barcode}")
        else:
            sheet.update(f"D{row}", "Отгружено")
            sheet.update(f"E{row}", f"{driver} | {datetime.now()}")

            st.success(f"✅ Отгружено: {barcode}")
            st.markdown("<script>playSound()</script>", unsafe_allow_html=True)
    else:
        st.error(f"❌ Не найдено: {barcode}")

# --- РУЧНОЙ СКАН (на всякий случай) ---
barcode_manual = st.text_input("🔎 Вставь или сканируй ШК")

if barcode_manual:
    mark_shipment(barcode_manual)

# --- КАМЕРА ---
st.subheader("📷 Сканирование через камеру")

class BarcodeScanner(VideoTransformerBase):
    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        barcodes = pyzbar.decode(img)

        for barcode in barcodes:
            code = barcode.data.decode("utf-8")
            st.session_state["last_code"] = code

        return img

webrtc_streamer(key="scanner", video_transformer_factory=BarcodeScanner)

# --- ОБРАБОТКА СКАНА С КАМЕРЫ ---
if "last_code" in st.session_state:
    code = st.session_state["last_code"]
    mark_shipment(code)
    del st.session_state["last_code"]

# --- ОСТАТКИ ---
st.subheader("📦 Осталось")
remaining = driver_df[driver_df["Статус"] != "Отгружено"]
st.dataframe(remaining)

# --- МАРШРУТНЫЙ ЛИСТ ---
st.subheader("🚚 Маршрутный лист")

if "Адрес" in df.columns:
    route = remaining.groupby("Адрес").size().reset_index(name="Кол-во")
    st.dataframe(route)

# --- ОТЧЁТ ---
st.subheader("📊 Отчёт по водителю")

report = pd.DataFrame({
    "Машина": [driver],
    "Всего": [total],
    "Отгружено": [done],
    "Осталось": [total - done],
    "Дата": [datetime.now()]
})

st.dataframe(report)

# --- ВЫГРУЗКА ---
csv = report.to_csv(index=False).encode("utf-8")
st.download_button("📥 Скачать отчёт", csv, "report.csv", "text/csv")