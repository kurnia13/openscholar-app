import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="OpenScholarHub",
    page_icon="🎓",
    layout="wide"
)

# --- CLASS LOGIKA PENCARIAN (BACKEND) ---
class ScholarEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'OpenScholarBot/WebVersion (mailto:researcher@example.com)'}

    def normalize_authors(self, author_list):
        if not author_list: return "Unknown Author"
        names = []
        for auth in author_list:
            if isinstance(auth, dict):
                if 'given' in auth and 'family' in auth: names.append(f"{auth['given']} {auth['family']}")
                elif 'name' in auth: names.append(auth['name'])
            elif isinstance(auth, str): names.append(auth)
        return ", ".join(names[:3])

    def detect_method(self, text):
        if not text or text == "No Abstract": return "Unspecified"
        text_lower = text.lower()
        quant = sum(1 for w in ['survey', 'statistical', 'regression', 'quantitative', 'p-value'] if w in text_lower)
        qual = sum(1 for w in ['interview', 'case study', 'thematic', 'qualitative', 'ethnography'] if w in text_lower)
        review = sum(1 for w in ['systematic review', 'literature review', 'meta-analysis'] if w in text_lower)
        
        if review > 0 and review >= quant: return "Literature Review"
        if quant > qual: return "Quantitative"
        if qual > quant: return "Qualitative"
        return "Mixed/General"

    # Cache data agar tidak request ulang saat klik filter
    @st.cache_data
    def fetch_data(_self, query, limit):
        # 1. CrossRef
        cr_results = []
        try:
            url = "https://api.crossref.org/works"
            params = {'query.bibliographic': query, 'rows': limit, 'select': 'title,author,published-print,DOI,abstract'}
            r = requests.get(url, params=params, headers=_self.headers)
            if r.status_code == 200:
                for item in r.json()['message']['items']:
                    abst = item.get('abstract', 'No Abstract').replace('<jats:p>', '').replace('</jats:p>', '')
                    cr_results.append({
                        'Source': 'CrossRef',
                        'Title': item.get('title', ['No Title'])[0],
                        'Authors': _self.normalize_authors(item.get('author', [])),
                        'Year': item['published-print']['date-parts'][0][0] if 'published-print' in item else 0,
                        'Method': _self.detect_method(abst),
                        'Abstract': abst[:200] + "..."
                    })
        except: pass

        # 2. DOAJ
        doaj_results = []
        try:
            url = f"https://doaj.org/api/v2/search/articles/{query}"
            r = requests.get(url, params={'pageSize': limit, 'page': 1})
            if r.status_code == 200:
                for item in r.json().get('results', []):
                    bib = item.get('bibjson', {})
                    abst = bib.get('abstract', 'No Abstract')
                    doaj_results.append({
                        'Source': 'DOAJ',
                        'Title': bib.get('title', 'No Title'),
                        'Authors': _self.normalize_authors(bib.get('author', [])),
                        'Year': int(bib.get('year', 0)),
                        'Method': _self.detect_method(abst),
                        'Abstract': abst[:200] + "..."
                    })
        except: pass
        
        return pd.DataFrame(cr_results + doaj_results)

# --- UI / FRONTEND ---
st.title("🎓 OpenScholarHub")
st.markdown("Mesin pencari jurnal **gratis & open-access** dengan deteksi metode otomatis.")

# Sidebar untuk Input
with st.sidebar:
    st.header("🔍 Panel Kontrol")
    query = st.text_input("Topik Riset", "Artificial Intelligence in Education")
    limit_per_source = st.slider("Jumlah Sampel per Sumber", 5, 50, 10)
    st.markdown("---")
    filter_method = st.multiselect(
        "Filter Metode", 
        ['Quantitative', 'Qualitative', 'Literature Review', 'Mixed/General'],
        default=['Quantitative', 'Qualitative', 'Literature Review', 'Mixed/General']
    )
    search_btn = st.button("Mulai Pencarian", type="primary")

# Logika Utama
if search_btn:
    engine = ScholarEngine()
    with st.spinner(f"Sedang mencari artikel tentang '{query}'..."):
        df = engine.fetch_data(query, limit_per_source)
    
    if not df.empty:
        # Cleaning & Filtering
        df['Year'] = pd.to_numeric(df['Year'], errors='coerce').fillna(0).astype(int)
        df = df[df['Year'] > 1900] # Hapus tahun error
        df_filtered = df[df['Method'].isin(filter_method)]
        
        # Statistik Ringkas
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ditemukan", f"{len(df)} Artikel")
        col1.metric("Setelah Filter", f"{len(df_filtered)} Artikel")
        top_source = df['Source'].mode()[0]
        col2.metric("Sumber Terbanyak", top_source)
        
        # Visualisasi (Langsung muncul otomatis)
        tab1, tab2 = st.tabs(["📊 Visualisasi Tren", "📄 Data Tabel"])
        
        with tab1:
            c1, c2 = st.columns(2)
            # Grafik Tren
            trend = df_filtered.groupby('Year').size().reset_index(name='Count')
            fig_line = px.line(trend, x='Year', y='Count', title='Tren Publikasi', markers=True)
            c1.plotly_chart(fig_line, use_container_width=True)
            
            # Grafik Donut
            fig_pie = px.pie(df_filtered, names='Method', title='Distribusi Metode', hole=0.4)
            c2.plotly_chart(fig_pie, use_container_width=True)
            
        with tab2:
            st.dataframe(df_filtered[['Year', 'Source', 'Method', 'Title', 'Authors']], use_container_width=True)
            
            # Fitur Download CSV
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Hasil (CSV)",
                data=csv,
                file_name=f"OpenScholar_{query}.csv",
                mime="text/csv"
            )
    else:
        st.error("Tidak ditemukan artikel. Coba kata kunci lain.")
