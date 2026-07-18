# Optimal-market-maker

<h1 align="center">📈 Optimal Market Making Simulator (US Equity)</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Pandas-2C2D72?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas">
  <img src="https://img.shields.io/badge/Plotly-239120?style=for-the-badge&logo=plotly&logoColor=white" alt="Plotly">
  <img src="https://img.shields.io/badge/Quant_Finance-111111?style=for-the-badge&logo=cashapp&logoColor=white" alt="Quant">
</p>

> **Description :** Ce projet implémente un environnement de backtesting événementiel (Event-Driven) pour simuler une stratégie de Market Making sur les marchés actions américains (US Equity). Il intègre une gestion avancée du risque d'inventaire et une comptabilité de niveau institutionnel incluant le coût de refinancement (Funding Cost).

---

<p align="center">
  <!-- Remplace le lien ci-dessous par ton propre GIF ou image une fois que tu l'auras généré -->
  <img src="https://via.placeholder.com/800x400.png?text=Insérer+ici+une+capture+du+graphique+Plotly" width="800" alt="Démonstration du backtest">
</p>

## ✨ Fonctionnalités Principales

* **Backtester Événementiel :** Simulation réaliste au niveau de la microseconde. L'automate réagit au flux (Quotes) et n'est exécuté que lorsqu'un `TRADE` réel consomme la liquidité fournie aux prix limites.
* **Comptabilité Institutionnelle (PnL) :** Décomposition stricte de la performance avec intégration du taux sans risque (SOFR) pour modéliser le coût de portage overnight.
* **Visualisation Interactive :** Rendu graphique haute résolution permettant d'inspecter l'exécution des ordres et la gestion de l'inventaire en temps réel.

---

## 📐 Modèle Mathématique (Avellaneda-Stoikov)

Le cœur de l'algorithme repose sur le contrôle stochastique pour ajuster dynamiquement le positionnement dans le carnet d'ordres. 

Le **prix de réserve** ($r$) est calculé pour décaler les cotations en fonction du risque d'inventaire ($q$) et de l'aversion au risque ($\gamma$) :
$$r = s - q\gamma\sigma^2(T-t)$$

Le **spread optimal** ($\delta$) est déterminé pour maximiser le profit tout en contrôlant la probabilité d'exécution ($k$) :
$$\delta = \gamma\sigma^2(T-t) + \frac{2}{\gamma} \ln\left(1 + \frac{\gamma}{k}\right)$$

---

## 🚀 Structure du Projet

* **`MarketMakerPnL` :** Classe dédiée au tracking de la position et au calcul du P&L (Intraday, Veille, Funding SOFR).
* **`OptimalStrategy` :** Implémentation mathématique gérant le calcul de la volatilité et le pricing dynamique des limites.
* **`run_full_backtest()` :** Moteur événementiel traitant le flux chronologique des données `.parquet`.

---

## 📊 Exemple de Résultat (Report)

En fin de journée, l'algorithme génère un rapport de P&L décomposé, séparant les gains de trading des coûts de financement du capital :

```text
--- BILAN DE CLÔTURE ---
PnL Intraday (Spread + MTM)      :   145.50 $PnL Veille (Variation de prix)   :   210.00$
  dont Coût de Financement (SOFR):  - 12.45 $
---------------------------------------------
PnL TOTAL                        :   343.05 $
Inventaire Final                 : 150 actions
