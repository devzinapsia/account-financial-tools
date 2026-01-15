#!/usr/bin/env python3
"""
Test standalone para verificar el scraping del BNA.
Ejecutar: python test_bna_scraping.py

Este archivo NO es un test de Odoo, es para probar el scraping
de forma independiente.
"""

import requests
from bs4 import BeautifulSoup

BNA_URL = "https://www.bna.com.ar/Personas"


def get_usd_rate_bna():
    """Obtiene la cotización del dólar desde BNA (Divisas)."""
    try:
        print(f"Conectando a {BNA_URL}...")
        response = requests.get(BNA_URL, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        results = soup.find(id="divisas")
        
        if not results:
            print("ERROR: No se encontró la tabla 'divisas'")
            return None
        
        rows = results.find_all("tr")
        
        for row in rows:
            cells = row.find_all("td")
            if cells and "Dolar U.S.A" in cells[0].text:
                compra = float(cells[1].text.strip().replace(',', '.'))
                venta = float(cells[2].text.strip().replace(',', '.'))
                
                print("\n" + "=" * 40)
                print("COTIZACIÓN BNA - DIVISAS")
                print("=" * 40)
                print(f"Dólar U.S.A:")
                print(f"  Compra: ${compra:,.2f}")
                print(f"  Venta:  ${venta:,.2f}")
                print(f"  Spread: ${venta - compra:,.2f}")
                print("=" * 40)
                print(f"\nValor para Odoo (inverso): {1/compra:.6f}")
                
                return compra
        
        print("ERROR: No se encontró el Dólar U.S.A. en la tabla")
        return None
        
    except requests.RequestException as e:
        print(f"ERROR de conexión: {e}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def debug_table():
    """Muestra toda la tabla de divisas para debug."""
    response = requests.get(BNA_URL, timeout=10)
    soup = BeautifulSoup(response.content, "html.parser")
    results = soup.find(id="divisas")
    
    if not results:
        print("No se encontró la tabla 'divisas'")
        return
    
    print("\n=== TABLA COMPLETA DE DIVISAS ===\n")
    rows = results.find_all("tr")
    
    for i, row in enumerate(rows):
        cells = row.find_all("td")
        if cells:
            moneda = cells[0].text.strip()
            compra = cells[1].text.strip() if len(cells) > 1 else "N/A"
            venta = cells[2].text.strip() if len(cells) > 2 else "N/A"
            print(f"{moneda:<30} | Compra: {compra:<15} | Venta: {venta}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        debug_table()
    else:
        get_usd_rate_bna()