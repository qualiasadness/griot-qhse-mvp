import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import nest_asyncio
import tempfile
import os

# Application du patch pour que l'audio fonctionne sur le Cloud
nest_asyncio.apply()

# ============================================================================
# 1. CONFIGURATION ET DESIGN
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE",
    page_icon="👷🏿‍♂️",
    layout="wide"
)

# CSS pour masquer les éléments inutiles et rendre l'interface propre
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp { background-color: #F8F9FA; }

    /* En-tête */
    .custom-header {
        background: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border-bottom: 3px solid #D97706;
    }
    
    /* Bulles de discussion */
    .stChatMessage { background-color: transparent; }
    div[data-testid="stChatMessageContent"] {
        border-radius: 15px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. FONCTIONS TECHNIQUES (ROBUSTES)
# ============================================================================

def get_gemini_model_safe(api_key):
    """Trouve le modèle Gemini disponible sans planter."""
    genai.configure(api_key=api_key)
    try:
        # On essaie le modèle flash standard
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        return 'models/gemini-1.5-flash'
    except:
        # Si ça échoue, on renvoie une valeur par défaut
        return 'gemini-1.5-flash'

async def generer_audio_async(texte, langue):
    """Génère l'audio avec une voix naturelle."""
    if langue == "wo": return None # Wolof pas supporté en audio
    
    voice = "fr-FR-HenriNeural" if langue == "fr" else "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(texte[:800], voice)
    
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    await communicate.save(tfile.name)
    return tfile.name

def generer_audio(texte, langue):
    try:
        return asyncio.run(generer_audio_async(texte, langue))
    except: return None

def repondre_ia(entree, type_entree, api_key, model_name):
    """Interroge Gemini (Texte ou Audio)."""
    genai.configure(api_key=api_key)
    
    system_instruction = """
    Tu es le Griot QHSE, expert sécurité Sénégal.
    - Si WOLOF : Réponds en WOLOF. Tag [WO].
    - Si FRANÇAIS : Réponds en FRANÇAIS. Tag [FR].
    - Si ANGLAIS : Réponds en ANGLAIS. Tag [EN].
    Sois bref, utile et bienveillant.
    """
    
    model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
    
    if type_entree == "audio":
        # Traitement audio natif
        myfile = genai.upload_file(entree)
        response = model.generate_content(["Réponds dans la langue parlée.", myfile])
    else:
        # Traitement texte
        response = model.generate_content(entree)
        
    return response.text

# ============================================================================
# 3. INTERFACE UTILISATEUR
# ============================================================================

def main():
    # En-tête
    st.markdown("""
    <div class="custom-header">
        <h1 style="color:#1E293B; margin:0;">🦁 Griot QHSE</h1>
        <p style="color:#64748B; margin:0;">Expert Sécurité • Wolof / Français / English</p>
    </div>
    """, unsafe_allow_html=True)

    # --- SIDEBAR (Clé API & Historique) ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # 1. Clé API
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("Licence Active ✅")
        else:
            api_key = st.text_input("Clé API Gemini", type="password")
            
        st.markdown("---")
        
        # 2. Historique de Session
        st.subheader("🗄️ Historique")
        if "messages" not in st.session_state:
            st.session_state.messages = []
            
        if st.button("🗑️ Effacer tout"):
            st.session_state.messages = []
            st.rerun()
            
        # Affichage compact de l'historique
        questions_user = [m for m in st.session_state.messages if m["role"] == "user"]
        if questions_user:
            for q in reversed(questions_user[-5:]):
                txt = "🎤 Vocal" if "Vocal" in q["content"] else q["content"][:20] + "..."
                st.caption(f"• {txt}")

    if not api_key:
        st.info("👋 Veuillez configurer la Clé API à gauche.")
        return

    # Détection modèle
    if "model_name" not in st.session_state:
        st.session_state.model_name = get_gemini_model_safe(api_key)

    # --- AFFICHAGE DU CHAT ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "audio_path" in msg:
                st.audio(msg["audio_path"])

    # --- ZONE D'ENTRÉE (TEXTE OU VOCAL) ---
    # Utilisation du nouveau micro officiel (Streamlit 1.39+)
    
    col1, col2 = st.columns([1, 4])
    with col1:
        audio_val = st.audio_input("Vocal", label_visibility="collapsed")
    with col2:
        text_val = st.chat_input("Écrivez votre message...")

    # Logique de traitement
    prompt_final = None
    type_input = None
    temp_path = None

    # Priorité à l'audio
    if audio_val:
        if "last_audio" not in st.session_state or st.session_state.last_audio != audio_val:
            st.session_state.last_audio = audio_val
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(audio_val.getvalue())
                temp_path = f.name
            prompt_final = temp_path
            type_input = "audio"
            
    elif text_val:
        prompt_final = text_val
        type_input = "text"

    # Si on a une entrée, on traite
    if prompt_final:
        # Affiche User
        with st.chat_message("user"):
            label = "🎤 Message Vocal" if type_input == "audio" else prompt_final
            st.markdown(label)
        st.session_state.messages.append({"role": "user", "content": label})

        # Réponse Assistant
        with st.chat_message("assistant"):
            with st.spinner("Le Griot réfléchit..."):
                try:
                    # Appel IA
                    reponse = repondre_ia(prompt_final, type_input, api_key, st.session_state.model_name)
                    
                    # Détection Langue et Tags
                    lang = "fr"
                    texte_clean = reponse
                    if "[WO]" in reponse: 
                        lang, texte_clean = "wo", reponse.replace("[WO]", "")
                    elif "[EN]" in reponse: 
                        lang, texte_clean = "en", reponse.replace("[EN]", "")
                    elif "[FR]" in reponse: 
                        lang, texte_clean = "fr", reponse.replace("[FR]", "")

                    st.markdown(texte_clean)
                    
                    # Audio (sauf Wolof)
                    out_audio = None
                    if lang != "wo":
                        out_audio = generer_audio(texte_clean, lang)
                        if out_audio: st.audio(out_audio)
                    else:
                        st.caption("🔇 (Audio Wolof non disponible)")

                    # Sauvegarde
                    msg_data = {"role": "assistant", "content": texte_clean}
                    if out_audio: msg_data["audio_path"] = out_audio
                    st.session_state.messages.append(msg_data)
                    
                    if temp_path: os.unlink(temp_path)

                except Exception as e:
                    st.error(f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    main()
