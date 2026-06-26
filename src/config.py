import os
import sys

# Cargar variables de entorno inyectadas por GitHub Secrets
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")  # Añadida correctamente

# Hosts de RapidAPI de destino
LLM_HOST = "open-ai21.p.rapidapi.com"
BET365_HOST = "bet36528.p.rapidapi.com"

def validate_environment():
    """Valida que las claves maestras estén presentes en el entorno antes de correr."""
    if not RAPIDAPI_KEY:
        print("CRITICAL ERROR: Falta la GitHub Secret: RAPIDAPI_KEY")
        sys.exit(1)
    if not API_FOOTBALL_KEY:
        print("WARNING: Falta la GitHub Secret: API_FOOTBALL_KEY. Algunas funciones secundarias podrían fallar.")

def get_llm_headers():
    """Cabeceras para el modelo Llama."""
    return {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': LLM_HOST,
        'Content-Type': "application/json"
    }

def get_bet365_headers():
    """Cabeceras para el endpoint de Bet365."""
    return {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': BET365_HOST,
        'Content-Type': "application/json"
    }
