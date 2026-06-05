#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
底部爆发潜力选股系统 - 完整版
功能：筛选处于重要底部区域且具备爆发潜力的股票
使用方法：直接运行 python 本文件

作者：量化助手
版本：v1.0
最后更新：2026-06-05
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ==================== 第一部分：核心扫描器类 ====================

class BottomEruptionScanner:
    """
    底部爆发潜力扫描器
    用于识别处于重要底部区域且即将爆发的股票
    """
    
    def __init__(self, config=None):
        """
        初始化扫描器，可自定义参数
        
        参数说明：
        - pb_percentile_threshold: PB百分位阈值，低于此值认为估值底部
        - lookback_days: 历史回溯天数
        - amplitude_threshold: 横盘振幅阈值
        - consolidation_days: 判断横盘所需最少天数
        - volume_shrink_ratio: 缩量比例（当日量/20日均量低于此值）
        - rsi_threshold: RSI超卖阈值
        - atr_ratio_low: ATR窒息阈值（短期ATR/长期ATR）
        - atr_ratio_mid: ATR中等阈值
        - ma_gap_threshold: 均线粘合阈值
        - ma_gap_mid: 均线接近阈值
        - volume_surge_ratio: 放量阈值
        - min_roe: 最低ROE要求
        - min_revenue_growth: 最低营收增长要求
        - weight_atr: ATR指标权重
        - weight_ma_gap: 均线粘合权重
        - weight_above_ma5: 站上MA5权重
        - weight_volume: 放量权重
        """
        self.config = {
            # 底部区域参数
            'pb_percentile_threshold': 0.20,
            'lookback_days': 500,
            'amplitude_threshold': 0.08,
            'consolidation_days': 20,
            'volume_shrink_ratio': 0.60,
            'rsi_threshold': 30,
            
            # 爆发潜力参数
            'atr_ratio_low': 0.70,
            'atr_ratio_mid': 0.85,
            'ma_gap_threshold': 0.01,
            'ma_gap_mid': 0.02,
            'volume_surge_ratio': 1.20,
            
            # 风控参数
            'min_roe': 0.05,
            'min_revenue_growth': 0.03,
            
            # 评分权重
            'weight_atr': 35,
            'weight_ma_gap': 30,
            'weight_above_ma5': 20,
            'weight_volume': 15,
        }
        if config:
            self.config.update(config)
    
    def calculate_atr(self, df, period=14):
        """
        计算ATR（平均真实波幅）
        
        参数：
        - df: 包含high, low, close的DataFrame
        - period: 计算周期
        """
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def calculate_rsi(self, df, period=14):
        """
        计算RSI（相对强弱指数）
        
        参数：
        - df: 包含close的DataFrame
        - period: 计算周期
        """
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, df, fast=12, slow=26, signal=9):
        """
        计算MACD指标
        
        参数：
        - df: 包含close的DataFrame
        - fast: 快线周期
        - slow: 慢线周期
        - signal: 信号线周期
        """
        exp1 = df['close'].ewm(span=fast, adjust=False).mean()
        exp2 = df['close'].ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_hist = macd - macd_signal
        return macd, macd_signal, macd_hist
    
    def calculate_bollinger_bands(self, df, period=20, std_dev=2):
        """
        计算布林带
        
        参数：
        - df: 包含close的DataFrame
        - period: 周期
        - std_dev: 标准差倍数
        """
        ma = df['close'].rolling(period).mean()
        std = df['close'].rolling(period).std()
        upper = ma + std_dev * std
        lower = ma - std_dev * std
        return upper, ma, lower
    
    def check_bottom_area(self, df):
        """
        检查是否处于重要底部区域
        
        参数：
        - df: 包含high, low, close, volume的DataFrame（可选pb_ratio）
        
        返回：
        - is_bottom: 是否为底部区域（布尔值）
        - score: 底部得分（0-5）
        - details: 详细判断结果
        """
        score = 0
        details = {}
        
        # 检查数据量是否充足
        min_required = max(self.config['lookback_days'], self.config['consolidation_days'] + 10)
        if len(df) < min_required:
            return False, 0, {'error': f'数据不足，需要{min_required}条，实际{len(df)}条'}
        
        # ===== 指标1：PB估值百分位（或价格位置替代）=====
        if 'pb_ratio' in df.columns and df['pb_ratio'].notna().any():
            pb_current = df['pb_ratio'].iloc[-1]
            pb_history = df['pb_ratio'].dropna()
            if len(pb_history) > 100:
                pb_percentile = (pb_history < pb_current).sum() / len(pb_history)
                is_pb_low = pb_percentile <= self.config['pb_percentile_threshold']
                score += int(is_pb_low)
                details['pb_low'] = is_pb_low
                details['pb_value'] = round(pb_current, 2)
                details['pb_percentile'] = round(pb_percentile, 3)
            else:
                details['pb_low'] = None
                details['pb_error'] = 'PB历史数据不足'
        else:
            # 替代方案：价格处于历史低位（距离250日低点10%以内）
            if len(df) >= 250:
                low_250 = df['close'].rolling(250).min().iloc[-1]
                price_position = (df['close'].iloc[-1] - low_250) / low_250
                is_price_low = price_position < 0.10
                score += int(is_price_low)
                details['price_low'] = is_price_low
                details['price_position'] = round(price_position, 4)
            else:
                details['price_low'] = None
        
        # ===== 指标2：布林带下轨位置 =====
        upper, middle, lower = self.calculate_bollinger_bands(df)
        at_lower = df['close'].iloc[-1] <= lower.iloc[-1]
        score += int(at_lower)
        details['at_boll_lower'] = at_lower
        
        # ===== 指标3：成交量萎缩 =====
        vol_ma20 = df['volume'].rolling(20).mean()
        vol_ratio = df['volume'].iloc[-1] / vol_ma20.iloc[-1] if vol_ma20.iloc[-1] != 0 else 1
        vol_shrink = vol_ratio < self.config['volume_shrink_ratio']
        score += int(vol_shrink)
        details['vol_shrink'] = vol_shrink
        details['vol_ratio'] = round(vol_ratio, 3)
        
        # ===== 指标4：横盘状态 =====
        recent_high = df['high'].iloc[-self.config['consolidation_days']:].max()
        recent_low = df['low'].iloc[-self.config['consolidation_days']:].min()
        amplitude = (recent_high - recent_low) / recent_low if recent_low != 0 else 1
        is_consolidation = amplitude < self.config['amplitude_threshold']
        score += int(is_consolidation)
        details['consolidation'] = is_consolidation
        details['amplitude'] = round(amplitude, 4)
        details['consolidation_days_checked'] = self.config['consolidation_days']
        
        # ===== 指标5：RSI低位 =====
        rsi = self.calculate_rsi(df)
        rsi_current = rsi.iloc[-1]
        rsi_low = rsi_current < self.config['rsi_threshold']
        score += int(rsi_low)
        details['rsi_low'] = rsi_low
        details['rsi_value'] = round(rsi_current, 1)
        
        # 综合判定（至少满足3条）
        is_bottom = score >= 3
        return is_bottom, score, details
    
    def check_eruption_potential(self, df):
        """
        检查爆发潜力
        
        参数：
        - df: 包含high, low, close, volume的DataFrame
        
        返回：
        - score: 爆发潜力得分（0-100）
        - details: 详细判断结果
        """
        score = 0
        details = {}
        
        # 检查数据量
        if len(df) < 60:
            return 0, {'error': '数据不足，需要至少60条数据'}
        
        # ===== 指标1：ATR窒息（波动率压缩）=====
        atr_short = self.calculate_atr(df, 20)
        atr_long = self.calculate_atr(df, 60)
        atr_ratio = atr_short.iloc[-1] / atr_long.iloc[-1] if atr_long.iloc[-1] != 0 else 1
        
        if atr_ratio < self.config['atr_ratio_low']:
            score += self.config['weight_atr']
            details['atr_level'] = 'extreme'
        elif atr_ratio < self.config['atr_ratio_mid']:
            score += self.config['weight_atr'] * 0.6
            details['atr_level'] = 'moderate'
        else:
            details['atr_level'] = 'normal'
        details['atr_ratio'] = round(atr_ratio, 4)
        
        # ===== 指标2：均线粘合度 =====
        ma5 = df['close'].rolling(5).mean()
        ma20 = df['close'].rolling(20).mean()
        ma_gap = abs(ma5.iloc[-1] - ma20.iloc[-1]) / ma20.iloc[-1] if ma20.iloc[-1] != 0 else 1
        
        if ma_gap < self.config['ma_gap_threshold']:
            score += self.config['weight_ma_gap']
            details['ma_gap_level'] = 'tight'
        elif ma_gap < self.config['ma_gap_mid']:
            score += self.config['weight_ma_gap'] * 0.5
            details['ma_gap_level'] = 'close'
        else:
            details['ma_gap_level'] = 'loose'
        details['ma_gap'] = round(ma_gap, 4)
        
        # ===== 指标3：股价站上MA5 =====
        above_ma5 = df['close'].iloc[-1] > ma5.iloc[-1]
        if above_ma5:
            score += self.config['weight_above_ma5']
        details['above_ma5'] = above_ma5
        
        # ===== 指标4：量比（相对5日均量）=====
        vol_ma5 = df['volume'].rolling(5).mean()
        vol_ratio = df['volume'].iloc[-1] / vol_ma5.iloc[-1] if vol_ma5.iloc[-1] != 0 else 1
        
        if vol_ratio > self.config['volume_surge_ratio']:
            score += self.config['weight_volume']
            details['volume_level'] = 'surge'
        elif vol_ratio > 1.0:
            score += self.config['weight_volume'] * 0.5
            details['volume_level'] = 'moderate'
        else:
            details['volume_level'] = 'shrink'
        details['vol_ratio'] = round(vol_ratio, 3)
        
        # ===== 额外指标1：连续放量趋势 =====
        if len(df) >= 6:
            recent_vol = df['volume'].iloc[-3:].mean()
            prior_vol = df['volume'].iloc[-6:-3].mean()
            vol_trend = recent_vol / prior_vol if prior_vol != 0 else 1
            details['vol_trend_ratio'] = round(vol_trend, 3)
            if vol_trend > 1.2:
                score += 10
                details['vol_trend'] = 'increasing'
            elif vol_trend < 0.8:
                details['vol_trend'] = 'decreasing'
            else:
                details['vol_trend'] = 'stable'
        
        # ===== 额外指标2：MACD金叉迹象 =====
        macd, macd_signal, macd_hist = self.calculate_macd(df)
        macd_bullish = macd.iloc[-1] > macd_signal.iloc[-1] and macd.iloc[-2] <= macd_signal.iloc[-2]
        details['macd_golden_cross'] = macd_bullish
        if macd_bullish:
            score += 10
        
        # ===== 额外指标3：成交额放大（如果有数据）=====
        if 'amount' in df.columns:
            amount_ma5 = df['amount'].rolling(5).mean()
            amount_ratio = df['amount'].iloc[-1] / amount_ma5.iloc[-1] if amount_ma5.iloc[-1] != 0 else 1
            details['amount_ratio'] = round(amount_ratio, 3)
            if amount_ratio > 1.3:
                score += 5
                details['amount_surge'] = True
        
        return min(score, 100), details
    
    def risk_filter(self, fundamentals):
        """
        风险过滤（基本面）
        
        参数：
        - fundamentals: 包含roe, revenue_growth等字段的字典
        
        返回：
        - True: 通过风控
        - False: 未通过风控
        """
        if not fundamentals:
            return True
        
        # ROE检查
        roe = fundamentals.get('roe', None)
        if roe is not None and roe < self.config['min_roe']:
            return False
        
        # 营收增长检查
        revenue_growth = fundamentals.get('revenue_growth', None)
        if revenue_growth is not None and revenue_growth < self.config['min_revenue_growth']:
            return False
        
        return True
    
    def analyze_single_stock(self, price_df, fundamentals=None, symbol=''):
        """
        分析单只股票（主函数）
        
        参数：
        - price_df: 价格数据DataFrame，需包含 open, high, low, close, volume 列
        - fundamentals: 基本面字典，可选 {'roe': 0.08, 'revenue_growth': 0.05}
        - symbol: 股票代码
        
        返回：
        - result: 包含所有分析结果的字典
        """
        result = {
            'symbol': symbol,
            'date': str(price_df.index[-1]) if hasattr(price_df.index[-1], 'strftime') else str(price_df.index[-1]),
            'signal': 'NO',
            'signal_strength': 0,
            'bottom_score': 0,
            'potential_score': 0,
            'bottom_details': {},
            'potential_details': {},
            'reason': ''
        }
        
        # 验证数据完整性
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in price_df.columns]
        if missing_cols:
            result['reason'] = f'缺少必要列: {missing_cols}'
            return result
        
        # 1. 底部区域判断
        is_bottom, bottom_score, bottom_details = self.check_bottom_area(price_df)
        result['bottom_score'] = bottom_score
        result['bottom_details'] = bottom_details
        
        if 'error' in bottom_details:
            result['reason'] = bottom_details['error']
            return result
        
        if not is_bottom:
            result['reason'] = f'未处于底部区域（得分{bottom_score}/5）'
            return result
        
        # 2. 风险过滤
        if not self.risk_filter(fundamentals):
            result['reason'] = '未通过基本面风控'
            result['signal'] = 'REJECT'
            return result
        
        # 3. 爆发潜力评估
        potential_score, potential_details = self.check_eruption_potential(price_df)
        result['potential_score'] = potential_score
        result['potential_details'] = potential_details
        
        # 4. 综合信号判定
        if potential_score >= 60:
            result['signal'] = 'STRONG_BUY'
            result['signal_strength'] = 3
        elif potential_score >= 40:
            result['signal'] = 'WATCH'
            result['signal_strength'] = 2
        elif potential_score >= 25:
            result['signal'] = 'HOLD'
            result['signal_strength'] = 1
        else:
            result['signal'] = 'IGNORE'
            result['signal_strength'] = 0
        
        result['reason'] = f'底部{bottom_score}/5分，爆发{potential_score}分'
        
        return result
    
    def scan_stock_list(self, stock_data_dict):
        """
        批量扫描股票列表
        
        参数：
        - stock_data_dict: {'symbol1': price_df1, 'symbol2': price_df2, ...}
                           或 {'symbol1': (price_df1, fundamentals1), ...}
        
        返回：
        - df_results: 分析结果DataFrame
        """
        results = []
        for symbol, data in stock_data_dict.items():
            if isinstance(data, tuple) and len(data) == 2:
                price_df, fundamentals = data
            else:
                price_df, fundamentals = data, None
            
            result = self.analyze_single_stock(price_df, fundamentals, symbol)
            results.append(result)
        
        # 转换为DataFrame并排序
        df_results = pd.DataFrame(results)
        if not df_results.empty:
            signal_order = {'STRONG_BUY': 3, 'WATCH': 2, 'HOLD': 1, 'NO': 0, 'REJECT': -1, 'IGNORE': -2}
            df_results['_order'] = df_results['signal'].map(signal_order).fillna(-3)
            df_results = df_results.sort_values(['_order', 'potential_score'], ascending=[False, False])
            df_results = df_results.drop('_order', axis=1)
        
        return df_results


