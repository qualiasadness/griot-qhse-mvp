"""
GRIOT QHSE - Assistant Trilingue (Wolof/Français/Anglais)
=========================================================
Logique : 
- Texte : Authentique dans les 3 langues via Gemini.
- Audio : Activé uniquement pour Français et Anglais (gTTS).
"""

import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
from gtts import gTTS
import tempfile
import os
import time
import re

# ============================================================================
# CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE",
    page_icon="👷🏿‍♂️",
    layout="wide"
)

# ============================================================================
# BASE DE DONNÉES
# ============================================================================

def init_db():
    conn = sqlite3.connect('qhse_logs.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS logs 
                     (id INTEGER PRIMARY KEY, question TEXT, reponse TEXT, date_heure TIMESTAMP)''')
    conn.commit()
    conn.close()

def enregistrer_log(question, reponse):
    try:
        conn = sqlite3.connect('qhse_logs.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO logs (question, reponse, date_heure) VALUES (?, ?, ?)', 
                       (question, reponse, datetime.now()))
        conn.commit()
        conn.close()
    except: pass

# ============================================================================
# CERVEAU IA (GEMINI) AVEC DÉTECTION INTELLIGENTE
# ============================================================================

def generer_reponse_et_langue(question, api_key):
    genai.configure(api_key=api_key)
    
    # On force l'IA à nous dire quelle langue elle utilise avec un TAG
    system_instruction = """
    Tu es "Griot QHSE", expert sécurité au Sénégal.
    
    RÈGLES STRICTES DE LANGUE :
    1. Si l'utilisateur parle WOLOF : Réponds en WOLOF PUR (Wolof bu xóot). Commence ta réponse par [WO].
    2. Si l'utilisateur parle FRANÇAIS : Réponds en FRANÇAIS. Commence ta réponse par [FR].
    3. Si l'utilisateur parle ANGLAIS : Réponds en ANGLAIS. Commence ta réponse par [EN].
    
    TON TON :
    - Professionnel, bienveillant, axé sur la sécurité (EPI, Normes).
    - Pas de traductions inutiles. Juste la réponse dans la bonne langue.
    """
    
    try:
        # Essai avec le modèle Flash (rapide)
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_instruction)
        response = model.generate_content(question)
        texte_brut = response.text
    except:
        try:
            # Plan B : Modèle Pro (plus stable si Flash échoue)
            model = genai.GenerativeModel('gemini-pro', system_instruction=system_instruction)
            response = model.generate_content(question)
            texte_brut = response.text
        except Exception as e:
            return f"[FR] Erreur technique : {e}", "fr"

    # Analyse du TAG pour savoir si on fait de l'audio
    if "[WO]" in texte_brut:
        langue = "wo"
        texte_propre = texte_brut.replace("[WO]", "").strip()
    elif "[EN]" in texte_brut:
        langue = "en"
        texte_propre = texte_brut.replace("[EN]", "").strip()
    else:
        # Par défaut on suppose français si pas de tag ou tag [FR]
        langue = "fr"
        texte_propre = texte_brut.replace("[FR]", "").strip()
        
    return texte_propre, langue

# ============================================================================
# GESTION AUDIO (SÉLECTIVE)
# ============================================================================

def generer_audio_selectif(texte, langue):
    """
    Génère l'audio SEULEMENT si c'est FR ou EN.
    Renvoie None si c'est Wolof.
    """
    if langue == "wo":
        return None # Pas d'audio pour le Wolof (car gTTS est mauvais)
    
    try:
        # gTTS supporte bien 'fr' et 'en'
        tts = gTTS(text=texte[:600], lang=langue, slow=False)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        tts.save(temp_file.name)
        return temp_file.name
    except:
        return None

# ============================================================================
# INTERFACE
# ============================================================================

def main():
    init_db()
    
    st.title("👷🏿‍♂️ Griot QHSE")
    st.markdown("Votre assistant sécurité : **Wolof**, **Français**, **English**.")
    
    # Sidebar Clé API
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        with st.sidebar:
            api_key = st.text_input("Clé API Google Gemini", type="password")
            st.info("Récupérez votre clé sur aistudio.google.com")

    if not api_key:
        st.warning("⚠️ Veuillez entrer la clé API pour activer le Griot.")
        return

    # Gestion de l'historique du chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Affichage des anciens messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Zone de saisie
    question = st.chat_input("Posez votre question (Ex: Naka lañuy solé EPI ?)")

    if question:
        # 1. Afficher la question utilisateur
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        # 2. Générer la réponse
        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                
                # Appel IA
                reponse_texte, langue_detectee = generer_reponse_et_langue(question, api_key)
                
                # Affichage Texte
                st.markdown(reponse_texte)
                
                # Gestion Audio
                if langue_detectee == "wo":
                    st.caption("🔇 *Audio désactivé pour le Wolof (lecture texte uniquement)*")
                else:
                    audio_path = generer_audio_selectif(reponse_texte, langue_detectee)
                    if audio_path:
                        st.audio(audio_path)
                        # Nettoyage fichier
                        try: os.unlink(audio_path)
                        except: pass
        
        # 3. Sauvegarder
        st.session_state.messages.append({"role": "assistant", "content": reponse_texte})
        enregistrer_log(question, reponse_texte)

if __name__ == "__main__":
    main()
