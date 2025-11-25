"""
GRIOT QHSE - Assistant Virtuel de Sécurité pour les Travailleurs Sénégalais
============================================================================
Application MVP utilisant Streamlit et Google Gemini (FREE)
Compatible avec Streamlit Cloud
"""

import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
from googletrans import Translator
from gtts import gTTS
import tempfile
import os
import time

# ============================================================================
# CONFIGURATION DE LA PAGE
# ============================================================================

st.set_page_config(
    page_title="Griot QHSE",
    page_icon="👷🏿‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# INITIALISATION DE LA BASE DE DONNÉES
# ============================================================================

def init_db():
    """
    Initialise la base de données SQLite et crée la table 'logs' si elle n'existe pas.
    
    Structure de la table:
    - id: Identifiant auto-incrémenté
    - question: Question posée par l'utilisateur
    - reponse: Réponse générée par l'IA
    - langue_detectee: Langue détectée (fr, wo, etc.)
    - date_heure: Timestamp de la requête
    """
    conn = sqlite3.connect('qhse_logs.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            reponse TEXT NOT NULL,
            langue_detectee TEXT,
            date_heure TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# ============================================================================
# FONCTION D'ENREGISTREMENT DES LOGS
# ============================================================================

def enregistrer_log(question, reponse, langue):
    """
    Enregistre une interaction utilisateur dans la base de données.
    
    Args:
        question (str): Question posée par l'utilisateur
        reponse (str): Réponse générée par l'IA
        langue (str): Code de langue détecté (ex: 'fr', 'wo')
    """
    try:
        conn = sqlite3.connect('qhse_logs.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO logs (question, reponse, langue_detectee, date_heure)
            VALUES (?, ?, ?, ?)
        ''', (question, reponse, langue, datetime.now()))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.warning(f"Erreur d'enregistrement : {e}")

# ============================================================================
# FONCTION DE RÉCUPÉRATION DE L'HISTORIQUE
# ============================================================================

def recuperer_historique():
    """
    Récupère tous les enregistrements de la base de données.
    
    Returns:
        list: Liste de tuples contenant (id, question, reponse, langue, date_heure)
    """
    try:
        conn = sqlite3.connect('qhse_logs.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM logs ORDER BY date_heure DESC LIMIT 50')
        historique = cursor.fetchall()
        
        conn.close()
        return historique
    except Exception as e:
        st.warning(f"Erreur de lecture : {e}")
        return []

# ============================================================================
# FONCTION DE DÉTECTION DE LANGUE
# ============================================================================

def detecter_langue(texte):
    """
    Détecte la langue d'un texte donné.
    
    Args:
        texte (str): Texte à analyser
        
    Returns:
        str: Code de langue détecté (ex: 'fr', 'wo', 'en')
    """
    try:
        translator = Translator()
        detection = translator.detect(texte)
        return detection.lang
    except Exception as e:
        st.warning(f"Erreur de détection de langue : {e}")
        return 'fr'  # Par défaut, on suppose le français

# ============================================================================
# FONCTION DE TRADUCTION
# ============================================================================

def traduire_texte(texte, langue_source, langue_cible):
    """
    Traduit un texte d'une langue source vers une langue cible.
    
    Args:
        texte (str): Texte à traduire
        langue_source (str): Code de la langue source
        langue_cible (str): Code de la langue cible
        
    Returns:
        str: Texte traduit
    """
    try:
        translator = Translator()
        traduction = translator.translate(texte, src=langue_source, dest=langue_cible)
        return traduction.text
    except Exception as e:
        st.error(f"Erreur de traduction : {e}")
        return texte  # Retourne le texte original en cas d'erreur

# ============================================================================
# FONCTION DE GÉNÉRATION DE RÉPONSE AVEC GEMINI FREE
# ============================================================================

def generer_reponse_gemini(question_fr, langue_originale, api_key):
    """
    Génère une réponse en utilisant l'API Google Gemini (VERSION FREE).
    Applique la logique "Expert QHSE" avec un system prompt strict.
    
    Args:
        question_fr (str): Question en français
        langue_originale (str): Langue d'origine de la question
        api_key (str): Clé API Gemini
        
    Returns:
        str: Réponse générée (bilingue si nécessaire)
    """
    
    # Configuration de l'API avec la clé fournie
    genai.configure(api_key=api_key)
    
    # System Prompt pour configurer l'IA en Expert QHSE
    system_instruction = """Tu es "Griot QHSE", un expert sénégalais en Qualité, Hygiène, Sécurité et Environnement.

TON RÔLE:
- Être strict sur les normes de sécurité (ISO 45001, équipements EPI, Code du Travail Sénégalais, etc.)
- Adopter un ton paternel et bienveillant envers les travailleurs
- TOUJOURS citer au moins une norme ou référence QHSE dans chaque réponse
- Prioriser la sécurité avant tout

IMPORTANT: Sois concis mais complet. Maximum 150 mots par langue."""
    
    try:
        # Utilisation du modèle FREE : gemini-1.5-flash
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=system_instruction
        )
        
        # Construction du prompt complet
        if langue_originale == 'wo':
            prompt = f"""Question (traduite du Wolof): {question_fr}

FORMAT DE RÉPONSE OBLIGATOIRE (car question en Wolof):

🇫🇷 FRANÇAIS:
[Ta réponse complète en français avec citation de norme]

🇸🇳 WOLOF:
[Ta réponse traduite en Wolof de manière simple et accessible]"""
        else:
            prompt = f"Question: {question_fr}\n\nRéponds en français avec citation de norme QHSE."
        
        # Génération avec gestion du rate limit
        response = model.generate_content(prompt)
        
        # Attente pour éviter le rate limit (FREE = 15 requêtes/minute)
        time.sleep(4)
        
        return response.text
        
    except Exception as e:
        if "quota" in str(e).lower() or "rate" in str(e).lower():
            return "⚠️ Limite de requêtes atteinte. Veuillez patienter 1 minute avant de réessayer."
        else:
            st.error(f"Erreur Gemini : {e}")
            return f"Désolé, une erreur s'est produite : {str(e)}"

# ============================================================================
# FONCTION DE SYNTHÈSE VOCALE
# ============================================================================

def generer_audio(texte, langue='fr'):
    """
    Génère un fichier audio à partir d'un texte en utilisant gTTS.
    
    Args:
        texte (str): Texte à convertir en audio
        langue (str): Code de langue pour la synthèse vocale
        
    Returns:
        str: Chemin du fichier audio temporaire
    """
    try:
        # Extraction de la partie en Wolof si présent
        if "🇸🇳 WOLOF:" in texte:
            partie_wolof = texte.split("🇸🇳 WOLOF:")[1].strip()
            texte_audio = partie_wolof
            langue = 'fr'  # gTTS ne supporte pas le Wolof, on utilise le français
        elif "🇫🇷 FRANÇAIS:" in texte:
            partie_fr = texte.split("🇫🇷 FRANÇAIS:")[1].split("🇸🇳")[0].strip()
            texte_audio = partie_fr
        else:
            texte_audio = texte
        
        # Nettoyage du texte (suppression des emojis et symboles)
        texte_audio = texte_audio.replace("🇫🇷", "").replace("🇸🇳", "").strip()
        
        # Génération de l'audio
        tts = gTTS(text=texte_audio[:500], lang=langue, slow=False)  # Limite à 500 caractères
        
        # Création d'un fichier temporaire
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        tts.save(temp_file.name)
        
        return temp_file.name
        
    except Exception as e:
        st.error(f"Erreur lors de la génération audio : {e}")
        return None

# ============================================================================
# FONCTION DE RÉCUPÉRATION DE LA CLÉ API
# ============================================================================

def get_api_key():
    """
    Récupère la clé API depuis Streamlit Secrets (Cloud) ou depuis l'input utilisateur (Local).
    
    Returns:
        str: Clé API Gemini ou None
    """
    # Priorité 1 : Streamlit Secrets (pour le déploiement Cloud)
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    
    # Priorité 2 : Session state (pour conserver la clé pendant la session)
    if "api_key" in st.session_state and st.session_state.api_key:
        return st.session_state.api_key
    
    return None

# ============================================================================
# INTERFACE PRINCIPALE
# ============================================================================

def main():
    """
    Fonction principale de l'application Streamlit.
    Gère l'interface utilisateur et la logique de l'application.
    """
    
    # Initialisation de la base de données
    init_db()
    
    # En-tête de l'application
    st.title("👷🏿‍♂️ Griot QHSE : Sécurité avant tout")
    st.markdown("---")
    st.markdown("""
    **Bienvenue sur Griot QHSE !** 🇸🇳
    
    Votre assistant virtuel de sécurité qui comprend le Wolof et le Français.
    Posez vos questions sur la sécurité au travail, les EPI, les normes ISO, etc.
    """)
    
    # ========================================================================
    # SIDEBAR - CONFIGURATION
    # ========================================================================
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Tentative de récupération de la clé depuis les secrets
        api_key_from_secrets = get_api_key()
        
        if api_key_from_secrets:
            st.success("✅ API Gemini configurée (Streamlit Cloud)")
            api_key = api_key_from_secrets
        else:
            # Champ de saisie de la clé API pour le test local
            api_key_input = st.text_input(
                "Clé API Google Gemini",
                type="password",
                help="Entrez votre clé API Gemini FREE pour activer l'assistant"
            )
            
            if api_key_input:
                st.session_state.api_key = api_key_input
                api_key = api_key_input
                st.success("✅ API Gemini configurée avec succès !")
            else:
                api_key = None
                st.warning("⚠️ Veuillez entrer votre clé API pour continuer")
        
        st.markdown("---")
        st.info("💡 **Gemini FREE** : 15 requêtes/minute\n\nUne pause de 4 secondes est appliquée entre chaque requête.")
        
        st.markdown("---")
        
        # ====================================================================
        # SIDEBAR - HISTORIQUE
        # ====================================================================
        
        st.header("📊 Historique des Requêtes")
        
        if st.button("🔄 Actualiser l'historique"):
            st.rerun()
        
        historique = recuperer_historique()
        
        if historique:
            st.info(f"Total : {len(historique)} dernières requêtes")
            
            # Affichage de l'historique dans un expander
            with st.expander("Voir l'historique"):
                for log in historique[:10]:  # Limite à 10 pour la performance
                    st.markdown(f"""
                    **#{log[0]}** | 🌐 {log[3].upper()} | 📅 {log[4][:16]}
                    
                    **Q:** {log[1][:80]}{'...' if len(log[1]) > 80 else ''}
                    """)
                    st.markdown("---")
        else:
            st.info("Aucune requête enregistrée")
        
        # ====================================================================
        # FOOTER SIDEBAR
        # ====================================================================
        
        st.markdown("---")
        st.markdown("""
        ### 📖 Guide d'utilisation
        
        1. **Configuration** : Entrez votre clé API Gemini FREE
        2. **Question** : Écrivez en Wolof ou en Français
        3. **Réponse** : Lisez et écoutez la réponse
        4. **Historique** : Consultez vos questions passées
        
        [🔗 Obtenir une clé API](https://makersuite.google.com/app/apikey)
        """)
    
    # ========================================================================
    # ZONE PRINCIPALE - CHAT INTERFACE
    # ========================================================================
    
    # Vérification de la clé API avant d'afficher l'interface
    if not api_key:
        st.error("🔐 L'application nécessite une clé API Gemini pour fonctionner.")
        st.info("👉 Obtenez votre clé **GRATUITE** sur : https://makersuite.google.com/app/apikey")
        
        with st.expander("📘 Comment obtenir votre clé API gratuite ?"):
            st.markdown("""
            1. Rendez-vous sur https://makersuite.google.com/app/apikey
            2. Connectez-vous avec votre compte Google
            3. Cliquez sur "Create API Key"
            4. Copiez la clé et collez-la dans la barre latérale
            
            ⚡ **Gratuit** : 15 requêtes par minute
            """)
        return
    
    # Zone de saisie de la question
    st.subheader("💬 Posez votre question")
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        question_utilisateur = st.text_area(
            "Votre question en Wolof ou en Français :",
            height=120,
            placeholder="Exemples:\n🇸🇳 Naka lañu mën a jàppale bu baax ci sa liggéey?\n🇫🇷 Quels sont les équipements de sécurité obligatoires sur un chantier?",
            key="question_input"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        bouton_envoyer = st.button("🚀 Envoyer", use_container_width=True, type="primary")
    
    # ========================================================================
    # TRAITEMENT DE LA QUESTION
    # ========================================================================
    
    if bouton_envoyer and question_utilisateur.strip():
        
        with st.spinner("🤔 Griot QHSE réfléchit..."):
            
            # Étape 1 : Détection de la langue
            langue_detectee = detecter_langue(question_utilisateur)
            st.info(f"🔍 Langue détectée : **{langue_detectee.upper()}**")
            
            # Étape 2 : Traduction en français si nécessaire (pour le Wolof)
            if langue_detectee == 'wo':
                with st.spinner("🔄 Traduction vers le français..."):
                    question_fr = traduire_texte(question_utilisateur, 'wo', 'fr')
                    st.info(f"🔄 Traduction : *{question_fr}*")
            else:
                question_fr = question_utilisateur
            
            # Étape 3 : Génération de la réponse avec Gemini FREE
            with st.spinner("⏳ Génération de la réponse (4 secondes d'attente pour respecter le rate limit)..."):
                reponse = generer_reponse_gemini(question_fr, langue_detectee, api_key)
            
            # Étape 4 : Affichage de la réponse
            st.markdown("---")
            st.subheader("✅ Réponse de Griot QHSE")
            
            # Affichage avec mise en forme
            if "⚠️" in reponse:
                st.warning(reponse)
            else:
                st.markdown(reponse)
            
            # Étape 5 : Génération de l'audio (seulement si pas d'erreur)
            if "⚠️" not in reponse and "Désolé" not in reponse:
                st.markdown("---")
                st.subheader("🔊 Écouter la réponse")
                
                with st.spinner("🎵 Génération de l'audio..."):
                    fichier_audio = generer_audio(reponse, langue_detectee)
                
                if fichier_audio:
                    with open(fichier_audio, 'rb') as audio_file:
                        audio_bytes = audio_file.read()
                        st.audio(audio_bytes, format='audio/mp3')
                    
                    # Nettoyage du fichier temporaire
                    try:
                        os.unlink(fichier_audio)
                    except:
                        pass
                
                # Étape 6 : Enregistrement dans la base de données
                enregistrer_log(question_utilisateur, reponse, langue_detectee)
                st.success("💾 Conversation enregistrée dans l'historique")
    
    elif bouton_envoyer:
        st.warning("⚠️ Veuillez entrer une question avant d'envoyer")
    
    # ========================================================================
    # SECTION EXEMPLES
    # ========================================================================
    
    st.markdown("---")
    st.subheader("💡 Exemples de questions")
    
    col_ex1, col_ex2 = st.columns(2)
    
    with col_ex1:
        st.markdown("""
        **🇫🇷 En Français :**
        - Quels sont les EPI obligatoires pour un soudeur ?
        - Comment prévenir les accidents sur un chantier ?
        - Quelle est la norme ISO pour la sécurité au travail ?
        """)
    
    with col_ex2:
        st.markdown("""
        **🇸🇳 En Wolof :**
        - Lan mooy EPI ?
        - Naka lañu mën a jàppale ci accident ?
        - Sumula ma am casque ci liggéey ?
        """)
    
    # ========================================================================
    # FOOTER
    # ========================================================================
    
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: gray;'>
        <p>🛡️ Griot QHSE v1.0 - Votre sécurité, notre priorité | Développé pour les travailleurs sénégalais 🇸🇳</p>
        <p><small>Propulsé par Google Gemini 1.5 Flash (FREE) & Streamlit</small></p>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# POINT D'ENTRÉE DE L'APPLICATION
# ============================================================================

if __name__ == "__main__":
    main()