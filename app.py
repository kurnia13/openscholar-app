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

    def detect_method(self, text):
        if not text or text == "Tidak ada abstrak": return "Unspecified"
        text_lower = text.lower()
        
        quant_keywords = ['survey', 'questionnaire', 'statistical', 'regression', 'quantitative', 'spss', 'sem', 'path analysis']
        qual_keywords = ['interview', 'focus group', 'case study', 'phenomenology', 'qualitative', 'ethnography', 'grounded theory']
        review_keywords = ['systematic review', 'literature review', 'meta-analysis', 'bibliometric']

        quant = sum(1 for w in quant_keywords if w in text_lower)
        qual = sum(1 for w in qual_keywords if w in text_lower)
        review = sum(1 for w in review_keywords if w in text_lower)
        
        if review > 0 and review >= quant: return "Literature Review"
        if quant > qual: return "Quantitative"
        if qual > quant: return "Qualitative"
        return "Mixed/General"

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
                    abst = item.get('abstract', 'Tidak ada abstrak').replace('<jats:p>', '').replace('</jats:p>', '')
                    
                    results.append({
                        'Sumber': 'CrossRef',
                        'Tahun': year,
                        'Judul': item.get('title', ['Tanpa Judul'])[0],
                        'Penulis': self.normalize_authors(item.get('author', [])),
                        'Abstrak': abst,
                        'Metode': self.detect_method(abst),
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
                        
                        abst = bib.get('abstract', 'Tidak ada abstrak')

                        results.append({
                            'Sumber': 'DOAJ',
                            'Tahun': year,
                            'Judul': bib.get('title', 'Tanpa Judul'),
                            'Penulis': self.normalize_authors(bib.get('author', [])),
                            'Abstrak': abst,
                            'Metode': self.detect_method(abst),
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
    
    # Tambahan Filter Metode di Sidebar
    filter_method = st.multiselect(
        "Filter Metode Penelitian",
        ['Quantitative', 'Qualitative', 'Literature Review', 'Mixed/General'],
        default=['Quantitative', 'Qualitative', 'Literature Review', 'Mixed/General']
    )
    
    limit = st.number_input("Jumlah Sampel per Sumber", min_value=5, max_value=100, value=20)
    
    btn_search = st.button("Cari Artikel", type="primary")

if btn_search:
    engine = ScholarEngine()
    
    with st.spinner("Sedang mencari dan menganalisis data..."):
        df = engine.fetch_data(broad_topic, years[0], years[1], limit)
    
    if not df.empty:
        # Filter Dataframe berdasarkan Pilihan Metode User
        df = df[df['Metode'].isin(filter_method)]
        
        if df.empty:
             st.warning("Artikel ditemukan, namun tidak ada yang cocok dengan filter Metode yang dipilih.")
        else:
            # Audit Relevansi
            relevance_data = []
            link_gs = []
            link_s2 = []

            for index, row in df.iterrows():
                # Hitung Skor
                full_text = f"{row['Judul']} {row['Abstrak']}"
                category, score = engine.calculate_relevance(full_text, specific_keywords)
                relevance_data.append((category, score))
                
                # Buat Link Hybrid
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
            col1.metric("Total Artikel", len(df))
            col2.metric("Sangat Relevan", len(df[df['Skor'] == 1.0]))
            col3.metric("Dominasi Metode", df['Metode'].mode()[0] if not df['Metode'].empty else "-")

            # Tampilkan Tabel Utama
            st.subheader("Hasil Pencarian")
            
            st.dataframe(
                df[['Kategori_Relevansi', 'Metode', 'Tahun', 'Judul', 'Link_Akses', 'Link_GS', 'Link_S2']],
                column_config={
                    "Link_Akses": st.column_config.LinkColumn(
                        "Akses Utama",
                        display_text="Buka Artikel"
                    ),
                    "Link_GS": st.column_config.LinkColumn(
                        "Google Scholar",
                        display_text="Cek GS"
                    ),
                    "Link_S2": st.column_config.LinkColumn(
                        "Semantic Scholar",
                        display_text="Cek S2"
                    ),
                    "Judul": st.column_config.TextColumn("Judul Artikel", width="medium"),
                    "Kategori_Relevansi": st.column_config.TextColumn("Relevansi", width="small"),
                    "Metode": st.column_config.TextColumn("Metode", width="small"),
                },
                use_container_width=True,
                hide_index=True
            )
            
            with st.expander("Lihat Analisis Visual"):
                tab1, tab2 = st.tabs(["Tren Waktu", "Distribusi Metode"])
                
                with tab1:
                    trend = df.groupby('Tahun').size().reset_index(name='Jumlah')
                    fig = px.line(trend, x='Tahun', y='Jumlah', title='Tren Publikasi')
                    st.plotly_chart(fig, use_container_width=True)
                
                with tab2:
                    dist = df['Metode'].value_counts().reset_index()
                    dist.columns = ['Metode', 'Jumlah']
                    fig2 = px.pie(dist, names='Metode', values='Jumlah', title='Proporsi Metode Penelitian')
                    st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("Tidak ditemukan artikel dalam rentang tahun dan topik tersebut.")
