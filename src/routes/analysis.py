from flask import Blueprint, jsonify, request
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append('/opt/.manus/.sandbox-runtime')
from data_api import ApiClient

analysis_bp = Blueprint('analysis', __name__)
client = ApiClient()

def calculate_rsi(prices, period=14):
    """Calcula o RSI (Relative Strength Index)"""
    if len(prices) < period + 1:
        return None
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calcula o MACD"""
    if len(prices) < slow:
        return None, None, None
    
    prices = np.array(prices)
    
    # Calcular EMAs
    ema_fast = pd.Series(prices).ewm(span=fast).mean()
    ema_slow = pd.Series(prices).ewm(span=slow).mean()
    
    # MACD line
    macd_line = ema_fast - ema_slow
    
    # Signal line
    signal_line = macd_line.ewm(span=signal).mean()
    
    # Histogram
    histogram = macd_line - signal_line
    
    return (round(macd_line.iloc[-1], 6), 
            round(signal_line.iloc[-1], 6), 
            round(histogram.iloc[-1], 6))

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calcula as Bandas de Bollinger"""
    if len(prices) < period:
        return None, None, None
    
    prices_series = pd.Series(prices)
    sma = prices_series.rolling(window=period).mean()
    std = prices_series.rolling(window=period).std()
    
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    
    return (round(upper_band.iloc[-1], 4),
            round(sma.iloc[-1], 4),
            round(lower_band.iloc[-1], 4))

def calculate_moving_averages(prices, periods=[20, 50, 200]):
    """Calcula médias móveis simples"""
    mas = {}
    for period in periods:
        if len(prices) >= period:
            ma = np.mean(prices[-period:])
            mas[f'sma_{period}'] = round(ma, 4)
        else:
            mas[f'sma_{period}'] = None
    return mas

def calculate_stochastic(highs, lows, closes, k_period=14, d_period=3):
    """Calcula o Oscilador Estocástico"""
    if len(closes) < k_period:
        return None, None
    
    lowest_low = np.min(lows[-k_period:])
    highest_high = np.max(highs[-k_period:])
    
    if highest_high == lowest_low:
        k_percent = 50
    else:
        k_percent = ((closes[-1] - lowest_low) / (highest_high - lowest_low)) * 100
    
    # Para simplificar, retornamos apenas o %K atual
    # Em uma implementação completa, calcularíamos o %D como média móvel do %K
    d_percent = k_percent  # Simplificado
    
    return round(k_percent, 2), round(d_percent, 2)

def generate_trading_signal(indicators, current_price):
    """Gera sinal de trading baseado nos indicadores"""
    signals = []
    score = 0
    
    # Análise RSI
    rsi = indicators.get('rsi')
    if rsi:
        if rsi < 30:
            signals.append("RSI indica sobrevendido (possível compra)")
            score += 20
        elif rsi > 70:
            signals.append("RSI indica sobrecomprado (possível venda)")
            score -= 20
        elif 40 <= rsi <= 60:
            signals.append("RSI em zona neutra")
            score += 5
    
    # Análise MACD
    macd = indicators.get('macd', {})
    if macd.get('macd') and macd.get('signal'):
        if macd['macd'] > macd['signal']:
            signals.append("MACD acima da linha de sinal (bullish)")
            score += 15
        else:
            signals.append("MACD abaixo da linha de sinal (bearish)")
            score -= 15
    
    # Análise Bollinger Bands
    bollinger = indicators.get('bollinger', {})
    if bollinger.get('upper') and bollinger.get('lower'):
        if current_price > bollinger['upper']:
            signals.append("Preço acima da banda superior (sobrecomprado)")
            score -= 10
        elif current_price < bollinger['lower']:
            signals.append("Preço abaixo da banda inferior (sobrevendido)")
            score += 10
        else:
            signals.append("Preço dentro das bandas de Bollinger")
    
    # Análise de Médias Móveis
    sma_20 = indicators.get('sma_20')
    sma_50 = indicators.get('sma_50')
    if sma_20 and sma_50:
        if sma_20 > sma_50:
            signals.append("SMA 20 acima da SMA 50 (tendência de alta)")
            score += 10
        else:
            signals.append("SMA 20 abaixo da SMA 50 (tendência de baixa)")
            score -= 10
    
    if current_price and sma_20:
        if current_price > sma_20:
            signals.append("Preço acima da SMA 20")
            score += 5
        else:
            signals.append("Preço abaixo da SMA 20")
            score -= 5
    
    # Determinar recomendação
    if score >= 30:
        recommendation = "STRONG_BUY"
        strength = "FORTE"
    elif score >= 15:
        recommendation = "BUY"
        strength = "MODERADO"
    elif score >= -15:
        recommendation = "HOLD"
        strength = "NEUTRO"
    elif score >= -30:
        recommendation = "SELL"
        strength = "MODERADO"
    else:
        recommendation = "STRONG_SELL"
        strength = "FORTE"
    
    confidence = min(abs(score) / 50, 1.0)
    
    return {
        'recommendation': recommendation,
        'strength': strength,
        'confidence': round(confidence, 2),
        'score': score,
        'signals': signals
    }

