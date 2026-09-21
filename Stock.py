# -*- coding: utf-8 -*-
"""
主升前夕识别系统 - 完整版
功能：捕捉主力已完成吸筹洗盘，即将拉升的临界点
"""

import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ==================== 基础股票分析类 ====================

class StockAnalyzer:
    """基础股票分析类"""
    
    def __init__(self):
        self._login()
        self._cache = {}
    
    def _login(self):
        lg = bs.login()
        if lg.error_code != '0':
            print(f"baostock登录警告: {lg.error_msg}")
        else:
            print("baostock连接成功")
    
    def _logout(self):
        bs.logout()
    
    def _get_baostock_code(self, code):
        return f"sh.{code}" if code.startswith('6') else f"sz.{code}"
    
    def get_stock_name(self, code):
        bs_code = self._get_baostock_code(code)
        try:
            rs = bs.query_stock_basic(code=bs_code)
            while rs.next():
                return rs.get_row_data()[1]
        except:
            pass
        return code
    
    def get_stock_history(self, code, days=250):
        """获取历史数据（带缓存）"""
        cache_key = f"{code}_{days}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        bs_code = self._get_baostock_code(code)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days+60)).strftime('%Y-%m-%d')
        try:
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag="3"
            )
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            if len(data_list) < 20:
                return None
            df = pd.DataFrame(data_list, columns=rs.fields)
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            self._cache[cache_key] = df
            return df
        except Exception as e:
            print(f"获取数据异常: {e}")
            return None
    
    def calc_rsi(self, df, period=14):
        close = df['close']
        if len(close) < period + 1:
            return 50
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        loss = loss.replace(0, np.nan)
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.fillna(50)
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def analyze(self, code):
        """基础分析"""
        print(f"\n{'='*70}")
        print(f"📊 基础行情分析 - {code}")
        print(f"{'='*70}")
        
        stock_name = self.get_stock_name(code)
        df = self.get_stock_history(code, days=250)
        
        if df is None:
            print("无法获取数据")
            return None
        
        current_price = df['close'].iloc[-1]
        latest_date = df['date'].iloc[-1]
        
        # 计算均线
        close = df['close'].values
        ma5 = np.mean(close[-5:]) if len(close) >= 5 else current_price
        ma10 = np.mean(close[-10:]) if len(close) >= 10 else current_price
        ma20 = np.mean(close[-20:]) if len(close) >= 20 else current_price
        ma60 = np.mean(close[-60:]) if len(close) >= 60 else current_price
        
        # 计算涨跌幅
        pct_change = (close[-1] - close[-2]) / close[-2] * 100 if len(close) >= 2 else 0
        
        print(f"\n📊 股票信息:")
        print(f"   代码: {code}")
        print(f"   名称: {stock_name}")
        print(f"   日期: {latest_date}")
        print(f"   最新价: {current_price:.2f} 元")
        print(f"   涨跌幅: {pct_change:.2f}%")
        
        print(f"\n📈 均线系统:")
        print(f"   MA5:  {ma5:.2f} 元")
        print(f"   MA10: {ma10:.2f} 元")
        print(f"   MA20: {ma20:.2f} 元")
        print(f"   MA60: {ma60:.2f} 元")
        
        # 均线排列判断
        if ma5 > ma10 > ma20 > ma60:
            print(f"   均线排列: 多头排列 ✅")
        elif ma5 < ma10 < ma20 < ma60:
            print(f"   均线排列: 空头排列 ❌")
        else:
            print(f"   均线排列: 震荡整理")
        
        # RSI
        rsi = self.calc_rsi(df)
        rsi_status = "超买区" if rsi > 70 else ("超卖区" if rsi < 30 else "中性区")
        print(f"\n📊 技术指标:")
        print(f"   RSI(14): {rsi:.1f} ({rsi_status})")
        
        return {'code': code, 'name': stock_name, 'price': current_price}


# ==================== 主升前夕检测类 ====================

