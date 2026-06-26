class QuantTrader:
    def __init__(self, kelly_fraction: float = 0.25, min_ev_threshold: float = 0.05):
        # Usamos Kelly Fraccional (ej. 0.25 = 25% de Kelly) para mitigar la varianza
        self.kelly_fraction = kelly_fraction
        self.min_ev_threshold = min_ev_threshold

    def calculate_ev(self, probability: float, decimal_odds: float) -> float:
        """
        Calcula el Valor Esperado (Expected Value).
        Fórmula: EV = (Probabilidad * Cuota) - 1
        """
        if probability <= 0 or decimal_odds <= 1:
            return -1.0
        return (probability * decimal_odds) - 1.0

    def calculate_kelly_stake(self, probability: float, decimal_odds: float) -> float:
        """
        Calcula el porcentaje de Stake recomendado usando el Criterio de Kelly Fraccional.
        """
        if probability <= 0 or decimal_odds <= 1:
            return 0.0
            
        q = 1.0 - probability
        b = decimal_odds - 1.0
        
        kelly_percentage = ( (b * probability) - q ) / b
        
        # Solo apostamos si Kelly es positivo (hay ventaja matemática)
        if kelly_percentage <= 0:
            return 0.0
            
        return round((kelly_percentage * self.kelly_fraction) * 100, 2)

    def evaluate_market(self, match_name: str, probabilities: dict, odds: dict) -> dict:
        """
        Cruza las probabilidades ajustadas con las cuotas reales para encontrar valor.
        """
        markets = [
            ("Home", probabilities.get("Home", 0), odds.get("odds_home", 0)),
            ("Draw", probabilities.get("Draw", 0), odds.get("odds_draw", 0)),
            ("Away", probabilities.get("Away", 0), odds.get("odds_away", 0))
        ]
        
        best_order = None
        highest_ev = -1
        
        for market_name, prob, odd in markets:
            if odd <= 1.0: continue
            
            ev = self.calculate_ev(prob, odd)
            if ev > highest_ev:
                highest_ev = ev
                stake = self.calculate_kelly_stake(prob, odd)
                best_order = {
                    "Mercado": market_name,
                    "Probabilidad_Real": round(prob * 100, 2),
                    "Cuota_Minima": odd,
                    "EV": round(ev, 4),
                    "Stake_Pct": stake
                }
                
        # Solo emitir orden si el EV supera nuestro umbral mínimo
        if highest_ev >= self.min_ev_threshold:
            return best_order
        else:
            return {"Estado": "NO BET", "Motivo": "EV insuficiente o negativo"}
