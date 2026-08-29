import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import re
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem Pendaftaran Santri", page_icon="🕌", layout="wide")

# --- KONEKSI KE GOOGLE SHEETS & GEMINI API ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("⚠️ Secrets belum disetting dengan benar di Streamlit Cloud. Pastikan API Key dan JSON Google Cloud sudah dimasukkan.")
    st.stop()

# --- FUNGSI BACA SHEETS ---
@st.cache_data(ttl=10) # Refresh data setiap 10 detik agar web selalu update
def ambil_data_sheets():
    # =====================================================================
    # UBAH TEKS DI BAWAH INI DENGAN URL GOOGLE SHEETS ANDA YANG SEBENARNYA!
    # =====================================================================
    url_sheet = "https://docs.google.com/spreadsheets/d/1swPGZxF6d_yUkIeQn_Z_ew1yEE-lvqlEYoUG6I5a0Bk/edit?gid=0#gid=0" 
    
    try:
        df = conn.read(spreadsheet=url_sheet, usecols=list(range(10)))
        return df.dropna(how='all') # Buang baris yang kosong
    except Exception:
        # Jika gagal/kosong, buat format kolom standar
        return pd.DataFrame(columns=[
            "No_KK", "Alamat", "Nama_Santri", "NIK_Santri", "TTL_Santri", 
            "Status_Anak", "Nama_Ayah", "Pekerjaan_Ayah", "Nama_Ibu", "Pekerjaan_Ibu"
        ])

# --- AUTO-DETECT MODEL TERBAIK ---
def get_model():
    tersedia = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    for keyword in ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-flash', 'gemini-1.5-pro']:
        for m in tersedia:
            if keyword in m: return m
    return tersedia[0]

# --- FUNGSI BACA KARTU KELUARGA (AI) ---
def baca_kk_dengan_ai(img_file):
    model = genai.GenerativeModel(get_model())
    img = Image.open(img_file)
    prompt = """
    Ekstrak data Kartu Keluarga (KK) ini. Keluarkan output WAJIB dalam format JSON murni tanpa backtick atau teks lain:
    {"no_kk": "NOMOR KK", "alamat_lengkap": "ALAMAT LENGKAP", "anggota": [{"nama": "NAMA", "nik": "16 DIGIT NIK", "tempat_lahir": "TEMPAT LAHIR", "tanggal_lahir": "TANGGAL LAHIR", "jenis_kelamin": "LAKI/PEREMPUAN", "pendidikan": "PENDIDIKAN", "pekerjaan": "PEKERJAAN", "status_keluarga": "KEPALA KELUARGA/ISTRI/ANAK"}]}
    """
    response = model.generate_content([prompt, img])
    teks = re.sub(r'```json|```', '', response.text).strip()
    return json.loads(teks)

# ==========================================
# ANTARMUKA PENGGUNA (UI)
# ==========================================
st.title("🕌 Sistem Terpadu Pendataan Santri Baru")

# Membuat 3 Tab Menu
tab1, tab2, tab3 = st.tabs(["📥 1. Input Data KK", "📊 2. Rekap Database", "✏️ 3. Info & Edit"])

# Ambil data mutakhir dari Google Sheets
db_santri = ambil_data_sheets()

