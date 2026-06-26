import numpy as np
from scipy.stats import poisson
import http.client
import json
import config

class EnsembleMLEngine:
    def __init__(self):
        # Límite máximo de goles a calcular para la matriz de Poisson
        self.max_goals = 5

    def calculate_base_probabilities(self, home_xg: float, away_xg: float) -> dict:
        """
        Calcula las probabilidades 1X2 usando la Distribución de Poisson 
        basada en los Goles Esperados (xG) de cada equipo.
        """
        home_poisson = [poisson.pmf(i, home_xg) for i in range(self.max_goals + 1)]
        away_poisson = [poisson.pmf(i, away_xg) for i in range(self.max_goals + 1)]
        
        prob_matrix = np.outer(home_poisson, away_poisson)
        
        prob_home = np.tril(prob_matrix, -1).sum()
        prob_draw = np.trace(prob_matrix)
        prob_away = np.triu(prob_matrix, 1).sum()
        
        # Extracción de marcadores exactos más probables
        exact_scores = []
        for i in range(self.max_goals + 1):
            for j in range(self.max_goals + 1):
                exact_scores.append(((i, j), prob_matrix[i][j]))
        
        exact_scores.sort(key=lambda x: x[1], reverse=True)
        
        return {
            "1X2": {"Home": prob_home, "Draw": prob_draw, "Away": prob_away},
            "Top_Scores": [
                {f"{score[0][0]}-{score[0][1]}": round(score[1], 4)} 
                for score in exact_scores[:2]
            ]
        }

    def reality_adjustment(self, match_data: dict, base_probs: dict) -> dict:
        """
        Envía el contexto del partido al endpoint de Llama en RapidAPI para aplicar
        un multiplicador/penalizador basado en factores humanos.
        """
        conn = http.client.HTTPSConnection(config.RAPIDAPI_HOST)
        
        prompt = (
            f"Eres un analista deportivo. Partido: {match_data['home_team']} vs {match_data['away_team']}. "
            f"Probabilidades matemáticas: {base_probs['1X2']}. "
            "Ajusta estas probabilidades considerando el contexto actual (lesiones, historial, localía). "
            "Responde ÚNICAMENTE con un JSON válido en este formato estricto, sin texto adicional: "
            "{\"Home\": 0.0, \"Draw\": 0.0, \"Away\": 0.0, \"Justificacion\": \"Breve razonamiento\"}"
        )
        
        payload = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "web_access": False
        })
        
        try:
            conn.request("POST", "/conversationllama", payload, config.get_rapidapi_headers())
            res = conn.getresponse()
            data = res.read().decode("utf-8")
            
            # Limpieza básica de la respuesta para extraer el JSON
            response_str = data
            if "```json" in response_str:
                response_str = response_str.split("```json")[1].split("```")[0].strip()
            
            adjusted_data = json.loads(response_str)
            return adjusted_data
            
        except Exception as e:
            print(f"Error en Ajuste de Realidad (RapidAPI): {e}. Usando probabilidades base.")
            return {
                "Home": base_probs["1X2"]["Home"],
                "Draw": base_probs["1X2"]["Draw"],
                "Away": base_probs["1X2"]["Away"],
                "Justificacion": "Fallo en API. Sin ajuste contextual."
            }
