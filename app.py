import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

st.set_page_config(
    page_title="🚚 Логистика PRO",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS для супер-дизайна ---
st.markdown("""
<style>
    /* Главный фон */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Карточки */
    .metric-card {
        background: white;
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        text-align: center;
        transition: transform 0.3s;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
    }
    
    .metric-value {
        font-size: 48px;
        font-weight: bold;
        color: #667eea;
    }
    
    .metric-label {
        font-size: 14px;
        color: #666;
        margin-top: 10px;
    }
    
    /* Кнопка камеры */
    .camera-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 50px;
        padding: 15px 40px;
        font-size: 18px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s;
        width: 100%;
    }
    
    .camera-btn:hover {
        transform: scale(1.05);
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    /* Таблица */
    .dataframe {
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
    }
    
    /* Заголовок */
    .main-title {
        text-align: center;
        color: white;
        font-size: 48px;
        margin-bottom: 30px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    
    /* Боковая панель */
    .sidebar-content {
        background: white;
        border-radius: 20px;
        padding: 20px;
        margin: 10px;
    }
    
    /* Анимация успеха */
    @keyframes success {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
    
    .success-animation {
        animation: success 0.5s ease;
    }
</style>
""", unsafe_allow_html=True)

# --- ЗАГОЛОВОК ---
st.markdown('<h1 class="main-title">🚚 Логистика PRO</h1>', unsafe_allow_html=True)

# --- ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(credentials)
        
        sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1soHrN7Iqd3jk9iLGdUGK9APxVfRBwWXHxoI8x2Hsh1o"
        ).worksheet("Отгрузка")
        
        return sheet
    except Exception as e:
        st.error(f"❌ Ошибка подключения: {e}")
        return None

# --- ЗАГРУЗКА ДАННЫХ ---
@st.cache_data(ttl=10)
def load_data():
    sheet = init_connection()
    if sheet:
        df = pd.DataFrame(sheet.get_all_records())
        return sheet, df
    return None, None

sheet, df = load_data()

if df is None or df.empty:
    st.error("❌ Не удалось загрузить данные")
    st.stop()

# --- САЙДБАР ДЛЯ ВЫБОРА МАШИНЫ ---
with st.sidebar:
    st.markdown('<div class="sidebar-content">', unsafe_allow_html=True)
    st.image("https://cdn-icons-png.flaticon.com/512/3413/3413013.png", width=80)
    st.markdown("### 🚛 Выберите автомобиль")
    
    if "Номер Машины" in df.columns:
        driver = st.selectbox("", df["Номер Машины"].dropna().unique(), label_visibility="collapsed")
        driver_df = df[df["Номер Машины"] == driver]
        
        total = len(driver_df)
        done = len(driver_df[driver_df["Статус"] == "Отгружено"])
        remaining = total - done
        
        st.markdown("---")
        st.markdown("### 📊 Статистика")
        st.metric("📦 Всего накладных", total)
        st.metric("✅ Отгружено", done)
        st.metric("⏳ Осталось", remaining, delta=f"{int(remaining/total*100) if total>0 else 0}%")
        
        # Прогресс-бар
        if total > 0:
            progress = done / total
            st.progress(progress, text=f"Прогресс: {int(progress*100)}%")
    else:
        st.error("Нет данных о машинах")
        st.stop()
    st.markdown('</div>', unsafe_allow_html=True)