# ==================== 第二部分：数据获取模块 ====================

class DataFetcher:
    """
    数据获取类
    支持多种数据源：本地CSV、模拟数据、以及数据源接口预留
    """
    
    @staticmethod
    def generate_mock_data(symbol='000725.SZ', days=500):
        """
        生成模拟数据（用于测试）
        模拟一个底部形态的股票数据
        """
        np.random.seed(42)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # 构建底部形态：长时间横盘 -> 缩量 -> 小幅回升
        n = len(dates)
        base_price = 100
        
        # 阶段1：前300天，高位震荡下跌
        price = np.ones(n) * base_price
        price[:200] = base_price + np.random.randn(200) * 3 - np.linspace(0, 10, 200)
        
        # 阶段2：中间150天，横盘筑底
        price[200:350] = 85 + np.random.randn(150) * 1.2
        
        # 阶段3：最后150天，底部缩量整理
        price[350:] = 84 + np.random.randn(n-350) * 1.0
        
        # 最后几天小幅回升
        price[-8:] = price[-8:] + [0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0]
        price = np.maximum(price, 70)  # 设置最低价
        
        # 成交量：底部缩量
        volume = np.ones(n) * 1000000
        volume[350:] = 550000 + np.random.randn(n-350) * 100000
        volume = np.maximum(volume, 300000)
        
        # 最后几天放量
        volume[-5:] = volume[-5:] * [1.2, 1.4, 1.5, 1.6, 1.8]
        
        # 成交额
        amount = price * volume * 0.01
        
        df = pd.DataFrame({
            'open': price * (0.99 + np.random.randn(n) * 0.005),
            'high': price * (1.01 + np.random.randn(n) * 0.003),
            'low': price * (0.98 + np.random.randn(n) * 0.005),
            'close': price,
            'volume': volume,
            'amount': amount,
        }, index=dates)
        
        # 确保OHLC关系正确
        df['high'] = df[['open', 'close', 'high']].max(axis=1)
        df['low'] = df[['open', 'close', 'low']].min(axis=1)
        
        # 添加模拟PB数据
        df['pb_ratio'] = 1.0 + np.random.randn(n) * 0.2
        df['pb_ratio'] = df['pb_ratio'].clip(0.8, 2.5)
        df.loc[df.index[-100:], 'pb_ratio'] = 1.1 + np.random.randn(100) * 0.1  # 底部PB低
        
        return df
    
    @staticmethod
    def load_from_csv(file_path, symbol_col='symbol', date_col='date', 
                      price_cols=['open', 'high', 'low', 'close', 'volume', 'amount']):
        """
        从CSV文件加载数据
        
        参数：
        - file_path: CSV文件路径
        - symbol_col: 股票代码列名
        - date_col: 日期列名
        - price_cols: 价格数据列名列表
        
        CSV文件格式示例：
        symbol,date,open,high,low,close,volume,amount
        000725.SZ,2026-01-01,4.12,4.18,4.08,4.15,1000000,4150000
        """
        df = pd.read_csv(file_path, parse_dates=[date_col])
        df = df.set_index(date_col)
        
        stock_dict = {}
        for symbol in df[symbol_col].unique():
            stock_df = df[df[symbol_col] == symbol][price_cols].copy()
            stock_dict[symbol] = stock_df
        
        return stock_dict
    
    @staticmethod
    def create_sample_csv(file_path='stock_data.csv'):
        """
        创建示例CSV文件，方便用户测试
        """
        # 生成两个股票的模拟数据
        df1 = DataFetcher.generate_mock_data('000725.SZ', 500)
        df2 = DataFetcher.generate_mock_data('600519.SH', 500)
        
        # 添加股票代码列
        df1['symbol'] = '000725.SZ'
        df2['symbol'] = '600519.SH'
        
        # 合并
        combined = pd.concat([df1, df2])
        combined = combined.reset_index()
        combined = combined.rename(columns={'index': 'date'})
        
        # 保存
        combined.to_csv(file_path, index=False)
        print(f"示例CSV文件已创建: {file_path}")
        return file_path


