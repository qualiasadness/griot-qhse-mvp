import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
import edge_tts
import asyncio
import nest_asyncio
from streamlit_mic_recorder import mic_recorder
import tempfile
import os

# Application du patch pour asyncio dans Streamlit
nest_asyncio.apply()

# ============================================================================
# 1. CONFIGURATION ET DESIGN PRO (CSS AVANCÉ)
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE | Plateforme Sécurité",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Palette de couleurs : Bleu Nuit (Confiance), Or (Sénégal), Blanc (Propreté)
st.markdown("""
<style>
    /* Masquer les éléments Streamlit par défaut pour faire "Logiciel" */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Fond général */
    .stApp {
        background-color: #F8F9FA;
    }

    /* Barre latérale pro */
    section[data-testid="stSidebar"] {
        background-color: #0F172A; /* Bleu très foncé */
        color: white;
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
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
        border-bottom: 4px solid #D97706; /* Or */
    }
    .custom-header h1 {
        margin: 0;
        color: #1E293B;
        font-family: 'Segoe UI', sans-serif;
        font-size: 1.8rem;
    }
    .custom-header p {
        margin: 0;
        color: #64748B;
    }

    /* Bulles de chat style WhatsApp/Messenger */
    .stChatMessage {
        background-color: transparent;
        border: none;
    }
    div[data-testid="stChatMessageContent"] {
        padding: 15px;
        border-radius: 15px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        font-family: 'Helvetica', sans-serif;
        line-height: 1.6;
    }
    /* Bulle Assistant (Griot) */
    div[data-testid="chatAvatarIcon-assistant"] + div[data-testid="stChatMessageContent"] {
        background-color: #FFFFFF;
        border-left: 5px solid #D97706;
        color: #334155;
    }
    /* Bulle Utilisateur */
    div[data-testid="chatAvatarIcon-user"] + div[data-testid="stChatMessageContent"] {
        background-color: #DBEAFE; /* Bleu clair */
        color: #1E3A8A;
        text-align: right;
    }

    /* Boutons stylisés */
    .stButton button {
        background-color: #D97706;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stButton button:hover {
        background-color: #B45309;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. FONCTIONS SYSTÈME (DB & AUDIO HD)
# ============================================================================

def init_db():
    try:
        conn = sqlite3.connect('qhse_master.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS interactions 
                     (id INTEGER PRIMARY KEY, titre TEXT, question TEXT, reponse TEXT, timestamp DATETIME)''')
        conn.commit()
        conn.close()
    except: pass

def get_history():
    try:
        conn = sqlite3.connect('qhse_master.db')
        c = conn.cursor()
        c.execute("SELECT id, titre, timestamp FROM interactions ORDER BY id DESC LIMIT 10")
        data = c.fetchall()
        conn.close()
        return data
    except: return []

def save_interaction(question, reponse):
    try:
        # On génère un titre court pour l'historique (les 30 premiers caractères)
        titre = (question[:25] + '...') if len(question) > 25 else question
        conn = sqlite3.connect('qhse_master.db')
        c = conn.cursor()
        c.execute("INSERT INTO interactions (titre, question, reponse, timestamp) VALUES (?, ?, ?, ?)",
                  (titre, question, reponse, datetime.now()))
        conn.commit()
        conn.close()
    except: pass

# --- AUDIO HAUTE QUALITÉ (EDGE TTS) ---
async def generer_audio_hd_async(texte, langue):
    """Génère un audio ultra-réaliste avec Microsoft Edge TTS."""
    if langue == "wo": return None # Wolof toujours pas supporté en TTS HD
    
    # Choix de la voix selon la langue
    voice = "fr-FR-HenriNeural" if langue == "fr" else "en-US-ChristopherNeural"
    
    communicate = edge_tts.Communicate(texte[:800], voice) # Limite pour la rapidité
    
    # Fichier temp
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    await communicate.save(tfile.name)
    return tfile.name

def generer_audio_hd(texte, langue):
    """Wrapper pour appeler la fonction async."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si une boucle tourne déjà (Streamlit), on utilise run_until_complete est risqué
            # On recrée une boucle locale juste pour ça ou on utilise asyncio.run si possible
            # Ici, nest_asyncio nous sauve.
            return loop.run_until_complete(generer_audio_hd_async(texte, langue))
        else:
            return asyncio.run(generer_audio_hd_async(texte, langue))
    except Exception as e:
        return None

# ============================================================================
# 3. INTELLIGENCE (TEXTE & AUDIO INPUT)
# ============================================================================

def get_gemini_model(api_key):
    genai.configure(api_key=api_key)
    # Recherche automatique du modèle
    for m in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
        try:
            model = genai.GenerativeModel(m)
            # Test léger
            model.generate_content("Test")
            return m
        except: continue
    return "models/gemini-1.5-flash"

def traiter_requete(entree_utilisateur, type_entree, api_key, model_name):
    """
    Traite soit du texte, soit de l'audio (bytes).
    Gemini Flash est MULTIMODAL : Il écoute l'audio !
    """
    genai.configure(api_key=api_key)
    
    system_instruction = """
    Rôle : Griot QHSE, expert sécurité Sénégal.
    Contexte : Tu parles à un travailleur.
    Langues : 
    - Si on parle Wolof -> Réponds Wolof Authentique. Tag [WO].
    - Si on parle Français -> Réponds Français Pro. Tag [FR].
    - Si on parle Anglais -> Réponds Anglais. Tag [EN].
    Consigne : Sois humain, direct, ne dis pas "je suis une IA".
    """
    
    model = genai.GenerativeModel(model_name, system_instruction=system_instruction)

    try:
        if type_entree == "audio":
            # On envoie l'audio brut à Gemini !
            # Il faut sauvegarder les bytes dans un fichier temporaire pour l'envoyer
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            tfile.write(entree_utilisateur)
            tfile.close()
            
            # Upload du fichier chez Google (temporaire)
            myfile = genai.upload_file(tfile.name)
            
            # Prompt multimodal
            response = model.generate_content(["Écoute cet audio. Si c'est du Wolof, réponds en Wolof. Sinon réponds dans la langue détectée.", myfile])
            
            # Nettoyage
            os.unlink(tfile.name)
        else:
            # Texte simple
            response = model.generate_content(entree_utilisateur)
            
        return response.text
        
    except Exception as e:
        return f"[FR] Erreur technique : {str(e)}"

# ============================================================================
# 4. INTERFACE UTILISATEUR
# ============================================================================

def main():
    init_db()
    
    # --- SIDEBAR (Menu Logiciel) ---
    with st.sidebar:
        st.markdown("### ⚙️ Panneau de Contrôle")
        
        # Clé API
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("Licence Active ✅")
        else:
            api_key = st.text_input("Clé de Licence (API)", type="password")
            
        st.markdown("---")
        
        # Historique Visuel
        st.markdown("### 🗄️ Dossiers Récents")
        historique = get_history()
        if historique:
            for item in historique:
                # Création de boutons pour chaque entrée d'historique
                if st.button(f"📄 {item[1]}", key=item[0], help=item[2]):
                    # Recharger une question n'est pas simple en Streamlit "chat", 
                    # mais on montre qu'on a la donnée.
                    st.toast("Chargement du dossier... (Fonctionnalité Démo)")
        else:
            st.caption("Aucun dossier enregistré.")

        st.markdown("---")
        st.markdown("<div style='text-align: center; color: #64748B; font-size: 0.8em;'>v3.0.1 - Ultimate Edition</div>", unsafe_allow_html=True)

    # --- ZONE PRINCIPALE ---
    
    # En-tête Custom
    st.markdown("""
    <div class="custom-header">
        <div>
            <h1>🦁 Griot QHSE</h1>
            <p>Assistant Intelligent de Sécurité au Travail</p>
        </div>
        <div style="background: #ECFDF5; color: #047857; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 0.9em;">
            🟢 En Ligne
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not api_key:
        st.warning("⚠️ En attente de la clé d'activation dans le panneau latéral.")
        return

    # Gestion de l'état (Session)
    if "messages" not in st.session_state:
        st.session_state.messages = [{
            "role": "assistant", 
            "content": "Salamalekum ! 👋🏿\n\nJe suis prêt. Vous pouvez m'écrire ou m'envoyer un message vocal (Wolof, Français, Anglais)."
        }]
    
    # Détection du modèle une seule fois
    if "model_name" not in st.session_state:
        st.session_state.model_name = get_gemini_model(api_key)

    # Affichage Chat
    for msg in st.session_state.messages:
        avatar = "🦁" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # --- ZONE D'ENTRÉE (Hybride : Texte + Audio) ---
    
    col_mic, col_text = st.columns([1, 4])
    
    audio_bytes = None
    user_text = None
    
    with col_mic:
        st.markdown("**Vocal**")
        # Enregistreur Audio
        audio_data = mic_recorder(
            start_prompt="🔴",
            stop_prompt="⏹️",
            key='recorder',
            format="wav",
            use_container_width=True
        )
        if audio_data:
            audio_bytes = audio_data['bytes']

    with col_text:
        user_text = st.chat_input("Écrivez votre message ici...")

    # LOGIQUE DE TRAITEMENT
    prompt_final = None
    type_input = None
    
    # Priorité à l'audio s'il vient d'être enregistré
    if audio_bytes and "last_audio_id" not in st.session_state:
        st.session_state.last_audio_id = audio_data['id'] # Pour éviter de traiter le même audio 2 fois
        prompt_final = audio_bytes
        type_input = "audio"
        display_msg = "🎤 *Message Vocal envoyé...*"
    elif audio_bytes and st.session_state.last_audio_id != audio_data['id']:
         st.session_state.last_audio_id = audio_data['id']
         prompt_final = audio_bytes
         type_input = "audio"
         display_msg = "🎤 *Message Vocal envoyé...*"
    elif user_text:
        prompt_final = user_text
        type_input = "text"
        display_msg = user_text

    if prompt_final:
        # 1. Afficher message User
        st.session_state.messages.append({"role": "user", "content": display_msg})
        with st.chat_message("user", avatar="👤"):
            st.markdown(display_msg)

        # 2. Réponse Assistant
        with st.chat_message("assistant", avatar="🦁"):
            placeholder = st.empty()
            with st.spinner("Analyse en cours..."):
                
                reponse_brute = traiter_requete(
                    prompt_final, 
                    type_input, 
                    api_key, 
                    st.session_state.model_name
                )
                
                # Parsing
                if "[WO]" in reponse_brute:
                    lang, txt = "wo", reponse_brute.replace("[WO]", "")
                elif "[EN]" in reponse_brute:
                    lang, txt = "en", reponse_brute.replace("[EN]", "")
                elif "[FR]" in reponse_brute:
                    lang, txt = "fr", reponse_brute.replace("[FR]", "")
                else:
                    lang, txt = "fr", reponse_brute

                placeholder.markdown(txt)
                
                # Audio HD
                if lang == "wo":
                    st.caption("🔇 *Audio non disponible pour le Wolof (limitation technique)*")
                else:
                    audio_path = generer_audio_hd(txt, lang)
                    if audio_path:
                        st.audio(audio_path, format="audio/mp3", start_time=0)
                        # Pas de suppression immédiate sinon Streamlit perd le fichier avant lecture
        
        # 3. Sauvegarde
        st.session_state.messages.append({"role": "assistant", "content": txt})
        save_interaction(display_msg if type_input == "text" else "Message Vocal", txt)

if __name__ == "__main__":
    main()
