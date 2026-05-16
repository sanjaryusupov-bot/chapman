import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
from PIL import Image
from pyzbar.pyzbar import decode

st.set_page_config(layout="wide")

# --- GOOGLE ---
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

st.title("🚚 Отгрузка (камера)")

# --- водитель ---
driver = st.selectbox("Машина", df["Номер Машины"].dropna().unique())
driver_df = df[df["Номер Машины"] == driver]

total = len(driver_df)
done = len(driver_df[driver_df["Статус"] == "Отгружено"])

col1, col2, col3 = st.columns(3)
col1.metric("Всего", total)
col2.metric("Отгружено", done)
col3.metric("Осталось", total - done)

# --- звук ---
st.markdown("""
<audio id="ok" src="https://www.soundjay.com/buttons/sounds/button-3.mp3"></audio>
<script>
function ok(){document.getElementById("ok").play();}
</script>
""", unsafe_allow_html=True)

# --- функция ---
def mark(barcode):
    match = df[df["Номера накладных"].astype(str) == barcode]

    if not match.empty:
        row = match.index[0] + 2
        status = sheet.acell(f"D{row}").value

        if status == "Отгружено":
            st.warning(f"⚠️ Уже: {barcode}")
        else:
            sheet.update(f"D{row}", "Отгружено")
            sheet.update(f"E{row}", f"{driver} | {datetime.now()}")

            st.success(f"✅ {barcode}")
            st.markdown("<script>ok()</script>", unsafe_allow_html=True)
    else:
        st.error(f"❌ Нет: {barcode}")

# --- камера ---
st.subheader("📷 Сканируй")

img_file = st.camera_input("Наведи на штрихкод")

if img_file is not None:
    image = Image.open(img_file)
    decoded = decode(image)

    if decoded:
        barcode = decoded[0].data.decode("utf-8")
        st.write(f"Найден: {barcode}")
        mark(barcode)
    else:
        st.warning("Не удалось считать")

# --- остатки ---
st.subheader("📦 Осталось")
st.dataframe(driver_df[driver_df["Статус"] != "Отгружено"])

# --- маршрут ---
if "Адрес" in df.columns:
    st.subheader("🚚 Маршрут")
    route = driver_df[driver_df["Статус"] != "Отгружено"].groupby("Адрес").size().reset_index(name="Кол-во")
    st.dataframe(route)

# --- отчёт ---
st.subheader("📊 Отчёт")

report = pd.DataFrame({
    "Машина": [driver],
    "Всего": [total],
    "Отгружено": [done],
    "Осталось": [total - done],
    "Дата": [datetime.now()]
})

st.dataframe(report)