# ==================== 第三部分：结果输出和报告模块 ====================

class ResultReporter:
    """结果输出类"""
    
    @staticmethod
    def print_summary(df_results):
        """打印简要摘要"""
        if df_results.empty:
            print("没有符合条件的股票。")
            return
        
        print("\n" + "=" * 100)
        print("底部爆发潜力选股结果摘要")
        print("=" * 100)
        
        # 统计各信号数量
        signal_counts = df_results['signal'].value_counts()
        print("\n信号分布：")
        for signal, count in signal_counts.items():
            print(f"  {signal}: {count}只")
        
        # 详细列表
        print("\n详细列表：")
        print("-" * 100)
        
        # 选择要显示的列
        display_cols = ['symbol', 'date', 'signal', 'bottom_score', 'potential_score']
        if all(col in df_results.columns for col in display_cols):
            print(df_results[display_cols].to_string(index=False))
    
    @staticmethod
    def print_detail(result):
        """打印单只股票的详细分析"""
        print("\n" + "=" * 100)
        print(f"股票详细分析：{result['symbol']}")
        print("=" * 100)
        
        print(f"\n基本信息：")
        print(f"  日期: {result['date']}")
        print(f"  信号: {result['signal']}")
        print(f"  信号强度: {result['signal_strength']}/3")
        print(f"  综合评分: 底部{result['bottom_score']}/5分，爆发{result['potential_score']}分")
        print(f"  判断理由: {result['reason']}")
        
        print(f"\n底部区域判断明细：")
        for k, v in result['bottom_details'].items():
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")
            else:
                print(f"  {k}: {v}")
        
        print(f"\n爆发潜力判断明细：")
        for k, v in result['potential_details'].items():
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")
            else:
                print(f"  {k}: {v}")
    
    @staticmethod
    def export_to_csv(df_results, file_path='bottom_eruption_results.csv'):
        """导出结果到CSV"""
        df_results.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"\n结果已导出到: {file_path}")
    
    @staticmethod
    def export_to_excel(df_results, file_path='bottom_eruption_results.xlsx'):
        """导出结果到Excel"""
        try:
            df_results.to_excel(file_path, index=False, engine='openpyxl')
            print(f"\n结果已导出到: {file_path}")
        except ImportError:
            print("\n需要安装openpyxl才能导出Excel: pip install openpyxl")
            ResultReporter.export_to_csv(df_results)


