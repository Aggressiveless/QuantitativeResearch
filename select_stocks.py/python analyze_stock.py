import baostock as bs
import pandas as pd
import numpy as np

# ========== 1. 获取股票数据 ==========
def get_stock_data(code, start_date='2025-01-01', end_date='2026-06-04'):
    """获取个股历史数据"""
    if code.startswith('6'):
        bs_code = f"sh.{code}"
    else:
        bs_code = f"sz.{code}"
    
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return None
    
    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,open,high,low,close,volume",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3"
    )
    
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    
    bs.logout()
    
    if len(data) < 20:
        print(f"数据不足，只获取到 {len(data)} 天")
        return None
    
    df = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    df['close'] = pd.to_numeric(df['close'])
    df['open'] = pd.to_numeric(df['open'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    df['volume'] = pd.to_numeric(df['volume'])
    
    return df

# ========== 2. 获取大盘数据 ==========
def get_index_data(start_date='2025-01-01', end_date='2026-06-04'):
    """获取上证指数数据"""
    lg = bs.login()
    if lg.error_code != '0':
        return None
    
    rs = bs.query_history_k_data_plus(
        "sh.000001",
        "date,close",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3"
    )
    
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    
    bs.logout()
    
    if len(data) < 20:
        return None
    
    df = pd.DataFrame(data, columns=['date', 'close'])
    df['close'] = pd.to_numeric(df['close'])
    return df

# ========== 3. 计算技术指标 ==========
def calculate_indicators(df):
    """计算所有技术指标"""
    close = df['close'].values
    volume = df['volume'].values
    
    ma5 = df['close'].rolling(5).mean().iloc[-1]
    ma10 = df['close'].rolling(10).mean().iloc[-1]
    ma20 = df['close'].rolling(20).mean().iloc[-1]
    ma60 = df['close'].rolling(60).mean().iloc[-1]
    
    price = close[-1]
    ma_bullish = price > ma20 > ma60
    ma_cross = ma5 > ma20
    
    pct_1d = (close[-1] - close[-2]) / close[-2] * 100 if len(close) > 1 else 0
    pct_5d = (close[-1] - close[-6]) / close[-6] * 100 if len(close) > 5 else 0
    pct_20d = (close[-1] - close[-20]) / close[-20] * 100 if len(close) > 20 else 0
    pct_60d = (close[-1] - close[-60]) / close[-60] * 100 if len(close) > 60 else 0
    
    daily_ret = []
    for i in range(1, min(21, len(close))):
        ret = (close[-i] - close[-i-1]) / close[-i-1] * 100
        daily_ret.append(ret)
    has_limit_up = any(r >= 9.8 for r in daily_ret)
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs)).iloc[-1]
    
    if rsi < 30:
        rsi_signal = "超卖 (买入机会)"
    elif rsi > 70:
        rsi_signal = "超买 (注意风险)"
    else:
        rsi_signal = "正常区间"
    
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    
    macd_signal = "金叉" if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2] else ""
    macd_signal += " 多头" if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-1] > 0 else ""
    macd_signal += " 空头" if dif.iloc[-1] < dea.iloc[-1] else ""
    
    std = df['close'].rolling(20).std()
    upper = ma20 + 2 * std
    lower = ma20 - 2 * std
    bb_position = ""
    if price > upper.iloc[-1]:
        bb_position = "突破上轨 (强势)"
    elif price < lower.iloc[-1]:
        bb_position = "跌破下轨 (弱势)"
    else:
        bb_position = "轨道内运行"
    
    avg_volume_5 = df['volume'].rolling(5).mean().iloc[-1]
    avg_volume_20 = df['volume'].rolling(20).mean().iloc[-1]
    volume_ratio = volume[-1] / avg_volume_5 if avg_volume_5 > 0 else 1
    volume_trend = "放量" if volume[-1] > avg_volume_5 else "缩量"
    liangbi = volume_ratio
    
    turnover_rate = (volume[-1] / avg_volume_20) * 5 if avg_volume_20 > 0 else 5
    turnover_rate = min(turnover_rate, 15)
    
    momentum = price > df['close'].iloc[-21] if len(df) > 20 else False
    
    return {
        'price': round(price, 2),
        'ma5': round(ma5, 2),
        'ma10': round(ma10, 2),
        'ma20': round(ma20, 2),
        'ma60': round(ma60, 2),
        'ma_bullish': ma_bullish,
        'ma_cross': ma_cross,
        'pct_1d': round(pct_1d, 2),
        'pct_5d': round(pct_5d, 2),
        'pct_20d': round(pct_20d, 2),
        'pct_60d': round(pct_60d, 2),
        'has_limit_up': has_limit_up,
        'rsi': round(rsi, 1),
        'rsi_signal': rsi_signal,
        'macd_signal': macd_signal,
        'bb_position': bb_position,
        'volume_ratio': round(liangbi, 2),
        'turnover_rate': round(turnover_rate, 2),
        'momentum': momentum,
        'volume_trend': volume_trend
    }

