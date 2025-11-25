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
    
    /* Style statut */
    div[data-testid="stStatusWidget"] {
        border: 1px solid #ddd;
        border-radius: 10px;
        background-color: #f9f9f9;
    }
    
    /* Header simple */
    .header {
        text-align: center;
        padding-bottom: 20px;
        border-bottom: 1px solid #eee;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. FONCTIONS TECHNIQUES (MODÈLE & AUDIO)
# ============================================================================

def trouver_bon_modele(api_key):
    """
    FORCE l'utilisation de FLASH (Gratuit & Rapide).
    Évite les modèles 'Pro' ou 'Exp' qui causent l'erreur 429.
    """
    genai.configure(api_key=api_key)
    try:
        # Liste de préférence (du plus stable au plus récent)
        # On ne veut QUE du flash pour éviter les limites
        modeles_gratuits = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-001",
            "gemini-1.5-flash-002",
            "gemini-1.5-flash-8b"
        ]
        
        # On demande à Google ce qui est dispo
        dispo = [m.name.replace("models/", "") for m in genai.list_models()]
        
        # On prend le premier modèle gratuit qui existe dans la liste dispo
        for m in modeles_gratuits:
            if m in dispo:
                return f"models/{m}"
        
        # Si on ne trouve rien, on force le standard
        return "models/gemini-1.5-flash"
        
    except Exception:
        # En cas de doute, on renvoie le modèle le plus standard
        return "models/gemini-1.5-flash"

async def generer_audio_hd_async(texte, langue):
    """
    Génère l'audio.
    Si Wolof (wo) -> Utilise la voix Française pour lire (lecture phonétique).
    """
    # Sélection de la voix
    if langue == "en":
        voice = "en-US-ChristopherNeural"
    else:
        # Pour FR et WOLOF, on utilise Henri (Français)
        # C'est la seule façon d'avoir du son pour le Wolof gratuitement
        voice = "fr-FR-HenriNeural"
    
    communicate = edge_tts.Communicate(texte, voice)
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    await communicate.save(tfile.name)
    return tfile.name

def generer_audio(texte, langue):
    try:
        return asyncio.run(generer_audio_hd_async(texte, langue))
    except Exception:
        return None

def detecter_et_repondre(entree, type_entree, api_key, nom_modele):
    genai.configure(api_key=api_key)
    
    # Prompt optimisé pour la sécurité et la langue
    system_instruction = """
    Tu es le Griot QHSE, expert sécurité Sénégal.
    
    RÈGLES DE RÉPONSE :
    1. Si l'utilisateur parle WOLOF -> Réponds en WOLOF. Ajoute [WO] au début.
    2. Si l'utilisateur parle FRANÇAIS -> Réponds en FRANÇAIS. Ajoute [FR] au début.
    3. Si l'utilisateur parle ANGLAIS -> Réponds en ANGLAIS. Ajoute [EN] au début.
    
    Format : Sois bienveillant, clair et cite les normes de sécurité si nécessaire.
    """
    
    model = genai.GenerativeModel(nom_modele, system_instruction=system_instruction)
    
    if type_entree == "audio":
        myfile = genai.upload_file(entree)
        response = model.generate_content(["Réponds dans la langue parlée.", myfile])
        return response.text
    else:
        response = model.generate_content(entree)
        return response.text

# ============================================================================
# 3. INTERFACE UTILISATEUR
# ============================================================================

def main():
    # En-tête propre
    st.markdown("""
        <div class="header">
            <h1>👷🏿‍♂️ Griot QHSE</h1>
            <span style="color:gray">Expert Sécurité • Wolof / Français / English</span>
        </div>
    """, unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("🔑 Connexion")
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("Licence Active")
        else:
            api_key = st.text_input("Clé API Gemini", type="password")
            
        st.markdown("---")
        if st.button("🗑️ Effacer la conversation"):
            st.session_state.messages = []
            st.rerun()

    if not api_key:
        st.info("⬅️ Entrez votre clé API à gauche pour commencer.")
        return

    # --- SÉLECTION DU MODÈLE (Une seule fois) ---
    if "modele_actif" not in st.session_state:
        with st.spinner("Configuration du Griot..."):
            st.session_state.modele_actif = trouver_bon_modele(api_key)
            # st.toast(f"Connecté sur : {st.session_state.modele_actif}") # Debug

    # --- HISTORIQUE ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "audio" in msg:
                st.audio(msg["audio"])

    # --- ZONE D'ENTRÉE ---
    
    # 1. Texte
    prompt_texte = st.chat_input("Écrivez votre message...")
    
    # 2. Audio (Natif Streamlit)
    prompt_audio = st.audio_input("Ou enregistrez un vocal")

    # LOGIQUE DE CHOIX
    prompt_final = None
    type_input = None
    audio_path_temp = None

    if prompt_audio:
        if "last_audio_processed" not in st.session_state or st.session_state.last_audio_processed != prompt_audio:
            st.session_state.last_audio_processed = prompt_audio
            # Sauvegarde temp
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
        # Affichage User
        with st.chat_message("user"):
            if type_input == "audio":
                st.markdown("🎤 *Message vocal envoyé...*")
            else:
                st.markdown(prompt_final)
        
        # Sauvegarde User
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt_final if type_input == "texte" else "🎤 *Vocal*"
        })

        # Réponse Assistant
        with st.chat_message("assistant"):
            status = st.status("Traitement en cours...", expanded=True)
            
            try:
                # 1. Texte
                status.write("🧠 Réflexion...")
                reponse = detecter_et_repondre(
                    prompt_final, 
                    type_input, 
                    api_key, 
                    st.session_state.modele_actif
                )
                
                # 2. Nettoyage
                lang = "fr"
                texte_propre = reponse
                
                if "[WO]" in reponse:
                    lang = "wo"
                    texte_propre = reponse.replace("[WO]", "")
                elif "[EN]" in reponse:
                    lang = "en"
                    texte_propre = reponse.replace("[EN]", "")
                elif "[FR]" in reponse:
                    lang = "fr"
                    texte_propre = reponse.replace("[FR]", "")
                
                # 3. Audio
                status.write("🗣️ Synthèse vocale...")
                audio_sortie = generer_audio(texte_propre, lang)
                
                status.update(label="Réponse prête !", state="complete", expanded=False)
                
                # Affichage
                st.markdown(texte_propre)
                if audio_sortie:
                    st.audio(audio_sortie)
                    if lang == "wo":
                        st.caption("ℹ️ *Lecture phonétique (Wolof)*")
                
                # Sauvegarde Bot
                msg_data = {"role": "assistant", "content": texte_propre}
                if audio_sortie:
                    msg_data["audio"] = audio_sortie
                st.session_state.messages.append(msg_data)
                
                # Ménage
                if audio_path_temp: os.unlink(audio_path_temp)

            except Exception as e:
                status.update(label="Erreur", state="error")
                if "429" in str(e):
                    st.error("⚠️ Trop de demandes rapides. Attendez 1 minute.")
                else:
                    st.error(f"Erreur : {str(e)}")

if __name__ == "__main__":
    main()
