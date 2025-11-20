import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- KONFIGURASI HALAMAN (Desain Baru) ---
st.set_page_config(
    page_title="Kurnia Research Engine", # Judul di Tab Browser
    page_icon="📚", # Ikon di Tab Browser
    layout="wide"
)

# --- FUNGSI KONVERSI RIS (METADATA LENGKAP v2.5) ---
def convert_df_to_ris(df):
    ris_text = ""
    for index, row in df.iterrows():
        ris_text += "TY  - JOUR\n"
        ris_text += f"TI  - {row['Judul']}\n"
        
        if row['Penulis'] and row['Penulis'] != "Penulis Tidak Diketahui":
            authors = row['Penulis'].split(",")
            for auth in authors:
                ris_text += f"AU  - {auth.strip()}\n"
        
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
            for kw in kws:
                ris_text += f"KW  - {kw.strip()}\n"
        
        if row['Abstrak'] != "Tidak ada abstrak":
            clean_abs = row['Abstrak'].replace('\n', ' ').replace('\r', '')
            ris_text += f"AB  - {clean_abs}\n"
            
        if "doi.org" in row['Link_Akses']:
            doi_clean = row['Link_Akses'].replace("https://doi.org/", "")
            ris_text += f"DO  - {doi_clean}\n"
        
        ris_text += f"UR  - {row['Link_Akses']}\n"
        ris_text += "ER  - \n\n"
        
    return ris_text

