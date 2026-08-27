import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import re
import pandas as pd

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem Pendaftaran Santri", page_icon="🕌", layout="wide")

# --- INISIALISASI DATABASE SEMENTARA ---
# Ini digunakan agar kita bisa mencoba fitur rekap & edit sebelum menyambung ke Google Sheets asli
if 'db_santri' not in st.session_state:
    st.session_state['db_santri'] = pd.DataFrame(columns=[
        "No_KK", "Alamat", "Nama_Santri", "NIK_Santri", "TTL_Santri", "Status_Anak",
        "Nama_Ayah", "Pekerjaan_Ayah", "Nama_Ibu", "Pekerjaan_Ibu"
    ])

# --- AUTENTIKASI API KEY AMAN ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except KeyError:
    st.error("⚠️ API Key belum disetting di Streamlit Secrets! Buka pengaturan Streamlit Cloud Anda.")
    st.stop()

# Auto-detect model terbaik
def get_model():
    tersedia = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    for keyword in ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-flash', 'gemini-1.5-pro']:
        for m in tersedia:
            if keyword in m: return m
    return tersedia[0]

# Fungsi Baca KK
def baca_kk_dengan_ai(img_file):
    model = genai.GenerativeModel(get_model())
    img = Image.open(img_file)
    prompt = """
    Ekstrak data KK. Format output WAJIB JSON:
    {"no_kk": "...", "alamat_lengkap": "...", "anggota": [{"nama": "...", "nik": "...", "tempat_lahir": "...", "tanggal_lahir": "...", "jenis_kelamin": "...", "pendidikan": "...", "pekerjaan": "...", "status_keluarga": "..."}]}
    """
    response = model.generate_content([prompt, img])
    teks = re.sub(r'```json|```', '', response.text).strip()
    return json.loads(teks)

st.title("🕌 Sistem Terpadu Pendataan Santri Baru")

# --- MEMBUAT 3 TAB MENU UTAMA ---
tab1, tab2, tab3 = st.tabs(["📥 1. Input Data KK", "📊 2. Rekap Database", "✏️ 3. Edit Data"])

# ==========================================
# TAB 1: INPUT DATA
# ==========================================
with tab1:
    uploaded_file = st.file_uploader("Unggah foto Kartu Keluarga (JPG/PNG)", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        col_img, col_form = st.columns([1, 1])
        with col_img:
            st.image(uploaded_file, caption="Preview Dokumen")
            
        with col_form:
            if st.button("🚀 Proses AI Pembaca KK", type="primary"):
                with st.spinner("Membaca data..."):
                    hasil = baca_kk_dengan_ai(uploaded_file)
                    if hasil and 'anggota' in hasil:
                        st.session_state['temp_kk'] = hasil
                        st.success("Berhasil dibaca!")
                    else:
                        st.error("Gagal membaca dokumen.")

        # Jika berhasil dibaca, munculkan dropdown pemetaan
        if 'temp_kk' in st.session_state:
            data = st.session_state['temp_kk']
            opsi = [f"{p['nama']} ({p['status_keluarga']})" for p in data['anggota']]
            
            st.markdown("### Pemetaan Anggota Keluarga")
            c1, c2, c3 = st.columns(3)
            with c1: ayah_idx = st.selectbox("Ayah:", range(len(opsi)), format_func=lambda x: opsi[x])
            with c2: ibu_idx = st.selectbox("Ibu:", range(len(opsi)), format_func=lambda x: opsi[x])
            with c3: santri_idx = st.selectbox("Santri:", range(len(opsi)), format_func=lambda x: opsi[x])
            
            if st.button("💾 Simpan ke Database"):
                s = data['anggota'][santri_idx]
                a = data['anggota'][ayah_idx]
                i = data['anggota'][ibu_idx]
                
                # Tambahkan ke DataFrame (Database Sementara)
                data_baru = pd.DataFrame([{
                    "No_KK": data.get('no_kk'),
                    "Alamat": data.get('alamat_lengkap'),
                    "Nama_Santri": s.get('nama'),
                    "NIK_Santri": s.get('nik'),
                    "TTL_Santri": f"{s.get('tempat_lahir')}, {s.get('tanggal_lahir')}",
                    "Status_Anak": "Terekam Otomatis",
                    "Nama_Ayah": a.get('nama'),
                    "Pekerjaan_Ayah": a.get('pekerjaan'),
                    "Nama_Ibu": i.get('nama'),
                    "Pekerjaan_Ibu": i.get('pekerjaan')
                }])
                st.session_state['db_santri'] = pd.concat([st.session_state['db_santri'], data_baru], ignore_index=True)
                st.success(f"✅ Data {s.get('nama')} berhasil masuk ke Database!")
                del st.session_state['temp_kk'] # Reset form

# ==========================================
# TAB 2: REKAP DATABASE
# ==========================================
with tab2:
    st.subheader("📋 Rekapitulasi Data Santri")
    st.dataframe(st.session_state['db_santri'], use_container_width=True)
    
    # Tombol Download Massal
    if not st.session_state['db_santri'].empty:
        csv = st.session_state['db_santri'].to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Database (CSV)", data=csv, file_name="database_santri.csv", mime="text/csv")

# ==========================================
# TAB 3: EDIT DATA
# ==========================================
with tab3:
    st.subheader("✏️ Koreksi Data Santri")
    if st.session_state['db_santri'].empty:
        st.info("Database masih kosong. Input data terlebih dahulu.")
    else:
        # Pilih santri yang mau diedit
        df = st.session_state['db_santri']
        pilihan_nama = st.selectbox("Pilih nama santri yang akan diedit:", df['Nama_Santri'].tolist())
        
        # Cari baris data santri tersebut
        idx = df[df['Nama_Santri'] == pilihan_nama].index[0]
        data_lama = df.iloc[idx]
        
        # Tampilkan form edit
        with st.form("form_edit"):
            st.markdown("Ubah data di bawah ini jika ada kesalahan dari pembacaan AI:")
            e_nama = st.text_input("Nama Santri", value=data_lama['Nama_Santri'])
            e_nik = st.text_input("NIK Santri", value=data_lama['NIK_Santri'])
            e_alamat = st.text_area("Alamat", value=data_lama['Alamat'])
            e_ayah = st.text_input("Nama Ayah", value=data_lama['Nama_Ayah'])
            e_ibu = st.text_input("Nama Ibu", value=data_lama['Nama_Ibu'])
            
            submit_edit = st.form_submit_button("Simpan Perubahan")
            
            if submit_edit:
                # Update database
                st.session_state['db_santri'].at[idx, 'Nama_Santri'] = e_nama
                st.session_state['db_santri'].at[idx, 'NIK_Santri'] = e_nik
                st.session_state['db_santri'].at[idx, 'Alamat'] = e_alamat
                st.session_state['db_santri'].at[idx, 'Nama_Ayah'] = e_ayah
                st.session_state['db_santri'].at[idx, 'Nama_Ibu'] = e_ibu
                st.success("✅ Data berhasil diperbarui! Silakan cek di Tab 2.")
