import baostock as bs
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# ========== 板块股票池数据库 ==========
def get_all_sectors():
    """所有可用的板块"""
    return {
        'CPO': [
            {'代码': '300308', '名称': '中际旭创', '板块': 'CPO'},
            {'代码': '300502', '名称': '新易盛', '板块': 'CPO'},
            {'代码': '300394', '名称': '天孚通信', '板块': 'CPO'},
            {'代码': '002281', '名称': '光迅科技', '板块': 'CPO'},
            {'代码': '000988', '名称': '华工科技', '板块': 'CPO'},
            {'代码': '603083', '名称': '剑桥科技', '板块': 'CPO'},
            {'代码': '688498', '名称': '源杰科技', '板块': 'CPO'},
            {'代码': '688313', '名称': '仕佳光子', '板块': 'CPO'},
            {'代码': '688048', '名称': '长光华芯', '板块': 'CPO'},
            {'代码': '300620', '名称': '光库科技', '板块': 'CPO'},
            {'代码': '688025', '名称': '杰普特', '板块': 'CPO'},
            {'代码': '300757', '名称': '罗博特科', '板块': 'CPO'},
            {'代码': '600487', '名称': '亨通光电', '板块': 'CPO'},
            {'代码': '601869', '名称': '长飞光纤', '板块': 'CPO'},
            {'代码': '600522', '名称': '中天科技', '板块': 'CPO'},
            {'代码': '000938', '名称': '紫光股份', '板块': 'CPO'},
            {'代码': '600498', '名称': '烽火通信', '板块': 'CPO'},
            {'代码': '002384', '名称': '东山精密', '板块': 'CPO'},
        ],
        'AI算力': [
            {'代码': '002230', '名称': '科大讯飞', '板块': 'AI算力'},
            {'代码': '300418', '名称': '昆仑万维', '板块': 'AI算力'},
            {'代码': '603019', '名称': '中科曙光', '板块': 'AI算力'},
            {'代码': '000977', '名称': '浪潮信息', '板块': 'AI算力'},
            {'代码': '300502', '名称': '新易盛', '板块': 'AI算力'},
            {'代码': '300308', '名称': '中际旭创', '板块': 'AI算力'},
            {'代码': '002463', '名称': '沪电股份', '板块': 'AI算力'},
        ],
        '半导体': [
            {'代码': '002371', '名称': '北方华创', '板块': '半导体'},
            {'代码': '688981', '名称': '中芯国际', '板块': '半导体'},
            {'代码': '603986', '名称': '兆易创新', '板块': '半导体'},
            {'代码': '002049', '名称': '紫光国微', '板块': '半导体'},
            {'代码': '300782', '名称': '卓胜微', '板块': '半导体'},
            {'代码': '688008', '名称': '澜起科技', '板块': '半导体'},
            {'代码': '688012', '名称': '中微公司', '板块': '半导体'},
        ],
        '新能源车': [
            {'代码': '002594', '名称': '比亚迪', '板块': '新能源车'},
            {'代码': '300750', '名称': '宁德时代', '板块': '新能源车'},
            {'代码': '002475', '名称': '立讯精密', '板块': '新能源车'},
            {'代码': '300124', '名称': '汇川技术', '板块': '新能源车'},
            {'代码': '002466', '名称': '天齐锂业', '板块': '新能源车'},
            {'代码': '002460', '名称': '赣锋锂业', '板块': '新能源车'},
            {'代码': '300014', '名称': '亿纬锂能', '板块': '新能源车'},
            {'代码': '002812', '名称': '恩捷股份', '板块': '新能源车'},
        ],
        '光伏': [
            {'代码': '300274', '名称': '阳光电源', '板块': '光伏'},
            {'代码': '002129', '名称': 'TCL中环', '板块': '光伏'},
            {'代码': '600438', '名称': '通威股份', '板块': '光伏'},
            {'代码': '300316', '名称': '晶盛机电', '板块': '光伏'},
            {'代码': '601012', '名称': '隆基绿能', '板块': '光伏'},
            {'代码': '002459', '名称': '晶澳科技', '板块': '光伏'},
            {'代码': '688599', '名称': '天合光能', '板块': '光伏'},
        ],
        '消费电子': [
            {'代码': '002475', '名称': '立讯精密', '板块': '消费电子'},
            {'代码': '300433', '名称': '蓝思科技', '板块': '消费电子'},
            {'代码': '002241', '名称': '歌尔股份', '板块': '消费电子'},
            {'代码': '300136', '名称': '信维通信', '板块': '消费电子'},
            {'代码': '002600', '名称': '领益智造', '板块': '消费电子'},
            {'代码': '300115', '名称': '长盈精密', '板块': '消费电子'},
        ],
        '医药': [
            {'代码': '600276', '名称': '恒瑞医药', '板块': '医药'},
            {'代码': '300760', '名称': '迈瑞医疗', '板块': '医药'},
            {'代码': '000538', '名称': '云南白药', '板块': '医药'},
            {'代码': '002415', '名称': '药明康德', '板块': '医药'},
            {'代码': '300015', '名称': '爱尔眼科', '板块': '医药'},
            {'代码': '002007', '名称': '华兰生物', '板块': '医药'},
        ],
        '券商': [
            {'代码': '600030', '名称': '中信证券', '板块': '券商'},
            {'代码': '600837', '名称': '海通证券', '板块': '券商'},
            {'代码': '601688', '名称': '华泰证券', '板块': '券商'},
            {'代码': '600999', '名称': '招商证券', '板块': '券商'},
            {'代码': '000776', '名称': '广发证券', '板块': '券商'},
            {'代码': '601211', '名称': '国泰君安', '板块': '券商'},
        ],
        '银行': [
            {'代码': '600036', '名称': '招商银行', '板块': '银行'},
            {'代码': '601398', '名称': '工商银行', '板块': '银行'},
            {'代码': '601288', '名称': '农业银行', '板块': '银行'},
            {'代码': '601939', '名称': '建设银行', '板块': '银行'},
            {'代码': '000001', '名称': '平安银行', '板块': '银行'},
            {'代码': '600016', '名称': '民生银行', '板块': '银行'},
        ],
        # ========== 新增板块 ==========
        '机器人': [
            {'代码': '300024', '名称': '机器人', '板块': '机器人'},
            {'代码': '002747', '名称': '埃斯顿', '板块': '机器人'},
            {'代码': '300124', '名称': '汇川技术', '板块': '机器人'},
            {'代码': '688017', '名称': '绿的谐波', '板块': '机器人'},
            {'代码': '002472', '名称': '双环传动', '板块': '机器人'},
            {'代码': '300161', '名称': '华中数控', '板块': '机器人'},
            {'代码': '002527', '名称': '新时达', '板块': '机器人'},
            {'代码': '688165', '名称': '埃夫特', '板块': '机器人'},
            {'代码': '002896', '名称': '中大力德', '板块': '机器人'},
            {'代码': '300607', '名称': '拓斯达', '板块': '机器人'},
        ],
        '低空经济': [
            {'代码': '002085', '名称': '万丰奥威', '板块': '低空经济'},
            {'代码': '300719', '名称': '安达维尔', '板块': '低空经济'},
            {'代码': '600038', '名称': '中直股份', '板块': '低空经济'},
            {'代码': '000801', '名称': '四川九洲', '板块': '低空经济'},
            {'代码': '002389', '名称': '航天彩虹', '板块': '低空经济'},
            {'代码': '300101', '名称': '振芯科技', '板块': '低空经济'},
            {'代码': '002151', '名称': '北斗星通', '板块': '低空经济'},
            {'代码': '300045', '名称': '华力创通', '板块': '低空经济'},
        ],
        '信创': [
            {'代码': '000977', '名称': '浪潮信息', '板块': '信创'},
            {'代码': '002230', '名称': '科大讯飞', '板块': '信创'},
            {'代码': '600536', '名称': '中国软件', '板块': '信创'},
            {'代码': '300454', '名称': '深信服', '板块': '信创'},
            {'代码': '002410', '名称': '广联达', '板块': '信创'},
            {'代码': '300059', '名称': '东方财富', '板块': '信创'},
            {'代码': '002065', '名称': '东华软件', '板块': '信创'},
            {'代码': '600588', '名称': '用友网络', '板块': '信创'},
            {'代码': '300033', '名称': '同花顺', '板块': '信创'},
        ],
    }

