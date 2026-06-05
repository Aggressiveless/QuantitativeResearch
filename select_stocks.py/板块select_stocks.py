import baostock as bs
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# ========== CPO 板块股票池 ==========
def get_cpo_stocks():
    """获取 CPO 板块核心股票列表"""
    cpo_stocks = [
        # 光模块龙头
        {'代码': '300308', '名称': '中际旭创', '板块': '光模块龙头'},
        {'代码': '300502', '名称': '新易盛', '板块': '光模块龙头'},
        {'代码': '300394', '名称': '天孚通信', '板块': '光模块龙头'},
        {'代码': '002281', '名称': '光迅科技', '板块': '光模块'},
        {'代码': '000988', '名称': '华工科技', '板块': '光模块'},
        {'代码': '603083', '名称': '剑桥科技', '板块': '光模块'},
        
        # 光芯片/硅光
        {'代码': '688498', '名称': '源杰科技', '板块': '光芯片'},
        {'代码': '688313', '名称': '仕佳光子', '板块': '光芯片'},
        {'代码': '688048', '名称': '长光华芯', '板块': '光芯片'},
        {'代码': '300620', '名称': '光库科技', '板块': '光器件'},
        
        # CPO设备
        {'代码': '688025', '名称': '杰普特', '板块': 'CPO设备'},
        {'代码': '300757', '名称': '罗博特科', '板块': 'CPO设备'},
        
        # 光纤光缆
        {'代码': '600487', '名称': '亨通光电', '板块': '光纤光缆'},
        {'代码': '601869', '名称': '长飞光纤', '板块': '光纤光缆'},
        {'代码': '600522', '名称': '中天科技', '板块': '光纤光缆'},
        
        # 网络设备
        {'代码': '000938', '名称': '紫光股份', '板块': '网络设备'},
        {'代码': '600498', '名称': '烽火通信', '板块': '网络设备'},
        
        # PCB/其他
        {'代码': '002384', '名称': '东山精密', '板块': 'PCB+光模块'},
        {'代码': '300476', '名称': '胜宏科技', '板块': 'PCB'},
    ]
    
    # 去重
    seen = set()
    unique_stocks = []
    for stock in cpo_stocks:
        if stock['代码'] not in seen:
            seen.add(stock['代码'])
            unique_stocks.append(stock)
    
    print(f"✅ CPO 板块股票池，共 {len(unique_stocks)} 只核心标的")
    return unique_stocks

# ========== 计算技术指标 ==========
def calc_technical_indicators(df):
    if len(df) < 20:
        return None, None, None
    
    close = df['close'].values
    pct_20d = (close[-1] - close[-20]) / close[-20] * 100
    daily_ret = []
    for i in range(1, min(21, len(close))):
        ret = (close[-i] - close[-i-1]) / close[-i-1] * 100
        daily_ret.append(ret)
    has_limit_up = any(r >= 9.8 for r in daily_ret)
    return pct_20d, has_limit_up, close[-1]

# ========== 识别主力偷偷进场 ==========
def detect_main_buying(df):
    if len(df) < 20:
        return False, "数据不足", None
    
    close = df['close'].values
    volume = df['volume'].values
    low = df['low'].values
    high = df['high'].values
    
    signals = []
    is_buying = False
    
    current_price = close[-1]
    price_position = (current_price - min(close[-60:])) / (max(close[-60:]) - min(close[-60:])) if max(close[-60:]) - min(close[-60:]) > 0 else 0.5
    vol_ratio = volume[-1] / volume[-20:].mean() if volume[-20:].mean() > 0 else 1
    
    # 信号1：底部放量
    if price_position < 0.3 and vol_ratio > 1.5:
        signals.append("🔍 底部放量，主力吸筹")
        is_buying = True
    
    # 信号2：连续小阳线
    recent_5d = close[-5:] if len(close) >= 5 else close
    small_up_days = 0
    for i in range(1, len(recent_5d)):
        if 0 < (recent_5d[i] - recent_5d[i-1]) / recent_5d[i-1] * 100 < 3:
            small_up_days += 1
    if small_up_days >= 3:
        signals.append("🔍 连续小阳线，温和吸筹")
        is_buying = True
    
    # 信号3：量缩价稳
    vol_shrink = volume[-5:].mean() < volume[-20:].mean() * 0.8
    price_stable = abs(close[-1] - close[-5]) / close[-5] * 100 < 3
    if vol_shrink and price_stable and price_position < 0.5:
        signals.append("🔍 缩量企稳，洗盘结束")
        is_buying = True
    
    # 信号4：长下影线
    open_price = df['open'].values if 'open' in df.columns else close
    lower_shadow = min(close[-1], open_price[-1]) - low[-1] if len(open_price) > 0 else 0
    body = abs(close[-1] - open_price[-1]) if len(open_price) > 0 else 0
    if lower_shadow > body * 2 and lower_shadow > 0 and price_position < 0.4:
        signals.append("🔍 长下影线，探底回升")
        is_buying = True
    
    # 信号5：RSI低位回升
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_current = rsi.iloc[-1]
    rsi_prev = rsi.iloc[-5] if len(rsi) > 5 else rsi_current
    
    if not pd.isna(rsi_prev) and not pd.isna(rsi_current):
        if rsi_prev < 35 and rsi_current > rsi_prev + 5:
            signals.append(f"🔍 RSI低位回升 ({rsi_prev:.1f} → {rsi_current:.1f})")
            is_buying = True
    
    # 计算建议买入价格区间
    buy_price_low = None
    buy_price_high = None
    
    if is_buying:
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        recent_low = min(close[-10:])
        support = max(ma20, recent_low)
        
        buy_price_low = round(support * 0.98, 2)
        buy_price_high = round(current_price * 1.05, 2)
        
        if buy_price_high <= buy_price_low:
            buy_price_high = round(buy_price_low * 1.05, 2)
    
    if is_buying:
        return True, " | ".join(signals), (buy_price_low, buy_price_high)
    else:
        return False, "无主力进场信号", None

