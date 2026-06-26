import os
from datetime import datetime, timezone
import pandas as pd

import config
from data_ingestion import DataIngestor
from ml_engine import EnsembleMLEngine
from quant_trader import QuantTrader

def _estimate_xg_from_odds(odds_home: float, odds_away: float) -> tuple:
    """
    Heurística cuantitativa para alimentar la matriz de Poisson. 
    Aproxima los Goles Esperados (xG) basándose en las cuotas implícitas del mercado,
    asumiendo un promedio estándar de 2.6 goles totales por partido.
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
    print("Iniciando Motor Cuantitativo Deportivo en Producción Live...")
    config.validate_environment()
    
    ingestor = DataIngestor()
    ml = EnsembleMLEngine()
    trader = QuantTrader(kelly_fraction=0.25, min_ev_threshold=0.03) 
    
    # 1. Extracción de Datos en Tiempo Real
    # Usamos 'soccer' global en The Odds API para traer múltiples ligas importantes activas a la vez
    print("Extrayendo cuotas de todos los partidos de fútbol activos en tiempo real...")
    df_odds = ingestor.get_real_time_odds(sport_key='soccer')
    
    # Lista de ligas principales a monitorear en API-FOOTBALL para realizar el cruce cruzado
    # 39: Premier League, 140: LaLiga, 71: Brasileirão, 253: MLS, 135: Serie A
    monitored_leagues = [39, 140, 71, 253, 135]
    df_fixtures_list = []
    
    print("Escaneando jornadas y fixtures en API-FOOTBALL...")
    for league_id in monitored_leagues:
        # Se asume temporada 2026 de acuerdo al año en curso
        df_league = ingestor.get_fixtures(league_id=league_id, season=2026)
        if not df_league.empty:
            df_fixtures_list.append(df_league)
            
    if df_fixtures_list:
        df_fixtures = pd.concat(df_fixtures_list, ignore_index=True)
    else:
        df_fixtures = pd.DataFrame()
    
    # 2. Fusión y Cruce de Datos Orgánicos
    df_merged = ingestor.merge_data(df_fixtures, df_odds)
    
    # Si tras el escaneo global sigue vacío (ej. horas de la madrugada sin partidos), 
    # mantenemos un aviso en el log pero generamos el reporte limpio vacío o informando la situación.
    if df_merged.empty:
        print("⚠️ No se detectaron intersecciones de partidos en este instante del día. Creando reporte de espera de mercado.")
        with open("reporte_trading.md", "w", encoding="utf-8") as f:
            f.write(f"# 🚀 Reporte de Trading Cuantitativo - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
                    "### 📊 ESTADO DEL MERCADO\n"
                    "> En este momento las cuotas de las casas de apuestas analizadas no se alinean con ventanas de partidos de fútbol programados para las próximas horas. El sistema volverá a escanear en el siguiente ciclo cron.")
        return

    # Inicializar la estructura del reporte en Markdown
    report_content = f"# 🚀 Reporte de Trading Cuantitativo - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
    report_content += f"**Partidos Reales Detectados y Procesados:** {len(df_merged)}\n\n---\n\n"

    # 3. Procesamiento Cuantitativo Evento por Evento
    for _, row in df_merged.iterrows():
        match_name = f"{row['home_team']} vs {row['away_team']}"
        print(f"Analizando mercado real: {match_name}")
        
        # Calcular xG Base
        home_xg, away_xg = _estimate_xg_from_odds(row['odds_home'], row['odds_away'])
        
        # Ejecución del Modelo 1: Distribución de Poisson
        base_probs = ml.calculate_base_probabilities(home_xg, away_xg)
        
        # Ejecución del Modelo 2: Ajuste Contextual de Realidad (Llama vía RapidAPI)
        match_data = {"home_team": row['home_team'], "away_team": row['away_team']}
        adjusted_context = ml.reality_adjustment(match_data, base_probs)
        
        # Evaluación de Valor y Gestión de Capital (Kelly / EV)
        odds_dict = {
            "odds_home": row['odds_home'], 
            "odds_draw": row['odds_draw'], 
            "odds_away": row['odds_away']
        }
        trade_order = trader.evaluate_market(match_name, adjusted_context, odds_dict)
        
        # 4. Construcción Estricta del Formato de Salida Obligatorio
        prob_home = adjusted_context.get('Home', base_probs['1X2']['Home'])
        prob_draw = adjusted_context.get('Draw', base_probs['1X2']['Draw'])
        prob_away = adjusted_context.get('Away', base_probs['1X2']['Away'])
        justificacion = adjusted_context.get('Justificacion', 'Sin observaciones anómalas en las plantillas.')

        report_content += f"## [PARTIDO / MERCADOS DETECTADOS]\n"
        report_content += f"**{match_name}**\n\n"
        
        report_content += f"### PROBABILIDAD DEL ENSAMBLE REAL\n"
        report_content += f"- **1X2:** Local: {prob_home:.2%} | Empate: {prob_draw:.2%} | Visita: {prob_away:.2%}\n"
        report_content += f"- **Marcadores Exactos (Poisson):** {list(base_probs['Top_Scores'][0].keys())[0]} ({list(base_probs['Top_Scores'][0].values())[0]*100:.2%}%), {list(base_probs['Top_Scores'][1].keys())[0]} ({list(base_probs['Top_Scores'][1].values())[0]*100:.2%}%)\n\n"
        
        report_content += f"### VALIDACIÓN CONTEXTUAL\n"
        report_content += f"> {justificacion}\n\n"
        
        if "Estado" not in trade_order:
            report_content += f"### INFORME DE VALOR\n"
            report_content += f"- **EV Detectado:** +{trade_order['EV']} (Con cuota base de {trade_order['Cuota_Minima']})\n\n"
            
            report_content += f"### ORDEN DE TRADING\n"
            report_content += f"- **Mercado a Operar:** {trade_order['Mercado']} (1X2)\n"
            report_content += f"- **Cuota Mínima (Límite):** {trade_order['Cuota_Minima']}\n"
            report_content += f"- **Stake (Kelly Fraccional):** {trade_order['Stake_Pct']}%\n"
        else:
            report_content += f"### INFORME DE VALOR Y ORDEN DE TRADING\n"
            report_content += f"- ⛔ **{trade_order['Estado']}:** {trade_order['Motivo']}\n"
            
        report_content += "---\n\n"

    # 5. Volcado de Datos final
    with open("reporte_trading.md", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"Ejecución completada. {len(df_merged)} partidos guardados en 'reporte_trading.md'.")

if __name__ == "__main__":
    main()
