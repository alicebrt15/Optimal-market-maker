import pandas as pd
from pathlib import Path


from shapely import length

# --- 1. CONFIGURATION ---
# Utilisation de Path pour la robustesse des chemins
chemin_dossier_parent = Path("ticker_US_Equity")

def lister_dates_disponibles(nb_jours=130):
    """
    Parcourt le dossier des données et retourne une liste des N premières dates disponibles.
    """
    chemin_base = chemin_dossier_parent
    if not chemin_base.exists():
        print(f"❌ Dossier de base introuvable : {chemin_base}")
        return []
        
    # Chercher tous les dossiers qui commencent par "date=" et extraire la date
    dossiers = sorted([d.name.split('=')[1] for d in chemin_base.iterdir() if d.is_dir() and d.name.startswith('date=')])
    
    print(f"📅 {len(dossiers[:nb_jours])} dates prêtes à être analysées (sur une limite de {nb_jours}).")
    return dossiers[:nb_jours]
   

def charger_et_nettoyer(date_voulue="2025-08-25"):
    chemin_fichier = chemin_dossier_parent / f"date={date_voulue}" / "ticks.parquet"
    if not chemin_fichier.exists():
        print(f"❌ Fichier introuvable : {chemin_fichier}")
        return None

    print(f"🚀 Chargement des données ({date_voulue})...")
    df = pd.read_parquet(chemin_fichier)
    df = df.sort_values('time').reset_index(drop=True)
    
    # Séparation Quotes / Trades
    df_quotes = df[df['event_type'].isin(['BID', 'ASK'])].copy()
    df_trades = df[df['event_type'] == 'TRADE'].copy()

    # Préparation NBBO
    bids = df_quotes[df_quotes['event_type'] == 'BID'][['time', 'value']].rename(columns={'value': 'Bid'}).sort_values('time')
    asks = df_quotes[df_quotes['event_type'] == 'ASK'][['time', 'value']].rename(columns={'value': 'Ask'}).sort_values('time')

    print("🔧 Calcul du Mid et synchronisation...")
    df_nbbo = pd.merge_asof(asks, bids, on='time', direction='backward')
    df_nbbo = df_nbbo.ffill().dropna(subset=['Bid', 'Ask'])
    df_nbbo['Mid'] = (df_nbbo['Bid'] + df_nbbo['Ask']) / 2
    df_nbbo['Spread'] = df_nbbo['Ask'] - df_nbbo['Bid']
    df_nbbo['vol']= ( df_nbbo['Mid'].diff().ewm(span=20, min_periods = 2).std().fillna(0.0001).clip(lower=0.0001) )
  # Volatilité lissée pour le calcul du spread optimal
    
    

    # Enrichissement des Trades
    df_trades_enriched = pd.merge_asof(
        df_trades.sort_values('time'),
        df_nbbo[['time','Bid', 'Ask', 'Mid','vol']],
        on='time',
        direction='backward'
    )

    def classify_trade(row):
        if row['value'] >= row['Ask']: return 'BUY'
        elif row['value'] <= row['Bid']: return 'SELL'
        return 'NEUTRAL'

    df_trades_enriched['side'] = df_trades_enriched.apply(classify_trade, axis=1)
    df_trades_enriched = df_trades_enriched[df_trades_enriched['side'].isin(['BUY', 'SELL'])].copy()
    
    print(
        f"✅ {len(df_trades_enriched):,} trades agressifs | "
        f"NBBO : {len(df_nbbo):,} ticks"
    )

    
    return  df_nbbo, df_trades_enriched
   
def load_macro_data(filepath="Rates.xlsx"):
    """
    Charge et fusionne les données de taux, FX et TN depuis le fichier Excel.
    """
    import pandas as pd
    
    # Lecture des onglets
    df_rates = pd.read_excel(filepath, sheet_name='Rates')
    df_fx = pd.read_excel(filepath, sheet_name='FX')
    df_tn = pd.read_excel(filepath, sheet_name='TN')
    
    # Nettoyage
    rates_clean = df_rates[['Date', 'SOFR']].dropna()
    fx_clean = df_fx[['Date', 'EURUSD']].dropna()
    tn_clean = df_tn[['Date', 'EURTN']].dropna()
    
    # Standardisation des dates pour la fusion
    for df in [rates_clean, fx_clean, tn_clean]:
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        
    # Fusion par Date
    df_macro = pd.merge(rates_clean, fx_clean, on='Date', how='inner')
    df_macro = pd.merge(df_macro, tn_clean, on='Date', how='inner')
    
    return df_macro.sort_values('Date').set_index('Date')