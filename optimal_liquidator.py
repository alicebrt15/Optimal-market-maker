import numpy as np
import pandas as pd

# Importer la fonction de chargement des données
from data import charger_et_nettoyer


class OptimalLiquidator:
    """
    Implémente une version simplifiée de la stratégie de liquidation 
    optimale de Cartea-Jaimungal.

    Ce modèle détermine la meilleure façon de liquider un inventaire sur un
    horizon de temps donné, en choisissant entre des ordres limites et des
    ordres de marché (agressifs) pour minimiser les coûts d'exécution et le
    risque de marché.
    """
    def __init__(self, gamma: float = 0.1, kappa: float = 1.0, phi: float = 1e-6, sigma: float = 0.1, A: float = 140.0):
        """
        Initialise le liquidateur avec les paramètres du modèle.

        Args:
            gamma (float): Paramètre d'aversion au risque de l'agent.
            kappa (float): Paramètre de décroissance de l'intensité du carnet d'ordres.
            phi (float): Pénalité pour l'inventaire terminal. Une valeur élevée force la liquidation.
            sigma (float): Volatilité du sous-jacent.
            A (float): Paramètre d'intensité de base du carnet d'ordres.
        """
        self.gamma = gamma
        self.kappa = kappa
        self.phi = phi
        self.sigma = sigma
        self.A = A
        self.T = None

        # Placeholder pour la solution de l'équation différentielle
        self._eta_t = None

    def solve(self, T: float):
        """
        Résout l'équation différentielle (ODE) du modèle pour un horizon de temps T.

        Dans le modèle Cartea-Jaimungal, la stratégie dépend de la solution
        d'une équation de type Riccati. Nous utilisons ici la solution analytique
        d'un cas simplifié.

        Args:
            T (float): Horizon de liquidation total en secondes.
        """
        self.T = T
        # Simplification: alpha est constant. Dans un modèle complet, il dépendrait du temps.
        alpha = self.phi * self.A * np.exp(-self.gamma * self.sigma**2 / (2 * self.kappa))
        
        if alpha <= 0:
            print("Warning: alpha is non-positive, which may lead to issues.")
            # Fallback to a small positive value to avoid division by zero
            self._eta_t = lambda t: 1e-9
        else:
            # Solution simplifiée de l'ODE pour eta(t).
            self._eta_t = lambda t: np.sqrt(alpha) / np.tanh(np.sqrt(alpha) * (T-t)) if T > t else 1e9

        print(f"✅ Solution pré-calculée pour un horizon de {T} secondes.")

    def get_optimal_strategy(self, t: float, q: int, mid_price: float):
        """
        Calcule les contrôles optimaux à un instant t avec un inventaire q.

        Args:
            t (float): Temps écoulé depuis le début de la liquidation (en secondes).
            q (int): Inventaire actuel (positif à vendre, négatif à acheter).
            mid_price (float): Le prix de marché actuel.

        Returns:
            Tuple[float, float]: Un tuple contenant :
                - optimal_bid (float): Le prix d'achat optimal à proposer.
                - optimal_ask (float): Le prix de vente optimal à proposer.
        """
        if self._eta_t is None:
            raise RuntimeError("La méthode .solve(T) doit être appelée avant d'utiliser get_optimal_strategy.")

        time_to_go = self.T - t
        if time_to_go <= 0:
            time_to_go = 1e-6 # Eviter la division par zéro

        # 1. Calcul du prix de réserve
        reservation_price = mid_price - q * self.gamma * self.sigma**2 * time_to_go

        # 2. Calcul du spread optimal
        eta_val = self._eta_t(t)
        # Logarithme peut être instable si l'argument est proche de zéro
        log_argument = 1 + (self.gamma * self.kappa / (2 * eta_val))
        
        if log_argument <= 0:
            spread = np.inf # Spread infini si l'argument est invalide
        else:
            spread = (1/self.kappa) * np.log(log_argument)

        optimal_bid = reservation_price - spread
        optimal_ask = reservation_price + spread
        
        return optimal_bid, optimal_ask

