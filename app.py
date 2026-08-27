import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import re
import pandas as pd
import io

# --- KONFIGURASI HALAMAN STREAMLIT ---
st.set_page_config(
    page_title="Pencatat Data Santri Otomatis (KK)",
    page_icon="📜",
    layout="centered"
)

st.title("📜 Ekstraktor KK Otomatis untuk Database Pesantren")
st.markdown("Unggah foto Kartu Keluarga (KK), pilih anggota keluarga, dan data siap disimpan ke database.")

# --- SIDEBAR: PENGATURAN API KEY ---
st.sidebar.header("⚙️ Konfigurasi")
# Operator bisa memasukkan API Key mereka sendiri lewat sidebar web
api_key_input = st.sidebar.text_input("Masukkan Gemini API Key:", type="password")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tips:** Dapatkan API Key gratis di [Google AI Studio](https://aistudio.google.com/app/apikey).")

# --- FUNGSI UTAMA AI ---
def baca_kk_dengan_ai(img_file, api_key):
    genai.configure(api_key=api_key)
    
    # Auto-detect model terbaik yang tersedia
    tersedia = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    nama_model = 'gemini-1.5-flash' # Default
    for keyword in ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-flash', 'gemini-1.5-pro', 'gemini-pro']:
        for m in tersedia:
            if keyword in m:
                nama_model = m
                break
        if nama_model: break

    model = genai.GenerativeModel(nama_model)
    img = Image.open(img_file)
    
    prompt = """
    Kamu adalah sistem ekstraksi dokumen kependudukan profesional. Analisis foto Kartu Keluarga ini dan ekstrak data berikut secara akurat:
    1. Nomor KK
    2. Alamat lengkap (Alamat, RT/RW, Desa/Kelurahan, Kecamatan, Kabupaten/Kota, Provinsi, Kode Pos)
    3. Daftar seluruh anggota keluarga di tabel, meliputi:
       - Nama Lengkap
       - NIK (16 digit)
       - Tempat Lahir
       - Tanggal Lahir (DD-MM-YYYY)
       - Jenis Kelamin (LAKI-LAKI / PEREMPUAN)
       - Pendidikan Terakhir
       - Jenis Pekerjaan
       - Status Hubungan Dalam Keluarga (KEPALA KELUARGA / ISTRI / ANAK)

    Keluarkan output HANYA dalam format JSON tulen tanpa teks pengantar, dengan struktur persis seperti ini:
    {
      "no_kk": "NOMOR_KK",
      "alamat_lengkap": "ALAMAT LENGKAP",
      "anggota": [
        {
          "nama": "...",
          "nik": "...",
          "tempat_lahir": "...",
          "tanggal_lahir": "...",
          "jenis_kelamin": "...",
          "pendidikan": "...",
          "pekerjaan": "...",
          "status_keluarga": "..."
        }
      ]
    }
    """
    
    try:
        response = model.generate_content([prompt, img])
        teks_json = response.text
        teks_json = re.sub(r'```json', '', teks_json)
        teks_json = re.sub(r'```', '', teks_json).strip()
        return json.loads(teks_json)
    except Exception as e:
        st.error(f"Gagal memproses gambar dengan AI: {e}")
        return None

# --- UTAMA: UPLOAD FILE ---
uploaded_file = st.file_uploader("Pilih foto Kartu Keluarga (JPG / PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Tampilkan preview gambar di web
    st.image(uploaded_file, caption="Preview KK yang Diunggah", use_container_width=True)
    
    if not api_key_input:
        st.warning("⚠️ Silakan masukkan Gemini API Key Anda terlebih dahulu pada panel di sebelah kiri (Sidebar).")
    else:
        if st.button("🚀 Ekstraksi Data KK dengan AI", type="primary"):
            with st.spinner("🧠 AI sedang membaca seluruh detail KK, mohon tunggu..."):
                hasil_data = baca_kk_dengan_ai(uploaded_file, api_key_input)
                
            if hasil_data and 'anggota' in hasil_data:
                st.success("✅ Berhasil menarik seluruh data administrasi KK!")
                
                # Simpan ke session_state agar tidak hilang saat interaksi dropdown
                st.session_state['hasil_data'] = hasil_data
            else:
                st.error("❌ Gagal membaca struktur KK. Pastikan foto terang dan jelas.")

# Jika data sudah tersimpan di sesi, tampilkan form pemetaan
if 'hasil_data' in st.session_state:
    data = st.session_state['hasil_data']
    no_kk = data.get('no_kk', '-')
    alamat = data.get('alamat_lengkap', '-')
    daftar_orang = data['anggota']
    
    st.markdown("---")
    st.subheader("📋 Pemetaan Anggota Keluarga")
    
    # Buat list pilihan untuk dropdown
    opsi_nama = [f"{p['nama']} ({p['status_keluarga']})" for p in daftar_orang]
    
    # Cari default index untuk Ayah dan Ibu
    def_ayah_idx = next((i for i, p in enumerate(daftar_orang) if "KEPALA" in str(p.get('status_keluarga')).upper()), 0)
    def_ibu_idx = next((i for i, p in enumerate(daftar_orang) if "ISTRI" in str(p.get('status_keluarga')).upper()), min(1, len(daftar_orang)-1))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        pilih_ayah_idx = st.selectbox("Pilih Ayah:", range(len(opsi_orang)), format_func=lambda x: opsi_orang[x], index=def_ayah_idx)
    with col2:
        pilih_ibu_idx = st.selectbox("Pilih Ibu:", range(len(opsi_orang)), format_func=lambda x: opsi_orang[x], index=def_ibu_idx)
    with col3:
        pilih_santri_idx = st.selectbox("Pilih Santri:", range(len(opsi_orang)), format_func=lambda x: opsi_orang[x], index=min(2, len(opsi_orang)-1))
        
    ayah = daftar_orang[pilih_ayah_idx]
    ibu = daftar_orang[pilih_ibu_idx]
    santri = daftar_orang[pilih_santri_idx]
    
    if st.button("💾 Generate & Validasi Data Santri", type="primary"):
        # Kalkulasi saudara
        list_anak = [p for p in daftar_orang if p != ayah and p != ibu]
        jumlah_saudara = max(0, len(list_anak) - 1)
        anak_ke = "?"
        for idx, anak in enumerate(list_anak):
            if anak == santri:
                anak_ke = idx + 1
                break
                
        st.markdown("### ✨ Hasil Profil Komprehensif")
        
        # Kartu Tampilan HTML yang Rapi
        html_output = f"""
        <div style='background:#f8fafc; padding:20px; border-radius:10px; border-left:6px solid #2563eb; font-family:sans-serif; color:#1e293b;'>
            <h4 style='color:#1e3a8a; margin-top:0;'>📍 DOMISILI KELUARGA</h4>
            <p><b>No. KK:</b> {no_kk}<br><b>Alamat:</b> {alamat}</p>
            <hr style='border:0; border-top:1px solid #cbd5e1;'>
            <h4 style='color:#0f172a;'>🟢 DATA SANTRI</h4>
            <p><b>Nama:</b> {santri.get('nama')}<br>
            <b>NIK:</b> {santri.get('nik')}<br>
            <b>TTL:</b> {santri.get('tempat_lahir')}, {santri.get('tanggal_lahir')}<br>
            <b>Pendidikan:</b> {santri.get('pendidikan')}<br>
            <b>Status:</b> Anak ke-{anak_ke} dari {len(list_anak)} bersaudara ({jumlah_saudara} saudara kandung)</p>
            <hr style='border:0; border-top:1px solid #cbd5e1;'>
            <h4 style='color:#0f172a;'>🔵 DATA ORANG TUA / WALI</h4>
            <p><b>Ayah:</b> {ayah.get('nama')} ({ayah.get('nik')}) | Pekerjaan: <b>{ayah.get('pekerjaan')}</b><br>
            <b>Ibu:</b> {ibu.get('nama')} ({ibu.get('nik')}) | Pekerjaan: <b>{ibu.get('pekerjaan')}</b></p>
        </div>
        """
        st.markdown(html_output, unsafe_allow_html=True)
        
        # Siapkan tombol Download ke CSV/Excel
        df_export = pd.DataFrame([{
            "No_KK": no_kk,
            "Alamat": alamat,
            "Nama_Santri": santri.get('nama'),
            "NIK_Santri": santri.get('nik'),
            "TTL_Santri": f"{santri.get('tempat_lahir')}, {santri.get('tanggal_lahir')}",
            "Status_Anak": f"Anak ke-{anak_ke} dari {len(list_anak)}",
            "Nama_Ayah": ayah.get('nama'),
            "NIK_Ayah": ayah.get('nik'),
            "Pekerjaan_Ayah": ayah.get('pekerjaan'),
            "Nama_Ibu": ibu.get('nama'),
            "NIK_Ibu": ibu.get('nik'),
            "Pekerjaan_Ibu": ibu.get('pekerjaan')
        }])
        
        csv_data = df_export.to_csv(index=false).encode('utf-8')
        st.download_button(
            label="📥 Download Data ke CSV (Excel Ready)",
            data=csv_data,
            file_name=f"data_santri_{santri.get('nama').replace(' ', '_')}.csv",
            mime="text/csv",
            type="secondary"
        )
