import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="OpenScholarHub",
    layout="wide"
)

# --- CLASS LOGIKA UTAMA ---
class ScholarEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'OpenScholarBot/WebVersion (mailto:researcher@example.com)'}

    def normalize_authors(self, author_list):
        if not author_list: return "Penulis Tidak Diketahui"
        names = []
        for auth in author_list:
            if isinstance(auth, dict):
                if 'given' in auth and 'family' in auth:
                    names.append(f"{auth['given']} {auth['family']}")
                elif 'name' in auth:
                    names.append(auth['name'])
            elif isinstance(auth, str):
                names.append(auth)
        return ", ".join(names[:3])

    def calculate_relevance(self, text, keywords):
        if not keywords:
            return "Umum", 0
            
        text_lower = text.lower() if text else ""
        keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        
        if not keyword_list:
            return "Umum", 0

        found_count = sum(1 for k in keyword_list if k in text_lower)
        score = found_count / len(keyword_list)

        if score == 1.0:
            return "Sangat Relevan", score
        elif score >= 0.5:
            return "Relevan", score
        elif score > 0:
            return "Terkait", score
        else:
            return "Topik Luas", score

    def fetch_data(self, broad_topic, start_year, end_year, limit):
        results = []

        # 1. CROSSREF API
        try:
            url = "https://api.crossref.org/works"
            filter_str = f"from-pub-date:{start_year}-01-01,until-pub-date:{end_year}-12-31"
            params = {
                'query.bibliographic': broad_topic,
                'rows': limit,
                'filter': filter_str,
                'select': 'title,author,published-print,DOI,URL,abstract'
            }
            r = requests.get(url, params=params, headers=self.headers)
            if r.status_code == 200:
                items = r.json().get('message', {}).get('items', [])
                for item in items:
                    year = 0
                    if 'published-print' in item and 'date-parts' in item['published-print']:
                        year = item['published-print']['date-parts'][0][0]
                    
                    doi = item.get('DOI')
                    link = f"https://doi.org/{doi}" if doi else item.get('URL', '#')
                    
                    results.append({
                        'Sumber': 'CrossRef',
                        'Tahun': year,
                        'Judul': item.get('title', ['Tanpa Judul'])[0],
                        'Penulis': self.normalize_authors(item.get('author', [])),
                        'Abstrak': item.get('abstract', 'Tidak ada abstrak').replace('<jats:p>', '').replace('</jats:p>', ''),
                        'Link_Akses': link
                    })
        except Exception:
            pass

        # 2. DOAJ API
        try:
            url = f"https://doaj.org/api/v2/search/articles/{broad_topic}"
            params = {'pageSize': limit, 'page': 1}
            r = requests.get(url, params=params)
            if r.status_code == 200:
                items = r.json().get('results', [])
                for item in items:
                    bib = item.get('bibjson', {})
                    year = int(bib.get('year', 0))
                    
                    if start_year <= year <= end_year:
                        link = bib.get('link', [{'url': '#'}])[0].get('url')
                        if not link or link == '#':
                            link = f"https://doaj.org/article/{item.get('id')}"

                        results.append({
                            'Sumber': 'DOAJ',
                            'Tahun': year,
                            'Judul': bib.get('title', 'Tanpa Judul'),
                            'Penulis': self.normalize_authors(bib.get('author', [])),
                            'Abstrak': bib.get('abstract', 'Tidak ada abstrak'),
                            'Link_Akses': link
                        })
        except Exception:
            pass

        return pd.DataFrame(results)

# --- UI / FRONTEND ---
st.title("OpenScholarHub")
st.markdown("Mesin Pencari Jurnal Akademik Terintegrasi")

with st.sidebar:
    st.header("Parameter Pencarian")
    
    broad_topic = st.text_input("Topik Utama (Bahasa Inggris)", "Islamic Economic Partnership")
    st.caption("Gunakan istilah umum untuk menarik data dari server.")
    
    specific_keywords = st.text_input("Kata Kunci Spesifik", "Syirkah, Integration")
    st.caption("Pisahkan dengan koma untuk audit relevansi.")
    
    st.markdown("---")
    
    current_year = datetime.now().year
    years = st.slider(
        "Rentang Tahun Publikasi",
        min_value=2000,
        max_value=current_year,
        value=(current_year-5, current_year)
    )
    
    limit = st.number_input("Jumlah Sampel per Sumber", min_value=5, max_value=100, value=20)
    
    btn_search = st.button("Cari Artikel", type="primary")

if btn_search:
    engine = ScholarEngine()
    
    with st.spinner("Sedang mencari data..."):
        df = engine.fetch_data(broad_topic, years[0], years[1], limit)
    
    if not df.empty:
        # Audit Relevansi
        relevance_data = []
        link_gs = []
        link_s2 = []

        for index, row in df.iterrows():
            # Hitung Skor
            full_text = f"{row['Judul']} {row['Abstrak']}"
            category, score = engine.calculate_relevance(full_text, specific_keywords)
            relevance_data.append((category, score))
            
            # Buat Link Hybrid (GS & S2)
            clean_title = row['Judul'].replace('"', '').replace("'", "")
            link_gs.append(f"https://scholar.google.com/scholar?q={clean_title}")
            link_s2.append(f"https://www.semanticscholar.org/search?q={clean_title}")
        
        df['Kategori_Relevansi'] = [x[0] for x in relevance_data]
        df['Skor'] = [x[1] for x in relevance_data]
        df['Link_GS'] = link_gs
        df['Link_S2'] = link_s2
        
        # Sorting
        df = df.sort_values(by=['Skor', 'Tahun'], ascending=[False, False])
        
        # Tampilkan Metrik
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ditemukan", len(df))
        col1.metric("Rentang Tahun", f"{years[0]} - {years[1]}")
        perfect_matches = len(df[df['Skor'] == 1.0])
        col2.metric("Sangat Relevan", perfect_matches)

        # Tampilkan Tabel Utama
        st.subheader("Hasil Pencarian")
        
        st.dataframe(
            df[['Kategori_Relevansi', 'Tahun', 'Judul', 'Link_Akses', 'Link_GS', 'Link_S2']],
            column_config={
                "Link_Akses": st.column_config.LinkColumn(
                    "Akses Utama",
                    help="Link ke Publisher atau PDF",
                    display_text="Buka Artikel"
                ),
                "Link_GS": st.column_config.LinkColumn(
                    "Google Scholar",
                    help="Cari PDF di Google Scholar",
                    display_text="Cek GS"
                ),
                "Link_S2": st.column_config.LinkColumn(
                    "Semantic Scholar",
                    help="Lihat sitasi di Semantic Scholar",
                    display_text="Cek S2"
                ),
                "Judul": st.column_config.TextColumn("Judul Artikel", width="medium"),
                "Kategori_Relevansi": st.column_config.TextColumn("Relevansi", width="small"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        with st.expander("Lihat Analisis Visual"):
            tab1, tab2 = st.tabs(["Tren Waktu", "Distribusi Relevansi"])
            
            with tab1:
                trend = df.groupby('Tahun').size().reset_index(name='Jumlah')
                fig = px.line(trend, x='Tahun', y='Jumlah', title='Tren Publikasi per Tahun')
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                dist = df['Kategori_Relevansi'].value_counts().reset_index()
                dist.columns = ['Kategori', 'Jumlah']
                fig2 = px.pie(dist, names='Kategori', values='Jumlah', title='Proporsi Relevansi Artikel')
                st.plotly_chart(fig2, use_container_width=True)

    else:
        st.warning("Tidak ditemukan artikel dalam rentang tahun dan topik tersebut.")