def get_stocks_by_sector(sector_name):
    """根据板块名称获取股票列表"""
    sectors = get_all_sectors()
    if sector_name in sectors:
        return sectors[sector_name]
    return []

def list_available_sectors():
    """列出所有可用板块"""
    sectors = get_all_sectors()
    print("\n📋 可用板块列表：")
    print("-" * 50)
    for i, name in enumerate(sectors.keys(), 1):
        print(f"   {i:2d}. {name}（{len(sectors[name])}只）")
    print("-" * 50)

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
    
    if price_position < 0.3 and vol_ratio > 1.5:
        signals.append("🔍 底部放量，主力吸筹")
        is_buying = True
    
    recent_5d = close[-5:] if len(close) >= 5 else close
    small_up_days = 0
    for i in range(1, len(recent_5d)):
        if 0 < (recent_5d[i] - recent_5d[i-1]) / recent_5d[i-1] * 100 < 3:
            small_up_days += 1
    if small_up_days >= 3:
        signals.append("🔍 连续小阳线，温和吸筹")
        is_buying = True
    
    vol_shrink = volume[-5:].mean() < volume[-20:].mean() * 0.8
    price_stable = abs(close[-1] - close[-5]) / close[-5] * 100 < 3
    if vol_shrink and price_stable and price_position < 0.5:
        signals.append("🔍 缩量企稳，洗盘结束")
        is_buying = True
    
    open_price = df['open'].values if 'open' in df.columns else close
    lower_shadow = min(close[-1], open_price[-1]) - low[-1] if len(open_price) > 0 else 0
    body = abs(close[-1] - open_price[-1]) if len(open_price) > 0 else 0
    if lower_shadow > body * 2 and lower_shadow > 0 and price_position < 0.4:
        signals.append("🔍 长下影线，探底回升")
        is_buying = True
    
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
def scan_stocks(stock_list, index_ret, price_min=0, price_max=20):
    buy_results = []
    buying_results = []
    sell_results = []
    
    total = len(stock_list)
    print(f"\n💰 价格过滤条件: {price_min} - {price_max} 元\n")
    
    for i, stock in enumerate(stock_list):
        code = stock['代码']
        name = stock['名称']
        sector = stock.get('板块', '未知')
        
        df = get_stock_history(code)
        if df is None:
            continue
        
        latest_close = df['close'].iloc[-1]
        
        # 价格区间过滤
        if latest_close < price_min or latest_close > price_max:
            print(f"⏭️ 跳过 {code} {name}（价格 {latest_close}，不在 {price_min}-{price_max} 区间）")
            continue
        
        print(f"📊 扫描 {i+1}/{total}: {code} {name} ({sector}) - 价格: {latest_close}")
        
        pct_20d, has_limit_up, _ = calc_technical_indicators(df)
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
            print(f"   🔍 检测到主力进场")
        
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
            print(f"   🔻 检测到出货信号")
        
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
                print(f"   ✅ 通过买入筛选！")
        
        time.sleep(0.1)
    
    return buy_results, buying_results, sell_results

