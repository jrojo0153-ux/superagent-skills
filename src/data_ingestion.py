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
        # Ventana de tiempo dinámica: consultamos ayer, hoy y mañana (UTC)
        # para garantizar la captura de cualquier jornada activa sin importar la zona horaria del partido
        now_utc = datetime.now(timezone.utc)
        self.target_dates = [
            (now_utc - timedelta(days=1)).strftime('%Y-%m-%d'),
            now_utc.strftime('%Y-%m-%d'),
            (now_utc + timedelta(days=1)).strftime('%Y-%m-%d')
        ]
        
    def _normalize_string(self, text):
        """
        Normaliza agresivamente los nombres de los equipos para maximizar 
        la tasa de coincidencia (match rate) entre ambas APIs.
        """
        if not isinstance(text, str): return ""
        # Remover acentos, eñes y caracteres especiales
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        text = text.lower().strip()
        
        # Eliminar ruidos o prefijos/sufijos corporativos y deportivos comunes
        noise_words = [
            "cr ", "fc", "sd", "sc", "clube", "club", "atletico", " de ", "sports", 
            "afc", "cf", "ud", "cd", "rcd", "ac", "inter", "juventude", "united"
        ]
        for word in noise_words:
            text = text.replace(word, "")
            
        # Remover espacios en blanco para compactar cadenas (ej: "manchester city" -> "manchestercity")
        return text.replace(" ", "").strip()

    def get_fixtures(self, league_id: int, season: int) -> pd.DataFrame:
        """
        Extrae los partidos programados desde API-FOOTBALL iterando sobre la ventana de fechas.
        """
        url = f"{config.API_FOOTBALL_BASE_URL}/fixtures"
        all_fixtures = []
        
        for date_str in self.target_dates:
            params = {
                "league": league_id,
                "season": season,
                "date": date_str
            }
            try:
                response = requests.get(url, headers=self.football_headers, params=params, timeout=12)
                response.raise_for_status()
                data = response.json()
                
                if not data.get('response'): 
                    continue
                    
                for item in data['response']:
                    # Evitar duplicar registros si un partido aparece en dos respuestas de la API
                    if any(f['fixture_id'] == item['fixture']['id'] for f in all_fixtures): 
                        continue
                        
                    all_fixtures.append({
                        'fixture_id': item['fixture']['id'],
                        'timestamp': item['fixture']['timestamp'],
                        'league_id': league_id,
                        'home_team': item['teams']['home']['name'],
                        'home_team_id': item['teams']['home']['id'],
                        'away_team': item['teams']['away']['name'],
                        'away_team_id': item['teams']['away']['id'],
                        'norm_home': self._normalize_string(item['teams']['home']['name']),
                        'norm_away': self._normalize_string(item['teams']['away']['name'])
                    })
            except Exception as e:
                print(f"Aviso: No se pudieron obtener partidos para la liga {league_id} en la fecha {date_str}: {e}")
                
        return pd.DataFrame(all_fixtures)

    def get_real_time_odds(self, sport_key: str = 'soccer', regions: str = 'eu', markets: str = 'h2h') -> pd.DataFrame:
        """
        Extrae las cuotas del mercado global de fútbol en tiempo real desde THE ODDS API.
        """
        # Endpoint para obtener cuotas de múltiples ligas simultáneamente usando 'soccer'
        url = f"{config.ODDS_API_BASE_URL}/{sport_key}/odds"
        params = {
            'apiKey': config.ODDS_API_KEY,
            'regions': regions,
            'markets': markets,
            'oddsFormat': 'decimal'
        }
        
        try:
            response = requests.get(url, params=params, timeout=12)
            response.raise_for_status()
            data = response.json()
            
            odds_list = []
            for match in data:
                # Si el evento no tiene corredores de apuestas disponibles, se ignora
                if not match.get('bookmakers') or len(match['bookmakers']) == 0: 
                    continue
                
                # Extraemos las cuotas del mercado principal del primer bookmaker regulado (ej: Pinnacle / Bet365)
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
            print(f"Error crítico extrayendo cuotas en tiempo real (The Odds API): {e}")
            return pd.DataFrame()

    def merge_data(self, df_fixtures: pd.DataFrame, df_odds: pd.DataFrame) -> pd.DataFrame:
        """
        Cruza los datos de partidos y cuotas mundiales mediante un cruce interno (inner join)
        basado en la normalización simétrica de nombres de equipos.
        """
        if df_fixtures.empty or df_odds.empty:
            print("Monitoreo de Mercado: Al menos una de las fuentes de datos (Fixtures/Cuotas) está vacía.")
            return pd.DataFrame()
            
        # Cruce exacto sobre las cadenas limpias de ambos lados
        merged_df = pd.merge(
            df_fixtures, 
            df_odds, 
            on=['norm_home', 'norm_away'], 
            how='inner'
        )
        return merged_df

if __name__ == "__main__":
    print("Módulo de Ingesta Inteligente y Multiliga Inicializado.")
