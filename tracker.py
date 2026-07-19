import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Trade:
    timestamp: pd.Timestamp
    side: str  # 'BUY' ou 'SELL'
    price: float
    quantity: float
    mid : float

class MarketMakerPnL:
    def __init__(self, inv_veille: float = 0.0, prix_cloture_veille : float = 0.0):
        self.inv_veille = inv_veille
        self.prix_cloture_veille = prix_cloture_veille

        self.cash = 0.0
        self.inventory_intraday = 0.0
        self.historical_cash = 0.0

        self.spread_pnl = 0.0
        self.inventory_pnl_intraday = 0.0
        
        self.trades: List[Dict] = []

    def update_on_trade(self, side: str, quantity: float, price: float, mid: float):
        side = side.upper()

        if side == 'BUY':
            self.cash -= quantity * price
            self.inventory_intraday += quantity
            edge = mid - price
        elif side == 'SELL':
            self.cash += quantity * price
            self.inventory_intraday -= quantity
            edge = price - mid
        else:
            raise ValueError("Side doit être 'BUY' ou 'SELL'.")
        
        self.spread_pnl += edge * quantity

        self.trades.append({
            'side'    : side,
            'qty'     : quantity,
            'price'   : price,
            'mid'     : mid,
            'edge'    : round(quantity * edge, 4),
        })

    def reset_for_new_day(self, current_mid: float, sofr_rate: float = 0.053, tn_points: float = 0.0):
        """
        Bascule l'inventaire en 'veille' et applique le coût de financement réel (SOFR) + points TN.
        """
        total_inv = self.inv_veille + self.inventory_intraday
        
        # Coût de financement (Base Money Market US : 360 jours)
        valeur_portee = total_inv * current_mid
        funding_cost = valeur_portee * (sofr_rate / 360)
        
        # Ajustement Tomorrow Next (en pips, divisé par 10 000)
        tn_adjustment = total_inv * (tn_points / 10000)

        # Mise à jour du cash historique net des frais de portage
        self.historical_cash += self.cash - funding_cost + tn_adjustment

        self.inv_veille = total_inv
        self.prix_cloture_veille = current_mid
        
        # Reset des compteurs journaliers
        self.cash                   = 0.0
        self.inventory_intraday     = 0.0
        self.spread_pnl             = 0.0
        self.inventory_pnl_intraday = 0.0
        self.trades                 = []
        
    def get_pnl_report(self, current_mid: float, sofr_rate: float = 0.053, fx_rate: float = 1.0, tn_points: float = 0.0) -> Dict:
        """
        Décomposition du P&L en Dollars avec coût de refinancement (SOFR), points TN et conversion EUR.
        """
        spread_pnl = self.spread_pnl
        inventory_pnl = (self.cash - spread_pnl) + (self.inventory_intraday * current_mid)
        pnl_intraday = spread_pnl + inventory_pnl

        # PnL de la pose veille (Mark-to-Market de l'ancien stock)
        variation_prix = current_mid - self.prix_cloture_veille
        pnl_veille_brut = self.inv_veille * variation_prix
        
        # Financement sur la position globale portée la nuit
        total_inv = self.inv_veille + self.inventory_intraday
        valeur_portee = total_inv * current_mid
        funding_cost = valeur_portee * (sofr_rate / 360)
        
        # Ajustement des points TN
        tn_adjustment = total_inv * (tn_points / 10000)
        
        # PnL Veille Net des coûts financiers
        pnl_veille_net = pnl_veille_brut - funding_cost + tn_adjustment
        
        # Cumul Global en Dollars
        pnl_total_usd = self.historical_cash + pnl_intraday + pnl_veille_net
        
        # Conversion du PnL global en Euros pour le desk Européen
        pnl_total_eur = pnl_total_usd / fx_rate if fx_rate > 0 else pnl_total_usd
        
        return {
            'spread_pnl'      : round(spread_pnl, 2),
            'inventory_pnl'   : round(inventory_pnl, 2),
            'pnl_intraday'    : round(pnl_intraday, 2),
            'pnl_veille'      : round(pnl_veille_net, 2),
            'funding_cost'    : round(funding_cost, 2),
            'tn_adjustment'   : round(tn_adjustment, 2),
            'pnl_total'       : round(pnl_total_usd, 2),
            'pnl_total_eur'   : round(pnl_total_eur, 2),
            'historical_cash' : round(self.historical_cash, 2),
            'total_inventory' : round(total_inv, 6),
        }