# ========== 主程序 ==========
if __name__ == "__main__":
    print("🚀 板块选股系统启动")
    print("=" * 70)
    print("功能：选择板块 + 价格区间过滤")
    print("识别：主力偷偷进场 | 经典买入条件 | 主力出货预警")
    print("=" * 70)
    
    # 显示可用板块
    list_available_sectors()
    
    # 用户选择板块
    while True:
        sector_input = input("\n请输入板块名称：").strip()
        stock_list = get_stocks_by_sector(sector_input)
        if stock_list:
            print(f"✅ 已选择板块：{sector_input}，共 {len(stock_list)} 只股票")
            break
        else:
            print(f"❌ 未找到板块「{sector_input}」，请重新输入")
            list_available_sectors()
    
    # 价格区间输入
    print("\n💰 价格区间过滤（扫描 0-20 元股票）")
    price_min = 0
    price_max = 20
    print(f"   当前设置：{price_min} - {price_max} 元")
    
    change = input("   是否修改价格区间？(y/n，默认 n)：").strip().lower()
    if change == 'y':
        try:
            price_min = float(input("   请输入最低价格：").strip())
            price_max = float(input("   请输入最高价格：").strip())
            print(f"   ✅ 已设置价格区间：{price_min} - {price_max} 元")
        except:
            print("   输入无效，使用默认区间 0-20 元")
    
    print(f"\n📋 板块「{sector_input}」共 {len(stock_list)} 只股票待扫描")
    print(f"💰 价格过滤：{price_min} - {price_max} 元\n")
    
    if len(stock_list) == 0:
        print("❌ 无法获取股票列表，程序退出")
        exit()
    
    index_ret = get_index_return(20)
    print(f"📈 上证指数20日涨幅: {index_ret:.2f}%\n")
    
    buy_results, buying_results, sell_results = scan_stocks(stock_list, index_ret, price_min, price_max)
    
    # 输出主力偷偷进场
    print("\n" + "=" * 70)
    print(f"🔍 【{sector_input}板块 - 主力偷偷进场】共 {len(buying_results)} 只股票")
    print("=" * 70)
    
    if buying_results:
        for r in buying_results:
            print(f"\n📌 {r['代码']} {r['名称']}")
            print(f"   板块: {r['板块']}")
            print(f"   当前价格: {r['价格']} 元")
            print(f"   20日涨幅: {r['20日涨幅%']}%")
            print(f"   进场信号: {r['进场信号']}")
            print(f"   💰 建议买入区间: {r['建议区间']} 元")
    else:
        print("暂无检测到主力进场信号")
    
    # 输出经典买入候选
    print("\n" + "=" * 70)
    print(f"🎯 【{sector_input}板块 - 经典买入候选】共 {len(buy_results)} 只股票")
    print("=" * 70)
    print("条件：20日涨幅3~5% + 有涨停 + 量比>1 + 换手5~10% + 市值50~200亿 + 强于大盘")
    print("-" * 70)
    
    if buy_results:
        for r in buy_results:
            print(f"{r['代码']} {r['名称']} | 价格:{r['价格']}元 | 20日涨幅:{r['20日涨幅%']}% | 市值:{r['市值(亿)']}亿 | 换手:{r['换手率%']}% | 量比:{r['量比']}")
    else:
        print("暂无符合条件的买入标的")
    
    # 输出主力出货预警
    print("\n" + "=" * 70)
    print(f"🔻 【{sector_input}板块 - 主力出货预警】共 {len(sell_results)} 只股票")
    print("=" * 70)
    print("-" * 70)
    
    if sell_results:
        for r in sell_results:
            print(f"\n📌 {r['代码']} {r['名称']}")
            print(f"   板块: {r['板块']}")
            print(f"   当前价格: {r['价格']} 元")
            print(f"   20日涨幅: {r['20日涨幅%']}%")
            print(f"   出货信号: {r['出货信号']}")
    else:
        print("暂未检测到主力出货信号")
    
    print("\n" + "=" * 70)
    print("⚠️ 风险提示：以上结果仅供参考，不构成投资建议")
    print("   投资有风险，入市需谨慎")
    print("=" * 70)