@analysis_bp.route('/indicators/<symbol>', methods=['GET'])
def get_technical_indicators(symbol):
    """Calcula indicadores técnicos para um símbolo"""
    try:
        # Obter dados de mercado
        response = client.call_api('YahooFinance/get_stock_chart', query={
            'symbol': symbol,
            'interval': '1d',
            'range': '6mo',  # 6 meses para ter dados suficientes
            'includePrePost': False
        })
        
        if not response or 'chart' not in response:
            return jsonify({'error': 'Dados não encontrados'}), 404
        
        chart_data = response['chart']['result'][0]
        timestamps = chart_data['timestamp']
        quote_data = chart_data['indicators']['quote'][0]
        
        # Extrair arrays de preços
        closes = [price for price in quote_data['close'] if price is not None]
        highs = [price for price in quote_data['high'] if price is not None]
        lows = [price for price in quote_data['low'] if price is not None]
        volumes = [vol for vol in quote_data['volume'] if vol is not None]
        
        if len(closes) < 20:
            return jsonify({'error': 'Dados insuficientes para análise'}), 400
        
        current_price = closes[-1]
        
        # Calcular indicadores
        indicators = {}
        
        # RSI
        indicators['rsi'] = calculate_rsi(closes)
        
        # MACD
        macd, signal, histogram = calculate_macd(closes)
        indicators['macd'] = {
            'macd': macd,
            'signal': signal,
            'histogram': histogram
        }
        
        # Bollinger Bands
        upper, middle, lower = calculate_bollinger_bands(closes)
        indicators['bollinger'] = {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }
        
        # Médias Móveis
        mas = calculate_moving_averages(closes)
        indicators.update(mas)
        
        # Estocástico
        k_percent, d_percent = calculate_stochastic(highs, lows, closes)
        indicators['stochastic'] = {
            'k': k_percent,
            'd': d_percent
        }
        
        # Volume médio
        if len(volumes) >= 20:
            indicators['avg_volume'] = round(np.mean(volumes[-20:]), 0)
            indicators['current_volume'] = volumes[-1] if volumes else 0
        
        # Gerar sinal de trading
        trading_signal = generate_trading_signal(indicators, current_price)
        
        result = {
            'symbol': symbol,
            'current_price': current_price,
            'timestamp': datetime.now().isoformat(),
            'indicators': indicators,
            'signal': trading_signal
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analysis_bp.route('/signals/<symbol>', methods=['GET'])
def get_trading_signals(symbol):
    """Retorna apenas os sinais de trading para um símbolo"""
    try:
        # Reutilizar a lógica de indicadores
        indicators_response = get_technical_indicators(symbol)
        
        if indicators_response.status_code != 200:
            return indicators_response
        
        data = indicators_response.get_json()
        
        # Retornar apenas o sinal
        return jsonify({
            'symbol': symbol,
            'current_price': data['current_price'],
            'timestamp': data['timestamp'],
            'signal': data['signal']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analysis_bp.route('/market-overview', methods=['GET'])
def get_market_overview():
    """Retorna uma visão geral do mercado com sinais para múltiplos ativos"""
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'EURUSD=X', 'BTC-USD', '^GSPC']
    overview = []
    
    for symbol in symbols:
        try:
            # Obter dados básicos
            response = client.call_api('YahooFinance/get_stock_chart', query={
                'symbol': symbol,
                'interval': '1d',
                'range': '1mo'
            })
            
            if response and 'chart' in response:
                chart_data = response['chart']['result'][0]
                meta = chart_data['meta']
                quote_data = chart_data['indicators']['quote'][0]
                
                closes = [price for price in quote_data['close'] if price is not None]
                
                if len(closes) >= 14:
                    current_price = closes[-1]
                    previous_close = meta.get('chartPreviousClose', closes[-2])
                    
                    # Calcular RSI rápido
                    rsi = calculate_rsi(closes[-20:]) if len(closes) >= 20 else None
                    
                    # Determinar tendência simples
                    if len(closes) >= 5:
                        recent_trend = "UP" if closes[-1] > closes[-5] else "DOWN"
                    else:
                        recent_trend = "NEUTRAL"
                    
                    # Sinal simples baseado em RSI
                    if rsi:
                        if rsi < 30:
                            signal = "BUY"
                        elif rsi > 70:
                            signal = "SELL"
                        else:
                            signal = "HOLD"
                    else:
                        signal = "HOLD"
                    
                    change = round(current_price - previous_close, 4)
                    change_percent = round((change / previous_close) * 100, 2) if previous_close > 0 else 0
                    
                    overview.append({
                        'symbol': symbol,
                        'name': meta.get('shortName', symbol),
                        'price': current_price,
                        'change': change,
                        'changePercent': change_percent,
                        'rsi': rsi,
                        'signal': signal,
                        'trend': recent_trend,
                        'currency': meta.get('currency', 'USD')
                    })
        except:
            continue
    
    return jsonify(overview)

@analysis_bp.route('/pattern-recognition/<symbol>', methods=['GET'])
def get_pattern_recognition(symbol):
    """Reconhecimento básico de padrões de candlestick"""
    try:
        response = client.call_api('YahooFinance/get_stock_chart', query={
            'symbol': symbol,
            'interval': '1d',
            'range': '1mo'
        })
        
        if not response or 'chart' not in response:
            return jsonify({'error': 'Dados não encontrados'}), 404
        
        chart_data = response['chart']['result'][0]
        quote_data = chart_data['indicators']['quote'][0]
        
        opens = [price for price in quote_data['open'] if price is not None]
        highs = [price for price in quote_data['high'] if price is not None]
        lows = [price for price in quote_data['low'] if price is not None]
        closes = [price for price in quote_data['close'] if price is not None]
        
        if len(closes) < 3:
            return jsonify({'error': 'Dados insuficientes'}), 400
        
        patterns = []
        
        # Verificar últimas 3 velas para padrões simples
        for i in range(max(0, len(closes) - 3), len(closes)):
            if i >= 1:  # Precisa de pelo menos 2 velas
                open_price = opens[i]
                high_price = highs[i]
                low_price = lows[i]
                close_price = closes[i]
                prev_close = closes[i-1]
                
                body_size = abs(close_price - open_price)
                total_range = high_price - low_price
                
                # Doji (corpo pequeno)
                if body_size < (total_range * 0.1) and total_range > 0:
                    patterns.append({
                        'pattern': 'Doji',
                        'type': 'Indecisão',
                        'significance': 'Possível reversão de tendência',
                        'candle_index': i
                    })
                
                # Hammer (martelo)
                if (close_price > open_price and 
                    (high_price - close_price) < body_size * 0.3 and
                    (open_price - low_price) > body_size * 2):
                    patterns.append({
                        'pattern': 'Hammer',
                        'type': 'Bullish',
                        'significance': 'Possível reversão de alta',
                        'candle_index': i
                    })
                
                # Shooting Star
                if (open_price > close_price and
                    (close_price - low_price) < body_size * 0.3 and
                    (high_price - open_price) > body_size * 2):
                    patterns.append({
                        'pattern': 'Shooting Star',
                        'type': 'Bearish',
                        'significance': 'Possível reversão de baixa',
                        'candle_index': i
                    })
                
                # Engulfing Bullish (precisa de 2 velas)
                if i >= 1:
                    prev_open = opens[i-1]
                    if (prev_open > prev_close and  # Vela anterior vermelha
                        close_price > open_price and  # Vela atual verde
                        open_price < prev_close and   # Abre abaixo do fechamento anterior
                        close_price > prev_open):     # Fecha acima da abertura anterior
                        patterns.append({
                            'pattern': 'Bullish Engulfing',
                            'type': 'Bullish',
                            'significance': 'Forte sinal de alta',
                            'candle_index': i
                        })
        
        return jsonify({
            'symbol': symbol,
            'patterns': patterns,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

