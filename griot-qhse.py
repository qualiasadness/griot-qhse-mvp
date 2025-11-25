import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import nest_asyncio
import tempfile
import os

# Patch pour l'audio sur le Cloud
nest_asyncio.apply()

# ============================================================================
# 1. CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE",
    page_icon="👷🏿‍♂️",
    layout="centered"
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: white; }
    /* Style pour le statut */
    div[data-testid="stStatusWidget"] {
        border: 1px solid #ddd;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. FONCTIONS TECHNIQUES INTELLIGENTES
# ============================================================================

def trouver_vrai_nom_modele(api_key):
    """
    Cette fonction empêche l'erreur 404.
    Elle demande à Google quel nom utiliser exactement.
    """
    genai.configure(api_key=api_key)
    try:
        # On liste les modèles disponibles pour TA clé
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                # On cherche le flash en priorité (gratuit et rapide)
                if 'flash' in m.name:
                    return m.name
                # Sinon le pro
                if 'pro' in m.name:
                    return m.name
        # Si on ne trouve rien de précis, on renvoie un défaut
        return 'models/gemini-1.5-flash'
    except Exception as e:
        # En cas d'erreur de connexion
        return None

async def generer_audio_hd_async(texte, langue):
    """
    Génère l'audio.
    Si Wolof (wo) -> On utilise la voix Française (Henri) pour lire le texte phonétiquement.
    """
    # Sélection de la voix
    if langue == "en":
        voice = "en-US-ChristopherNeural"
    else:
        # Pour FR et WOLOF, on utilise Henri (Français)
        voice = "fr-FR-HenriNeural"
    
    communicate = edge_tts.Communicate(texte, voice)
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    await communicate.save(tfile.name)
    return tfile.name

def generer_audio(texte, langue):
    try:
        return asyncio.run(generer_audio_hd_async(texte, langue))
    except Exception as e:
        return None

def detecter_et_repondre(entree, type_entree, api_key, nom_modele):
    genai.configure(api_key=api_key)
    
    system_instruction = """
    Tu es le Griot QHSE, expert sécurité Sénégal.
    
    RÈGLES IMPORTANTES :
    1. Si l'utilisateur écrit/parle en WOLOF : Réponds en WOLOF. Ajoute le tag [WO] au début.
    2. Si l'utilisateur écrit/parle en FRANÇAIS : Réponds en FRANÇAIS. Ajoute le tag [FR] au début.
    3. Si l'utilisateur écrit/parle en ANGLAIS : Réponds en ANGLAIS. Ajoute le tag [EN] au début.
    
    Sois bref et direct.
    """
    
    model = genai.GenerativeModel(nom_modele, system_instruction=system_instruction)
    
    if type_entree == "audio":
        myfile = genai.upload_file(entree)
        response = model.generate_content(["Réponds dans la langue de cet audio.", myfile])
        return response.text
    else:
        response = model.generate_content(entree)
        return response.text

# ============================================================================
# 3. INTERFACE
# ============================================================================

def main():
    st.title("👷🏿‍♂️ Griot QHSE")
    st.caption("Expert Sécurité • Wolof / Français / English")

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🔑 Connexion")
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("Clé API Active")
        else:
            api_key = st.text_input("Clé API Gemini", type="password")
            
        if st.button("🔄 Reset"):
            st.session_state.messages = []
            st.rerun()

    if not api_key:
        st.warning("Entrez votre clé API à gauche pour commencer.")
        return

    # --- RECHERCHE DU MODÈLE (Anti-Erreur 404) ---
    if "nom_modele_valide" not in st.session_state:
        with st.spinner("Connexion à Google..."):
            nom = trouver_vrai_nom_modele(api_key)
            if nom:
                st.session_state.nom_modele_valide = nom
                # st.toast(f"Connecté à : {nom}") # Debug optionnel
            else:
                st.error("Impossible de trouver un modèle. Vérifiez votre Clé API.")
                return

    # --- HISTORIQUE ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "audio" in msg:
                st.audio(msg["audio"])

    # --- ENTRÉES (TEXTE OU VOCAL) ---
    prompt_texte = st.chat_input("Votre message (Wolof / Fr)...")
    prompt_audio = st.audio_input("Ou enregistrez un vocal")

    # Logique de sélection
    prompt_final = None
    type_input = None
    audio_path_temp = None

    if prompt_audio:
        if "last_audio_id" not in st.session_state or st.session_state.last_audio_id != prompt_audio:
            st.session_state.last_audio_id = prompt_audio
            # Sauvegarde temporaire du fichier audio utilisateur
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(prompt_audio.getvalue())
                audio_path_temp = f.name
            
            prompt_final = audio_path_temp
            type_input = "audio"
            
    elif prompt_texte:
        prompt_final = prompt_texte
        type_input = "texte"

    # --- TRAITEMENT ---
    if prompt_final:
        # Affiche le message User
        with st.chat_message("user"):
            if type_input == "audio":
                st.markdown("🎤 *Message vocal envoyé...*")
            else:
                st.markdown(prompt_final)
        
        # Ajout historique User
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt_final if type_input == "texte" else "🎤 *Vocal*"
        })

        # Réponse Bot
        with st.chat_message("assistant"):
            status = st.status("Traitement en cours...", expanded=True)
            
            try:
                # 1. Génération Texte
                status.write("🧠 Le Griot réfléchit...")
                reponse = detecter_et_repondre(
                    prompt_final, 
                    type_input, 
                    api_key, 
                    st.session_state.nom_modele_valide
                )
                
                # 2. Détection Langue
                lang = "fr"
                texte_propre = reponse
                
                if "[WO]" in reponse:
                    lang = "wo" # On garde 'wo' pour savoir, mais l'audio sera forcé
                    texte_propre = reponse.replace("[WO]", "")
                elif "[EN]" in reponse:
                    lang = "en"
                    texte_propre = reponse.replace("[EN]", "")
                elif "[FR]" in reponse:
                    lang = "fr"
                    texte_propre = reponse.replace("[FR]", "")
                
                status.write("🗣️ Génération de la voix...")
                
                # 3. Génération Audio (Même pour Wolof maintenant !)
                audio_sortie = generer_audio(texte_propre, lang)
                
                status.update(label="Terminé !", state="complete", expanded=False)
                
                # Affichage
                st.markdown(texte_propre)
                if audio_sortie:
                    st.audio(audio_sortie)
                    if lang == "wo":
                        st.caption("ℹ️ *Lecture avec accent français (le Wolof n'est pas supporté nativement)*")
                
                # Sauvegarde historique Bot
                msg_data = {"role": "assistant", "content": texte_propre}
                if audio_sortie:
                    msg_data["audio"] = audio_sortie
                st.session_state.messages.append(msg_data)
                
                # Nettoyage
                if audio_path_temp: os.unlink(audio_path_temp)

            except Exception as e:
                status.update(label="Erreur", state="error")
                st.error(f"Erreur : {str(e)}")

if __name__ == "__main__":
    main()