# --- ОСНОВНОЙ КОНТЕНТ ---
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 📷 Сканирование штрихкода")
    st.markdown("Нажмите на кнопку и наведите камеру на штрихкод")
    
    # Кнопка для открытия камеры
    if st.button("📸 ОТКРЫТЬ КАМЕРУ", use_container_width=True, type="primary"):
        st.session_state.show_camera = True
    
    # Камера появляется только по кнопке
    if st.session_state.get('show_camera', False):
        st.markdown("### 🎥 Наведите на штрихкод")
        
        # HTML камера с авто-распознаванием
        camera_html = """
        <style>
            #reader {
                width: 100%;
                max-width: 500px;
                margin: 0 auto;
                border-radius: 20px;
                overflow: hidden;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            }
            .scanner-status {
                text-align: center;
                margin-top: 10px;
                font-size: 14px;
            }
            .close-btn {
                background: #ff4757;
                color: white;
                border: none;
                border-radius: 50px;
                padding: 10px 20px;
                margin-top: 10px;
                cursor: pointer;
            }
        </style>
        
        <div id="reader"></div>
        <div id="status" class="scanner-status">⏳ Ожидание сканирования...</div>
        <div style="text-align: center; margin-top: 10px;">
            <button onclick="closeCamera()" class="close-btn">✖️ Закрыть камеру</button>
        </div>
        
        <script src="https://unpkg.com/html5-qrcode@2.3.8/minified/html5-qrcode.min.js"></script>
        <script>
        let html5QrCode = null;
        
        function startScanner() {
            html5QrCode = new Html5Qrcode("reader");
            const config = {
                fps: 10,
                qrbox: { width: 300, height: 300 },
                aspectRatio: 1.0,
                formatsToSupport: [
                    Html5QrcodeSupportedFormats.QR_CODE,
                    Html5QrcodeSupportedFormats.CODE_128,
                    Html5QrcodeSupportedFormats.EAN_13,
                    Html5QrcodeSupportedFormats.CODE_39,
                    Html5QrcodeSupportedFormats.CODE_93,
                    Html5QrcodeSupportedFormats.ITF,
                    Html5QrcodeSupportedFormats.UPC_A,
                    Html5QrcodeSupportedFormats.UPC_E
                ]
            };
            
            html5QrCode.start(
                { facingMode: "environment" },
                config,
                (decodedText) => {
                    document.getElementById('status').innerHTML = '✅ Найден: ' + decodedText;
                    document.getElementById('status').style.color = 'green';
                    
                    // Отправляем в Streamlit
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.value = decodedText;
                    input.id = 'scanned_barcode';
                    document.body.appendChild(input);
                    input.dispatchEvent(new Event('input'));
                    
                    // Останавливаем сканер
                    if (html5QrCode) {
                        html5QrCode.stop();
                    }
                },
                (error) => {
                    console.log(error);
                }
            ).catch(err => {
                document.getElementById('status').innerHTML = '❌ Ошибка: ' + err;
                document.getElementById('status').style.color = 'red';
            });
        }
        
        function closeCamera() {
            if (html5QrCode) {
                html5QrCode.stop();
            }
            // Отправляем сигнал закрытия
            const input = document.createElement('input');
            input.type = 'text';
            input.value = '__CLOSE__';
            input.id = 'scanned_barcode';
            document.body.appendChild(input);
            input.dispatchEvent(new Event('input'));
        }
        
        startScanner();
        </script>
        """
        
        from streamlit.components.v1 import html
        html(camera_html, height=500)
        
        # Обработка сканирования
        if 'scanned_barcode' in st.session_state:
            barcode = st.session_state.scanned_barcode
            if barcode == '__CLOSE__':
                st.session_state.show_camera = False
                del st.session_state.scanned_barcode
                st.rerun()
            elif barcode:
                st.balloons()
                st.success(f"✅ Отсканировано: {barcode}")
                
                # Отмечаем отгрузку
                match = df[df["Номера накладных"].astype(str).str.strip() == barcode]
                if not match.empty:
                    row = match.index[0] + 2
                    sheet.update(f"D{row}", "Отгружено")
                    sheet.update(f"E{row}", f"{driver} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    st.success(f"🎉 Накладная {barcode} успешно отгружена!")
                    time.sleep(1)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"❌ Накладная {barcode} не найдена!")
                del st.session_state.scanned_barcode

with col2:
    st.markdown("### ⌨️ Быстрый ввод")
    
    with st.form(key="manual_form"):
        barcode_manual = st.text_input("Номер накладной", placeholder="Введите номер...")
        submitted = st.form_submit_button("✅ Отгрузить", use_container_width=True)
        
        if submitted and barcode_manual:
            match = df[df["Номера накладных"].astype(str).str.strip() == barcode_manual]
            if not match.empty:
                row = match.index[0] + 2
                sheet.update(f"D{row}", "Отгружено")
                sheet.update(f"E{row}", f"{driver} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                st.success(f"✅ Накладная {barcode_manual} отгружена!")
                st.cache_data.clear()
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("❌ Накладная не найдена!")

# --- ТАБЛИЦА ОСТАВШИХСЯ НАКЛАДНЫХ ---
st.markdown("---")
st.markdown("### 📋 Осталось отгрузить")

remaining_df = driver_df[driver_df["Статус"] != "Отгружено"]

if not remaining_df.empty:
    # Красивое отображение таблицы
    display_cols = []
    if "Номера накладных" in remaining_df.columns:
        display_cols.append("Номера накладных")
    if "Адрес" in remaining_df.columns:
        display_cols.append("Адрес")
    
    if display_cols:
        # Добавляем индексацию
        display_data = remaining_df[display_cols].reset_index(drop=True)
        display_data.index = display_data.index + 1
        st.dataframe(
            display_data,
            use_container_width=True,
            height=400,
            column_config={
                "index": "№",
                "Номера накладных": "Номер накладной",
                "Адрес": "Адрес доставки"
            }
        )
    else:
        st.dataframe(remaining_df, use_container_width=True)
else:
    st.success("🎉 Поздравляем! Все накладные отгружены!")

# --- ИНФОРМАЦИОННАЯ ПАНЕЛЬ ---
st.markdown("---")
col_info1, col_info2, col_info3 = st.columns(3)

with col_info1:
    st.info(f"🚛 **Текущий водитель:** {driver}")

with col_info2:
    if total > 0:
        percent = int((done / total) * 100)
        st.info(f"📊 **Выполнено:** {percent}%")

with col_info3:
    st.info(f"🕐 **Последнее обновление:** {datetime.now().strftime('%H:%M:%S')}")

# --- КНОПКА ОБНОВЛЕНИЯ ---
if st.button("🔄 Обновить данные", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
