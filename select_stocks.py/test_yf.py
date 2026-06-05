import yfinance as yf

def get_a_stock_data(code):
    """使用 yfinance 获取 A 股数据"""
    if code.startswith('6'):
        yf_code = f"{code}.SS"
    else:
        yf_code = f"{code}.SZ"
    
    print(f"正在获取 {yf_code} ...")
    
    try:
        stock = yf.Ticker(yf_code)
        df = stock.history(start="2025-01-01")
        
        if df.empty:
            print(f"❌ {code} 无数据")
            return None
        
        print(f"✅ {code} 获取成功！共 {len(df)} 条数据")
        print("\n最近5天收盘价：")
        print(df[['Close']].tail())
        return df
        
    except Exception as e:
        print(f"❌ {code} 失败: {e}")
        return None

if __name__ == "__main__":
    print("="*40)
    print("测试 yfinance 获取 A 股数据")
    print("="*40)
    
    get_a_stock_data("600909")
    
    print("\n" + "="*40)
    
    get_a_stock_data("000100")