class PreMainRiseDetector:
    """主升前夕识别器 - 捕捉爆发前临界点"""
    
    def __init__(self, analyzer):
        self.analyzer = analyzer
    
    def detect_pre_main_rise(self, df, current_price):
        """
        识别主升浪启动前夕的信号
        核心特征：筹码集中 + 地量 + 均线粘合 + 形态收敛
        """
        if len(df) < 120:
            return None
        
        signals = []
        score = 0
        details = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        # ========== 核心信号 ==========
        
        # 1. 筹码高度集中（最重要）
        chip_result = self._detect_chip_concentration(df, current_price)
        if chip_result:
            signals.append(chip_result)
            score += 4
            details['筹码集中'] = chip_result
        
        # 2. 地量信号
        volume_result = self._detect_extreme_shrink(df)
        if volume_result:
            signals.append(volume_result)
            score += 3
            details['地量'] = volume_result
        
        # 3. 均线粘合
        ma_result = self._detect_ma_convergence(df)
        if ma_result:
            signals.append(ma_result)
            score += 3
            details['均线粘合'] = ma_result
        
        # 4. 形态收敛
        pattern_result = self._detect_pattern_convergence(df)
        if pattern_result:
            signals.append(pattern_result)
            score += 3
            details['形态收敛'] = pattern_result
        
        # 5. 主力试盘
        test_result = self._detect_test_volume(df)
        if test_result:
            signals.append(test_result)
            score += 2
            details['试盘'] = test_result
        
        # 6. 底部抬高
        higher_low_result = self._detect_higher_low(df)
        if higher_low_result:
            signals.append(higher_low_result)
            score += 2
            details['底部抬高'] = higher_low_result
        
        # 7. 缩量回调
        pullback_result = self._detect_healthy_pullback(df)
        if pullback_result:
            signals.append(pullback_result)
            score += 2
            details['缩量回调'] = pullback_result
        
        # 8. 低位区域
        low_pos_result = self._detect_low_position(df)
        if low_pos_result:
            signals.append(low_pos_result)
            score += 1
            details['低位区域'] = low_pos_result
        
        # 综合判断
        is_pre_main_rise = score >= 8
        confidence = self._calc_confidence(score, signals)
        urgency = self._calc_urgency(score, signals)
        direction = self._predict_direction(df, current_price)
        
        return {
            '是否主升前夕': is_pre_main_rise,
            '置信度': f"{confidence:.1f}%",
            '评分': score,
            '信号数量': len(signals),
            '检测信号': signals[:10],
            '紧迫程度': urgency,
            '爆发方向': direction,
            '细节': details,
            '操作建议': self._get_advice(is_pre_main_rise, confidence, urgency, direction)
        }
    
    # ==================== 信号检测方法 ====================
    
    def _detect_chip_concentration(self, df, current_price):
        """检测筹码高度集中"""
        if len(df) < 120:
            return None
        
        close = df['close'].values
        volume = df['volume'].values
        
        prices = close[-120:]
        vols = volume[-120:]
        
        lower_bound = current_price * 0.9
        upper_bound = current_price * 1.1
        
        mask = (prices >= lower_bound) & (prices <= upper_bound)
        concentrated_vol = np.sum(vols[mask]) if any(mask) else 0
        total_vol = np.sum(vols)
        
        concentration_ratio = concentrated_vol / total_vol if total_vol > 0 else 0
        
        if concentration_ratio > 0.5:
            return {
                '信号': '🪙 筹码高度集中',
                '描述': f'120日成交量{concentration_ratio*100:.0f}%集中在当前价±10%区间',
                '强度': '强',
                '优先级': 'A'
            }
        return None
    
    def _detect_extreme_shrink(self, df):
        """检测地量"""
        if len(df) < 60:
            return None
        
        volume = df['volume'].values
        
        avg_vol_120 = np.mean(volume[-140:-20]) if len(volume) >= 140 else np.mean(volume[:-20])
        current_vol = volume[-1]
        
        ratio = current_vol / avg_vol_120 if avg_vol_120 > 0 else 1
        
        if ratio < 0.5:
            return {
                '信号': '📉 地量见地价',
                '描述': f'成交量仅为120日均量的{ratio*100:.0f}%，浮筹清洗干净',
                '强度': '强',
                '优先级': 'A'
            }
        return None
    
    def _detect_ma_convergence(self, df):
        """检测均线粘合"""
        if len(df) < 60:
            return None
        
        close = df['close'].values
        
        ma5 = np.mean(close[-5:])
        ma10 = np.mean(close[-10:])
        ma20 = np.mean(close[-20:])
        ma60 = np.mean(close[-60:])
        
        mas = [ma5, ma10, ma20, ma60]
        mean_ma = np.mean(mas)
        
        if mean_ma == 0:
            return None
        
        dispersion = np.std(mas) / mean_ma
        
        if dispersion < 0.03:
            return {
                '信号': '📊 均线高度粘合',
                '描述': f'MA5({ma5:.2f}) MA10({ma10:.2f}) MA20({ma20:.2f}) MA60({ma60:.2f})，离散度仅{dispersion*100:.2f}%',
                '强度': '强',
                '优先级': 'A'
            }
        elif dispersion < 0.05:
            return {
                '信号': '📈 均线即将粘合',
                '描述': f'离散度{dispersion*100:.2f}%，均线正在汇聚',
                '强度': '中',
                '优先级': 'B'
            }
        return None
    
    def _detect_pattern_convergence(self, df):
        """检测形态收敛"""
        if len(df) < 60:
            return None
        
        close = df['close'].values
        
        vol_recent = np.std(close[-20:] / np.mean(close[-20:]))
        vol_old = np.std(close[-60:-20] / np.mean(close[-60:-20])) if len(close) >= 60 else vol_recent
        
        vol_ratio = vol_recent / vol_old if vol_old > 0 else 1
        
        if vol_ratio < 0.6:
            return {
                '信号': '🔺 形态收敛末端',
                '描述': f'波动率收窄{vol_ratio*100:.0f}%，三角形整理接近末端',
                '强度': '强',
                '优先级': 'A'
            }
        return None
    
    def _detect_test_volume(self, df):
        """检测主力试盘"""
        if len(df) < 10:
            return None
        
        close = df['close'].values
        open_price = df['open'].values
        high = df['high'].values
        low = df['low'].values
        
        for i in range(-3, 0):
            if i < -len(close):
                continue
            
            body = abs(close[i] - open_price[i])
            candle_range = high[i] - low[i]
            
            if candle_range == 0:
                continue
            
            upper_shadow = high[i] - max(close[i], open_price[i])
            if upper_shadow > body * 2 and upper_shadow > 0:
                if len(close) >= 60 and close[i] < np.mean(close[-60:]) * 1.05:
                    return {
                        '信号': '🎯 主力试盘信号',
                        '描述': '出现长上影线，测试上方抛压',
                        '强度': '中',
                        '优先级': 'B'
                    }
            
            lower_shadow = min(close[i], open_price[i]) - low[i]
            if lower_shadow > body * 2 and lower_shadow > 0:
                if len(close) >= 60 and close[i] < np.mean(close[-60:]) * 1.05:
                    return {
                        '信号': '🎯 主力试盘信号',
                        '描述': '出现长下影线，测试下方承接力',
                        '强度': '中',
                        '优先级': 'B'
                    }
        return None
    
    def _detect_higher_low(self, df):
        """检测底部抬高"""
        if len(df) < 60:
            return None
        
        low = df['low'].values
        
        lows = []
        for i in range(-30, 0):
            if i < -len(low):
                continue
            if i > 0 and i < len(low) - 1:
                if low[i] < low[i-1] and low[i] < low[i+1]:
                    lows.append((i, low[i]))
        
        if len(lows) >= 3:
            recent_lows = lows[-3:]
            if recent_lows[1][1] > recent_lows[0][1] and recent_lows[2][1] > recent_lows[1][1]:
                return {
                    '信号': '📈 底部逐步抬高',
                    '描述': f'低点 {recent_lows[0][1]:.2f} -> {recent_lows[1][1]:.2f} -> {recent_lows[2][1]:.2f}',
                    '强度': '中',
                    '优先级': 'B'
                }
        return None
    
    def _detect_healthy_pullback(self, df):
        """检测健康缩量回调"""
        if len(df) < 30:
            return None
        
        close = df['close'].values
        volume = df['volume'].values
        
        if len(close) >= 10:
            recent_high = max(close[-10:-1]) if len(close) > 10 else max(close[:-1])
            current = close[-1]
            
            if current < recent_high * 0.97:
                avg_vol_old = np.mean(volume[-20:-5]) if len(volume) >= 25 else np.mean(volume[:-5])
                avg_vol_new = np.mean(volume[-5:])
                vol_ratio = avg_vol_new / avg_vol_old if avg_vol_old > 0 else 1
                
                if vol_ratio < 0.8:
                    ma20 = np.mean(close[-20:]) if len(close) >= 20 else close[-1]
                    if current > ma20 * 0.97:
                        return {
                            '信号': '✅ 健康缩量回调',
                            '描述': f'回调{(recent_high-current)/recent_high*100:.1f}%，缩量{vol_ratio*100:.0f}%',
                            '强度': '中',
                            '优先级': 'B'
                        }
        return None
    
    def _detect_low_position(self, df):
        """检测低位区域"""
        if len(df) < 120:
            return None
        
        close = df['close'].values
        min_120 = np.min(close[-120:])
        max_120 = np.max(close[-120:])
        current = close[-1]
        
        position = (current - min_120) / (max_120 - min_120) if max_120 > min_120 else 0.5
        
        if position < 0.3:
            return {
                '信号': '📍 历史低位区域',
                '描述': f'股价处于120日区间的{position*100:.0f}%分位',
                '强度': '弱',
                '优先级': 'C'
            }
        return None
    
    # ==================== 综合分析 ====================
    
    def _calc_confidence(self, score, signals):
        base = min(score * 6, 75)
        a_signals = sum(1 for s in signals if s.get('优先级') == 'A')
        b_signals = sum(1 for s in signals if s.get('优先级') == 'B')
        base += a_signals * 5 + b_signals * 2
        return min(base, 95)
    
    def _calc_urgency(self, score, signals):
        urgency = 0
        if score >= 12:
            urgency += 3
        elif score >= 10:
            urgency += 2
        elif score >= 8:
            urgency += 1
        
        for s in signals:
            if '均线高度粘合' in str(s):
                urgency += 2
            elif '地量' in str(s):
                urgency += 2
        
        if urgency >= 5:
            return "🚀 极度紧迫 - 随时可能爆发！"
        elif urgency >= 3:
            return "🔥 较为紧迫 - 近期可能启动"
        elif urgency >= 1:
            return "📊 一般紧迫 - 需持续观察"
        return "⏳ 尚需等待"
    
    def _predict_direction(self, df, current_price):
        if len(df) < 60:
            return "方向不明"
        
        close = df['close'].values
        ma20 = np.mean(close[-20:])
        ma60 = np.mean(close[-60:])
        
        if current_price > ma20 > ma60:
            return "📈 向上突破概率大"
        elif current_price < ma20 < ma60:
            return "📉 向下突破概率大"
        elif abs(current_price - ma20) / ma20 < 0.02:
            return "↔️ 方向待定，需放量确认"
        elif current_price > ma20:
            return "📈 偏向上突破"
        return "📉 偏向下突破"
    
    def _get_advice(self, is_pre, confidence, urgency, direction):
        if not is_pre:
            return "暂未识别到主升前夕信号，建议继续观察"
        if confidence > 80 and "极度紧迫" in urgency:
            return f"⭐ 强烈关注！{direction}，建议在突破时跟进"
        if confidence > 70:
            return f"📊 重点关注！{direction}，建议轻仓试探"
        if confidence > 60:
            return f"🔍 适当关注。{direction}，等待放量确认"
        return "📌 持续跟踪，信号尚需确认"


