import os
from datetime import datetime, timezone
import pandas as pd

import config
from data_ingestion import DataIngestor
from ml_engine import EnsembleMLEngine
from quant_trader import QuantTrader

def _estimate_xg_from_odds(odds_home: float, odds_away: float) -> tuple:
    """Aproxima los Goles Esperados (xG) basándose en las cuotas implícitas."""
    if odds_home <= 0 or odds_away <= 0:
        return 1.3, 1.3
    implied_home = 1 / odds_home
    implied_away = 1 / odds_away
    total_implied = implied_home + implied_away
    home_xg = (implied_home / total_implied) * 2.6
    away_xg = (implied_away / total_implied) * 2.6
    return round(home_xg, 2), round(away_xg, 2)

def main():
    print("Iniciando Motor Cuantitativo - Bet365 Live...")
    config.validate_environment()
    
    ingestor = DataIngestor()
    ml = EnsembleMLEngine()
    trader = QuantTrader(kelly_fraction=0.25, min_ev_threshold=0.03) 
    
    print("Extrayendo partidos y cuotas unificadas desde Bet365...")
    # IDs de torneos pasados por parámetro (Mundial / Clasificatorias)
    df_data = ingestor.get_tournament_data(tournament_ids="17,31")
    
    if df_data.empty:
        print("⚠️ No se encontraron mercados activos de Bet365 para estos IDs en este momento.")
        with open("reporte_trading.md", "w", encoding="utf-8") as f:
            f.write(f"# 🚀 Reporte de Trading - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
                    "### 📊 ESTADO\n> Mercados cerrados o sin eventos disponibles para los IDs seleccionados.")
        return

    report_content = f"# 🚀 Reporte de Trading Cuantitativo - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
    report_content += f"**Eventos Orgánicos Analizados:** {len(df_data)}\n\n---\n\n"

    for _, row in df_data.iterrows():
        match_name = f"{row['home_team']} vs {row['away_team']}"
        print(f"Procesando: {match_name}")
        
        home_xg, away_xg = _estimate_xg_from_odds(row['odds_home'], row['odds_away'])
        base_probs = ml.calculate_base_probabilities(home_xg, away_xg)
        
        # Ajuste Contextual con Llama
        match_data = {"home_team": row['home_team'], "away_team": row['away_team']}
        adjusted_context = ml.reality_adjustment(match_data, base_probs)
        
        # Evaluar Valor Económico
        odds_dict = {
            "odds_home": row['odds_home'], 
            "odds_draw": row['odds_draw'], 
            "odds_away": row['odds_away']
        }
        trade_order = trader.evaluate_market(match_name, adjusted_context, odds_dict)
        
        # Formateo del Reporte
        prob_home = adjusted_context.get('Home', base_probs['1X2']['Home'])
        prob_draw = adjusted_context.get('Draw', base_probs['1X2']['Draw'])
        prob_away = adjusted_context.get('Away', base_probs['1X2']['Away'])
        justificacion = adjusted_context.get('Justificacion', 'Sin anomalías físicas reportadas.')

        report_content += f"## [PARTIDO / MERCADOS DETECTADOS]\n"
        report_content += f"**{match_name}**\n\n"
        
        report_content += f"### PROBABILIDAD DEL ENSAMBLE REAL\n"
        report_content += f"- **1X2:** Local: {prob_home:.2%} | Empate: {prob_draw:.2%} | Visita: {prob_away:.2%}\n"
        report_content += f"- **Marcadores Exactos (Poisson):** {list(base_probs['Top_Scores'][0].keys())[0]} ({list(base_probs['Top_Scores'][0].values())[0]*100:.2%}%), {list(base_probs['Top_Scores'][1].keys())[0]} ({list(base_probs['Top_Scores'][1].values())[0]*100:.2%}%)\n\n"
        
        report_content += f"### VALIDACIÓN CONTEXTUAL\n"
        report_content += f"> {justificacion}\n\n"
        
        if "Estado" not in trade_order:
            report_content += f"### INFORME DE VALOR\n"
            report_content += f"- **EV Detectado:** +{trade_order['EV']} (Cuota: {trade_order['Cuota_Minima']})\n\n"
            report_content += f"### ORDEN DE TRADING\n"
            report_content += f"- **Mercado a Operar:** {trade_order['Mercado']} (1X2)\n"
            report_content += f"- **Cuota Mínima:** {trade_order['Cuota_Minima']}\n"
            report_content += f"- **Stake (Kelly):** {trade_order['Stake_Pct']}%\n"
        else:
            report_content += f"### INFORME DE VALOR Y ORDEN DE TRADING\n"
            report_content += f"- ⛔ **{trade_order['Estado']}:** {trade_order['Motivo']}\n"
            
        report_content += "---\n\n"

    with open("reporte_trading.md", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("Ejecución finalizada con éxito. Reporte generado de manera real.")

if __name__ == "__main__":
    main()