# ========== 识别主力出货信号 ==========
def detect_main_selling(df):
    if len(df) < 20:
        return False, "数据不足"
    
    close = df['close'].values
    volume = df['volume'].values
    high = df['high'].values
    open_price = df['open'].values if 'open' in df.columns else close
    
    signals = []
    is_selling = False
    
    pct_1d = (close[-1] - close[-2]) / close[-2] * 100 if len(close) > 1 else 0
    vol_ratio = volume[-1] / volume[-20:].mean() if volume[-20:].mean() > 0 else 1
    
    if pct_1d < -3 and vol_ratio > 1.5:
        signals.append("⚠️ 高位放量下跌")
        is_selling = True
    
    body = abs(close[-1] - open_price[-1]) if len(open_price) > 0 else 0
    upper_shadow = high[-1] - max(close[-1], open_price[-1]) if len(open_price) > 0 else 0
    if upper_shadow > body * 2 and upper_shadow > 0:
        signals.append("⚠️ 长上影线，冲高回落")
        is_selling = True
    
    if is_selling:
        return True, " | ".join(signals)
    else:
        return False, "无主力出货信号"

# ========== 获取实时数据 ==========
def get_stock_detail(code):
    try:
        import akshare as ak
        spot = ak.stock_zh_a_spot_em()
        row = spot[spot['代码'] == code]
        if row.empty:
            return None
        market_cap = row['总市值'].values[0]
        if market_cap == '-' or market_cap == 0:
            return None
        market_cap = float(market_cap)
        
        turnover = row['换手率'].values[0]
        turnover = float(turnover) if turnover != '-' else 0
        
        volume_ratio = row['量比'].values[0]
        volume_ratio = float(volume_ratio) if volume_ratio != '-' else 0
        
        return market_cap, turnover, volume_ratio
    except:
        return None

# ========== 获取指数涨跌幅 ==========
def get_index_return(days=20):
    lg = bs.login()
    if lg.error_code != '0':
        return 0
    
    rs = bs.query_history_k_data_plus(
        "sh.000001",
        "date,close",
        start_date='2025-01-01',
        end_date='2026-06-04',
        frequency="d",
        adjustflag="3"
    )
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    bs.logout()
    
    if len(data) < days + 1:
        return 0
    df = pd.DataFrame(data, columns=['date', 'close'])
    df['close'] = pd.to_numeric(df['close'])
    ret = (df['close'].iloc[-1] - df['close'].iloc[-days-1]) / df['close'].iloc[-days-1] * 100
    return ret

