import http.client
import json
import pandas as pd
import config

class DataIngestor:
    def __init__(self):
        self.host = config.BET365_HOST
        self.headers = config.get_bet365_headers()
        
        # Guardamos la llave de API-FOOTBALL en los atributos de la clase 
        # por si se requiere para expansiones de estadísticas o fixtures secundarios
        self.football_key = config.API_FOOTBALL_KEY
        self.football_headers = {
            'x-apisports-key': self.football_key
        }

    def get_tournament_data(self, tournament_ids: str = "17,31") -> pd.DataFrame:
        """
        Extrae partidos y cuotas unificados de Bet365 mapeando el JSON nativo.
        """
        conn = http.client.HTTPSConnection(self.host)
        path = f"/odds-by-tournaments?tournamentIds={tournament_ids.replace(',', '%2C')}&verbosity=3"
        
        try:
            conn.request("GET", path, headers=self.headers)
            res = conn.getresponse()
            raw_data = res.read().decode("utf-8")
            data = json.loads(raw_data)
            
            events_list = []
            # Estructura nativa de Bet365 API
            results = data.get('results', data.get('data', []))
            
            for event in results:
                home_team = event.get('home_team', event.get('home', {}).get('name', 'Desconocido'))
                away_team = event.get('away_team', event.get('away', {}).get('name', 'Desconocido'))
                
                # Extracción de cuotas 1X2 (Decimales)
                odds = event.get('odds', {})
                odds_home = odds.get('home', odds.get('1', 0))
                odds_draw = odds.get('draw', odds.get('X', 0))
                odds_away = odds.get('away', odds.get('2', 0))
                
                if odds_home and odds_away:
                    events_list.append({
                        'home_team': home_team,
                        'away_team': away_team,
                        'odds_home': float(odds_home),
                        'odds_draw': float(odds_draw) if odds_draw else 0.0,
                        'odds_away': float(odds_away)
                    })
            
            return pd.DataFrame(events_list)
            
        except Exception as e:
            print(f"Error extrayendo datos de Bet365: {e}")
            return pd.DataFrame()

    def merge_data(self, df_fixtures: pd.DataFrame, df_odds: pd.DataFrame) -> pd.DataFrame:
        """Mantiene compatibilidad de interfaz retornando el DataFrame unificado."""
        return df_fixtures

if __name__ == "__main__":
    print("Módulo de Ingesta Bet365 e Inicialización de API-Football completado.")
