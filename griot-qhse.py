"""
GRIOT QHSE - Assistant Virtuel de Sécurité pour les Travailleurs Sénégalais
============================================================================
Application MVP utilisant Streamlit et Google Gemini (FREE)
Compatible avec Streamlit Cloud
"""

import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
# Remplacement de googletrans par deep_translator et langdetect
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory, LangDetectException
from gtts import gTTS
import tempfile
import os
import time

# Pour rendre la détection de langue cohérente (seed)
DetectorFactory.seed = 0

# ============================================================================
# CONFIGURATION DE LA PAGE
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE",
    page_icon="👷🏿‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# INITIALISATION DE LA BASE DE DONNÉES
# ============================================================================

def init_db():
    conn = sqlite3.connect('qhse_logs.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            reponse TEXT NOT NULL,
            langue_detectee TEXT,
            date_heure TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# ============================================================================
# FONCTION D'ENREGISTREMENT DES LOGS
# ============================================================================

def enregistrer_log(question, reponse, langue):
    try:
        conn = sqlite3.connect('qhse_logs.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO logs (question, reponse, langue_detectee, date_heure)
            VALUES (?, ?, ?, ?)
        ''', (question, reponse, langue, datetime.now()))
        conn.commit()
        conn.close()
    except Exception as e:
        st.warning(f"Erreur d'enregistrement : {e}")

# ============================================================================
# FONCTION DE RÉCUPÉRATION DE L'HISTORIQUE
# ============================================================================

def recuperer_historique():
    try:
        conn = sqlite3.connect('qhse_logs.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM logs ORDER BY date_heure DESC LIMIT 50')
        historique = cursor.fetchall()
        conn.close()
        return historique
    except Exception as e:
        st.warning(f"Erreur de lecture : {e}")
        return []

# ============================================================================
# FONCTION DE DÉTECTION DE LANGUE (Mise à jour)
# ============================================================================

def detecter_langue(texte):
    """
    Détecte la langue avec langdetect.
    """
    try:
        if not texte or len(texte.strip()) < 2:
            return 'fr'
        lang = detect(texte)
        # Si c'est détecté comme inconnu ou autre, on vérifie
        return lang
    except LangDetectException:
        return 'fr'  # Par défaut français si échec
    except Exception as e:
        st.warning(f"Info détection : {e}")
        return 'fr'

# ============================================================================
# FONCTION DE TRADUCTION (Mise à jour)
# ============================================================================

def traduire_texte(texte, langue_source, langue_cible):
    """
    Traduit un texte avec deep-translator.
    """
    try:
        # 'auto' pour la source fonctionne souvent mieux si langdetect échoue
        src = 'auto' if langue_source == 'wo' else langue_source
        
        translator = GoogleTranslator(source=src, target=langue_cible)
        traduction = translator.translate(texte)
        return traduction
    except Exception as e:
        st.error(f"Erreur de traduction : {e}")
        return texte

# ============================================================================
# FONCTION DE GÉNÉRATION DE RÉPONSE AVEC GEMINI FREE
# ============================================================================

def generer_reponse_gemini(question_fr, langue_originale, api_key):
    genai.configure(api_key=api_key)
    
    system_instruction = """Tu es "Griot QHSE", un expert sénégalais en Qualité, Hygiène, Sécurité et Environnement.
TON RÔLE:
- Être strict sur les normes de sécurité (ISO 45001, EPI, Code du Travail Sénégalais)
- Adopter un ton paternel et bienveillant
- TOUJOURS citer une norme ou référence QHSE
- Prioriser la sécurité

IMPORTANT: Sois concis. Max 150 mots par langue."""
    
    try:
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=system_instruction
        )
        
        # Wolof n'est pas toujours bien détecté par langdetect (parfois 'fr' ou 'en'),
        # mais si l'utilisateur dit que c'est du Wolof ou si le contexte le suggère.
        # Ici on se base sur la détection précédente.
        
        if langue_originale == 'wo':
            prompt = f"""Question (contexte Sénégal): {question_fr}

FORMAT DE RÉPONSE OBLIGATOIRE:
🇫🇷 FRANÇAIS:
[Réponse expert QHSE en français]

🇸🇳 WOLOF:
[Traduction en Wolof simple]"""
        else:
            prompt = f"Question: {question_fr}\n\nRéponds en français avec citation de norme QHSE."
        
        response = model.generate_content(prompt)
        time.sleep(2) # Pause pour rate limit
        return response.text
        
    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            return "⚠️ Limite de requêtes atteinte. Veuillez patienter."
        else:
            return f"Erreur Gemini : {str(e)}"

# ============================================================================
# FONCTION DE SYNTHÈSE VOCALE
# ============================================================================

def generer_audio(texte, langue='fr'):
    try:
        if "🇸🇳 WOLOF:" in texte:
            partie_wolof = texte.split("🇸🇳 WOLOF:")[1].strip()
            texte_audio = partie_wolof
            langue = 'fr' 
        elif "🇫🇷 FRANÇAIS:" in texte:
            partie_fr = texte.split("🇫🇷 FRANÇAIS:")[1].split("🇸🇳")[0].strip()
            texte_audio = partie_fr
        else:
            texte_audio = texte
        
        texte_audio = texte_audio.replace("🇫🇷", "").replace("🇸🇳", "").replace("*", "").strip()
        
        if not texte_audio:
            return None

        tts = gTTS(text=texte_audio[:500], lang=langue, slow=False)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        tts.save(temp_file.name)
        return temp_file.name
        
    except Exception as e:
        return None

# ============================================================================
# GET API KEY
# ============================================================================

def get_api_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    if "api_key" in st.session_state:
        return st.session_state.api_key
    return None

# ============================================================================
# MAIN
# ============================================================================

def main():
    init_db()
    st.title("👷🏿‍♂️ Griot QHSE : Sécurité avant tout")
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        api_key_secrets = get_api_key()
        
        if api_key_secrets:
            st.success("✅ API Connectée")
            api_key = api_key_secrets
        else:
            api_key_input = st.text_input("Clé API Google Gemini", type="password")
            if api_key_input:
                st.session_state.api_key = api_key_input
                api_key = api_key_input
            else:
                api_key = None
                st.warning("Entrez votre clé API")
        
        st.markdown("---")
        if st.button("🔄 Actualiser historique"):
            st.rerun()
        
        historique = recuperer_historique()
        if historique:
            with st.expander("Voir l'historique"):
                for log in historique[:5]:
                    st.text(f"{log[4][:16]} - {log[1][:30]}...")

    if not api_key:
        st.info("👋 Veuillez configurer votre clé API pour commencer.")
        return

    st.subheader("💬 Posez votre question")
    col1, col2 = st.columns([4, 1])
    
    with col1:
        question = st.text_area("Votre question (Wolof/Français):", height=100)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        envoyer = st.button("Envoyer", type="primary", use_container_width=True)

    if envoyer and question:
        with st.spinner("Analyse et réflexion..."):
            # 1. Détection
            lang = detecter_langue(question)
            
            # 2. Traduction si nécessaire (pour le contexte Gemini)
            if lang != 'fr':
                q_fr = traduire_texte(question, lang, 'fr')
            else:
                q_fr = question
            
            # 3. Génération
            reponse = generer_reponse_gemini(q_fr, lang, api_key)
            
            st.markdown("---")
            st.subheader("✅ Réponse")
            st.markdown(reponse)
            
            # 4. Audio
            if "⚠️" not in reponse:
                path = generer_audio(reponse, lang)
                if path:
                    st.audio(path)
                    try: os.unlink(path)
                    except: pass
            
            enregistrer_log(question, reponse, lang)

if __name__ == "__main__":
    main()
