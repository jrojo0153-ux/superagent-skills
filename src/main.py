import os
from datetime import datetime, timezone
import pandas as pd

import config
from data_ingestion import DataIngestor
from ml_engine import EnsembleMLEngine
from quant_trader import QuantTrader

def _estimate_xg_from_odds(odds_home: float, odds_away: float) -> tuple:
    """
    Heurística para alimentar la matriz de Poisson. 
    Aproxima los Goles Esperados (xG) basándose en las cuotas del mercado,
    asumiendo un promedio estándar de 2.6 goles por partido de élite.
    """
    if odds_home <= 0 or odds_away <= 0:
        return 1.3, 1.3
        
    implied_home = 1 / odds_home
    implied_away = 1 / odds_away
    total_implied = implied_home + implied_away
    
    home_xg = (implied_home / total_implied) * 2.6
    away_xg = (implied_away / total_implied) * 2.6
    return round(home_xg, 2), round(away_xg, 2)

def main():
    print("Iniciando Motor Cuantitativo Deportivo...")
    config.validate_environment()
    
    ingestor = DataIngestor()
    ml = EnsembleMLEngine()
    trader = QuantTrader(kelly_fraction=0.25, min_ev_threshold=0.03) # Configurable
    
    # 1. Extracción (Ejemplo: Premier League)
    print("Extrayendo partidos programados...")
    df_fixtures = ingestor.get_fixtures(league_id=39, season=2023) 
    
    print("Extrayendo cuotas en tiempo real...")
    df_odds = ingestor.get_real_time_odds(sport_key='soccer_epl')
    
    # 2. Fusión de Datos
    df_merged = ingestor.merge_data(df_fixtures, df_odds)
    
    if df_merged.empty:
        print("No hay partidos cruzados con cuotas disponibles hoy.")
        with open("reporte_trading.md", "w", encoding="utf-8") as f:
            f.write("# 📉 Reporte Cuantitativo\n\n**Sin oportunidades detectadas hoy.**")
        return

    # Iniciar escritura del reporte
    report_content = f"# 🚀 Reporte de Trading Cuantitativo - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"

    # 3. Procesamiento y Trading Evento por Evento
    for _, row in df_merged.iterrows():
        match_name = f"{row['home_team']} vs {row['away_team']}"
        print(f"Procesando Motor Lógico: {match_name}")
        
        # Calcular xG Base
        home_xg, away_xg = _estimate_xg_from_odds(row['odds_home'], row['odds_away'])
        
        # Cálculos Matemáticos (Poisson)
        base_probs = ml.calculate_base_probabilities(home_xg, away_xg)
        
        # Ajuste Contextual (Llama vía RapidAPI)
        match_data = {"home_team": row['home_team'], "away_team": row['away_team']}
        adjusted_context = ml.reality_adjustment(match_data, base_probs)
        
        # Evaluación Cuantitativa (Kelly y EV)
        odds_dict = {
            "odds_home": row['odds_home'], 
            "odds_draw": row['odds_draw'], 
            "odds_away": row['odds_away']
        }
        trade_order = trader.evaluate_market(match_name, adjusted_context, odds_dict)
        
        # 4. Formateo Estricto de Salida
        prob_home = adjusted_context.get('Home', base_probs['1X2']['Home'])
        prob_draw = adjusted_context.get('Draw', base_probs['1X2']['Draw'])
        prob_away = adjusted_context.get('Away', base_probs['1X2']['Away'])
        justificacion = adjusted_context.get('Justificacion', 'Sin justificación disponible por latencia de API.')

        report_content += f"## [PARTIDO / MERCADOS DETECTADOS]\n"
        report_content += f"**{match_name}**\n\n"
        
        report_content += f"### PROBABILIDAD DEL ENSAMBLE REAL\n"
        report_content += f"- **1X2:** Local: {prob_home:.2%} | Empate: {prob_draw:.2%} | Visita: {prob_away:.2%}\n"
        report_content += f"- **Marcadores Exactos (Poisson):** {list(base_probs['Top_Scores'][0].keys())[0]} ({list(base_probs['Top_Scores'][0].values())[0]*100:.2%}%), {list(base_probs['Top_Scores'][1].keys())[0]} ({list(base_probs['Top_Scores'][1].values())[0]*100:.2 বিপুল}%)\n\n"
        
        report_content += f"### VALIDACIÓN CONTEXTUAL\n"
        report_content += f"> {justificacion}\n\n"
        
        if "Estado" not in trade_order:
            # Hay orden de valor
            report_content += f"### INFORME DE VALOR\n"
            report_content += f"- **EV Detectado:** +{trade_order['EV']} (Con cuota base de {trade_order['Cuota_Minima']})\n\n"
            
            report_content += f"### ORDEN DE TRADING\n"
            report_content += f"- **Mercado a Operar:** {trade_order['Mercado']} (1X2)\n"
            report_content += f"- **Cuota Mínima (Límite):** {trade_order['Cuota_Minima']}\n"
            report_content += f"- **Stake (Kelly Fraccional):** {trade_order['Stake_Pct']}%\n"
        else:
            # No hay valor
            report_content += f"### INFORME DE VALOR Y ORDEN DE TRADING\n"
            report_content += f"- ⛔ **{trade_order['Estado']}:** {trade_order['Motivo']}\n"
            
        report_content += "---\n\n"

    # 5. Generar Artefacto
    with open("reporte_trading.md", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("Ejecución finalizada. Archivo 'reporte_trading.md' generado.")

if __name__ == "__main__":
    main()
