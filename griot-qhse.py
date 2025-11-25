"""
GRIOT QHSE - Assistant Trilingue (Wolof/Français/Anglais)
=========================================================
Correction : Gestion robuste des modèles Gemini (Flash/Pro/1.0)
pour éviter l'erreur 404.
"""

import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
from gtts import gTTS
import tempfile
import os
import time

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
# CERVEAU IA (GEMINI) AVEC SÉLECTION AUTOMATIQUE DU MODÈLE
# ============================================================================

def generer_reponse_et_langue(question, api_key):
    genai.configure(api_key=api_key)
    
    system_instruction = """
    Tu es "Griot QHSE", expert sécurité au Sénégal.
    RÈGLES DE LANGUE :
    1. Si Wolof : Réponds en WOLOF PUR. Commence par [WO].
    2. Si Français : Réponds en FRANÇAIS. Commence par [FR].
    3. Si Anglais : Réponds en ANGLAIS. Commence par [EN].
    Ton : Professionnel et bienveillant.
    """
    
    # Liste des modèles à tester dans l'ordre de préférence
    # Google change souvent les noms, on les teste tous pour éviter l'erreur 404
    modeles_a_tester = [
        'gemini-1.5-flash',       # Le plus rapide et gratuit
        'gemini-1.5-flash-latest',# Variante
        'gemini-1.5-pro',         # Le plus intelligent
        'gemini-1.0-pro',         # L'ancien modèle stable
        'gemini-pro'              # Le nom historique (souvent obsolète)
    ]

    texte_brut = None
    erreur_message = ""

    # Boucle pour trouver un modèle qui fonctionne
    for nom_modele in modeles_a_tester:
        try:
            model = genai.GenerativeModel(nom_modele, system_instruction=system_instruction)
            response = model.generate_content(question)
            texte_brut = response.text
            break # Si ça marche, on sort de la boucle
        except Exception as e:
            # On garde l'erreur en mémoire et on passe au modèle suivant
            erreur_message = str(e)
            continue
    
    # Si aucun modèle n'a marché après tous les essais
    if texte_brut is None:
        return f"[FR] Désolé, erreur de connexion aux modèles Google. Détail: {erreur_message}", "fr"

    # Analyse du TAG pour savoir si on fait de l'audio
    if "[WO]" in texte_brut:
        langue = "wo"
        texte_propre = texte_brut.replace("[WO]", "").strip()
    elif "[EN]" in texte_brut:
        langue = "en"
        texte_propre = texte_brut.replace("[EN]", "").strip()
    else:
        langue = "fr"
        texte_propre = texte_brut.replace("[FR]", "").strip()
        
    return texte_propre, langue

# ============================================================================
# GESTION AUDIO (SÉLECTIVE)
# ============================================================================

def generer_audio_selectif(texte, langue):
    if langue == "wo":
        return None 
    
    try:
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

    # Historique
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Zone de saisie
    question = st.chat_input("Posez votre question (Ex: Naka lañuy solé EPI ?)")

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                
                reponse_texte, langue_detectee
