import streamlit as st
if "language" not in st.session_state:
    st.session_state['language'] = "en"

from config.settings import GET_PATH, GET_URL, GET_WHOSCORED # Dictionaries
from config.settings import Settings # Classes
from config.langs import translator # Variables
from streamlit_marquee import streamlit_marquee as marquee

# ------------------------------------------------------------------------------- #

_ = translator.translate
set = Settings(default_color="green")
version = set.load_module_version


# ------------------------------------------------------------------------------- #
# -- FOOTER SECTION ------------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

def footer():
    st.write(_("app.ui.element.dash"))
    marquee(
        content=f"""
            Dependencies → 
            Streamlit v{version("streamlit")} | 
            BeautifulSoup v{version("beautifulsoup4")} | 
            Cloudscraper v{version("cloudscraper")} |
            Socceraction v{version("socceraction")} |
            Soccerdata v{version("soccerdata")} |
            Streamlit Marquee v{version("streamlit-marquee")} |
            Pandas v{version("pandas")} |
            Requests v{version("requests")} |
            Regex v{version("re")} |
            Random v{version("random")} |
            Authlib v{version("Authlib")}
        """,
        background="#40000088",
        color="#ffffff",
        width="auto",
        lineHeight="0px",
        fontSize="12px",
        animaitionDuration="10s",
    )

   
# ------------------------------------------------------------------------------- #
# -- APP UI SECTION ------------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

def auth():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem !important;
        }
        
        div[data-testid="stVerticalBlockBorderWrapper"]:first-of-type {
            position: fixed; top: 0; left: 0; width: 100%;
            background-color: #f0f2f6; /* Light gray background */
            padding: 1rem 2rem; border-bottom: 2px solid #e0e0e0;
            z-index: 99999; /* Keeps it on top of other content */
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------------------------------- #

    col1, col2 = st.columns(2)

    with col1:
        for i in range(2):
            set.logMsg(_('app.ui.element.void'), level=6)
            
        if "title" in st.session_state:
            st.caption(st.session_state['title'])

    # --------------------------------------------------------------------------- #

    with col2:
        with st.container(horizontal=True, horizontal_alignment="right"):
            translator.render_selector(horizontal=True)


# ------------------------------------------------------------------------------- #
# -- MAIN SECTION --------------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

def main():
    set.logMsg(_('app.ui.element.void'), level=6)
    print("App.py")
    print(_('app.ui.element.dash'))

    st.set_page_config(
        page_title="Veritasq",
        layout="wide"
    )

    # --------------------------------------------------------------------------- #

    home_page = st.Page(
        "pages/dashboard.py",
        title="Veritasq Dashboard",
        icon=":material/home:"
    )
    exploration = st.Page(
        "pages/exploration.py",
        title="Data Exploration",
        icon=":material/search:"
    )
    preprocessing = st.Page(
        "pages/preprocessing.py",
        title="Data Preprocessing",
        icon=":material/recycling:"
    )
    feature = st.Page(
        "pages/feature.py",
        title="Feature Engineering",
        icon=":material/engineering:",
        default=True
    )
    summary = st.Page(
        "pages/summary.py",
        title="Summary Page",
        icon=":material/cognition_2:"
    )

    # --------------------------------------------------------------------------- #
    
    pages_structure = {
        "Core App": [home_page],
        "Management": [summary, exploration, preprocessing, feature]
    }
    pg = st.navigation(pages_structure, position="top")
    pg.run()


# ------------------------------------------------------------------------------- #

if __name__ == "__main__":
    auth()
    main()
    footer()

