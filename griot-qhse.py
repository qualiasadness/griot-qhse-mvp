import streamlit as st
import sys

# --- BLOC DE SÉCURITÉ AU DÉMARRAGE ---
try:
    import google.generativeai as genai
    import edge_tts
    import asyncio
    import nest_asyncio
    import tempfile
    import os
    
    # Patch asyncio
    nest_asyncio.apply()

except Exception as e:
    st.error("🚨 CRASH AU DÉMARRAGE (Erreur d'importation)")
    st.error(f"Détail : {e}")
    st.info("Conseil : Changez la version de Python pour 3.10 ou 3.11 dans les Settings de Streamlit Cloud.")
    st.stop()

# ============================================================================
# CONFIGURATION
# ============================================================================
st.set_page_config(page_title="Griot QHSE", page_icon="🦁", layout="centered")

# CSS Minimaliste pour éviter les conflits d'affichage
st.markdown("""
<style>
    .stApp { background-color: white; }
    h1 { color: #1E293B; text-align: center; }
    .subtitle { color: #64748B; text-align: center; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# LOGIQUE MÉTIER
# ============================================================================

def get_gemini_model_safe(api_key):
    genai.configure(api_key=api_key)
    try:
        # On teste une génération simple pou
