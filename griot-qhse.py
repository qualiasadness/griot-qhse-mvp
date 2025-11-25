import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
from gtts import gTTS
import tempfile
import os
import time

# ----------------------------------------------------------------------------
# 1. CONFIGURATION (Doit être la 1ère commande Streamlit)
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Griot QHSE",
    page_icon="👷🏿‍♂️",
    layout="wide"
)

# ----------------------------------------------------------------------------
# 2. FONCTIONS (Base de données & Audio)
# ----------------------------------------------------------------------------

def init_db():
    """Initialise la base de données de manière sécurisée."""
    try:
        conn = sqlite3.connect('qhse_logs.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS logs 
                         (id INTEGER PRIMARY KEY, question TEXT, reponse TEXT, date_heure TIMESTAMP)''')
        conn.commit()
        conn.close()
    except Exception as e:
        st.warning(f"Note: La base de données n'a pas pu être créée (Erreur: {e}). L'app continue quand même.")

def enregistrer_log(question, reponse):
    try:
        conn = sqlite3.connect('qhse_logs.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO logs (question, reponse, date_heure) VALUES (?, ?, ?)', 
                       (question, reponse, datetime.now()))
        conn.commit()
        conn.close()
    except:
        pass # On ignore les erreurs d'écriture pour ne pas bloquer l'app

def generer_audio_safe(texte, langue):
    """Génère l'audio seulement si la langue n'est pas Wolof."""
    if langue == "wo":
        return None
    
    try:
        tts = gTTS(text=texte[:500], lang=langue, slow=False)
        # Utilisation de suffixe unique pour éviter les conflits de fichiers
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        tts.save(tfile.name)
        return tfile.name
    except Exception:
        return None

# ----------------------------------------------------------------------------
# 3. INTELLIGENCE ARTIFICIELLE
# ----------------------------------------------------------------------------

def generer_reponse_robuste(question, api_key):
    """Essaie plusieurs modèles pour éviter l'erreur 404."""
    genai.configure(api_key=api_key)
    
    system_instruction = """
    Tu es Griot QHSE, expert sécurité Sénégal.
    - Si WOLOF : Réponds en Wolof pur. Débute par [WO].
    - Si FRANÇAIS : Réponds en Français. Débute par [FR].
    - Si ANGLAIS : Réponds en Anglais. Débute par [EN].
    """
    
    # Liste des modèles à tester (du plus rapide au plus ancien)
    modeles = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    
    for modele in modeles:
        try:
            model = genai.GenerativeModel(modele, system_instruction=system_instruction)
            response = model.generate_content(question)
            return response.text # Si ça marche, on retourne le texte
        except:
            continue # Si ça rate, on essaie le suivant
            
    return "[FR] Erreur : Impossible de contacter l'IA (Tous les modèles ont échoué)."

# ----------------------------------------------------------------------------
# 4. INTERFACE PRINCIPALE
# ----------------------------------------------------------------------------

def main():
    # Titre et Intro
    st.title("👷🏿‍♂️ Griot QHSE")
    st.markdown("**Assistant Sécurité Trilingue (Wolof / Français / Anglais)**")
    
    # Vérification API Key
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        api_key = st.text_input("🔑 Entrez votre clé API Gemini :", type="password")
    
    if not api_key:
        st.info("Veuillez entrer une clé API pour commencer.")
        st.stop() # Arrête le script proprement ici si pas de clé

    # Initialisation DB
    init_db()

    # Chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input Utilisateur
    prompt = st.chat_input("Posez votre question ici...")

    if prompt:
        # Affichage User
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Génération Assistant
        with st.chat_message("assistant"):
            with st.spinner("Le Griot réfléchit..."):
                reponse_brute = generer_reponse_robuste(prompt, api_key)
                
                # Détection langue via les tags
                if "[WO]" in reponse_brute:
                    langue = "wo"
                    texte = reponse_brute.replace("[WO]", "")
                elif "[EN]" in reponse_brute:
                    langue = "en"
                    texte = reponse_brute.replace("[EN]", "")
                else:
                    langue = "fr"
                    texte = reponse_brute.replace("[FR]", "")
                
                # Affichage Texte
                st.markdown(texte)
                
                # Audio (Sauf Wolof)
                if langue == "wo":
                    st.caption("🔇 *Lecture texte (Audio Wolof désactivé)*")
                else:
                    audio_path = generer_audio_safe(texte, langue)
                    if audio_path:
                        st.audio(audio_path)
                        try: os.unlink(audio_path)
                        except: pass
        
        # Sauvegarde
        st.session_state.messages.append({"role": "assistant", "content": texte})
        enregistrer_log(prompt, texte)

# ----------------------------------------------------------------------------
# 5. POINT D'ENTRÉE SÉCURISÉ (C'est ça qui évite l'écran blanc)
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Si ça plante, on affiche l'erreur en gros sur l'écran
        st.error("🚨 Une erreur critique est survenue au démarrage :")
        st.code(str(e))
        st.info("Essayez de changer la version de Python en 3.11 dans les réglages Streamlit.")
