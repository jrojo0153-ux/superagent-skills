import requests
import pandas as pd
from datetime import datetime, timezone
import unicodedata
import sys

# Importamos la configuración validada en el Paso 1
import config

class DataIngestor:
    def __init__(self):
        self.football_headers = {
            'x-apisports-key': config.API_FOOTBALL_KEY
        }
        self.today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
    def _normalize_string(self, text):
        """
        Normaliza los nombres de los equipos para cruzar datos entre APIs.
        Elimina acentos, pasa a minúsculas y quita espacios extra.
        """
        if not isinstance(text, str): return ""
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        return text.lower().strip()

    def get_fixtures(self, league_id: int, season: int) -> pd.DataFrame:
        """
        Extrae los partidos programados para el día actual desde API-FOOTBALL.
        """
        url = f"{config.API_FOOTBALL_BASE_URL}/fixtures"
        params = {
            "league": league_id,
            "season": season,
            "date": self.today_date
        }
        
        try:
            response = requests.get(url, headers=self.football_headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('response'):
                return pd.DataFrame()
                
            fixtures = []
            for item in data['response']:
                fixtures.append({
                    'fixture_id': item['fixture']['id'],
                    'timestamp': item['fixture']['timestamp'],
                    'home_team': item['teams']['home']['name'],
                    'home_team_id': item['teams']['home']['id'],
                    'away_team': item['teams']['away']['name'],
                    'away_team_id': item['teams']['away']['id'],
                    'norm_home': self._normalize_string(item['teams']['home']['name']),
                    'norm_away': self._normalize_string(item['teams']['away']['name'])
                })
            return pd.DataFrame(fixtures)
            
        except requests.exceptions.RequestException as e:
            print(f"Error extrayendo fixtures (API-FOOTBALL): {e}")
            return pd.DataFrame()

    def get_real_time_odds(self, sport_key: str, regions: str = 'eu', markets: str = 'h2h') -> pd.DataFrame:
        """
        Extrae las cuotas en tiempo real desde THE ODDS API.
        """
        url = f"{config.ODDS_API_BASE_URL}/{sport_key}/odds"
        params = {
            'apiKey': config.ODDS_API_KEY,
            'regions': regions,
            'markets': markets,
            'oddsFormat': 'decimal'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            odds_list = []
            for match in data:
                # Extraer la mejor cuota promedio de los bookmakers disponibles
                if not match.get('bookmakers'): continue
                
                # Para este diseño, tomamos el primer bookmaker (ej. Pinnacle/Bet365) para simplicidad y rapidez
                market = match['bookmakers'][0]['markets'][0]
                outcomes = {outcome['name']: outcome['price'] for outcome in market['outcomes']}
                
                odds_list.append({
                    'home_team_odds_name': match['home_team'],
                    'away_team_odds_name': match['away_team'],
                    'norm_home': self._normalize_string(match['home_team']),
                    'norm_away': self._normalize_string(match['away_team']),
                    'commence_time': match['commence_time'],
                    'odds_home': outcomes.get(match['home_team'], 0),
                    'odds_away': outcomes.get(match['away_team'], 0),
                    'odds_draw': outcomes.get('Draw', 0)
                })
            return pd.DataFrame(odds_list)
            
        except requests.exceptions.RequestException as e:
            print(f"Error extrayendo cuotas (THE ODDS API): {e}")
            return pd.DataFrame()

    def merge_data(self, df_fixtures: pd.DataFrame, df_odds: pd.DataFrame) -> pd.DataFrame:
        """
        Cruza los datos de los partidos con sus respectivas cuotas utilizando 
        nombres normalizados.
        """
        if df_fixtures.empty or df_odds.empty:
            print("Advertencia: Uno de los DataFrames está vacío. No hay intersección de datos hoy.")
            return pd.DataFrame()
            
        # Hacemos un inner join basado en los nombres normalizados de los equipos locales
        # Nota en producción: Se requiere un diccionario de mapeo avanzado para cruces 100% exactos.
        merged_df = pd.merge(
            df_fixtures, 
            df_odds, 
            on=['norm_home', 'norm_away'], 
            how='inner'
        )
        
        return merged_df

if __name__ == "__main__":
    # Prueba de humo rápida si se ejecuta el archivo directamente
    print("Módulo de Ingesta Inicializado. Listo para ser llamado por el Orquestador.")