# ========== 4. 获取详细信息 ==========
def get_stock_info(code):
    """获取股票基本信息和实时数据"""
    try:
        import akshare as ak
        spot = ak.stock_zh_a_spot_em()
        row = spot[spot['代码'] == code]
        if not row.empty:
            market_cap = row['总市值'].values[0]
            turnover = row['换手率'].values[0]
            liangbi = row['量比'].values[0]
            
            market_cap = float(market_cap) if market_cap != '-' else 0
            turnover = float(turnover) if turnover != '-' else 0
            liangbi = float(liangbi) if liangbi != '-' else 0
            
            return {
                'market_cap': market_cap,
                'turnover': turnover,
                'liangbi': liangbi
            }
    except:
        pass
    return {'market_cap': 0, 'turnover': 0, 'liangbi': 0}

# ========== 5. 强于大盘判断 ==========
def compare_with_index(stock_df, index_df):
    if stock_df is None or index_df is None:
        return 0
    
    stock_20d = (stock_df['close'].iloc[-1] - stock_df['close'].iloc[-20]) / stock_df['close'].iloc[-20] * 100
    index_20d = (index_df['close'].iloc[-1] - index_df['close'].iloc[-20]) / index_df['close'].iloc[-20] * 100
    
    return round(stock_20d - index_20d, 2)

# ========== 6. 主力资金分析 ==========
def analyze_money_flow(df):
    close = df['close'].values
    volume = df['volume'].values
    
    recent_volume = volume[-5:].mean()
    avg_volume = volume[-20:].mean()
    
    volume_trend = "放量" if recent_volume > avg_volume * 1.2 else "缩量" if recent_volume < avg_volume * 0.8 else "持平"
    
    price_up = close[-1] > close[-6]
    volume_up = recent_volume > avg_volume
    
    if price_up and volume_up:
        money_flow_signal = "价涨量增，主力可能进场"
    elif price_up and not volume_up:
        money_flow_signal = "价涨量缩，上涨乏力"
    elif not price_up and volume_up:
        money_flow_signal = "价跌量增，主力可能出货"
    else:
        money_flow_signal = "价跌量缩，观望"
    
    return money_flow_signal, volume_trend

