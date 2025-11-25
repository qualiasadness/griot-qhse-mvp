import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import nest_asyncio
import tempfile
import os

# Application du patch pour asyncio
nest_asyncio.apply()

# ============================================================================
# 1. CONFIGURATION ET DESIGN (TON CSS)
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE | Plateforme Sécurité",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Masquer les éléments par défaut */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp { background-color: #F8F9FA; }

    /* Barre latérale pro */
    section[data-testid="stSidebar"] {
        background-color: #0F172A;
        color: white;
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] span {
        color: #F1F5F9 !important;
    }
    
    /* Header personnalisé */
    .custom-header {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 2rem;
        border-bottom: 4px solid #D97706;
    }
    
    /* Bulles de chat */
    .stChatMessage { background-color: transparent; border: none; }
    
    div[data-testid="chatAvatarIcon-assistant"] { background-color: white !important; }
    div[data-testid="chatAvatarIcon-user"] { background-color: #DBEAFE !important; }

    div[data-testid="stChatMessageContent"] {
        padding: 15px;
        border-radius: 15px;
        font-family: 'Helvetica', sans-serif;
        line-height: 1.6;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    /* Couleurs Bulles */
    div[data-testid="chatAvatarIcon-assistant"] + div[data-testid="stChatMessageContent"] {
        background-color: #FFFFFF;
        border-left: 5px solid #D97706;
        color: #334155;
    }
    div[data-testid="chatAvatarIcon-user"] + div[data-testid="stChatMessageContent"] {
        background-color: #DBEAFE;
        color: #1E3A8A;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. FONCTIONS TECHNIQUES (ROBUSTES)
# ============================================================================

# Fonction pour trouver le bon modèle sans erreur
def get_gemini_model_safe(api_key):
    genai.configure(api_key=api_key)
    try:
        # On essaie d'abord Flash (Gratuit)
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        model.generate_content("test")
        return 'models/gemini-1.5-flash'
    except:
        return 'gemini-1.5-flash'

# Audio HD
async def generer_audio_hd_async(texte, langue):
    if langue == "wo": return None # Pas d'audio pour Wolof
    voice = "fr-FR-HenriNeural" if langue == "fr" else "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(texte[:800], voice)
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    await communicate.save(tfile.name)
    return tfile.name

def generer_audio(texte, langue):
    try:
        return asyncio.run(generer_audio_hd_async(texte, langue))
    except: return None

# Traitement IA
def traiter_requete(entree, type_entree, api_key, model_name):
    genai.configure(api_key=api_key)
    system_instruction = """
    Tu es le Griot QHSE, expert sécurité Sénégal.
    - Si WOLOF : Réponds en WOLOF. Tag [WO].
    - Si FRANÇAIS : Réponds en FRANÇAIS. Tag [FR].
    - Si ANGLAIS : Réponds en ANGLAIS. Tag [EN].
    Sois bref et pro.
    """
    model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
    
    try:
        if type_entree == "audio":
            myfile = genai.upload_file(entree)
            response = model.generate_content(["Réponds dans la langue parlée.", myfile])
        else:
            response = model.generate_content(entree)
        return response.text
    except Exception as e:
        return f"[FR] Erreur: {e}"

# ============================================================================
# 3. INTERFACE UTILISATEUR
# ============================================================================

def main():
    # --- HEADER ---
    st.markdown("""
    <div class="custom-header">
        <div>
            <h1 style="color:#1E293B;">🦁 Griot QHSE</h1>
            <p style="color:#64748B;">Assistant Intelligent de Sécurité au Travail</p>
        </div>
        <div style="background: #ECFDF5; color: #047857; padding: 5px 15px; border-radius: 20px; font-weight: bold;">
            🟢 En Ligne
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- SIDEBAR & HISTORIQUE ---
    with st.sidebar:
        st.header("⚙️ Contrôle")
        
        # Gestion Clé API (Secrets ou Input)
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("Licence Active ✅")
        else:
            api_key = st.text_input("Clé API Gemini", type="password")

        st.markdown("---")
        st.subheader("🗄️ Historique (Session)")
        
        # Init historique session
        if "messages" not in st.session_state:
            st.session_state.messages = []
            
        # Affichage de l'historique dans la sidebar (Les 5 derniers échanges)
        # On filtre pour ne prendre que les questions de l'utilisateur
        questions = [m for m in st.session_state.messages if m["role"] == "user"]
        if questions:
            for i, q in enumerate(reversed(questions[-5:])):
                label = "🎤 Vocal" if "Vocal" in q["content"] else q["content"][:20] + "..."
                st.button(f"📄 {label}", key=f"hist_{i}", disabled=True)
        else:
            st.caption("Aucune interaction.")
            
        st.markdown("---")
        if st.button("🗑️ Effacer tout"):
            st.session_state.messages = []
            st.rerun()

    if not api_key:
        st.info("👋 Veuillez entrer votre clé API à gauche.")
        return

    # Modèle actif
    if "model_name" not in st.session_state:
        st.session_state.model_name = get_gemini_model_safe(api_key)

    # --- CHAT DISPLAY ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "audio_path" in msg:
                st.audio(msg["audio_path"])

    # --- INPUTS (LE COEUR DU SYSTÈME) ---
    
    # 1. AUDIO INPUT (OFFICIEL STREAMLIT 1.39)
    # Plus fiable que mic_recorder
    audio_val = st.audio_input("🎙️ Enregistrer un vocal")
    
    # 2. TEXT INPUT
    text_val = st.chat_input("Écrivez votre message...")

    # LOGIQUE DE TRAITEMENT
    prompt_final = None
    type_input = None
    temp_path = None

    # Priorité à l'audio s'il vient d'être capturé
    if audio_val:
        # On vérifie si c'est un nouvel audio pour éviter les boucles
        if "last_audio_proc" not in st.session_state or st.session_state.last_audio_proc != audio_val:
            st.session_state.last_audio_proc = audio_val
            # Sauvegarde temp
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(audio_val.getvalue())
                temp_path = f.name
            prompt_final = temp_path
            type_input = "audio"

    elif text_val:
        prompt_final = text_val
        type_input = "text"

    # SI ENTRÉE DÉTECTÉE
    if prompt_final:
        # Affichage User
        with st.chat_message("user"):
            label = "🎤 *Message Vocal*" if type_input == "audio" else prompt_final
            st.markdown(label)
        
        st.session_state.messages.append({"role": "user", "content": label})

        # Réponse Assistant
        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                resp = traiter_requete(prompt_final, type_input, api_key, st.session_state.model_name)
                
                # Parsing langue
                lang, txt = "fr", resp
                if "[WO]" in resp: lang, txt = "wo", resp.replace("[WO]", "")
                elif "[EN]" in resp: lang, txt = "en", resp.replace("[EN]", "")
                elif "[FR]" in resp: lang, txt = "fr", resp.replace("[FR]", "")
                
                st.markdown(txt)
                
                # Audio Output
                out_audio = None
                if lang != "wo":
                    out_audio = generer_audio(txt, lang)
                    if out_audio: st.audio(out_audio)
                else:
                    st.caption("🔇 (Audio Wolof non dispo)")
                
                # Sauvegarde
                msg_data = {"role": "assistant", "content": txt}
                if out_audio: msg_data["audio_path"] = out_audio
                st.session_state.messages.append(msg_data)