# ==================== 主升前夕分析器 ====================

class PreMainRiseAnalyzer:
    """主升前夕完整分析器"""
    
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.detector = PreMainRiseDetector(analyzer)
    
    def analyze_pre_main_rise(self, code):
        """完整的主升前夕分析"""
        print(f"\n{'='*70}")
        print(f"🎯 主升前夕识别系统 - {code}")
        print(f"{'='*70}")
        
        df = self.analyzer.get_stock_history(code, days=250)
        if df is None:
            print("无法获取数据")
            return None
        
        current_price = df['close'].iloc[-1]
        stock_name = self.analyzer.get_stock_name(code)
        
        print(f"\n📊 股票信息:")
        print(f"   代码: {code}")
        print(f"   名称: {stock_name}")
        print(f"   当前价: {current_price:.2f} 元")
        
        result = self.detector.detect_pre_main_rise(df, current_price)
        
        if result is None:
            print("数据不足")
            return None
        
        print(f"\n{'='*70}")
        print(f"🔍 识别结果")
        print(f"{'='*70}")
        print(f"   主升前夕: {'✅ 是' if result['是否主升前夕'] else '❌ 否'}")
        print(f"   评分: {result['评分']} 分（≥8分为主升前夕）")
        print(f"   置信度: {result['置信度']}")
        print(f"   紧迫程度: {result['紧迫程度']}")
        print(f"   爆发方向: {result['爆发方向']}")
        
        print(f"\n📋 检测到的信号:")
        for i, signal in enumerate(result['检测信号'], 1):
            priority = "🔴" if signal.get('优先级') == 'A' else "🟡" if signal.get('优先级') == 'B' else "🟢"
            print(f"   {i}. {priority} {signal['信号']}: {signal['描述']}")
        
        print(f"\n💡 操作建议:")
        print(f"   {result['操作建议']}")
        
        # 如果是主升前夕，打印策略
        if result['是否主升前夕']:
            self._print_strategy(df, current_price)
        
        return result
    
    def _print_strategy(self, df, current_price):
        """打印交易策略"""
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        print(f"\n{'='*70}")
        print(f"🎯 操作策略")
        print(f"{'='*70}")
        
        ma20 = np.mean(close[-20:]) if len(close) >= 20 else current_price
        recent_low = min(low[-10:]) if len(low) >= 10 else current_price
        recent_high = max(high[-20:]) if len(high) >= 20 else current_price
        
        print(f"\n   📍 关键点位:")
        print(f"      当前价: {current_price:.2f} 元")
        print(f"      支撑位: {recent_low:.2f} 元")
        print(f"      MA20: {ma20:.2f} 元")
        print(f"      突破位: {recent_high:.2f} 元")
        
        print(f"\n   📊 买入策略:")
        print(f"      激进: 当前价附近建仓")
        print(f"      稳健: 突破 {recent_high:.2f} 元时跟进")
        
        stop_loss = min(recent_low * 0.97, ma20 * 0.95)
        print(f"\n   🛑 止损: {stop_loss:.2f} 元")
        
        target1 = recent_high * 1.05
        print(f"\n   🎯 第一目标: {target1:.2f} 元")


