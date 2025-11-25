import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import nest_asyncio
import tempfile
import os

# Patch technique indispensable pour l'audio sur le Cloud
nest_asyncio.apply()

# ============================================================================
# 1. CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE",
    page_icon="👷🏿‍♂️",
    layout="centered"
)

# Style épuré (Fond blanc, chat propre)
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: white; }
    div[data-testid="stStatusWidget"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. FONCTION ANTI-ERREUR 404 (CRITIQUE)
# ============================================================================

def trouver_modele_disponible(api_key):
    """
    Cette fonction liste les modèles réellement disponibles pour TA clé.
    Elle évite l'erreur 404 en ne prenant qu'un modèle qui existe.
    """
    genai.configure(api_key=api_key)
    try:
        # On demande la liste à Google
        liste_modeles = genai.list_models()
        
        # On cherche un modèle 'flash' (gratuit et rapide)
        for m in liste_modeles:
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name.lower():
                    return m.name  # On retourne le nom exact
        
        # Si pas de flash, on prend le premier 'gemini' dispo
        for m in liste_modeles:
             if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name.lower():
                 return m.name
                 
        return 'gemini-1.5-flash' # Fallback ultime
        
    except Exception as e:
        return 'gemini-1.5-flash'

# ============================================================================
# 3. FONCTIONS AUDIO & IA
# ============================================================================

async def generer_audio_hd_async(texte, langue):
    # Voix Française (Henri) utilisée pour FR et WOLOF (lecture phonétique)
    # Voix Anglaise (Christopher) pour l'anglais
    voice = "en-US-ChristopherNeural" if langue == "en" else "fr-FR-HenriNeural"
    
    communicate = edge_tts.Communicate(texte, voice)
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    await communicate.save(tfile.name)
    return tfile.name

def generer_audio(texte, langue):
    try:
        return asyncio.run(generer_audio_hd_async(texte, langue))
    except: return None

def repondre_avec_ia(entree, type_entree, api_key, nom_modele):
    genai.configure(api_key=api_key)
    
    system_instruction = """
    Tu es le Griot QHSE, expert sécurité Sénégal.
    1. Si Wolof : Réponds en WOLOF. Commence par [WO].
    2. Si Français : Réponds en FRANÇAIS. Commence par [FR].
    3. Si Anglais : Réponds en ANGLAIS. Commence par [EN].
    Sois bref, paternel et technique (normes ISO, EPI).
    """
    
    # Utilisation du nom de modèle DÉCOUVERT (pas deviné)
    model = genai.GenerativeModel(nom_modele, system_instruction=system_instruction)
    
    if type_entree == "audio":
        myfile = genai.upload_file(entree)
        response = model.generate_content(["Réponds dans la langue parlée.", myfile])
    else:
        response = model.generate_content(entree)
        
    return response.text

# ============================================================================
# 4. INTERFACE UTILISATEUR
# ============================================================================

def main():
    # En-tête simple
    st.markdown("<h1 style='text-align: center;'>👷🏿‍♂️ Griot QHSE</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Expert Sécurité • Wolof / Français / English</p>", unsafe_allow_html=True)

    # --- GESTION DE LA CLÉ API (SECRETS) ---
    api_key = None
    
    if "GEMINI_API_KEY" in st.secrets:
        # Cas 1 : La clé est dans les secrets (Déploiement Cloud)
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        # Cas 2 : Pas de secret, on demande à l'utilisateur (Mode test)
        with st.sidebar:
            st.warning("⚠️ Mode Test")
            api_key = st.text_input("Clé API Gemini", type="password")

    if not api_key:
        st.info("Configuration requise : Ajoutez GEMINI_API_KEY dans les secrets pour activer l'app.")
        return

    # --- INITIALISATION INTELLIGENTE ---
    if "modele_nom" not in st.session_state:
        # On cherche le modèle UNE SEULE FOIS au démarrage
        modele_trouve = trouver_modele_disponible(api_key)
        st.session_state.modele_nom = modele_trouve

    # --- HISTORIQUE ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "audio" in msg:
                st.audio(msg["audio"])

    # --- ENTRÉES ---
    # NOUVEAU MICRO OFFICIEL
    prompt_audio = st.audio_input("Enregistrer un vocal")
    prompt_texte = st.chat_input("Écrire un message...")

    prompt_final = None
    type_input = None
    temp_path = None

    # Priorité Audio > Texte
    if prompt_audio:
        if "last_audio" not in st.session_state or st.session_state.last_audio != prompt_audio:
            st.session_state.last_audio = prompt_audio
            # Sauvegarde temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(prompt_audio.getvalue())
                temp_path = f.name
            prompt_final = temp_path
            type_input = "audio"
            
    elif prompt_texte:
        prompt_final = prompt_texte
        type_input = "texte"

    # --- TRAITEMENT ---
    if prompt_final:
        # Affichage User
        with st.chat_message("user"):
            if type_input == "audio":
                st.markdown("🎤 *Vocal envoyé*")
            else:
                st.markdown(prompt_final)
        
        st.session_state.messages.append({"role": "user", "content": prompt_final if type_input == "texte" else "🎤 *Vocal*"})

        # Réponse
        with st.chat_message("assistant"):
            status = st.status("Le Griot réfléchit...", expanded=True)
            try:
                # 1. Texte
                status.write("🧠 Analyse...")
                reponse = repondre_avec_ia(prompt_final, type_input, api_key, st.session_state.modele_nom)
                
                # 2. Parsing Langue
                lang = "fr"
                texte_clean = reponse
                if "[WO]" in reponse:
                    lang = "wo"
                    texte_clean = reponse.replace("[WO]", "")
                elif "[EN]" in reponse:
                    lang = "en"
                    texte_clean = reponse.replace("[EN]", "")
                elif "[FR]" in reponse:
                    lang = "fr"
                    texte_clean = reponse.replace("[FR]", "")

                # 3. Audio Output
                status.write("🗣️ Synthèse vocale...")
                audio_out = generer_audio(texte_clean, lang)
                
                status.update(label="Terminé", state="complete", expanded=False)
                
                st.markdown(texte_clean)
                if audio_out:
                    st.audio(audio_out)
                    if lang == "wo":
                        st.caption("ℹ️ *Lecture phonétique (Wolof)*")

                # Save
                msg_data = {"role": "assistant", "content": texte_clean}
                if audio_out: msg_data["audio"] = audio_out
                st.session_state.messages.append(msg_data)
                
                if temp_path:
                    os.unlink(temp_path)

            except Exception as e:
                status.update(label="Erreur", state="error")
                st.error(f"Erreur technique : {e}")

if __name__ == "__main__":
    main()