# --- CLASS LOGIKA UTAMA (v2.5) ---
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
        if not keywords:
            return "Umum", 0
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

        # 1. CROSSREF API
        try:
            url = "https://api.crossref.org/works"
            filter_str = f"from-pub-date:{start_year}-01-01,until-pub-date:{end_year}-12-31"
            params = {
                'query.bibliographic': broad_topic,
                'rows': limit,
                'filter': filter_str,
                'select': 'title,author,published-print,published-online,DOI,URL,abstract,container-title,volume,issue,page,subject'
            }
            r = requests.get(url, params=params, headers=self.headers)
            if r.status_code == 200:
                items = r.json().get('message', {}).get('items', [])
                for item in items:
                    year = 0
                    if 'published-print' in item and 'date-parts' in item['published-print']:
                        year = item['published-print']['date-parts'][0][0]
                    elif 'published-online' in item and 'date-parts' in item['published-online']:
                        year = item['published-online']['date-parts'][0][0]
                    
                    doi = item.get('DOI')
                    link = f"https://doi.org/{doi}" if doi else item.get('URL', '#')
                    abst = item.get('abstract', 'Tidak ada abstrak').replace('<jats:p>', '').replace('</jats:p>', '')
                    container = item.get('container-title', [])
                    journal_name = container[0] if container else ""
                    
                    results.append({
                        'Sumber': 'CrossRef',
                        'Tahun': year,
                        'Judul': item.get('title', ['Tanpa Judul'])[0],
                        'Penulis': self.normalize_authors(item.get('author', [])),
                        'Abstrak': abst,
                        'Metode': self.detect_method(abst),
                        'Link_Akses': link,
                        'Nama_Jurnal': journal_name,
                        'Volume': item.get('volume', ''),
                        'Isu': item.get('issue', ''),
                        'Halaman': item.get('page', ''),
                        'Keywords': ", ".join(item.get('subject', []))
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
                        journal_info = bib.get('journal', {})
                        start_p = bib.get('start_page', '')
                        end_p = bib.get('end_page', '')
                        pages = f"{start_p}-{end_p}" if start_p and end_p else start_p

                        results.append({
                            'Sumber': 'DOAJ',
                            'Tahun': year,
                            'Judul': bib.get('title', 'Tanpa Judul'),
                            'Penulis': self.normalize_authors(bib.get('author', [])),
                            'Abstrak': abst,
                            'Metode': self.detect_method(abst),
                            'Link_Akses': link,
                            'Nama_Jurnal': journal_info.get('title', ''),
                            'Volume': journal_info.get('volume', ''),
                            'Isu': journal_info.get('number', ''),
                            'Halaman': pages,
                            'Keywords': ", ".join(bib.get('keywords', []))
                        })
        except Exception:
            pass

        return pd.DataFrame(results)

# --- UI / FRONTEND (Desain Baru) ---
# Judul Utama yang Bersih
st.title("Kurnia Research Engine")
st.caption("Modern Academic Search & Bibliometric Tool")

with st.sidebar:
    # Sidebar Minimalis tanpa Logo
    st.header("Search Parameters") # Menggunakan Bahasa Inggris agar lebih 'tech'
    
    broad_topic = st.text_input("Primary Topic (English)", "Islamic Economic Partnership")
    specific_keywords = st.text_input("Specific Keywords (Audit)", "Syirkah, Integration")
    
    st.markdown("---")
    
    current_year = datetime.now().year
    years = st.slider("Publication Year Range", 2000, current_year, (current_year-5, current_year))
    
    filter_method = st.multiselect(
        "Methodology Filter",
        ['Quantitative', 'Qualitative', 'Literature Review', 'Mixed/General'],
        default=['Quantitative', 'Qualitative', 'Literature Review', 'Mixed/General']
    )
    
    limit = st.number_input("Sample Size per Source", 5, 100, 20)
    
    # Tombol akan otomatis mengikuti primaryColor dari config.toml
    btn_search = st.button("Start Research Search", type="primary")

if btn_search:
    engine = ScholarEngine()
    with st.spinner("Searching and Analyzing Data..."):
        df = engine.fetch_data(broad_topic, years[0], years[1], limit)
    
    if not df.empty:
        df = df[df['Metode'].isin(filter_method)]
        if df.empty:
             st.warning("No articles found matching the methodology filter.")
        else:
            relevance_data = []
            link_gs = []
            link_s2 = []
            for index, row in df.iterrows():
                full_text = f"{row['Judul']} {row['Abstrak']}"
                category, score = engine.calculate_relevance(full_text, specific_keywords)
                relevance_data.append((category, score))
                
                clean_title = row['Judul'].replace('"', '').replace("'", "")
                link_gs.append(f"https://scholar.google.com/scholar?q={clean_title}")
                link_s2.append(f"https://www.semanticscholar.org/search?q={clean_title}")
            
            df['Kategori_Relevansi'] = [x[0] for x in relevance_data]
            df['Skor'] = [x[1] for x in relevance_data]
            df['Link_GS'] = link_gs
            df['Link_S2'] = link_s2
            df = df.sort_values(by=['Skor', 'Tahun'], ascending=[False, False])
            
            # Tampilkan Metrik Minimalis
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Articles Found", len(df))
            col2.metric("Highly Relevant", len(df[df['Skor'] == 1.0]))
            col3.metric("Dominant Method", df['Metode'].mode()[0] if not df['Metode'].empty else "-")

            st.subheader("Search Results")
            
            # Link akan otomatis berwarna biru (primaryColor)
            st.dataframe(
                df[['Kategori_Relevansi', 'Tahun', 'Judul', 'Nama_Jurnal', 'Link_Akses', 'Link_GS', 'Link_S2']],
                column_config={
                    "Link_Akses": st.column_config.LinkColumn("Access", display_text="Open"),
                    "Link_GS": st.column_config.LinkColumn("G.Scholar", display_text="GS"),
                    "Link_S2": st.column_config.LinkColumn("S.Scholar", display_text="S2"),
                    "Judul": st.column_config.TextColumn("Title", width="medium"),
                    "Nama_Jurnal": st.column_config.TextColumn("Journal", width="small"),
                    "Kategori_Relevansi": st.column_config.TextColumn("Relevance", width="small"),
                },
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")
            st.subheader("📥 Download References")
            d_col1, d_col2 = st.columns(2)
            # Tombol download akan otomatis berwarna biru
            csv = df.to_csv(index=False).encode('utf-8')
            d_col1.download_button("Download Table (CSV)", csv, f"KurniaResearch_{broad_topic}.csv", "text/csv", use_container_width=True, type="primary")
            
            ris_data = convert_df_to_ris(df)
            d_col2.download_button("Download Full Citation (.ris)", ris_data, f"KurniaResearch_{broad_topic}.ris", "application/x-research-info-systems", use_container_width=True, type="primary")
            
            with st.expander("Visual Analysis"):
                tab1, tab2 = st.tabs(["Publication Trend", "Methodology Distribution"])
                with tab1:
                    trend = df.groupby('Tahun').size().reset_index(name='Count')
                    fig = px.line(trend, x='Tahun', y='Count', title='Publication Trend per Year')
                    st.plotly_chart(fig, use_container_width=True)
                with tab2:
                    dist = df['Metode'].value_counts().reset_index()
                    dist.columns = ['Method', 'Count']
                    fig2 = px.pie(dist, names='Method', values='Count', title='Methodology Proportion')
                    st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("No articles found for the given topic and year range.")
