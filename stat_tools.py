import numpy as np
import pandas as pd
from dataclasses import dataclass
from kapparegression import estimate_as_parameters



class OptimalStrategy:
    def __init__(self, gamma=0.1, kappa=100.0):
        self.gamma = gamma  # Aversion au risque
        self.kappa = kappa  # Intensité de liquidité du carnet

    def calculate_volatility(self, price_history, window=20):
        """Calcule la volatilité réalisée (stats)."""
        if len(price_history) < window:
            return 0.0001 # Valeur par défaut
        
        # Variations absolues discrètes (P_t - P_{t-1})
        returns = np.diff(price_history)
        
        # Utilisation d'une volatilité discrète lissée par EWMA (Exponential Weighted Moving Average)
        # Cela donne plus d'importance aux chocs de prix récents et filtre le "bruit" haute fréquence.
        series_returns = pd.Series(returns)
        vol_ewma = series_returns.ewm(span=window).std().iloc[-1]
        
        # Sécurité : si le marché est totalement plat (vol = 0 ou NaN), on garde un minimum
        return vol_ewma if pd.notna(vol_ewma) and vol_ewma > 0.0001 else 0.0001

    def get_quotes(self, mid_price, current_inventory, vol, time_left=1.0):
        """
        Calcule le Bid et l'Ask optimaux (Modèle Avellaneda-Stoikov).
        """
        # Calcul du Skew (décalage de l'inventaire)
        # r = s - q * gamma * sigma^2 * T
        reservation_price = mid_price - (current_inventory * self.gamma * (vol**2) * time_left)
        
        # Calcul du spread optimal
        # s = gamma * sigma^2 * T + 2/gamma * ln(1 + gamma/kappa)
        spread = (self.gamma * (vol**2) * time_left) + (2/self.gamma * np.log(1 + self.gamma/self.kappa))
        
        bid = reservation_price - (spread / 2)
        ask = reservation_price + (spread / 2)
        
        return bid, ask