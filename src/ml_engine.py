import numpy as np
from scipy.stats import poisson
import http.client
import json
import config

class EnsembleMLEngine:
    def __init__(self):
        self.max_goals = 5

    def calculate_base_probabilities(self, home_xg: float, away_xg: float) -> dict:
        home_poisson = [poisson.pmf(i, home_xg) for i in range(self.max_goals + 1)]
        away_poisson = [poisson.pmf(i, away_xg) for i in range(self.max_goals + 1)]
        prob_matrix = np.outer(home_poisson, away_poisson)
        
        prob_home = np.tril(prob_matrix, -1).sum()
        prob_draw = np.trace(prob_matrix)
        prob_away = np.triu(prob_matrix, 1).sum()
        
        exact_scores = []
        for i in range(self.max_goals + 1):
            for j in range(self.max_goals + 1):
                exact_scores.append(((i, j), prob_matrix[i][j]))
        exact_scores.sort(key=lambda x: x[1], reverse=True)
        
        return {
            "1X2": {"Home": prob_home, "Draw": prob_draw, "Away": prob_away},
            "Top_Scores": [{f"{s[0][0]}-{s[0][1]}": round(s[1], 4)} for s in exact_scores[:2]]
        }

    def reality_adjustment(self, match_data: dict, base_probs: dict) -> dict:
        conn = http.client.HTTPSConnection(config.LLM_HOST)
        prompt = (
            f"Analista deportivo. Partido: {match_data['home_team']} vs {match_data['away_team']}. "
            f"Probabilidades: {base_probs['1X2']}. Ajusta por contexto real (bajas, localía). "
            "Responde SOLO un JSON válido: {\"Home\": 0.0, \"Draw\": 0.0, \"Away\": 0.0, \"Justificacion\": \"texto\"}"
        )
        payload = json.dumps({"messages": [{"role": "user", "content": prompt}], "web_access": False})
        
        try:
            conn.request("POST", "/conversationllama", payload, config.get_llm_headers())
            res = conn.getresponse()
            response_str = res.read().decode("utf-8")
            if "```json" in response_str:
                response_str = response_str.split("```json")[1].split("```")[0].strip()
            return json.loads(response_str)
        except Exception:
            return {
                "Home": base_probs["1X2"]["Home"], "Draw": base_probs["1X2"]["Draw"], "Away": base_probs["1X2"]["Away"],
                "Justificacion": "Sin ajuste contextual por latencia."
            }