def run_liquidation_backtest(inventory_to_liquidate: int, df_nbbo: pd.DataFrame, df_trades: pd.DataFrame, liquidation_horizon_hours: int = 2):
    """
    Exécute un backtest de la stratégie de liquidation sur une journée de données.

    Args:
        inventory_to_liquidate (int): La quantité d'inventaire à liquider.
                                      > 0 pour vendre, < 0 pour acheter.
        df_nbbo (pd.DataFrame): DataFrame contenant les données NBBO.
        df_trades (pd.DataFrame): DataFrame contenant les données de trades enrichies.
        liquidation_horizon_hours (int): L'horizon de temps pour la liquidation en heures.

    Returns:
        dict: Un dictionnaire contenant les résultats de la liquidation.
    """
    if df_trades is None or df_nbbo is None:
        return {
            "total_qty_executed": 0,
            "cash_change": 0,
            "remaining_inventory": inventory_to_liquidate
        }

    # Déterminer si on achète ou si on vend
    side = 'sell' if inventory_to_liquidate > 0 else 'buy'
    
    # Filtrer les trades pertinents
    if side == 'sell':
        df_market_aggressors = df_trades[df_trades['side'] == 'BUY'].copy()
    else:
        df_market_aggressors = df_trades[df_trades['side'] == 'SELL'].copy()

    if df_market_aggressors.empty:
        return {
            "total_qty_executed": 0,
            "cash_change": 0,
            "remaining_inventory": inventory_to_liquidate
        }

    # 2. Paramètres de la simulation
    liquidator = OptimalLiquidator(gamma=0.01, kappa=0.5, phi=1e-4, sigma=df_nbbo['vol'].mean())
    
    liquidation_horizon_seconds = liquidation_horizon_hours * 3600

    start_time = df_market_aggressors['time'].iloc[0]
    end_time = start_time + pd.Timedelta(seconds=liquidation_horizon_seconds)

    print(f"\n--- 🚀 LANCEMENT DU BACKTEST DE LIQUIDATION ({side.upper()}) ---")
    print(f"Objectif: {'Vendre' if side == 'sell' else 'Acheter'} {abs(inventory_to_liquidate)} actions en {liquidation_horizon_hours} heures.")
    print(f"Horizon: {start_time.time()} -> {end_time.time()}")
    print("-" * 50)

    # 3. Initialisation du backtest
    liquidator.solve(liquidation_horizon_seconds)
    
    inventory = inventory_to_liquidate
    cash_change = 0
    
    trades_in_window = df_market_aggressors[
        (df_market_aggressors['time'] >= start_time) & 
        (df_market_aggressors['time'] <= end_time)
    ]

    # 4. Boucle événementielle
    for _, trade in trades_in_window.iterrows():
        if (side == 'sell' and inventory <= 0) or (side == 'buy' and inventory >= 0):
            break

        current_time = trade['time']
        time_elapsed = (current_time - start_time).total_seconds()
        current_mid_price = trade['Mid']

        my_bid, my_ask = liquidator.get_optimal_strategy(t=time_elapsed, q=inventory, mid_price=current_mid_price)

        if side == 'sell' and trade['value'] >= my_ask:
            qty_executed = min(inventory, trade['volume'])
            inventory -= qty_executed
            cash_change += qty_executed * my_ask
            print(f"[{current_time.time()}] HIT! Vente de {qty_executed} @ {my_ask:.2f} | Inv. restant: {inventory}")
        
        elif side == 'buy' and trade['value'] <= my_bid:
            qty_executed = min(abs(inventory), trade['volume'])
            inventory += qty_executed
            cash_change -= qty_executed * my_bid
            print(f"[{current_time.time()}] HIT! Achat de {qty_executed} @ {my_bid:.2f} | Inv. restant: {inventory}")

    # 5. Bilan
    total_qty_executed = abs(inventory_to_liquidate - inventory)
    
    return {
        "total_qty_executed": total_qty_executed,
        "cash_change": cash_change,
        "remaining_inventory": inventory
    }


if __name__ == '__main__':
    # --- Exemple d'utilisation ---
    # 1. Charger les données pour une journée
    df_nbbo, df_trades_enriched = charger_et_nettoyer(date_voulue="2025-08-25")

    if df_nbbo is not None and df_trades_enriched is not None:
        # 2. Définir l'inventaire à liquider
        inventory_to_sell = 2000
        
        # 3. Exécuter le backtest de liquidation
        results = run_liquidation_backtest(
            inventory_to_liquidate=inventory_to_sell,
            df_nbbo=df_nbbo,
            df_trades=df_trades_enriched,
            liquidation_horizon_hours=2
        )

        # 4. Afficher les résultats
        print("\n--- 🏁 BILAN FINAL DE LA LIQUIDATION ---")
        print(f"Quantité totale exécutée: {results['total_qty_executed']} / {abs(inventory_to_sell)}")
        print(f"Variation de cash       : {results['cash_change']:.2f} $")
        print(f"Inventaire restant      : {results['remaining_inventory']}")
        if results['total_qty_executed'] > 0:
            avg_price = abs(results['cash_change'] / results['total_qty_executed'])
            print(f"Prix moyen d'exécution  : {avg_price:.4f}")
        print("-" * 50)