# ==================== 第四部分：主程序和示例 ====================

def main():
    """
    主函数 - 运行示例
    """
    print("\n" + "=" * 100)
    print("底部爆发潜力选股系统")
    print("=" * 100)
    
    # ===== 步骤1：初始化扫描器 =====
    print("\n[1/4] 初始化扫描器...")
    scanner = BottomEruptionScanner()
    
    # 可选：自定义配置
    # custom_config = {
    #     'min_roe': 0.03,  # 放宽ROE要求
    #     'volume_surge_ratio': 1.15,  # 降低放量要求
    # }
    # scanner = BottomEruptionScanner(custom_config)
    
    # ===== 步骤2：获取数据 =====
    print("[2/4] 获取数据...")
    
    # 方式1：使用模拟数据（推荐用于测试）
    print("  使用模拟数据进行测试...")
    mock_data = DataFetcher.generate_mock_data('000725.SZ', 500)
    
    # 方式2：从CSV文件加载（取消注释以使用）
    # try:
    #     stock_dict = DataFetcher.load_from_csv('stock_data.csv')
    # except FileNotFoundError:
    #     print("  未找到CSV文件，创建示例文件...")
    #     sample_file = DataFetcher.create_sample_csv()
    #     stock_dict = DataFetcher.load_from_csv(sample_file)
    
    # 构建数据字典
    # 添加基本面数据（可选）
    fundamentals = {'roe': 0.08, 'revenue_growth': 0.05}
    stock_data_dict = {
        '000725.SZ': (mock_data, fundamentals),
    }
    
    # 如果有多个股票
    # stock_data_dict = {
    #     '000725.SZ': (df1, fundamentals1),
    #     '600519.SH': (df2, fundamentals2),
    # }
    
    # ===== 步骤3：执行扫描 =====
    print("[3/4] 执行扫描分析...")
    results = scanner.scan_stock_list(stock_data_dict)
    
    # ===== 步骤4：输出结果 =====
    print("[4/4] 输出结果...")
    
    # 创建报告器
    reporter = ResultReporter()
    
    # 打印摘要
    reporter.print_summary(results)
    
    # 如果有结果，打印第一只股票的详细分析
    if not results.empty and results.iloc[0]['signal'] in ['STRONG_BUY', 'WATCH']:
        first_result = scanner.analyze_single_stock(
            stock_data_dict[results.iloc[0]['symbol']][0],
            stock_data_dict[results.iloc[0]['symbol']][1] if isinstance(stock_data_dict[results.iloc[0]['symbol']], tuple) else None,
            results.iloc[0]['symbol']
        )
        reporter.print_detail(first_result)
    
    # 导出结果
    if not results.empty:
        reporter.export_to_csv(results)
        # reporter.export_to_excel(results)  # 需要openpyxl
    
    print("\n" + "=" * 100)
    print("分析完成！")
    print("=" * 100)
    
    return results


# ==================== 单独使用示例 ====================

def quick_test():
    """
    快速测试函数 - 直接分析一只股票
    """
    # 创建扫描器
    scanner = BottomEruptionScanner()
    
    # 生成测试数据
    df = DataFetcher.generate_mock_data('TEST.SH', 500)
    
    # 分析
    result = scanner.analyze_single_stock(df, None, 'TEST.SH')
    
    # 打印结果
    print(f"\n股票: {result['symbol']}")
    print(f"信号: {result['signal']}")
    print(f"底部得分: {result['bottom_score']}/5")
    print(f"爆发得分: {result['potential_score']}/100")
    print(f"原因: {result['reason']}")
    
    return result


# ==================== 命令行入口 ====================

if __name__ == '__main__':
    # 运行主程序
    results = main()
    
    # 也可以单独运行快速测试
    # quick_test()