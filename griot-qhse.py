import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import nest_asyncio
import tempfile
import os

# Patch technique obligatoire pour l'audio sur le Cloud
nest_asyncio.apply()

# ============================================================================
# 1. CONFIGURATION (SIMPLE & PROPRE)
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE",
    page_icon="🦁",
    layout="centered"
)

# On cache juste le menu hamburger pour faire "App"
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: white; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. FONCTIONS TECHNIQUES (ROBUSTES)
# ============================================================================

async def generer_audio_hd_async(texte, langue):
    """Génère l'audio avec Edge TTS (Voix quasi-humaine)."""
    if langue == "wo": return None
    # Voix : Henri (FR) ou Christopher (EN)
    voice = "fr-FR-HenriNeural" if langue == "fr" else "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(texte, voice)
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    await communicate.save(tfile.name)
    return tfile.name

def generer_audio(texte, langue):
    try:
        return asyncio.run(generer_audio_hd_async(texte, langue))
    except Exception as e:
        print(f"Erreur Audio: {e}")
        return None

def detecter_et_repondre(entree, type_entree, api_key):
    genai.configure(api_key=api_key)
    
    # Prompt simplifié et strict
    system_instruction = """
    Tu es le Griot QHSE.
    RÈGLES :
    1. Si je parle WOLOF -> Réponds en WOLOF. Mets le tag [WO] au début.
    2. Si je parle FRANÇAIS -> Réponds en FRANÇAIS. Mets le tag [FR] au début.
    3. Si je parle ANGLAIS -> Réponds en ANGLAIS. Mets le tag [EN] au début.
    Sois concis et utile pour un travailleur sur chantier.
    """
    
    # On utilise flash par défaut
    model = genai.GenerativeModel('models/gemini-1.5-flash', system_instruction=system_instruction)
    
    if type_entree == "audio":
        # Traitement natif de l'audio par Gemini
        myfile = genai.upload_file(entree)
        response = model.generate_content(["Réponds dans la langue parlée dans cet audio.", myfile])
        return response.text
    else:
        # Traitement texte
        response = model.generate_content(entree)
        return response.text

# ============================================================================
# 3. INTERFACE PRINCIPALE
# ============================================================================

def main():
    st.title("🦁 Griot QHSE")
    st.caption("Expert Sécurité • Wolof / Français / English")

    # --- SIDEBAR (CONFIGURATION) ---
    with st.sidebar:
        st.header("🔐 Connexion")
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("Licence Active")
        else:
            api_key = st.text_input("Clé API Gemini", type="password")
            
        if st.button("🗑️ Nouvelle Conversation"):
            st.session_state.messages = []
            st.rerun()

    if not api_key:
        st.info("⬅️ Veuillez entrer votre Clé API dans le menu à gauche pour commencer.")
        return

    # --- HISTORIQUE DES MESSAGES ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "audio" in msg:
                st.audio(msg["audio"])

    # --- ZONE D'ENTRÉE (LA PARTIE IMPORTANTE) ---
    
    # 1. INPUT TEXTE
    prompt_texte = st.chat_input("Écrivez votre message ici...")
    
    # 2. INPUT AUDIO (NOUVEAUTÉ STREAMLIT 1.39)
    # C'est beaucoup plus stable que les boutons personnalisés
    prompt_audio = st.audio_input("Ou enregistrez votre voix (Mic)")

    # --- TRAITEMENT ---
    prompt_final = None
    type_input = None
    fichier_audio_path = None

    # Logique de priorité : Si on a un audio nouveau, on le prend
    if prompt_audio:
        # Astuce pour ne pas re-traiter le même fichier audio en boucle
        # On compare la taille ou l'ID si possible, sinon on gère via session state
        if "last_audio" not in st.session_state or st.session_state.last_audio != prompt_audio:
            st.session_state.last_audio = prompt_audio
            prompt_final = prompt_audio # C'est un fichier UploadedFile
            # On le sauvegarde temporairement sur le disque pour Gemini
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(prompt_audio.getvalue())
                fichier_audio_path = f.name
            
            prompt_final = fichier_audio_path
            type_input = "audio"
            
    # Sinon on prend le texte
    elif prompt_texte:
        prompt_final = prompt_texte
        type_input = "texte"

    # SI ON A UNE ENTRÉE À TRAITER
    if prompt_final:
        # Affiche le message utilisateur
        with st.chat_message("user"):
            if type_input == "audio":
                st.markdown("🎤 *Message vocal envoyé...*")
                st.audio(prompt_audio) # On réécoute ce qu'on a envoyé
            else:
                st.markdown(prompt_final)

        # Ajoute à l'historique session
        msg_user = {"role": "user", "content": prompt_final if type_input == "texte" else "🎤 *Message vocal*"}
        st.session_state.messages.append(msg_user)

        # GÉNÉRATION RÉPONSE
        with st.chat_message("assistant"):
            # Boite de statut pour voir que ça ne plante pas
            status = st.status("🔄 Le Griot réfléchit...", expanded=True)
            
            try:
                # 1. Appel API
                status.write("🧠 Analyse de la question...")
                reponse_brute = detecter_et_repondre(prompt_final, type_input, api_key)
                
                # 2. Nettoyage Tags
                lang, texte = "fr", reponse_brute
                if "[WO]" in reponse_brute: lang, texte = "wo", reponse_brute.replace("[WO]", "")
                elif "[EN]" in reponse_brute: lang, texte = "en", reponse_brute.replace("[EN]", "")
                elif "[FR]" in reponse_brute: lang, texte = "fr", reponse_brute.replace("[FR]", "")
                
                status.write("📝 Rédaction de la réponse...")
                
                # 3. Génération Audio HD
                audio_path = None
                if lang != "wo":
                    status.write("🗣️ Synthèse vocale HD...")
                    audio_path = generer_audio(texte, lang)
                
                status.update(label="✅ Terminé !", state="complete", expanded=False)
                
                # Affichage final
                st.markdown(texte)
                if audio_path:
                    st.audio(audio_path)
                    
                # Sauvegarde historique
                msg_bot = {"role": "assistant", "content": texte}
                if audio_path:
                    msg_bot["audio"] = audio_path
                st.session_state.messages.append(msg_bot)

                # Nettoyage fichier temp audio entrée
                if type_input == "audio" and fichier_audio_path:
                    os.unlink(fichier_audio_path)

            except Exception as e:
                status.update(label="❌ Erreur", state="error")
                st.error(f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    main()
