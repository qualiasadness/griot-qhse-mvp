import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
from gtts import gTTS
import tempfile
import os
import time

# ============================================================================
# 1. CONFIGURATION & ESTHÉTIQUE
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE | Assistant Sécurité",
    page_icon="🛡️",
    layout="centered"  # Centered est souvent plus élégant pour un chat
)

# CSS Personnalisé pour un look "Pro"
st.markdown("""
<style>
    /* En-tête stylisé */
    .main-header {
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        color: white !important;
        margin: 0;
        font-family: 'Helvetica', sans-serif;
    }
    .main-header p {
        font-size: 1.1em;
        opacity: 0.9;
    }
    /* Style des messages */
    .stChatMessage {
        border-radius: 10px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. LOGIQUE MÉTIER
# ============================================================================

def init_db():
    try:
        conn = sqlite3.connect('qhse_logs.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS logs 
                         (id INTEGER PRIMARY KEY, question TEXT, reponse TEXT, date_heure TIMESTAMP)''')
        conn.commit()
        conn.close()
    except: pass

def enregistrer_log(question, reponse):
    try:
        conn = sqlite3.connect('qhse_logs.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO logs (question, reponse, date_heure) VALUES (?, ?, ?)', 
                       (question, reponse, datetime.now()))
        conn.commit()
        conn.close()
    except: pass

def generer_audio_safe(texte, langue):
    if langue == "wo": return None
    try:
        tts = gTTS(text=texte[:500], lang=langue, slow=False)
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        tts.save(tfile.name)
        return tfile.name
    except: return None

# ============================================================================
# 3. INTELLIGENCE ARTIFICIELLE (AVEC DÉTAIL D'ERREUR)
# ============================================================================

def generer_reponse_robuste(question, api_key):
    genai.configure(api_key=api_key)
    
    system_instruction = """
    Tu es "Le Griot QHSE", un expert sage et technique en sécurité au Sénégal.
    
    RÈGLES DE LANGUE :
    - Si WOLOF : Réponds en WOLOF PUR (Wolof bu xóot). Commence par [WO].
    - Si FRANÇAIS : Réponds en FRANÇAIS. Commence par [FR].
    - Si ANGLAIS : Réponds en ANGLAIS. Commence par [EN].
    
    TON STYLE :
    - Utilise des emojis pour illustrer (ex: ⚠️, 👷, ✅).
    - Sois bienveillant comme un père, mais strict sur les règles.
    - Cite les EPI nécessaires.
    """
    
    # On teste le modèle le plus standard en premier
    modeles = ['gemini-1.5-flash', 'gemini-1.0-pro']
    last_error = ""

    for modele in modeles:
        try:
            model = genai.GenerativeModel(modele, system_instruction=system_instruction)
            response = model.generate_content(question)
            return response.text
        except Exception as e:
            last_error = str(e)
            continue # On passe au suivant
            
    # Si on arrive ici, c'est que tout a échoué. On renvoie l'erreur technique pour comprendre.
    return f"[FR] 🚫 ERREUR TECHNIQUE : {last_error}"

# ============================================================================
# 4. INTERFACE UTILISATEUR
# ============================================================================

def main():
    init_db()

    # --- EN-TÊTE ---
    st.markdown("""
    <div class="main-header">
        <h1>🦁 Griot QHSE</h1>
        <p>Votre Expert Sécurité : Wolof • Français • English</p>
    </div>
    """, unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3061/3061341.png", width=100)
        st.title("Paramètres")
        
        # Récupération Clé API
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("✅ Clé API chargée (Secrets)")
        else:
            api_key = st.text_input("🔑 Clé API Gemini", type="password")
            st.caption("Si vous n'avez pas de clé, créez-en une sur Google AI Studio.")

        st.markdown("---")
        if st.button("🗑️ Effacer la conversation"):
            st.session_state.messages = []
            st.rerun()

    if not api_key:
        st.warning("👋 Veuillez entrer votre clé API dans la barre latérale pour activer le Griot.")
        return

    # --- CHAT ---
    if "messages" not in st.session_state:
        # Message d'accueil par défaut
        st.session_state.messages = [{
            "role": "assistant", 
            "content": "Salamalekum ! 👋🏿 Ma ngi tudd Griot QHSE.\n\nPosez-moi une question sur la sécurité au travail (EPI, Risques, Chantier...) en **Wolof**, **Français** ou **Anglais**."
        }]

    # Affichage des messages
    for msg in st.session_state.messages:
        # Choix de l'avatar selon le rôle
        avatar = "🦁" if msg["role"] == "assistant" else "👷🏿‍♂️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # --- ZONE DE SAISIE ---
    prompt = st.chat_input("Ex: Naka lañuy aar sunu bopp ci chantier? / Quels sont les EPI obligatoires ?")

    if prompt:
        # 1. Message User
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👷🏿‍♂️"):
            st.markdown(prompt)

        # 2. Réponse Assistant
        with st.chat_message("assistant", avatar="🦁"):
            message_placeholder = st.empty()
            with st.spinner("Le Griot consulte les anciens..."):
                
                reponse_brute = generer_reponse_robuste(prompt, api_key)
                
                # Gestion Erreur API visible
                if "🚫 ERREUR TECHNIQUE" in reponse_brute:
                    st.error("Problème de connexion avec Google Gemini.")
                    st.code(reponse_brute.split(":", 1)[1]) # Affiche le code d'erreur exact
                    st.info("Vérifiez que votre Clé API est valide et que vous n'avez pas dépassé le quota gratuit.")
                    texte = "Désolé, je ne peux pas répondre pour l'instant."
                    langue = "fr"
                else:
                    # Nettoyage des tags
                    if "[WO]" in reponse_brute:
                        langue = "wo"
                        texte = reponse_brute.replace("[WO]", "")
                    elif "[EN]" in reponse_brute:
                        langue = "en"
                        texte = reponse_brute.replace("[EN]", "")
                    else:
                        langue = "fr"
                        texte = reponse_brute.replace("[FR]", "")
                    
                    # Affichage
                    message_placeholder.markdown(texte)

                    # Audio
                    if langue == "wo":
                        st.caption("🔇 *Texte en Wolof (Audio désactivé)*")
                    else:
                        audio_path = generer_audio_safe(texte, langue)
                        if audio_path:
                            st.audio(audio_path)
                            try: os.unlink(audio_path)
                            except: pass
        
        # 3. Sauvegarde
        st.session_state.messages.append({"role": "assistant", "content": texte})
        enregistrer_log(prompt, texte)

if __name__ == "__main__":
    main()
