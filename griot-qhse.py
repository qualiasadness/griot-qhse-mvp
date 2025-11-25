import streamlit as st
import google.generativeai as genai

# ============================================================================
# 1. DESIGN PROPRE (Gris/Blanc/Bleu)
# ============================================================================
st.set_page_config(page_title="Griot QHSE", page_icon="🦁", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: white; }
    .header {
        text-align: center;
        padding: 20px;
        border-bottom: 2px solid #D97706;
        margin-bottom: 20px;
    }
    h1 { color: #1E293B; margin:0; }
    p { color: #64748B; }
    .stChatMessage { background-color: transparent; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 2. LOGIQUE SIMPLE
# ============================================================================

def main():
    # En-tête
    st.markdown("""
    <div class="header">
        <h1>🦁 Griot QHSE</h1>
        <p>Expert Sécurité • Wolof / Français / English</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar Clé API
    with st.sidebar:
        st.header("⚙️ Paramètres")
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("Licence Active ✅")
        else:
            api_key = st.text_input("Clé API Gemini", type="password")

        st.markdown("---")
        if st.button("🗑️ Effacer l'historique"):
            st.session_state.messages = []
            st.rerun()

    if not api_key:
        st.info("⬅️ Mets ta clé API à gauche pour commencer.")
        return

    # Configuration Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-1.5-flash", system_instruction="""
    Tu es le Griot QHSE. 
    - Si je parle Wolof -> Réponds en Wolof.
    - Si je parle Français -> Réponds en Français.
    - Si je parle Anglais -> Réponds en Anglais.
    Sois bref et pro.
    """)

    # Historique
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Affichage Chat
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Zone de saisie
    prompt = st.chat_input("Pose ta question ici...")

    if prompt:
        # User
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Assistant
        with st.chat_message("assistant"):
            try:
                response = model.generate_content(prompt)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Erreur : {e}")

if __name__ == "__main__":
    main()
