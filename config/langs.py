import json
import streamlit as st

from pathlib import Path
from typing import TypedDict, Dict, Literal

from config.settings import GET_PATH

# ------------------------------------------------------------------------------- #
# LANGUAGE AND TRANSLATION UTILITIES -------------------------------------------- #
# ------------------------------------------------------------------------------- #

Language = TypedDict("Language", {
    'en': str,
    'id': str,
    'jv': str
})

GET_LANGUAGE: Language = {
    'en': "English",
    'id': "Bahasa Indonesia",
    'jv': "Basa Jawa"
}
DEFAULT_LANGUAGE = "English"

    
# ------------------------------------------------------------------------------- #

TranslationDict = Literal[
    "app.ui.element.void",
    "app.ui.element.dash",
    "app.title",
    "app.welcome",
    "app.extraction.title",
    "app.extraction.description",
    "app.extraction.source.label",
    "app.extraction.source.option_map.1",
    "app.extraction.source.option_map.2",
    "app.extraction.source.option_map.3",
    "app.extraction.source.option_map.4",
    "app.extraction.whoscored.scraper_load",
    "app.extraction.console.wh_region_loader",
    "app.extraction.label.wh_region",
    "app.extraction.caption.wh_region_selected",
    "app.extraction.label.wh_tournament",
    "app.extraction.caption.wh_tournament_selected",
    "app.extraction.label.wh_season",
    "app.extraction.caption.wh_season_selected",
    "app.extraction.caption.info_1",
    "app.extraction.caption.info_2",
    "app.extraction.directory.label",
    "app.extraction.directory.placeholder",
    "app.extraction.button.ws_scraper_config",
    "app.extraction.button.error.ws_scraper_config",
    "app.extraction.toast.ws_scraper_config",
    "app.feature.suggestion",
    "app.feature.title",
    "app.feature.description",
    "app.feature.selection.option_map.1",
    "app.feature.selection.option_map.2",
    "app.feature.selection.option_map.3",
    "app.feature.selection.option_map.4",
    "app.feature.selection.label",
    "app.feature.selection.1.subheader",
    "app.feature.selection.1.df_label",
    "app.feature.selection.1.df_caption_1",
    "app.feature.selection.1.df_caption_2",
    "app.feature.selection.1.error",
    "global.page_link.extraction_pagination",
    "global.page_link.feature_pagination",
    "pagination_info",
    "settings.language_selector.label",
    "utils.scraper.wh_region_get",
    "matches_df_select_columns",
    "matches_df_select_columns_warning",
    "matches_df_select_columns_info",
]

# ------------------------------------------------------------------------------- #
# -- FUNCTION SECTION ----------------------------------------------------------- #
# ------------------------------------------------------------------------------- #

class Linguistics:
    def __init__(self, locales_dir: Path, available_languages: Dict[str, str], default_language: str):
        """
        Initialize the Translator with directories and default settings.
        """
        self.locales_dir = locales_dir
        self.available_languages = available_languages
        self.default_language = default_language

        # Initialize Streamlit session state for language upon instantiation
        if "language" not in st.session_state:
            st.session_state.language = self.default_language


    # --------------------------------------------------------------------------- #

    @staticmethod
    @st.cache_data
    def _load_translation_file(path: str) -> dict:
        """
        Static method to load the JSON file. 
        Using @staticmethod ensures st.cache_data doesn't try to hash 'self'.
        Passed as a string because Streamlit prefers hashing strings over Path objects.
        """
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


    # --------------------------------------------------------------------------- #

    @property
    def current_language(self) -> str:
        """Helper to get the current language from session state."""
        return st.session_state.language


    # --------------------------------------------------------------------------- #

    def get_translations(self) -> dict:
        """
        Fetch the translation dictionary for the currently selected language.
        """
        path = self.locales_dir / f"{self.current_language}.json"
        
        if not path.exists():
            st.info(f"Translation file not found: {path}")
            return {}
            
        return self._load_translation_file(str(path))


    # --------------------------------------------------------------------------- #
    
    def translate(self, key: TranslationDict) -> str:
        """
        gettext-style translation helper.
        Often mapped to `_` in practice.

        #### Example use:
        - `from config.langs import translator`
        - `_ = translator.translate`
        """
        translations = self.get_translations()
        return translations.get(key, f"❓{key}")


    # --------------------------------------------------------------------------- #

    def render_selector(
        self, 
        horizontal: bool = True
    ):
        """
        Render language selector with *st.radio*.

        Parameters
        ----------
        horizontal : bool
        + True (horizontal, default)
        + False (vertical)
        """
        language_codes = list(self.available_languages.keys())
        
        st.radio(
            label=self.translate("settings.language_selector.label"),
            options=language_codes,
            format_func=lambda code: self.available_languages[code],
            key="language",
            horizontal=horizontal
        )


# ------------------------------------------------------------------------------- #

translator = Linguistics(
    locales_dir=GET_PATH['locales'],
    available_languages=GET_LANGUAGE,
    default_language=DEFAULT_LANGUAGE
)


# ------------------------------------------------------------------------------- #
