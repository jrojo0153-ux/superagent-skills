import os
import sys

# Cargar variables de entorno inyectadas por GitHub Secrets
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# Configuraciones Base de las APIs
RAPIDAPI_HOST = "open-ai21.p.rapidapi.com"
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4/sports"

def validate_environment():
    """Valida que todas las claves maestras estén presentes en el entorno antes de la ejecución."""
    missing_keys = []
    if not API_FOOTBALL_KEY: missing_keys.append("API_FOOTBALL_KEY")
    if not ODDS_API_KEY: missing_keys.append("ODDS_API_KEY")
    if not RAPIDAPI_KEY: missing_keys.append("RAPIDAPI_KEY")
    
    if missing_keys:
        print(f"CRITICAL ERROR: Faltan las siguientes GitHub Secrets: {', '.join(missing_keys)}")
        sys.exit(1)

def get_rapidapi_headers():
    """Genera las cabeceras estándar para la conexión con el motor lógico en RapidAPI."""
    return {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST,
        'Content-Type': "application/json"
    }