# ==================== 批量扫描 ====================

class PreMainRiseScanner:
    """批量扫描器"""
    
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.detector = PreMainRiseDetector(analyzer)
    
    def scan(self, stock_list):
        """批量扫描"""
        results = []
        
        print(f"\n正在扫描 {len(stock_list)} 只股票...")
        
        for i, code in enumerate(stock_list):
            print(f"  [{i+1}/{len(stock_list)}] {code}...")
            
            df = self.analyzer.get_stock_history(code, days=250)
            if df is None:
                continue
            
            current_price = df['close'].iloc[-1]
            result = self.detector.detect_pre_main_rise(df, current_price)
            
            if result and result['是否主升前夕'] and result['评分'] >= 8:
                name = self.analyzer.get_stock_name(code)
                results.append({
                    '代码': code,
                    '名称': name,
                    '当前价': current_price,
                    '评分': result['评分'],
                    '置信度': result['置信度'],
                    '紧迫程度': result['紧迫程度'],
                    '方向': result['爆发方向'],
                    '信号': [s['信号'] for s in result['检测信号'][:3]]
                })
        
        results.sort(key=lambda x: x['评分'], reverse=True)
        return results


# ==================== 主程序 ====================

def main():
    base_analyzer = StockAnalyzer()
    pre_rise_analyzer = PreMainRiseAnalyzer(base_analyzer)
    scanner = PreMainRiseScanner(base_analyzer)
    
    while True:
        print("\n" + "="*70)
        print("🎯 主升前夕识别系统 v1.0")
        print("="*70)
        print("功能：捕捉主力已完成吸筹洗盘，即将拉升的临界点")
        print("="*70)
        print("1. 单只股票主升前夕分析")
        print("2. 批量扫描主升前夕潜力股")
        print("3. 基础行情分析")
        print("4. 退出")
        print("="*70)
        
        choice = input("\n请选择 (1-4): ").strip()
        
        if choice == '4':
            base_analyzer._logout()
            print("感谢使用，再见！")
            break
        
        if choice == '1':
            code = input("请输入6位股票代码: ").strip()
            if not (code.isdigit() and len(code) == 6):
                print("❌ 请输入正确的6位数字股票代码")
                continue
            pre_rise_analyzer.analyze_pre_main_rise(code)
        
        elif choice == '2':
            print("\n请输入股票列表（用逗号分隔）")
            print("例如：000001,600519,300750,000858")
            stock_input = input("股票列表: ").strip()
            stock_list = [s.strip() for s in stock_input.split(',') if s.strip().isdigit()]
            
            if not stock_list:
                print("请输入有效的股票代码")
                continue
            
            results = scanner.scan(stock_list)
            
            if not results:
                print("\n❌ 未找到符合主升前夕条件的股票")
                continue
            
            print(f"\n{'='*70}")
            print(f"🎯 主升前夕潜力股（共{len(results)}只）")
            print(f"{'='*70}")
            
            for i, stock in enumerate(results, 1):
                print(f"\n{i}. {stock['代码']} - {stock['名称']}")
                print(f"   当前价: {stock['当前价']:.2f} 元")
                print(f"   评分: {stock['评分']} 分 | 置信度: {stock['置信度']}")
                print(f"   紧迫程度: {stock['紧迫程度']}")
                print(f"   方向: {stock['方向']}")
                print(f"   信号: {', '.join(stock['信号'])}")
        
        elif choice == '3':
            code = input("请输入6位股票代码: ").strip()
            if not (code.isdigit() and len(code) == 6):
                print("❌ 请输入正确的6位数字股票代码")
                continue
            base_analyzer.analyze(code)
        
        else:
            print("无效选择")


if __name__ == "__main__":
    main()