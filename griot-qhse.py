import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
from gtts import gTTS
import tempfile
import os

# ============================================================================
# 1. CONFIGURATION & STYLE
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE | Expert Sécurité",
    page_icon="🦁",
    layout="centered"
)

# Style CSS Pro
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
        border: 2px solid #FFD700;
    }
    .stChatMessage {
        border-radius: 15px;
        padding: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .info-box {
        background-color: #e0f7fa;
        padding: 10px;
        border-radius: 5px;
        font-size: 0.8em;
        color: #006064;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. LOGIQUE INTELLIGENTE (AUTO-DETECTION DU MODÈLE)
# ============================================================================

def trouver_modele_disponible(api_key):
    """
    Fonction CRITIQUE : Elle demande à Google quels modèles sont dispos
    pour cette clé API au lieu de deviner un nom au hasard.
    """
    genai.configure(api_key=api_key)
    try:
        # On liste tous les modèles disponibles pour cette clé
        liste_modeles = genai.list_models()
        
        modele_choisi = None
        
        # On cherche un modèle Gemini qui sait générer du contenu
        for m in liste_modeles:
            if 'generateContent' in m.supported_generation_methods:
                nom = m.name.lower()
                # On préfère le modèle Flash (plus rapide) ou Pro récent
                if 'gemini' in nom:
                    if 'flash' in nom:
                        return m.name # Priorité au Flash
                    if 'pro' in nom and not modele_choisi:
                        modele_choisi = m.name # Sinon on garde le Pro sous le coude
        
        # Si on a trouvé un Pro mais pas de Flash, on prend le Pro
        if modele_choisi:
            return modele_choisi
            
        # Si la liste est vide ou bizarre, on tente le nom par défaut le plus sûr
        return "models/gemini-1.5-flash"
        
    except Exception as e:
        return None

def generer_reponse(question, api_key, nom_modele):
    """Génère la réponse avec le modèle qu'on a trouvé."""
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
        return f"[FR] 🚫 Erreur sur le modèle {nom_modele} : {str(e)}"

# ============================================================================
# 3. FONCTIONS UTILITAIRES (AUDIO & DB)
# ============================================================================

def init_db():
    try:
        conn = sqlite3.connect('qhse_logs.db')
        conn.cursor().execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, question TEXT, reponse TEXT)')
        conn.commit()
        conn.close()
    except: pass

def generer_audio(texte, langue):
    if langue == "wo": return None # Pas d'audio pour Wolof (qualité médiocre)
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
    init_db()

    # EN-TÊTE
    st.markdown("""
    <div class="main-header">
        <h1>🦁 Griot QHSE</h1>
        <p>Expert Sécurité Trilingue (Wolof • Fr • En)</p>
    </div>
    """, unsafe_allow_html=True)

    # SIDEBAR
    with st.sidebar:
        st.header("⚙️ Configuration")
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("✅ Clé API active")
        else:
            api_key = st.text_input("🔑 Clé API Gemini", type="password")
        
        st.markdown("---")
        
        # AFFICHAGE DU MODÈLE DÉTECTÉ (POUR LE DEBUG)
        if api_key:
            if "nom_modele_actif" not in st.session_state:
                with st.spinner("Recherche du meilleur modèle..."):
                    modele_trouve = trouver_modele_disponible(api_key)
                    if modele_trouve:
                        st.session_state.nom_modele_actif = modele_trouve
                    else:
                        st.error("Impossible de lister les modèles. Vérifiez la clé.")
            
            if "nom_modele_actif" in st.session_state:
                st.info(f"🤖 Modèle actif : **{st.session_state.nom_modele_actif}**")
                
                if st.button("🔄 Changer de modèle"):
                    del st.session_state.nom_modele_actif
                    st.rerun()

    if not api_key:
        st.warning("Veuillez entrer une clé API pour commencer.")
        return

    # CHAT
    if "messages" not in st.session_state:
        st.session_state.messages = [{
            "role": "assistant", 
            "content": "Jàmm nga am ! Ma ngi tudd Griot QHSE. 🦁\nPoser votre question sécurité en Wolof, Français ou Anglais."
        }]

    for msg in st.session_state.messages:
        avatar = "🦁" if msg["role"] == "assistant" else "👷🏿‍♂️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # INPUT
    prompt = st.chat_input("Votre question...")

    if prompt:
        # User
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👷🏿‍♂️"):
            st.markdown(prompt)

        # Assistant
        with st.chat_message("assistant", avatar="🦁"):
            message_placeholder = st.empty()
            
            # Vérification qu'on a un modèle
            nom_modele = st.session_state.get("nom_modele_actif", "models/gemini-1.5-flash")
            
            with st.spinner("Le Griot réfléchit..."):
                reponse_brute = generer_reponse(prompt, api_key, nom_modele)
                
                # Gestion des langues et tags
                if "[WO]" in reponse_brute:
                    langue, texte = "wo", reponse_brute.replace("[WO]", "")
                elif "[EN]" in reponse_brute:
                    langue, texte = "en", reponse_brute.replace("[EN]", "")
                elif "[FR]" in reponse_brute:
                    langue, texte = "fr", reponse_brute.replace("[FR]", "")
                elif "🚫 Erreur" in reponse_brute:
                    langue, texte = "error", reponse_brute
                else:
                    langue, texte = "fr", reponse_brute # Par défaut

                message_placeholder.markdown(texte)

                # Audio
                if langue == "wo":
                    st.caption("🔇 *Audio Wolof désactivé (Texte uniquement)*")
                elif langue != "error":
                    path = generer_audio(texte, langue)
                    if path:
                        st.audio(path)
                        try: os.unlink(path)
                        except: pass
        
        st.session_state.messages.append({"role": "assistant", "content": texte})

if __name__ == "__main__":
    main()