# ========== 7. 生成买入建议 ==========
def generate_suggestion(indicators, info, compare_result, money_flow):
    score = 0
    reasons = []
    
    if indicators['ma_bullish']:
        score += 2
        reasons.append("✅ 均线多头排列 (+2)")
    elif indicators['ma_cross']:
        score += 1
        reasons.append("✅ 5日线上穿20日线 (+1)")
    
    if 3 <= indicators['pct_20d'] <= 5:
        score += 1
        reasons.append(f"✅ 20日涨幅 {indicators['pct_20d']}% 在理想区间 (+1)")
    
    if indicators['has_limit_up']:
        score += 1
        reasons.append("✅ 20日内有涨停 (+1)")
    
    if indicators['rsi'] < 40:
        score += 1
        reasons.append(f"✅ RSI {indicators['rsi']} 处于低位 (+1)")
    elif indicators['rsi'] > 80:
        score -= 1
        reasons.append(f"⚠️ RSI {indicators['rsi']} 超买区 (-1)")
    
    if info['liangbi'] > 1:
        score += 1
        reasons.append(f"✅ 量比 {info['liangbi']} > 1 (+1)")
    else:
        reasons.append(f"⚠️ 量比 {info['liangbi']} < 1")
    
    if 5 <= info['turnover'] <= 10:
        score += 1
        reasons.append(f"✅ 换手率 {info['turnover']}% 在理想区间 (+1)")
    
    if 50 <= info['market_cap'] <= 200:
        score += 1
        reasons.append(f"✅ 市值 {info['market_cap']:.1f}亿 在50-200亿区间 (+1)")
    elif info['market_cap'] > 200:
        reasons.append(f"⚠️ 市值 {info['market_cap']:.1f}亿 偏大")
    
    if compare_result > 0:
        score += 1
        reasons.append(f"✅ 强于大盘 {compare_result}% (+1)")
    else:
        reasons.append(f"⚠️ 弱于大盘 {abs(compare_result)}%")
    
    if "进场" in money_flow:
        score += 1
        reasons.append(f"✅ {money_flow} (+1)")
    
    if score >= 6:
        suggestion = "🔥 强烈看多 - 符合多项买入条件"
    elif score >= 4:
        suggestion = "📈 看多 - 可以考虑关注"
    elif score >= 2:
        suggestion = "⚪ 中性 - 观望为主"
    else:
        suggestion = "📉 看空 - 建议回避"
    
    return suggestion, score, reasons

# ========== 8. 主分析函数 ==========
def analyze_stock(code):
    print("="*60)
    print(f"📊 量化分析报告：{code}")
    print("="*60)
    
    stock_df = get_stock_data(code)
    index_df = get_index_data()
    
    if stock_df is None:
        print("❌ 无法获取股票数据")
        return
    
    indicators = calculate_indicators(stock_df)
    info = get_stock_info(code)
    compare_result = compare_with_index(stock_df, index_df)
    money_flow, volume_trend = analyze_money_flow(stock_df)
    
    print(f"\n📈 当前价格: {indicators['price']}")
    print(f"\n📊 技术指标:")
    print(f"   5日均线: {indicators['ma5']} | 10日均线: {indicators['ma10']}")
    print(f"   20日均线: {indicators['ma20']} | 60日均线: {indicators['ma60']}")
    print(f"   均线多头排列: {'是' if indicators['ma_bullish'] else '否'}")
    print(f"   5日线上穿20日线: {'是' if indicators['ma_cross'] else '否'}")
    
    print(f"\n📈 涨跌幅:")
    print(f"   1日: {indicators['pct_1d']}% | 5日: {indicators['pct_5d']}%")
    print(f"   20日: {indicators['pct_20d']}% | 60日: {indicators['pct_60d']}%")
    print(f"   20日内有涨停: {'是' if indicators['has_limit_up'] else '否'}")
    
    print(f"\n📊 其他指标:")
    print(f"   RSI: {indicators['rsi']} ({indicators['rsi_signal']})")
    print(f"   MACD: {indicators['macd_signal']}")
    print(f"   布林带: {indicators['bb_position']}")
    print(f"   动量指标: {'看多' if indicators['momentum'] else '看空'}")
    
    print(f"\n💰 资金/量能:")
    print(f"   量比: {info['liangbi']} | 换手率: {info['turnover']}%")
    print(f"   成交量趋势: {indicators['volume_trend']}")
    print(f"   资金流向: {money_flow}")
    
    print(f"\n📊 基本面:")
    print(f"   总市值: {info['market_cap']:.2f} 亿")
    print(f"   强于大盘: {compare_result}%")
    
    suggestion, score, reasons = generate_suggestion(indicators, info, compare_result, money_flow)
    
    print(f"\n{'='*60}")
    print(f"🎯 综合评分: {score}/9")
    print(f"💡 投资建议: {suggestion}")
    print(f"\n📝 评分详情:")
    for r in reasons:
        print(f"   {r}")
    print("="*60)

# ========== 9. 运行（交互式） ==========
if __name__ == "__main__":
    print("🚀 股票量化分析系统启动")
    print("=" * 40)
    
    while True:
        stock_code = input("\n请输入股票代码（输入 q 退出）：").strip()
        
        if stock_code.lower() == 'q':
            print("再见！")
            break
        
        if not stock_code:
            continue
        
        analyze_stock(stock_code)