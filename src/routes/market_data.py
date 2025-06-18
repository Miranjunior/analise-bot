from flask import Blueprint, jsonify, request
import sys
import os
sys.path.append('/opt/.manus/.sandbox-runtime')
from data_api import ApiClient
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

market_bp = Blueprint('market', __name__)
client = ApiClient()

# Cache para armazenar dados temporariamente
market_cache = {}

@market_bp.route('/symbols', methods=['GET'])
def get_symbols():
    """Retorna lista de símbolos disponíveis"""
    symbols = {
        'forex': [
            {'symbol': 'EURUSD=X', 'name': 'EUR/USD', 'type': 'forex'},
            {'symbol': 'GBPUSD=X', 'name': 'GBP/USD', 'type': 'forex'},
            {'symbol': 'USDJPY=X', 'name': 'USD/JPY', 'type': 'forex'},
            {'symbol': 'AUDUSD=X', 'name': 'AUD/USD', 'type': 'forex'},
            {'symbol': 'USDCAD=X', 'name': 'USD/CAD', 'type': 'forex'},
        ],
        'stocks': [
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'type': 'stock'},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'type': 'stock'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corp.', 'type': 'stock'},
            {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'type': 'stock'},
            {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'type': 'stock'},
        ],
        'crypto': [
            {'symbol': 'BTC-USD', 'name': 'Bitcoin', 'type': 'crypto'},
            {'symbol': 'ETH-USD', 'name': 'Ethereum', 'type': 'crypto'},
            {'symbol': 'ADA-USD', 'name': 'Cardano', 'type': 'crypto'},
            {'symbol': 'DOT-USD', 'name': 'Polkadot', 'type': 'crypto'},
            {'symbol': 'LINK-USD', 'name': 'Chainlink', 'type': 'crypto'},
        ],
        'indices': [
            {'symbol': '^GSPC', 'name': 'S&P 500', 'type': 'index'},
            {'symbol': '^DJI', 'name': 'Dow Jones', 'type': 'index'},
            {'symbol': '^IXIC', 'name': 'NASDAQ', 'type': 'index'},
            {'symbol': '^FTSE', 'name': 'FTSE 100', 'type': 'index'},
            {'symbol': '^N225', 'name': 'Nikkei 225', 'type': 'index'},
        ]
    }
    return jsonify(symbols)

@market_bp.route('/data/<symbol>', methods=['GET'])
def get_market_data(symbol):
    """Obtém dados de mercado para um símbolo específico"""
    try:
        interval = request.args.get('interval', '1d')
        range_param = request.args.get('range', '1mo')
        
        # Mapear intervalos para o formato da API
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '60m', '4h': '60m', '1d': '1d', '1w': '1wk', '1M': '1mo'
        }
        
        api_interval = interval_map.get(interval, '1d')
        
        # Chamar a API do Yahoo Finance
        response = client.call_api('YahooFinance/get_stock_chart', query={
            'symbol': symbol,
            'interval': api_interval,
            'range': range_param,
            'includePrePost': False,
            'includeAdjustedClose': True
        })
        
        if not response or 'chart' not in response:
            return jsonify({'error': 'Dados não encontrados'}), 404
            
        chart_data = response['chart']['result'][0]
        timestamps = chart_data['timestamp']
        indicators = chart_data['indicators']['quote'][0]
        
        # Processar dados
        data = []
        for i, timestamp in enumerate(timestamps):
            if (indicators['open'][i] is not None and 
                indicators['high'][i] is not None and 
                indicators['low'][i] is not None and 
                indicators['close'][i] is not None):
                
                data.append({
                    'timestamp': timestamp,
                    'datetime': datetime.fromtimestamp(timestamp).isoformat(),
                    'open': round(indicators['open'][i], 4),
                    'high': round(indicators['high'][i], 4),
                    'low': round(indicators['low'][i], 4),
                    'close': round(indicators['close'][i], 4),
                    'volume': indicators['volume'][i] if indicators['volume'][i] else 0
                })
        
        # Metadados
        meta = chart_data['meta']
        result = {
            'symbol': symbol,
            'meta': {
                'currency': meta.get('currency', 'USD'),
                'exchangeName': meta.get('exchangeName', ''),
                'regularMarketPrice': meta.get('regularMarketPrice', 0),
                'regularMarketTime': meta.get('regularMarketTime', 0),
                'timezone': meta.get('timezone', 'UTC')
            },
            'data': data
        }
        
        # Cache dos dados
        market_cache[f"{symbol}_{interval}_{range_param}"] = result
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/quote/<symbol>', methods=['GET'])
def get_quote(symbol):
    """Obtém cotação atual de um símbolo"""
    try:
        response = client.call_api('YahooFinance/get_stock_chart', query={
            'symbol': symbol,
            'interval': '1d',
            'range': '1d',
            'includePrePost': False
        })
        
        if not response or 'chart' not in response:
            return jsonify({'error': 'Cotação não encontrada'}), 404
            
        chart_data = response['chart']['result'][0]
        meta = chart_data['meta']
        
        quote = {
            'symbol': symbol,
            'price': meta.get('regularMarketPrice', 0),
            'currency': meta.get('currency', 'USD'),
            'marketTime': meta.get('regularMarketTime', 0),
            'dayHigh': meta.get('regularMarketDayHigh', 0),
            'dayLow': meta.get('regularMarketDayLow', 0),
            'volume': meta.get('regularMarketVolume', 0),
            'previousClose': meta.get('chartPreviousClose', 0),
            'change': 0,
            'changePercent': 0
        }
        
        # Calcular mudança
        if quote['previousClose'] > 0:
            quote['change'] = round(quote['price'] - quote['previousClose'], 4)
            quote['changePercent'] = round((quote['change'] / quote['previousClose']) * 100, 2)
        
        return jsonify(quote)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/watchlist', methods=['GET'])
