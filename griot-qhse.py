import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
from gtts import gTTS
import tempfile
import os
import uuid

# ============================================================================
# 1. CONFIGURATION & STYLE
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE | Assistant Sécurité",
    page_icon="🦁",
    layout="wide"  # Je remets 'wide' pour avoir de la place pour l'historique à gauche
)

# Style CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #134E5E 0%, #71B280 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stChatMessage {
        border-radius: 15px;
        padding: 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    /* Style pour l'historique dans la sidebar */
    .history-item {
        padding: 8px;
        background-color: #f0f2f6;
        border-radius: 5px;
        margin-bottom: 5px;
        font-size: 0.9em;
        border-left: 3px solid #71B280;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. GESTION DE SESSION & DB (C'est ici que se joue l'isolation)
# ============================================================================

def init_session():
    """Crée un ID unique pour chaque utilisateur (Isolation des données)."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if "messages" not in st.session_state:
        st.session_state.messages = [{
            "role": "assistant", 
            "content": "Salamalekum ! 👋🏿 Ma ngi tudd **Griot QHSE**.\n\nJe suis là pour répondre à vos questions sur la sécurité (EPI, Risques, Code du travail...) en **Wolof**, **Français** ou **Anglais**."
        }]

def init_db():
    try:
        conn = sqlite3.connect('qhse_logs_v2.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS logs 
                         (id INTEGER PRIMARY KEY, session_id TEXT, question TEXT, reponse TEXT, date_heure TIMESTAMP)''')
        conn.commit()
        conn.close()
    except: pass

def enregistrer_log(question, reponse):
    try:
        conn = sqlite3.connect('qhse_logs_v2.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO logs (session_id, question, reponse, date_heure) VALUES (?, ?, ?, ?)', 
                       (st.session_state.session_id, question, reponse, datetime.now()))
        conn.commit()
        conn.close()
    except: pass

def recuperer_historique_utilisateur():
    """
    Récupère UNIQUEMENT l'historique de l'utilisateur en cours (via session_id).
    C'est ça qui garantit que l'utilisateur ne voit que ses propres questions.
    """
    try:
        conn = sqlite3.connect('qhse_logs_v2.db')
        cursor = conn.cursor()
        # La clause WHERE session_id = ... est la clé de l'isolation
        cursor.execute('SELECT question, date_heure FROM logs WHERE session_id = ? ORDER BY date_heure DESC', 
                       (st.session_state.session_id,))
        logs = cursor.fetchall()
        conn.close()
        return logs
    except:
        return []

# ============================================================================
# 3. LOGIQUE IA
# ============================================================================

def get_api_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    return None

def trouver_modele_disponible(api_key):
    genai.configure(api_key=api_key)
    try:
        liste = genai.list_models()
        for m in liste:
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name.lower(): return m.name
        for m in liste:
            if 'generateContent' in m.supported_generation_methods:
                if 'gemini' in m.name.lower(): return m.name
        return "models/gemini-1.5-flash"
    except:
        return "models/gemini-1.5-flash"

def generer_reponse(question, api_key, nom_modele):
    genai.configure(api_key=api_key)
    system_instruction = """
    Tu es "Le Griot QHSE", expert sécurité au Sénégal.
    1. Si on te parle WOLOF -> Réponds en WOLOF (Wolof pur). Commence par [WO].
    2. Si on te parle FRANÇAIS -> Réponds en FRANÇAIS. Commence par [FR].
    3. Si on te parle ANGLAIS -> Réponds en ANGLAIS. Commence par [EN].
    Ton : Paternel, Sage, Expert Technique (Normes, EPI).
    """
    try:
        model = genai.GenerativeModel(nom_modele, system_instruction=system_instruction)
        response = model.generate_content(question)
        return response.text
    except Exception as e:
        return f"[FR] 🚫 Erreur technique : {str(e)}"

def generer_audio(texte, langue):
    if langue == "wo": return None
    try:
        tts = gTTS(text=texte[:500], lang=langue, slow=False)
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        tts.save(tfile.name)
        return tfile.name
    except: return None

# ============================================================================
# 4. INTERFACE UTILISATEUR
# ============================================================================

def main():
    init_session()
    init_db()

    # --- EN-TÊTE ---
    st.markdown("""
    <div class="main-header">
        <h1>🦁 Griot QHSE</h1>
        <p>Expert Sécurité Trilingue (Wolof • Fr • En)</p>
    </div>
    """, unsafe_allow_html=True)

    # --- SIDEBAR (HISTORIQUE PERSONNEL) ---
    with st.sidebar:
        st.header("🕒 Vos questions")
        st.caption("Historique de cette session uniquement")
        
        # Récupération et affichage de l'historique SOLO
        historique = recuperer_historique_utilisateur()
        
        if historique:
            for log in historique:
                question_courte = (log[0][:40] + '..') if len(log[0]) > 40 else log[0]
                heure = log[1].split(' ')[1][:5] # Récupère juste HH:MM
                st.markdown(f"""
                <div class="history-item">
                    <b>{heure}</b> : {question_courte}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            if st.button("🗑️ Nouvelle Session"):
                # On génère un nouvel ID pour repartir à zéro
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.messages = []
                st.rerun()
        else:
            st.info("Posez votre première question pour voir l'historique ici.")

    # --- CONFIG AUTO ---
    api_key = get_api_key()
    if not api_key:
        st.error("⚠️ Clé API manquante dans les Secrets Streamlit.")
        st.stop()

    if "nom_modele_actif" not in st.session_state:
        st.session_state.nom_modele_actif = trouver_modele_disponible(api_key)

    # --- CHAT ---
    for msg in st.session_state.messages:
        avatar = "🦁" if msg["role"] == "assistant" else "👷🏿‍♂️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # --- INPUT ---
    prompt = st.chat_input("Votre question (ex: EPI Soudure ?)")

    if prompt:
        # User
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👷🏿‍♂️"):
            st.markdown(prompt)

        # Assistant
        with st.chat_message("assistant", avatar="🦁"):
            message_placeholder = st.empty()
            with st.spinner("..."):
                reponse_brute = generer_reponse(prompt, api_key, st.session_state.nom_modele_actif)
                
                if "[WO]" in reponse_brute:
                    langue, texte = "wo", reponse_brute.replace("[WO]", "")
                elif "[EN]" in reponse_brute:
                    langue, texte = "en", reponse_brute.replace("[EN]", "")
                elif "[FR]" in reponse_brute:
                    langue, texte = "fr", reponse_brute.replace("[FR]", "")
                else:
                    langue, texte = "fr", reponse_brute

                message_placeholder.markdown(texte)

                if langue == "wo":
                    st.caption("🔇 *Texte Wolof*")
                elif "🚫" not in texte:
                    path = generer_audio(texte, langue)
                    if path:
                        st.audio(path)
                        try: os.unlink(path)
                        except: pass
        
        st.session_state.messages.append({"role": "assistant", "content": texte})
        
        # Enregistrement et rechargement pour mettre à jour la sidebar
        enregistrer_log(prompt, texte)
        st.rerun()

if __name__ == "__main__":
    main()
