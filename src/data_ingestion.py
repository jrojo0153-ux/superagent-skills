import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import unicodedata

import config

class DataIngestor:
    def __init__(self):
        self.football_headers = {
            'x-apisports-key': config.API_FOOTBALL_KEY
        }
        # Ventana de tiempo: Consultamos ayer, hoy y mañana para capturar cualquier partido de la jornada activa
        now_utc = datetime.now(timezone.utc)
        self.target_dates = [
            (now_utc - timedelta(days=1)).strftime('%Y-%m-%d'),
            now_utc.strftime('%Y-%m-%d'),
            (now_utc + timedelta(days=1)).strftime('%Y-%m-%d')
        ]
        
    def _normalize_string(self, text):
        """
        Normaliza de forma agresiva los nombres de los equipos para maximizar cruces.
        """
        if not isinstance(text, str): return ""
        # Quitar acentos y caracteres especiales
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        text = text.lower().strip()
        # Eliminar ruidos comunes de nombres en ambas APIs
        noise_words = ["cr ", "fc", "sd", "sc", "clube", "club", "atletico", " de ", "sports"]
        for word in noise_words:
            text = text.replace(word, "")
        return text.replace(" ", "").strip()

    def get_fixtures(self, league_id: int, season: int) -> pd.DataFrame:
        """
        Extrae los partidos iterando sobre la ventana de fechas para evitar pérdidas por zona horaria.
        """
        url = f"{config.API_FOOTBALL_BASE_URL}/fixtures"
        all_fixtures = []
        
        # Iteramos en nuestra ventana de 3 días
        for date_str in self.target_dates:
            params = {
                "league": league_id,
                "season": season,
                "date": date_str
            }
            try:
                response = requests.get(url, headers=self.football_headers, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if not data.get('response'): continue
                    
                for item in data['response']:
                    # Evitar duplicados si la API re-lista un partido
                    if any(f['fixture_id'] == item['fixture']['id'] for f in all_fixtures): continue
                        
                    all_fixtures.append({
                        'fixture_id': item['fixture']['id'],
                        'timestamp': item['fixture']['timestamp'],
                        'home_team': item['teams']['home']['name'],
                        'home_team_id': item['teams']['home']['id'],
                        'away_team': item['teams']['away']['name'],
                        'away_team_id': item['teams']['away']['id'],
                        'norm_home': self._normalize_string(item['teams']['home']['name']),
                        'norm_away': self._normalize_string(item['teams']['away']['name'])
                    })
            except Exception as e:
                print(f"Aviso en recolección de fixture para la fecha {date_str}: {e}")
                
        return pd.DataFrame(all_fixtures)

    def get_real_time_odds(self, sport_key: str, regions: str = 'eu', markets: str = 'h2h') -> pd.DataFrame:
        """
        Extrae las cuotas del mercado actual.
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
                if not match.get('bookmakers') or len(match['bookmakers']) == 0: continue
                
                market = match['bookmakers'][0]['markets'][0]
                outcomes = {outcome['name']: outcome['price'] for outcome in market['outcomes']}
                
                odds_list.append({
                    'home_team_odds_name': match['home_team'],
                    'away_team_odds_name': match['away_team'],
                    'norm_home': self._normalize_string(match['home_team']),
                    'norm_away': self._normalize_string(match['away_team']),
                    'odds_home': outcomes.get(match['home_team'], 0),
                    'odds_away': outcomes.get(match['away_team'], 0),
                    'odds_draw': outcomes.get('Draw', outcomes.get('Tie', 0))
                })
            return pd.DataFrame(odds_list)
            
        except Exception as e:
            print(f"Error extrayendo cuotas: {e}")
            return pd.DataFrame()

    def merge_data(self, df_fixtures: pd.DataFrame, df_odds: pd.DataFrame) -> pd.DataFrame:
        """
        Cruza los dataframes utilizando la normalización elástica de cadenas.
        """
        if df_fixtures.empty or df_odds.empty:
            return pd.DataFrame()
            
        # Unimos usando las columnas normalizadas e inmunes a diferencias de nomenclatura corporativa
        merged_df = pd.merge(
            df_fixtures, 
            df_odds, 
            on=['norm_home', 'norm_away'], 
            how='inner'
        )
        return merged_df
