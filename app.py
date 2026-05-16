import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
from PIL import Image
import io
import re

# Альтернатива для pyzbar - используем простой OCR или ручной ввод
try:
    from pyzbar.pyzbar import decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    st.warning("⚠️ Автоматическое распознавание штрихкодов недоступно. Используйте ручной ввод.")

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

st.title("🚚 Отгрузка")

# --- водитель ---
driver = st.selectbox("Машина", df["Номер Машины"].dropna().unique())
driver_df = df[df["Номер Машины"] == driver]

total = len(driver_df)
done = len(driver_df[driver_df["Статус"] == "Отгружено"])

col1, col2, col3 = st.columns(3)
col1.metric("Всего", total)
col2.metric("Отгружено", done)
col3.metric("Осталось", total - done)

# --- звук (альтернативный способ) ---
st.markdown("""
<script>
function playSound() {
    var audio = new Audio('https://www.soundjay.com/buttons/sounds/button-3.mp3');
    audio.play();
}
</script>
""", unsafe_allow_html=True)

# --- функция маркировки ---
def mark(barcode):
    # Очищаем штрихкод от лишних символов
    barcode = str(barcode).strip()
    
    # Ищем совпадение
    match = df[df["Номера накладных"].astype(str).str.strip() == barcode]

    if not match.empty:
        row = match.index[0] + 2
        status = sheet.acell(f"D{row}").value

        if status == "Отгружено":
            st.warning(f"⚠️ Уже отгружено: {barcode}")
        else:
            sheet.update(f"D{row}", "Отгружено")
            sheet.update(f"E{row}", f"{driver} | {datetime.now()}")

            st.success(f"✅ Отгружено: {barcode}")
            # Вызываем звук через JS
            st.markdown("<script>playSound()</script>", unsafe_allow_html=True)
            st.rerun()
    else:
        st.error(f"❌ Не найден: {barcode}")

# --- ручной ввод (работает всегда) ---
st.subheader("⌨️ Ручной ввод")
barcode_input = st.text_input("Введите номер накладной или отсканируйте штрихкод:", key="barcode_input")
if barcode_input:
    mark(barcode_input)
    st.session_state.barcode_input = ""  # Очищаем поле
    st.rerun()

# --- камера (если доступна библиотека) ---
if PYZBAR_AVAILABLE:
    st.subheader("📷 Сканирование камерой")
    img_file = st.camera_input("Наведите на штрихкод")

    if img_file is not None:
        image = Image.open(img_file)
        decoded = decode(image)

        if decoded:
            barcode = decoded[0].data.decode("utf-8")
            st.write(f"Найден штрихкод: {barcode}")
            mark(barcode)
        else:
            st.warning("Штрихкод не распознан. Используйте ручной ввод.")
else:
    st.info("💡 Для сканирования камерой установите библиотеки: \n```\npip install pyzbar opencv-python-headless\n```\nПока используйте ручной ввод.")

# --- остатки ---
st.subheader("📦 Осталось отгрузить")
remaining_df = driver_df[driver_df["Статус"] != "Отгружено"]
if not remaining_df.empty:
    st.dataframe(remaining_df[["Номера накладных", "Адрес"]], use_container_width=True)
else:
    st.success("🎉 Все накладные отгружены!")

# --- маршрут ---
if "Адрес" in df.columns:
    st.subheader("🚚 Маршрут")
    route = driver_df[driver_df["Статус"] != "Отгружено"].groupby("Адрес").size().reset_index(name="Кол-во")
    if not route.empty:
        st.dataframe(route, use_container_width=True)
    else:
        st.info("Маршрут завершён")

# --- отчёт по машине ---
st.subheader("📊 Отчёт по машине")

# Получаем все машины для отчёта
all_trucks = df.groupby("Номер Машины").agg({
    "Номера накладных": "count",
    "Статус": lambda x: (x == "Отгружено").sum()
}).reset_index()

all_trucks.columns = ["Машина", "Всего", "Отгружено"]
all_trucks["Осталось"] = all_trucks["Всего"] - all_trucks["Отгружено"]

st.dataframe(all_trucks, use_container_width=True)

# --- экспорт отчёта ---
if st.button("📥 Скачать отчёт"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv = all_trucks.to_csv(index=False)
    st.download_button(
        label="💾 Скачать CSV",
        data=csv,
        file_name=f"otgruzka_report_{timestamp}.csv",
        mime="text/csv"
    )
