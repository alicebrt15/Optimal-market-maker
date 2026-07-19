import os
import pandas as pd
import plotly.graph_objects as graph_objects
from plotly.subplots import make_subplots

def generer_dashboard_performance(fichier_csv="resultats_backtest.csv"):
    """
    Lit les résultats du backtest et génère un dashboard interactif Plotly en Euros.
    """
    if not os.path.exists(fichier_csv):
        print(f"❌ Erreur : Le fichier '{fichier_csv}' est introuvable. Lance simu.py d'abord.")
        return

    # 1. Chargement des données
    df = pd.read_csv(fichier_csv)
    df['date'] = pd.to_datetime(df['date'])
    
    # Calcul des P&L cumulés pour le graphique d'évolution
    # (Note : pnl_total dans ton tracker est déjà cumulé, mais on s'assure de la trajectoire)
    dates = df['date'].dt.strftime('%Y-%m-%d')

    # 2. Création de la structure du Dashboard (3 sous-graphiques verticaux)
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "📈 Évolution du P&L Cumulé (Base de Reporting : EUR vs USD)",
            "📦 Évolution de l'Inventaire de Clôture (Contrôle du Risque)",
            "📊 Décomposition des Composantes du P&L Journalier (USD)"
        )
    )

    # -------------------------------------------------------------------------
    # GRAPHIQUE 1 : P&L Cumulé (EUR et USD)
    # -------------------------------------------------------------------------
    fig.add_trace(
        graph_objects.Scatter(
            x=dates, y=df['pnl_total_eur'],
            name="P&L Cumulé (EUR)",
            mode='lines+markers',
            line=dict(color='#2ecc71', width=3),
            marker=dict(size=6)
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        graph_objects.Scatter(
            x=dates, y=df['pnl_total'],
            name="P&L Cumulé (USD)",
            mode='lines',
            line=dict(color='#3498db', width=1.5, dash='dash'),
            opacity=0.7
        ),
        row=1, col=1
    )

    # -------------------------------------------------------------------------
    # GRAPHIQUE 2 : Tracking de l'inventaire
    # -------------------------------------------------------------------------
    fig.add_trace(
        graph_objects.Bar(
            x=dates, y=df['total_inventory'],
            name="Inventaire Final (Actions)",
            marker_color=np.where(df['total_inventory'] >= 0, '#9b59b6', '#e67e22'),
            opacity=0.85
        ),
        row=2, col=1
    )

    # -------------------------------------------------------------------------
    # GRAPHIQUE 3 : Décomposition Fine (Spread vs Sélection Adverse vs Funding)
    # -------------------------------------------------------------------------
    fig.add_trace(
        graph_objects.Bar(
            x=dates, y=df['spread_pnl'],
            name="Gains du Spread",
            marker_color='#1abc9c'
        ),
        row=3, col=1
    )
    
    fig.add_trace(
        graph_objects.Bar(
            x=dates, y=df['inventory_pnl'],
            name="Sélection Adverse (P&L Inv)",
            marker_color='#e74c3c'
        ),
        row=3, col=1
    )
    
    fig.add_trace(
        graph_objects.Bar(
            x=dates, y=df['funding_cost'],
            name="Coût de Financement (SOFR)",
            marker_color='#34495e'
        ),
        row=3, col=1
    )

    # -------------------------------------------------------------------------
    # CONFIGURATION DU DESIGN GLOBAL
    # -------------------------------------------------------------------------
    fig.update_layout(
        title=dict(
            text="<b>Tableau de Bord de Performance - Optimal Market Maker</b>",
            x=0.5, y=0.95,
            font=dict(size=20, color='#2c3e50')
        ),
        template="plotly_white",
        height=900,
        width=1100,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # Ajustement des axes
    fig.update_yaxes(title_text="Montant (€ / $)", row=1, col=1)
    fig.update_yaxes(title_text="Quantité (Titres)", row=2, col=1)
    fig.update_yaxes(title_text="Impact Journalier ($)", row=3, col=1)
    fig.update_xaxes(title_text="Dates de Simulation", row=3, col=1)

  
    fig.write_html("dashboard.html")
    print("📊 Dashboard généré avec succès dans le fichier 'dashboard.html' !")
    print("👉 Va dans ton dossier de projet et double-clique sur 'dashboard.html' pour l'ouvrir instantanément.")

if __name__ == "__main__":
    import numpy as np  # requis pour la coloration conditionnelle de l'inventaire
    generer_dashboard_performance()