# ========== 获取个股历史数据 ==========
def get_stock_history(code):
    bs_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
    lg = bs.login()
    if lg.error_code != '0':
        return None
    
    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,open,high,low,close,volume",
        start_date='2025-01-01',
        end_date='2026-06-04',
        frequency="d",
        adjustflag="3"
    )
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    bs.logout()
    
    if len(data) < 20:
        return None
    df = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    for col in ['close', 'open', 'high', 'low', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

# ========== 扫描股票 ==========
def scan_stocks(stock_list, index_ret):
    buy_results = []
    buying_results = []
    sell_results = []
    
    total = len(stock_list)
    for i, stock in enumerate(stock_list):
        code = stock['代码']
        name = stock['名称']
        sector = stock.get('板块', 'CPO')
        print(f"📊 扫描 {i+1}/{total}: {code} {name} ({sector})")
        
        df = get_stock_history(code)
        if df is None:
            continue
        
        pct_20d, has_limit_up, latest_close = calc_technical_indicators(df)
        if pct_20d is None:
            continue
        
        detail = get_stock_detail(code)
        
        # 检查主力偷偷进场
        is_buying, buying_desc, price_range = detect_main_buying(df)
        if is_buying:
            price_range_str = f"{price_range[0]} - {price_range[1]}" if price_range else "待定"
            buying_results.append({
                '代码': code,
                '名称': name,
                '板块': sector,
                '价格': latest_close,
                '进场信号': buying_desc,
                '建议区间': price_range_str,
                '20日涨幅%': round(pct_20d, 2)
            })
            print(f"   🔍 {code} 检测到主力进场")
        
        # 检查主力出货信号
        is_selling, sell_desc = detect_main_selling(df)
        if is_selling:
            sell_results.append({
                '代码': code,
                '名称': name,
                '板块': sector,
                '价格': latest_close,
                '出货信号': sell_desc,
                '20日涨幅%': round(pct_20d, 2)
            })
            print(f"   🔻 {code} 检测到出货信号")
        
        # 检查原买入条件
        buy_condition_1 = (3 <= pct_20d <= 5 and has_limit_up)
        buy_condition_2 = (pct_20d > index_ret) if index_ret != 0 else True
        
        if buy_condition_1 and buy_condition_2 and detail is not None:
            market_cap, turnover, vol_ratio = detail
            if 50 <= market_cap <= 200 and 5 <= turnover <= 10 and vol_ratio > 1:
                buy_results.append({
                    '代码': code,
                    '名称': name,
                    '板块': sector,
                    '价格': latest_close,
                    '20日涨幅%': round(pct_20d, 2),
                    '市值(亿)': round(market_cap, 1),
                    '换手率%': turnover,
                    '量比': vol_ratio,
                })
                print(f"   ✅ {code} 通过买入筛选！")
        
        time.sleep(0.1)
    
    return buy_results, buying_results, sell_results

# ========== 主程序 ==========
if __name__ == "__main__":
    print("🚀 CPO 板块选股系统启动")
    print("=" * 70)
    print("功能1：符合经典买入条件的 CPO 股票")
    print("功能2：识别主力偷偷进场的 CPO 股票（带建议价格区间）")
    print("功能3：识别主力出货预警的 CPO 股票")
    print("=" * 70)
    
    stock_list = get_cpo_stocks()
    print(f"\n📋 CPO 板块共 {len(stock_list)} 只股票待扫描\n")
    
    if len(stock_list) == 0:
        print("❌ 无法获取股票列表，程序退出")
        exit()
    
    index_ret = get_index_return(20)
    print(f"📈 上证指数20日涨幅: {index_ret:.2f}%\n")
    
    buy_results, buying_results, sell_results = scan_stocks(stock_list, index_ret)
    
    # 输出主力偷偷进场
    print("\n" + "=" * 70)
    print(f"🔍 【CPO板块 - 主力偷偷进场】共 {len(buying_results)} 只股票")
    print("=" * 70)
    
    if buying_results:
        for r in buying_results:
            print(f"\n📌 {r['代码']} {r['名称']} ({r['板块']})")
            print(f"   当前价格: {r['价格']}")
            print(f"   20日涨幅: {r['20日涨幅%']}%")
            print(f"   进场信号: {r['进场信号']}")
            print(f"   💰 建议买入区间: {r['建议区间']}")
    else:
        print("暂无检测到主力进场信号")
    
    # 输出经典买入候选
    print("\n" + "=" * 70)
    print(f"🎯 【CPO板块 - 经典买入候选】共 {len(buy_results)} 只股票")
    print("=" * 70)
    print("条件：20日涨幅3~5% + 有涨停 + 量比>1 + 换手5~10% + 市值50~200亿 + 强于大盘")
    print("-" * 70)
    
    if buy_results:
        for r in buy_results:
            print(f"{r['代码']} {r['名称']} | 价格:{r['价格']} | 20日涨幅:{r['20日涨幅%']}% | 市值:{r['市值(亿)']}亿 | 换手:{r['换手率%']}% | 量比:{r['量比']}")
    else:
        print("暂无符合条件的买入标的")
    
    # 输出主力出货预警
    print("\n" + "=" * 70)
    print(f"🔻 【CPO板块 - 主力出货预警】共 {len(sell_results)} 只股票")
    print("=" * 70)
    print("-" * 70)
    
    if sell_results:
        for r in sell_results:
            print(f"\n📌 {r['代码']} {r['名称']} ({r['板块']})")
            print(f"   当前价格: {r['价格']}")
            print(f"   20日涨幅: {r['20日涨幅%']}%")
            print(f"   出货信号: {r['出货信号']}")
    else:
        print("暂未检测到主力出货信号")
    
    print("\n" + "=" * 70)
    print("⚠️ 风险提示：以上结果仅供参考，不构成投资建议")
    print("   投资有风险，入市需谨慎")
    print("=" * 70)