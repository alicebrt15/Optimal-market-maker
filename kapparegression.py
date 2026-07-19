import numpy as np
import pandas as pd

def estimate_as_parameters(df_trades_enriched, r2_min: float = 0.5, n_bins: int = 20):
    """
    Estime les paramètres A et kappa du modèle d'Avellaneda-Stoikov 
    par régression linéaire sur l'historique des trades.
    """

    FALLBACK = (100.0, 1.0)

    #verifs initiales
    if df_trades_enriched is None or df_trades_enriched.empty:
        print("⚠️  DataFrame vide.")
        return FALLBACK
    
    required_cols = {'time', 'side', 'value', 'Mid'}
    if not required_cols.issubset(df_trades_enriched.columns):
        print(f"⚠️  Colonnes manquantes : {required_cols - set(df_trades_enriched.columns)}")
        return FALLBACK


    #temps total 
    temps_total = (
        df_trades_enriched['time'].max() - df_trades_enriched['time'].min()
    ).total_seconds()

    if temps_total <= 0:
        print("⚠️  Fenêtre temporelle nulle.")
        return FALLBACK
    

    # 1. Filtrer pour ne garder que les trades agressifs identifiés (BUY/SELL)
    trades = df_trades_enriched[df_trades_enriched['side'].isin(['BUY', 'SELL'])].copy()
    
    if trades.empty:
        print("⚠️  Aucun trade agressif trouvé.")
        return FALLBACK

    # 2. Calcul de la distance au Mid (delta relatif) au moment exact du trade
    trades['delta_pct'] = np.abs(trades['value'] - trades['Mid'])
    
    # 2.5 Filtrer les valeurs extrêmes (outliers) pour ne pas aplatir la droite de régression
    q_low  = trades['delta_pct'].quantile(0.025)
    q_high = trades['delta_pct'].quantile(0.975)

    trades = trades[(trades['delta_pct'] >= q_low) & (trades['delta_pct'] <= q_high)]

    if trades.empty:
        print("⚠️  Aucun trade agressif après filtrage des outliers.")
        return FALLBACK
    
    # 3. Regrouper par tranches de delta (arrondi au centime près)
    try:
        trades['delta_bin'] = pd.qcut(
            trades['delta_pct'],
            q=n_bins,
            duplicates='drop'   # si trop peu de diversité dans les deltas
        )
    except ValueError:
        print("⚠️  Pas assez de diversité dans les deltas pour créer les bins.")
        return FALLBACK
    
    # On ignore les bins aberrants avec moins de 5 trades pour ne pas fausser la pente
    trade_counts = trades.groupby('delta_bin', observed=True).size()
    
    seuil_min = max(5, int(len(trades) * 0.01))   # au moins 1% des trades
    trade_counts = trade_counts[trade_counts >= seuil_min]

    if len(trade_counts) < 3:
        print("⚠️ Pas assez de diversité dans les spreads pour estimer kappa.")
        return FALLBACK
        
    # ── 6. Optimisation : Calcul des vrais deltas moyens par bin ──────────────
    # Au lieu de prendre le milieu théorique (interval.mid), 
    # on prend la moyenne réelle des deltas des trades présents dans ce bin.
    grouped = trades.groupby('delta_bin', observed=True)['delta_pct']
    deltas = grouped.mean().values
    
    # L'intensité lambda reste le nombre de trades divisé par le temps total
    lambdas = trade_counts.values / temps_total
    
    # 7. Régression linéaire : ln(lambda) = ln(A) - kappa * delta
    y = np.log(lambdas)
    x = deltas
    
    slope, intercept = np.polyfit(x, y, 1)

    # ── 8. Calcul du R² et validation ─────────────────────────────────────────
    y_pred  = slope * x + intercept
    ss_res  = np.sum((y - y_pred) ** 2)
    ss_tot  = np.sum((y - np.mean(y)) ** 2)
    r2      = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
 
    if r2 < r2_min:
        print(f"⚠️  R²={r2:.3f} < seuil={r2_min} — régression peu fiable, fallback.")
        return FALLBACK
    
    if slope >= 0:
        print(f"⚠️  Pente positive ({slope:.4f}) — relation anormale, fallback.")
        return FALLBACK
 
    kappa = -slope
    A     = np.exp(intercept)
    print(f"✅ Estimation réussie : kappa={kappa:.2f}, A={A:.2f}, R²={r2:.3f}")
    return kappa, A