# ------------------------------------------
# TAB 1: INPUT DATA
# ------------------------------------------
with tab1:
    uploaded_file = st.file_uploader("Unggah foto Kartu Keluarga (JPG/PNG)", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        col_img, col_form = st.columns([1, 1])
        with col_img:
            st.image(uploaded_file, caption="Preview Dokumen", use_container_width=True)
            
        with col_form:
            if st.button("🚀 Proses AI Pembaca KK", type="primary"):
                with st.spinner("Membaca dan menganalisis data, mohon tunggu..."):
                    try:
                        hasil = baca_kk_dengan_ai(uploaded_file)
                        if hasil and 'anggota' in hasil:
                            st.session_state['temp_kk'] = hasil
                            st.success("✅ Dokumen berhasil dibaca!")
                        else:
                            st.error("❌ Gagal membaca dokumen. Struktur tidak sesuai.")
                    except Exception as e:
                        st.error(f"❌ Terjadi kesalahan: {e}")

        # Jika data sukses diurai, munculkan dropdown pemetaan
        if 'temp_kk' in st.session_state:
            data = st.session_state['temp_kk']
            opsi = [f"{p['nama']} ({p.get('status_keluarga', '-')})" for p in data['anggota']]
            
            # Cari default indeks
            def_ayah_idx = next((i for i, p in enumerate(data['anggota']) if "KEPALA" in str(p.get('status_keluarga')).upper()), 0)
            def_ibu_idx = next((i for i, p in enumerate(data['anggota']) if "ISTRI" in str(p.get('status_keluarga')).upper()), min(1, len(data['anggota'])-1))
            def_santri_idx = min(2, len(data['anggota'])-1)
            
            st.markdown("---")
            st.markdown("### 📋 Pemetaan Identitas Keluarga")
            c1, c2, c3 = st.columns(3)
            with c1: ayah_idx = st.selectbox("Pilih Ayah:", range(len(opsi)), format_func=lambda x: opsi[x], index=def_ayah_idx)
            with c2: ibu_idx = st.selectbox("Pilih Ibu:", range(len(opsi)), format_func=lambda x: opsi[x], index=def_ibu_idx)
            with c3: santri_idx = st.selectbox("Pilih Calon Santri:", range(len(opsi)), format_func=lambda x: opsi[x], index=def_santri_idx)
            
            if st.button("💾 Simpan Permanen ke Google Sheets", type="primary"):
                s = data['anggota'][santri_idx]
                a = data['anggota'][ayah_idx]
                i = data['anggota'][ibu_idx]
                nik_baru = str(s.get('nik')).strip()
                
                # FILTER ANTI DATA GANDA
                if not db_santri.empty and nik_baru in db_santri['NIK_Santri'].astype(str).str.strip().values:
                    st.error(f"⚠️ DATA DITOLAK! NIK {nik_baru} atas nama {s.get('nama')} sudah terdaftar di database.")
                else:
                    data_baru = pd.DataFrame([{
                        "No_KK": str(data.get('no_kk', '-')),
                        "Alamat": str(data.get('alamat_lengkap', '-')),
                        "Nama_Santri": str(s.get('nama', '-')),
                        "NIK_Santri": nik_baru,
                        "TTL_Santri": f"{s.get('tempat_lahir', '-')} , {s.get('tanggal_lahir', '-')}",
                        "Status_Anak": "Terekam Otomatis via AI",
                        "Nama_Ayah": str(a.get('nama', '-')),
                        "Pekerjaan_Ayah": str(a.get('pekerjaan', '-')),
                        "Nama_Ibu": str(i.get('nama', '-')),
                        "Pekerjaan_Ibu": str(i.get('pekerjaan', '-'))
                    }])
                    
                    # Menggabungkan data lama dan baru
                    db_update = pd.concat([db_santri, data_baru], ignore_index=True)
                    
                    # =====================================================================
                    # UBAH TEKS DI BAWAH INI DENGAN URL GOOGLE SHEETS ANDA YANG SEBENARNYA!
                    # =====================================================================
                    url_sheet = "PASTE_URL_GOOGLE_SHEETS_ANDA_DISINI"
                    
                    with st.spinner("Menulis ke Google Sheets..."):
                        conn.update(spreadsheet=url_sheet, data=db_update)
                    
                    st.success(f"✅ Alhamdulillah! Data santri {s.get('nama')} berhasil disimpan ke Cloud!")
                    st.cache_data.clear() # Paksa refresh data agar langsung muncul di Tab 2
                    del st.session_state['temp_kk'] # Bersihkan form pendaftaran

# ------------------------------------------
# TAB 2: REKAP DATABASE
# ------------------------------------------
with tab2:
    st.subheader("📋 Rekapitulasi Data Santri (Sinkronisasi Real-Time)")
    
    df_tampil = db_santri.copy()
    if not df_tampil.empty:
        # Mengubah nomor indeks tabel agar dimulai dari angka 1 (Bukan 0)
        df_tampil.index = range(1, len(df_tampil) + 1)
        
    st.dataframe(df_tampil, use_container_width=True)
    
    if not df_tampil.empty:
        st.info(f"Total santri terdaftar: {len(df_tampil)} anak.")

# ------------------------------------------
# TAB 3: EDIT DATA
# ------------------------------------------
with tab3:
    st.markdown("### ✏️ Koreksi & Pengeditan Data")
    st.info("""
    **Demi keamanan dan integritas data (agar format tidak berantakan), fitur pengeditan data dilakukan langsung melalui Google Sheets.**
    
    Langkah mengubah data jika ada kesalahan:
    1. Buka file Google Sheets Anda.
    2. Ubah data yang salah (misal: ada *typo* huruf pada nama atau alamat).
    3. Setelah diubah di Sheets, data di aplikasi web ini (pada **Tab 2**) akan otomatis ikut berubah menyesuaikan data terbaru.
    """)
