import streamlit as st
import google.generativeai as genai
import sqlite3
import edge_tts
import asyncio
import nest_asyncio
from streamlit_mic_recorder import mic_recorder
import tempfile
import os

# Patch pour que l'audio fonctionne sur le Cloud
nest_asyncio.apply()

# ============================================================================
# 1. CONFIGURATION & DESIGN "CLEAN UI"
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE",
    page_icon="👷🏿‍♂️",
    layout="centered", # Centré pour ressembler à une app mobile/chat
    initial_sidebar_state="collapsed" # Sidebar cachée par défaut pour épurér
)

# CSS pour un look "Premium" et unifié
st.markdown("""
<style>
    /* 1. Fond général propre */
    .stApp {
        background-color: #ffffff;
    }
    
    /* 2. En-tête minimaliste */
    .header-container {
        padding: 20px 0;
        text-align: center;
        border-bottom: 1px solid #eee;
        margin-bottom: 20px;
    }
    .header-title {
        font-family: 'Helvetica Neue', sans-serif;
        font-size: 24px;
        font-weight: 700;
        color: #111;
        margin: 0;
    }
    .header-subtitle {
        color: #666;
        font-size: 14px;
        margin-top: 5px;
    }

    /* 3. Bulles de chat modernes (Style iMessage) */
    .stChatMessage {
        background-color: transparent;
        border: none;
    }
    
    /* Bulle Utilisateur (Bleu moderne) */
    div[data-testid="chatAvatarIcon-user"] {
        background-color: #007AFF !important;
    }
    div[data-testid="chatAvatarIcon-user"] + div {
        background-color: #007AFF;
        color: white;
        border-radius: 18px 18px 0 18px;
        padding: 12px 18px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* Bulle Assistant (Gris doux) */
    div[data-testid="chatAvatarIcon-assistant"] {
        background-color: #E9E9EB !important;
    }
    div[data-testid="chatAvatarIcon-assistant"] + div {
        background-color: #F2F2F7;
        color: #000;
        border-radius: 18px 18px 18px 0;
        padding: 12px 18px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Cacher les éléments inutiles */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Styliser le bouton micro */
    .mic-recorder-container {
        text-align: center;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. LOGIQUE TECHNIQUE (ROBUSTE)
# ============================================================================

def init_db():
    try:
        conn = sqlite3.connect('qhse_v4.db')
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, msg TEXT, date TIMESTAMP)')
        conn.commit()
        conn.close()
    except: pass

async def generer_audio_hd_async(texte, langue):
    """Génère l'audio (Henri pour FR, Christopher pour EN)."""
    if langue == "wo": return None
    voice = "fr-FR-HenriNeural" if langue == "fr" else "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(texte[:800], voice)
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    await communicate.save(tfile.name)
    return tfile.name

def generer_audio(texte, langue):
    try:
        return asyncio.run(generer_audio_hd_async(texte, langue))
    except: return None

def traiter_gemini(entree, type_entree, api_key):
    genai.configure(api_key=api_key)
    # Prompt optimisé
    system_instruction = """
    Tu es le Griot QHSE. 
    1. Langue d'entrée = WOLOF -> Réponds en WOLOF. Tag [WO].
    2. Langue d'entrée = FRANÇAIS -> Réponds en FRANÇAIS. Tag [FR].
    3. Langue d'entrée = ANGLAIS -> Réponds en ANGLAIS. Tag [EN].
    Ton : Court, précis, professionnel. Pas de blabla.
    """
    
    # Recherche du modèle
    model_name = 'models/gemini-1.5-flash' # Par défaut
    
    try:
        model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
        
        if type_entree == "audio":
            # Traitement Audio
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            tfile.write(entree)
            tfile.close()
            myfile = genai.upload_file(tfile.name)
            response = model.generate_content(["Réponds dans la langue de l'audio.", myfile])
            os.unlink(tfile.name)
        else:
            # Traitement Texte
            response = model.generate_content(entree)
            
        return response.text
    except Exception as e:
        return f"[FR] Erreur: {str(e)}"

# ============================================================================
# 3. INTERFACE UTILISATEUR (MAIN)
# ============================================================================

def main():
    init_db()

    # --- HEADER ---
    st.markdown("""
        <div class="header-container">
            <div class="header-title">👷🏿‍♂️ Griot QHSE</div>
            <div class="header-subtitle">Expert Sécurité • Wolof / Français / English</div>
        </div>
    """, unsafe_allow_html=True)

    # --- CONFIGURATION (Cachée dans un expander pour la propreté) ---
    with st.sidebar:
        st.header("Paramètres")
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("API Connectée")
        else:
            api_key = st.text_input("Clé API Gemini", type="password")
        
        if st.button("Effacer l'historique"):
            st.session_state.messages = []
            st.rerun()

    if not api_key:
        st.info("👋 Veuillez entrer votre clé API dans le menu à gauche ( > )")
        return

    # --- GESTION MESSAGES ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Affichage de l'historique
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Si un audio est lié à ce message (stocké dans le dictionnaire)
            if "audio_path" in msg:
                st.audio(msg["audio_path"])

    # --- ZONE D'ACTION ---
    
    # 1. ENREGISTREUR VOCAL (Placé juste avant le chat input)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Le composant mic_recorder renvoie un dictionnaire quand l'enregistrement finit
        audio_data = mic_recorder(
            start_prompt="🎙️ Appuyer pour parler (Wolof/Fr)",
            stop_prompt="🟥 Arrêter",
            just_once=True,
            use_container_width=True,
            key="recorder"
        )

    # 2. CHAMPS TEXTE
    user_input = st.chat_input("Ou écrivez votre message ici...")

    # --- LOGIQUE DE TRAITEMENT UNIQUE ---
    prompt = None
    input_type = None

    # Vérification : Est-ce de l'audio ?
    if audio_data and audio_data['bytes']:
        # On vérifie si on n'a pas déjà traité cet audio précis (bug fréquent Streamlit)
        if "last_audio_bytes" not in st.session_state or st.session_state.last_audio_bytes != audio_data['bytes']:
            st.session_state.last_audio_bytes = audio_data['bytes']
            prompt = audio_data['bytes']
            input_type = "audio"
    
    # Vérification : Est-ce du texte ? (Priorité à l'audio si les deux arrivent en même temps)
    if user_input and not prompt:
        prompt = user_input
        input_type = "text"

    # SI ON A UNE ENTRÉE VALIDE, ON TRAITE
    if prompt:
        # Affiche le message User
        with st.chat_message("user"):
            if input_type == "audio":
                st.markdown("*🎤 Message vocal envoyé...*")
                st.session_state.messages.append({"role": "user", "content": "*🎤 Message vocal envoyé...*"})
            else:
                st.markdown(prompt)
                st.session_state.messages.append({"role": "user", "content": prompt})

        # Génère la réponse
        with st.chat_message("assistant"):
            with st.spinner("..."):
                reponse_brute = traiter_gemini(prompt, input_type, api_key)
                
                # Parsing simple des tags
                lang, text = "fr", reponse_brute
                if "[WO]" in reponse_brute: lang, text = "wo", reponse_brute.replace("[WO]", "")
                elif "[EN]" in reponse_brute: lang, text = "en", reponse_brute.replace("[EN]", "")
                elif "[FR]" in reponse_brute: lang, text = "fr", reponse_brute.replace("[FR]", "")
                
                st.markdown(text)
                
                # Audio HD (Seulement si pas Wolof)
                audio_file = None
                if lang != "wo":
                    audio_file = generer_audio(text, lang)
                    if audio_file:
                        st.audio(audio_file)
                else:
                    st.caption("🔇 Wolof (Texte uniquement)")

                # Sauvegarde dans session
                msg_data = {"role": "assistant", "content": text}
                if audio_file:
                    msg_data["audio_path"] = audio_file
                st.session_state.messages.append(msg_data)

if __name__ == "__main__":
    main()
