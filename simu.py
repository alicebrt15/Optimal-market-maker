import pandas as pd
import numpy as np
from tracker import MarketMakerPnL
from stat_tools import OptimalStrategy
from kapparegression import estimate_as_parameters
from data import lister_dates_disponibles, charger_et_nettoyer

def load_macro_data(filepath="Rates.xlsx"):
    """
    Charge, nettoie et fusionne les onglets du fichier Rates.xlsx par Date.
    """
    df_rates = pd.read_excel(filepath, sheet_name='Rates')
    df_fx = pd.read_excel(filepath, sheet_name='FX')
    df_tn = pd.read_excel(filepath, sheet_name='TN')
    
    r = df_rates[['Date', 'SOFR']].dropna()
    f = df_fx[['Date', 'EURUSD']].dropna()
    t = df_tn[['Date', 'EURTN']].dropna()
    
    # Transformation des dates au format chaîne standard YYYY-MM-DD
    r['Date'] = pd.to_datetime(r['Date']).dt.strftime('%Y-%m-%d')
    f['Date'] = pd.to_datetime(f['Date']).dt.strftime('%Y-%m-%d')
    t['Date'] = pd.to_datetime(t['Date']).dt.strftime('%Y-%m-%d')
    
    # Fusion des tables
    df_macro = pd.merge(r, f, on='Date', how='inner')
    df_macro = pd.merge(df_macro, t, on='Date', how='inner')
    
    return df_macro.set_index('Date')


def run_backtest_multijours(nb_jours=130, gamma=0.1, max_inventory=15000, q_bar=500):
    dates = lister_dates_disponibles(nb_jours)
    if not dates:
        print("⚠️ Aucune date trouvée.")
        return pd.DataFrame()

    # Chargement préalable de la matrice macroéconomique
    try:
        df_macro = load_macro_data("Rates.xlsx")
        print("✅ Matrice de taux et FX (Rates.xlsx) chargée avec succès.")
    except Exception as e:
        print(f"❌ Erreur lors du chargement de Rates.xlsx : {e}")
        return pd.DataFrame()

    pnl_tracker = None
    strategy = OptimalStrategy(gamma=gamma)
    results = []

    last_mid = 0.0
    last_vol = 0.0001

    print(f"🚀 Lancement de la simulation ({len(dates)} jours)")
    
    for i_jour, date_str in enumerate(dates):
        print(f"\n=======================================================")
        print(f"📅 JOUR {i_jour + 1} : {date_str}")
        print(f"=======================================================")
            
        resultats = charger_et_nettoyer(date_str)
        if resultats is None:
            continue
            
        df_nbbo, df_trades_enriched = resultats
        daily_volume_usd = 0
       
        strategy.kappa, _ = estimate_as_parameters(df_trades_enriched)
        print(f"✅ Paramètres calibrés pour la journée : kappa = {strategy.kappa:.2f}")
        
        if pnl_tracker is None:
            start_price = df_nbbo['Mid'].iloc[0]
            pnl_tracker = MarketMakerPnL(inv_veille=0.0, prix_cloture_veille=start_price)
            last_mid = start_price
            print(f"✅ Tracker initialisé avec un prix de départ de {start_price:.2f}")
            
        # Extraction des paramètres macro pour la journée courante (date_str)
        if date_str in df_macro.index:
            sofr_rate = float(df_macro.loc[date_str, 'SOFR']) / 100.0
            fx_rate = float(df_macro.loc[date_str, 'EURUSD'])
            tn_points = float(df_macro.loc[date_str, 'EURTN'])
        else:
            sofr_rate, fx_rate, tn_points = 0.053, 1.15, 0.0

        for i, row in df_trades_enriched.iterrows():
            price = row["value"]
            current_mid = row["Mid"]
            vol = row["vol"]
            volume_row = row["volume"]
            bid_price = row["Bid"]
            ask_price = row["Ask"]

            last_mid = current_mid
            last_vol = vol

            total_inv = pnl_tracker.inv_veille + pnl_tracker.inventory_intraday
            my_bid, my_ask = strategy.get_quotes(current_mid, total_inv, vol)
            
            if my_bid <= 0 or my_ask <= 0 or my_bid >= my_ask:
                continue
 
            if price >= my_ask:
                if total_inv > -max_inventory:
                    qty = min(volume_row, max_inventory + total_inv)
                    if qty > 0:
                        pnl_tracker.update_on_trade('SELL', qty, price, current_mid)
                        daily_volume_usd += qty * price
 
            elif price <= my_bid:
                if total_inv < max_inventory:
                    qty = min(volume_row, max_inventory - total_inv)
                    if qty > 0:
                        pnl_tracker.update_on_trade('BUY', qty, price, current_mid)
                        daily_volume_usd += qty * price
            
            # Hedging logic
            total_inv = pnl_tracker.inv_veille + pnl_tracker.inventory_intraday
            if total_inv > q_bar:
                qty_to_hedge = total_inv - q_bar
                print(f"🔥 HEDGING: Inventory {total_inv} > {q_bar}. Selling {qty_to_hedge} at market.")
                pnl_tracker.update_on_trade('SELL', qty_to_hedge, bid_price, current_mid)
                daily_volume_usd += qty_to_hedge * bid_price
            elif total_inv < -q_bar:
                qty_to_hedge = abs(total_inv) - q_bar
                print(f"🔥 HEDGING: Inventory {total_inv} < -{q_bar}. Buying {qty_to_hedge} at market.")
                pnl_tracker.update_on_trade('BUY', qty_to_hedge, ask_price, current_mid)
                daily_volume_usd += qty_to_hedge * ask_price


        final = pnl_tracker.get_pnl_report(last_mid, sofr_rate=sofr_rate, fx_rate=fx_rate, tn_points=tn_points)
        pnl_bps = (final['pnl_total'] / daily_volume_usd) * 10000 if daily_volume_usd > 0 else 0
        
        results.append({
            'date'             : date_str,
            'time'             : df_trades_enriched['time'].iloc[-1],
            'pnl_total'        : final['pnl_total'],
            'pnl_total_eur'    : final['pnl_total_eur'],
            'spread_pnl'       : final['spread_pnl'],
            'inventory_pnl'    : final['inventory_pnl'],
            'pnl_veille'       : final['pnl_veille'],
            'funding_cost'     : final['funding_cost'],
            'tn_adjustment'    : final['tn_adjustment'],
            'total_inventory'  : final['total_inventory'],
            'historical_cash'  : final['historical_cash'],
            'kappa'            : strategy.kappa,
            'mid'              : last_mid,
            'vol'              : round(last_vol, 6),
            'volume_traite_usd': daily_volume_usd,
            'pnl_bps'          : pnl_bps,
        })
 
        pnl_tracker.reset_for_new_day(current_mid=last_mid, sofr_rate=sofr_rate, tn_points=tn_points)
 
    return pd.DataFrame(results)
 
if __name__ == "__main__":
    df_results = run_backtest_multijours(nb_jours=10, gamma=1.0)
 
    if not df_results.empty:
        cols = ['date', 'pnl_total', 'pnl_total_eur', 'spread_pnl', 'inventory_pnl',
                'total_inventory', 'kappa', 'vol', 'funding_cost', 'volume_traite_usd', 'pnl_bps']
        print("\n📊 Résultats par jour :")
        print(df_results[cols].to_string(index=False))
 
        fichier_csv = "resultats_backtest.csv"
        df_results.to_csv(fichier_csv, index=False)
        print(f"\n💾 Résultats sauvegardés : {fichier_csv}")