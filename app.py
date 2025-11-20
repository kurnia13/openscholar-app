import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- KONFIGURASI HALAMAN & CSS KUSTOM ---
st.set_page_config(
    page_title="Kurnia Research Engine",
    page_icon="📚",
    layout="wide"
)

# HACK CSS: Untuk membuat tampilan mirip prototype "Big Tech"
# 1. Menghilangkan padding atas yang berlebihan.
# 2. Membuat container hasil terlihat seperti "Kartu Putih" dengan bayangan halus.
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
            background-color: #FFFFFF;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border: 1px solid #E2E8F0;
        }
        h1 { color: #1E293B; font-weight: 800; }
        .metric-container {
            text-align: center;
        }
        .metric-value {
            font-size: 2.5rem;
            font-weight: 800;
            color: #1E293B;
            line-height: 1.2;
        }
        .metric-label {
            font-size: 0.875rem;
            color: #64748B;
            font-weight: 500;
        }
    </style>
""", unsafe_allow_html=True)

# --- LOGIKA ENGINE V2.5 (TIDAK BERUBAH) ---
# (Bagian ini sama persis dengan sebelumnya, hanya disembunyikan untuk menghemat ruang.
# Logika ini sudah terbukti bekerja.)
def convert_df_to_ris(df):
    ris_text = ""
    for index, row in df.iterrows():
        ris_text += "TY  - JOUR\n"
        ris_text += f"TI  - {row['Judul']}\n"
        if row['Penulis'] and row['Penulis'] != "Penulis Tidak Diketahui":
            authors = row['Penulis'].split(",")
            for auth in authors: ris_text += f"AU  - {auth.strip()}\n"
        if row['Nama_Jurnal']: ris_text += f"JO  - {row['Nama_Jurnal']}\n"
        if row['Tahun']: ris_text += f"PY  - {row['Tahun']}\n"
        if row['Volume']: ris_text += f"VL  - {row['Volume']}\n"
        if row['Isu']: ris_text += f"IS  - {row['Isu']}\n"
        if row['Halaman']:
            pages = str(row['Halaman']).split('-')
            if len(pages) >= 1: ris_text += f"SP  - {pages[0].strip()}\n"
            if len(pages) >= 2: ris_text += f"EP  - {pages[1].strip()}\n"
        if row['Keywords']:
            kws = row['Keywords'].split(',')
            for kw in kws: ris_text += f"KW  - {kw.strip()}\n"
        if row['Abstrak'] != "Tidak ada abstrak":
            clean_abs = row['Abstrak'].replace('\n', ' ').replace('\r', '')
            ris_text += f"AB  - {clean_abs}\n"
        if "doi.org" in row['Link_Akses']:
            doi_clean = row['Link_Akses'].replace("https://doi.org/", "")
            ris_text += f"DO  - {doi_clean}\n"
        ris_text += f"UR  - {row['Link_Akses']}\n"
        ris_text += "ER  - \n\n"
    return ris_text

class ScholarEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'KurniaResearchBot/1.0 (mailto:researcher@example.com)'}
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
        return ", ".join(names)
    def detect_method(self, text):
        if not text or text == "Tidak ada abstrak": return "Unspecified"
        text_lower = text.lower()
        quant_keywords = ['survey', 'questionnaire', 'statistical', 'regression', 'quantitative', 'spss', 'sem', 'path analysis', 'pls', 'data analysis', 'hypothesis']
        qual_keywords = ['interview', 'focus group', 'case study', 'phenomenology', 'qualitative', 'ethnography', 'grounded theory', 'observation', 'thematic analysis']
        review_keywords = ['systematic review', 'literature review', 'meta-analysis', 'bibliometric', 'scoping review', 'state of the art']
        quant = sum(1 for w in quant_keywords if w in text_lower)
        qual = sum(1 for w in qual_keywords if w in text_lower)
        review = sum(1 for w in review_keywords if w in text_lower)
        if review > 0 and review >= quant: return "Literature Review"
        if quant > qual: return "Quantitative"
        if qual > quant: return "Qualitative"
        return "Mixed/General"
    def calculate_relevance(self, text, keywords):
        if not keywords: return "Umum", 0
        text_lower = text.lower() if text else ""
        keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        if not keyword_list: return "Umum", 0
        found_count = sum(1 for k in keyword_list if k in text_lower)
        score = found_count / len(keyword_list)
        if score == 1.0: return "Sangat Relevan", score
        elif score >= 0.5: return "Relevan", score
        elif score > 0: return "Terkait", score
        else: return "Topik Luas", score
    def fetch_data(self, broad_topic, start_year, end_year, limit):
        results = []
        try:
            url = "https://api.crossref.org/works"
            filter_str = f"from-pub-date:{start_year}-01-01,until-pub-date:{end_year}-12-31"
            params = {'query.bibliographic': broad_topic, 'rows': limit, 'filter': filter_str, 'select': 'title,author,published-print,published-online,DOI,URL,abstract,container-title,volume,issue,page,subject'}
            r = requests.get(url, params=params, headers=self.headers)
            if r.status_code == 200:
                items = r.json().get('message', {}).get('items', [])
                for item in items:
                    year = 0
                    if 'published-print' in item and 'date-parts' in item['published-print']: year = item['published-print']['date-parts'][0][0]
                    elif 'published-online' in item and 'date-parts' in item['published-online']: year = item['published-online']['date-parts'][0][0]
                    doi = item.get('DOI')
                    link = f"https://doi.org/{doi}" if doi else item.get('URL', '#')
                    abst = item.get('abstract', 'Tidak ada abstrak').replace('<jats:p>', '').replace('</jats:p>', '')
                    container = item.get('container-title', [])
                    journal_name = container[0] if container else ""
                    results.append({'Sumber': 'CrossRef', 'Tahun': year, 'Judul': item.get('title', ['Tanpa Judul'])[0], 'Penulis': self.normalize_authors(item.get('author', [])), 'Abstrak': abst, 'Metode': self.detect_method(abst), 'Link_Akses': link, 'Nama_Jurnal': journal_name, 'Volume': item.get('volume', ''), 'Isu': item.get('issue', ''), 'Halaman': item.get('page', ''), 'Keywords': ", ".join(item.get('subject', []))})
        except Exception: pass
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
                        if not link or link == '#': link = f"https://doaj.org/article/{item.get('id')}"
                        abst = bib.get('abstract', 'Tidak ada abstrak')
                        journal_info = bib.get('journal', {})
                        start_p = bib.get('start_page', '')
                        end_p = bib.get('end_page', '')
                        pages = f"{start_p}-{end_p}" if start_p and end_p else start_p
                        results.append({'Sumber': 'DOAJ', 'Tahun': year, 'Judul': bib.get('title', 'Tanpa Judul'), 'Penulis': self.normalize_authors(bib.get('author', [])), 'Abstrak': abst, 'Metode': self.detect_method(abst), 'Link_Akses': link, 'Nama_Jurnal': journal_info.get('title', ''), 'Volume': journal_info.get('volume', ''), 'Isu': journal_info.get('number', ''), 'Halaman': pages, 'Keywords': ", ".join(bib.get('keywords', []))})
        except Exception: pass
        return pd.DataFrame(results)

# --- UI / FRONTEND BARU (SESUAI PROTOTYPE) ---

# Header Utama
st.title("Kurnia Research Engine")
st.markdown("<h3 style='color: #64748B; font-weight: 400; margin-top: -15px;'>Modern Academic Search & Bibliometric Tool</h3>", unsafe_allow_html=True)
st.markdown("---")

# Layout Kolom: Kiri (Filter) dan Kanan (Hasil)
# Kita TIDAK menggunakan st.sidebar lagi agar mirip prototype
left_col, right_col = st.columns([1, 3], gap="large")

with left_col:
    st.subheader("Search Parameters")
    broad_topic = st.text_input("Primary Topic", "Islamic Economic Partnership")
    
    st.write("") # Spacer
    current_year = datetime.now().year
    years = st.slider("Year Range", 2000, current_year, (current_year-5, current_year))
    
    st.write("") # Spacer
    filter_method = st.multiselect(
        "Methodology",
        ['Quantitative', 'Qualitative', 'Literature Review', 'Mixed/General'],
        default=['Quantitative', 'Qualitative', 'Literature Review', 'Mixed/General']
    )
    
    st.write("") # Spacer
    limit = st.number_input("Sample Size", 5, 100, 20)
    
    st.write("") # Spacer
    # Tombol utama, warnanya akan biru sesuai config.toml
    btn_search = st.button("Start Search", type="primary", use_container_width=True)

# Area Hasil di Kolom Kanan
with right_col:
    if btn_search:
        engine = ScholarEngine()
        with st.spinner("Analyzing academic databases..."):
            df = engine.fetch_data(broad_topic, years[0], years[1], limit)
        
        if not df.empty:
            df = df[df['Metode'].isin(filter_method)]
            if df.empty:
                 st.warning("No articles found matching the methodology filter.")
            else:
                # Proses Data
                relevance_data = []
                link_gs = []
                link_s2 = []
                for index, row in df.iterrows():
                    full_text = f"{row['Judul']} {row['Abstrak']}"
                    category, score = engine.calculate_relevance(full_text, row['Keywords']) # Gunakan keywords dari metadata
                    relevance_data.append((category, score))
                    clean_title = row['Judul'].replace('"', '').replace("'", "")
                    link_gs.append(f"https://scholar.google.com/scholar?q={clean_title}")
                    link_s2.append(f"https://www.semanticscholar.org/search?q={clean_title}")
                
                df['Kategori_Relevansi'] = [x[0] for x in relevance_data]
                df['Skor'] = [x[1] for x in relevance_data]
                df['Link_GS'] = link_gs
                df['Link_S2'] = link_s2
                df = df.sort_values(by=['Skor', 'Tahun'], ascending=[False, False])
                
                # --- TAMPILAN METRIK ALA PROTOTYPE (Custom HTML) ---
                # Menggunakan container agar CSS di atas membuat efek "Card"
                with st.container():
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.markdown(f"""<div class="metric-container"><div class="metric-value">{len(df)}</div><div class="metric-label">Total Articles</div></div>""", unsafe_allow_html=True)
                    with m2:
                        st.markdown(f"""<div class="metric-container"><div class="metric-value">{len(df[df['Skor'] == 1.0])}</div><div class="metric-label">Highly Relevant</div></div>""", unsafe_allow_html=True)
                    with m3:
                        dom_method = df['Metode'].mode()[0] if not df['Metode'].empty else "-"
                        st.markdown(f"""<div class="metric-container"><div class="metric-value" style="font-size: 1.8rem;">{dom_method}</div><div class="metric-label">Dominant Method</div></div>""", unsafe_allow_html=True)

                    st.write("") # Spacer
                    st.write("") # Spacer

                    # --- TABEL DATA ---
                    st.dataframe(
                        df[['Kategori_Relevansi', 'Tahun', 'Judul', 'Nama_Jurnal', 'Link_Akses', 'Link_GS', 'Link_S2']],
                        column_config={
                            "Link_Akses": st.column_config.LinkColumn("Access", display_text="Open"),
                            "Link_GS": st.column_config.LinkColumn("GS", display_text="GS", width="small"),
                            "Link_S2": st.column_config.LinkColumn("S2", display_text="S2", width="small"),
                            "Judul": st.column_config.TextColumn("Title", width="large"),
                            "Nama_Jurnal": st.column_config.TextColumn("Journal", width="medium"),
                            "Kategori_Relevansi": st.column_config.TextColumn("Relevance", width="small"),
                            "Tahun": st.column_config.TextColumn("Year", width="small"),
                        },
                        use_container_width=True,
                        hide_index=True
                    )

                    st.write("") # Spacer
                    st.markdown("---")
                    
                    # --- TOMBOL DOWNLOAD SEJAJAR ---
                    d_col1, d_col2 = st.columns(2, gap="medium")
                    with d_col1:
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button("Download Table (CSV)", csv, f"Kurnia_{broad_topic}.csv", "text/csv", use_container_width=True, type="primary")
                    with d_col2:
                        ris_data = convert_df_to_ris(df)
                        st.download_button("Download Full Citation (.ris)", ris_data, f"Kurnia_{broad_topic}.ris", "application/x-research-info-systems", use_container_width=True, type="primary")
        else:
            st.info("Enter parameters on the left and click search to begin.")
    else:
        # Tampilan awal yang bersih sebelum mencari
        st.markdown("""
            <div style='text-align: center; padding: 5rem; color: #64748B;'>
                <h3>Ready to Research?</h3>
                <p>Configure your search parameters on the left panel to start exploring academic databases.</p>
            </div>
        """, unsafe_allow_html=True)