def get_watchlist():
    """Retorna uma watchlist padrão com cotações"""
    default_symbols = ['AAPL', 'GOOGL', 'MSFT', 'EURUSD=X', 'BTC-USD']
    watchlist = []
    
    for symbol in default_symbols:
        try:
            response = client.call_api('YahooFinance/get_stock_chart', query={
                'symbol': symbol,
                'interval': '1d',
                'range': '1d'
            })
            
            if response and 'chart' in response:
                chart_data = response['chart']['result'][0]
                meta = chart_data['meta']
                
                price = meta.get('regularMarketPrice', 0)
                previous_close = meta.get('chartPreviousClose', 0)
                change = round(price - previous_close, 4) if previous_close > 0 else 0
                change_percent = round((change / previous_close) * 100, 2) if previous_close > 0 else 0
                
                watchlist.append({
                    'symbol': symbol,
                    'name': meta.get('shortName', symbol),
                    'price': price,
                    'change': change,
                    'changePercent': change_percent,
                    'currency': meta.get('currency', 'USD')
                })
        except:
            continue
    
    return jsonify(watchlist)

@market_bp.route('/search', methods=['GET'])
def search_symbols():
    """Busca símbolos por nome ou código"""
    query = request.args.get('q', '').upper()
    
    if not query:
        return jsonify([])
    
    # Lista expandida de símbolos para busca
    all_symbols = [
        # Forex
        {'symbol': 'EURUSD=X', 'name': 'EUR/USD', 'type': 'forex'},
        {'symbol': 'GBPUSD=X', 'name': 'GBP/USD', 'type': 'forex'},
        {'symbol': 'USDJPY=X', 'name': 'USD/JPY', 'type': 'forex'},
        {'symbol': 'AUDUSD=X', 'name': 'AUD/USD', 'type': 'forex'},
        {'symbol': 'USDCAD=X', 'name': 'USD/CAD', 'type': 'forex'},
        {'symbol': 'USDCHF=X', 'name': 'USD/CHF', 'type': 'forex'},
        {'symbol': 'NZDUSD=X', 'name': 'NZD/USD', 'type': 'forex'},
        {'symbol': 'EURGBP=X', 'name': 'EUR/GBP', 'type': 'forex'},
        
        # Stocks
        {'symbol': 'AAPL', 'name': 'Apple Inc.', 'type': 'stock'},
        {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'type': 'stock'},
        {'symbol': 'MSFT', 'name': 'Microsoft Corp.', 'type': 'stock'},
        {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'type': 'stock'},
        {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'type': 'stock'},
        {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'type': 'stock'},
        {'symbol': 'NVDA', 'name': 'NVIDIA Corp.', 'type': 'stock'},
        {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'type': 'stock'},
        
        # Crypto
        {'symbol': 'BTC-USD', 'name': 'Bitcoin', 'type': 'crypto'},
        {'symbol': 'ETH-USD', 'name': 'Ethereum', 'type': 'crypto'},
        {'symbol': 'ADA-USD', 'name': 'Cardano', 'type': 'crypto'},
        {'symbol': 'DOT-USD', 'name': 'Polkadot', 'type': 'crypto'},
        {'symbol': 'LINK-USD', 'name': 'Chainlink', 'type': 'crypto'},
        {'symbol': 'LTC-USD', 'name': 'Litecoin', 'type': 'crypto'},
        
        # Indices
        {'symbol': '^GSPC', 'name': 'S&P 500', 'type': 'index'},
        {'symbol': '^DJI', 'name': 'Dow Jones', 'type': 'index'},
        {'symbol': '^IXIC', 'name': 'NASDAQ', 'type': 'index'},
        {'symbol': '^FTSE', 'name': 'FTSE 100', 'type': 'index'},
        {'symbol': '^N225', 'name': 'Nikkei 225', 'type': 'index'},
    ]
    
    # Filtrar símbolos que correspondem à busca
    results = []
    for item in all_symbols:
        if (query in item['symbol'].upper() or 
            query in item['name'].upper()):
            results.append(item)
    
    return jsonify(results[:10])  # Limitar a 10 resultados

