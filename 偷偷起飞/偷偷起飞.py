# -*- coding: utf-8 -*-
"""
主升前夕全自动扫描系统（baostock 版）
依赖: pip install baostock pandas numpy
"""

import time
import numpy as np
import pandas as pd
import baostock as bs
from datetime import datetime, timedelta


# ==================== 股票分析器 ====================
class StockAnalyzer:
    """股票数据获取与分析器（基于 baostock）"""

    def __init__(self):
        self._logged_in = False
        self._stock_list_cache = None

    def _ensure_login(self):
        if not self._logged_in:
            lg = bs.login()
            if lg.error_code != '0':
                raise ConnectionError(f"baostock 登录失败: {lg.error_msg}")
            self._logged_in = True

    def _convert_code(self, code):
        code = str(code).strip()
        if code.startswith('6'):
            return f"sh.{code}"
        elif code.startswith(('0', '3')):
            return f"sz.{code}"
        elif code.startswith(('4', '8')):
            return f"bj.{code}"
        else:
            return f"sh.{code}"

    def get_all_stock_list(self):
        """获取全部 A 股列表（自动往前找最近有数据的交易日）"""
        if self._stock_list_cache is not None:
            return self._stock_list_cache

        self._ensure_login()

        stocks = []
        found_day = None

        for offset in range(0, 15):
            query_day = (datetime.now() - timedelta(days=offset)).strftime('%Y-%m-%d')
            try:
                rs = bs.query_all_stock(day=query_day)
            except Exception as e:
                print(f"⚠️ 查询 {query_day} 异常: {e}")
                continue

            if rs.error_code != '0':
                print(f"⚠️ 查询 {query_day} 失败: {rs.error_msg}")
                continue

            temp = []
            while rs.next():
                row = rs.get_row_data()
                code_full = row[0]  # 如 sh.600000
                name = row[2]
                if code_full.startswith('sh.6') or code_full.startswith('sz.0') or code_full.startswith('sz.3'):
                    code = code_full.split('.')[1]
                    if 'ST' in name or '退' in name:
                        continue
                    temp.append({'code': code, 'name': name})

            print(f"  📅 {query_day}: 获取到 {len(temp)} 只 A 股")

            if len(temp) > 100:
                stocks = temp
                found_day = query_day
                break

        if stocks:
            print(f"✅ 最终使用 {found_day} 的股票列表，共 {len(stocks)} 只")
        else:
            print("❌ 连续 15 天均无法获取股票列表，请检查网络或 baostock 服务状态")

        self._stock_list_cache = stocks
        return stocks

    def get_stock_history(self, code, days=250):
        self._ensure_login()
        bs_code = self._convert_code(code)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

        try:
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2"
            )
        except Exception as e:
            print(f"\n⚠️ 获取 {code} 异常: {e}")
            return None

        if rs.error_code != '0':
            return None

        data_list = []
        try:
            while rs.next():
                data_list.append(rs.get_row_data())
        except Exception as e:
            print(f"\n⚠️ 读取 {code} 数据异常: {e}")
            return None
        # ... 后面的保持不变

        if not data_list:
            return None

        df = pd.DataFrame(data_list, columns=rs.fields)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.dropna(subset=['close', 'volume']).reset_index(drop=True)

        if len(df) > days:
            df = df.iloc[-days:].reset_index(drop=True)

        return df

    def get_stock_name(self, code):
        if self._stock_list_cache is None:
            self.get_all_stock_list()
        for s in self._stock_list_cache:
            if s['code'] == code:
                return s['name']
        return code

    def get_latest_trading_day(self):
        return datetime.now().strftime('%Y-%m-%d')

    def _logout(self):
        if self._logged_in:
            try:
                bs.logout()
            except Exception:
                pass
            self._logged_in = False


# ==================== 主升前夕检测器 ====================
class PreMainRiseDetector:
    """主升前夕信号检测器"""

    def __init__(self, analyzer):
        self.analyzer = analyzer

    def _check_extreme_volume(self, df):
        if len(df) < 60:
            return 0
        volume = df['volume'].values
        avg_vol = np.mean(volume[-140:-20]) if len(volume) >= 140 else np.mean(volume[:-20])
        current_vol = volume[-1]
        ratio = current_vol / avg_vol if avg_vol > 0 else 1
        if ratio < 0.4:
            return 3
        elif ratio < 0.6:
            return 2
        return 0

    def _check_ma_convergence(self, df):
        if len(df) < 60:
            return 0
        close = df['close'].values
        ma5 = np.mean(close[-5:])
        ma10 = np.mean(close[-10:])
        ma20 = np.mean(close[-20:])
        ma60 = np.mean(close[-60:])
        mas = [ma5, ma10, ma20, ma60]
        mean_ma = np.mean(mas)
        if mean_ma == 0:
            return 0
        dispersion = np.std(mas) / mean_ma
        if dispersion < 0.03:
            return 3
        elif dispersion < 0.05:
            return 2
        return 0

    def _check_pattern_convergence(self, df):
        if len(df) < 60:
            return 0
        close = df['close'].values
        vol_recent = np.std(close[-20:] / np.mean(close[-20:]))
        vol_old = np.std(close[-60:-20] / np.mean(close[-60:-20])) if len(close) >= 60 else vol_recent
        vol_ratio = vol_recent / vol_old if vol_old > 0 else 1
        if vol_ratio < 0.5:
            return 3
        elif vol_ratio < 0.7:
            return 2
        return 0

    def _check_higher_low(self, df):
        if len(df) < 60:
            return 0
        low = df['low'].values
        lows = []
        for i in range(-30, 0):
            if i < -len(low):
                continue
            if -len(low) < i < -1:
                if low[i] < low[i - 1] and low[i] < low[i + 1]:
                    lows.append((i, low[i]))
        if len(lows) >= 3:
            recent_lows = lows[-3:]
            if recent_lows[1][1] > recent_lows[0][1] and recent_lows[2][1] > recent_lows[1][1]:
                return 2
        return 0

    def _check_low_position(self, df):
        if len(df) < 120:
            return 0
        close = df['close'].values
        min_120 = np.min(close[-120:])
        max_120 = np.max(close[-120:])
        current = close[-1]
        position = (current - min_120) / (max_120 - min_120) if max_120 > min_120 else 0.5
        if position < 0.3:
            return 1
        return 0

    def _get_signal_details(self, df, current_price):
        details = []
        close = df['close'].values
        volume = df['volume'].values

        if len(df) >= 120:
            prices = close[-120:]
            vols = volume[-120:]
            lower = current_price * 0.9
            upper = current_price * 1.1
            mask = (prices >= lower) & (prices <= upper)
            concentrated = np.sum(vols[mask]) if any(mask) else 0
            total = np.sum(vols)
            ratio = concentrated / total if total > 0 else 0
            if ratio > 0.4:
                details.append(f"筹码集中度{ratio * 100:.0f}%")

        if len(df) >= 60:
            avg_vol = np.mean(volume[-140:-20]) if len(volume) >= 140 else np.mean(volume[:-20])
            current_vol = volume[-1]
            ratio = current_vol / avg_vol if avg_vol > 0 else 1
            if ratio < 0.6:
                details.append(f"地量(均量{ratio * 100:.0f}%)")

        if len(df) >= 60:
            ma5 = np.mean(close[-5:])
            ma10 = np.mean(close[-10:])
            ma20 = np.mean(close[-20:])
            ma60 = np.mean(close[-60:])
            mas = [ma5, ma10, ma20, ma60]
            mean_ma = np.mean(mas)
            if mean_ma > 0:
                dispersion = np.std(mas) / mean_ma
                if dispersion < 0.05:
                    details.append(f"均线粘合(离散度{dispersion * 100:.2f}%)")

        return details

    def detect_pre_main_rise(self, df, current_price):
        if df is None or len(df) < 60:
            return None

        score = 0
        signals = []

        v = self._check_extreme_volume(df)
        if v > 0:
            score += v
            signals.append("地量")

        m = self._check_ma_convergence(df)
        if m > 0:
            score += m
            signals.append("均线粘合")

        p = self._check_pattern_convergence(df)
        if p > 0:
            score += p
            signals.append("形态收敛")

        h = self._check_higher_low(df)
        if h > 0:
            score += h
            signals.append("低点抬高")

        l = self._check_low_position(df)
        if l > 0:
            score += l
            signals.append("低位")

        details = self._get_signal_details(df, current_price)

        return {
            '是否主升前夕': score >= 5,
            '评分': score,
            '信号数量': len(signals),
            '信号列表': signals,
            '详细信号': details
        }


# ==================== 自动扫描器 ====================
class AutoScanner:
    """全自动扫描器"""

    def __init__(self):
        self.analyzer = StockAnalyzer()
        self.detector = PreMainRiseDetector(self.analyzer)
        self.results = []

    # ---------- 板块过滤 ----------
    def _filter_by_market(self, stocks, market):
        """
        market:
          'all' 全部
          'sh'  沪市主板 6 开头
          'sz'  深市主板 0 开头（不含创业板）
          'cyb' 创业板 3 开头
          'bj'  北证 4/8 开头
        也支持组合，如 'sh,cyb'
        """
        if not market or market == 'all':
            return stocks

        markets = [m.strip().lower() for m in market.split(',') if m.strip()]

        def match(code):
            if 'sh' in markets and code.startswith('6'):
                return True
            if 'sz' in markets and code.startswith('0'):
                return True
            if 'cyb' in markets and code.startswith('3'):
                return True
            if 'bj' in markets and code.startswith(('4', '8')):
                return True
            return False

        return [s for s in stocks if match(s['code'])]

    def scan_all_stocks(self, min_score=8, max_stocks=None, market='all'):
        print("\n" + "=" * 70)
        print("🤖 全自动主升前夕扫描系统")
        print("=" * 70)

        print("\n📊 获取股票列表...")
        all_stocks = self.analyzer.get_all_stock_list()

        if not all_stocks:
            print("❌ 无法获取股票列表")
            return []

        # 按板块过滤
        all_stocks = self._filter_by_market(all_stocks, market)
        print(f"✅ 当前板块范围: {market}，共 {len(all_stocks)} 只股票")

        if max_stocks:
            all_stocks = all_stocks[:max_stocks]
            print(f"🔧 测试模式：仅扫描前 {max_stocks} 只")

        print(f"\n🔄 开始扫描...")
        print("-" * 70)

        self.results = []
        total = len(all_stocks)

        for i, stock in enumerate(all_stocks, 1):
            code = stock['code']
            name = stock['name']

            # ✅ 改为每次循环都打印，并加上 flush=True 强制刷新
            print(f"  进度: {i}/{total} ({i / total * 100:.1f}%) 正在扫描: {code} {name}", end="\r", flush=True)

            df = self.analyzer.get_stock_history(code, days=250)
            if df is None or len(df) < 60:
                continue
            # ...
            # time.sleep(0.1)  # ⚠️ 建议删掉或改为 0.01，5000多只股票加上这个延迟太慢了

            current_price = df['close'].iloc[-1]
            result = self.detector.detect_pre_main_rise(df, current_price)

            if result and result['是否主升前夕'] and result['评分'] >= min_score:
                self.results.append({
                    '代码': code,
                    '名称': name,
                    '当前价': round(current_price, 2),
                    '评分': result['评分'],
                    '信号数量': result['信号数量'],
                    '信号列表': result['信号列表'],
                    '详情': result['详细信号']
                })

            time.sleep(0.1)

        print(f"\n\n✅ 扫描完成！共发现 {len(self.results)} 只主升前夕股票")
        self.results.sort(key=lambda x: x['评分'], reverse=True)
        return self.results

    def scan_stock_list(self, stock_codes, min_score=8):
        print("\n" + "=" * 70)
        print("🤖 自定义股票池扫描")
        print("=" * 70)

        print(f"\n📊 共 {len(stock_codes)} 只股票待扫描")
        print(f"🔄 开始扫描...")
        print("-" * 70)

        self.results = []

        for i, code in enumerate(stock_codes, 1):
            print(f"  [{i}/{len(stock_codes)}] {code}...", end="")

            name = self.analyzer.get_stock_name(code)
            df = self.analyzer.get_stock_history(code, days=250)

            if df is None or len(df) < 60:
                print(" ❌ 无数据")
                continue

            current_price = df['close'].iloc[-1]
            result = self.detector.detect_pre_main_rise(df, current_price)

            if result and result['是否主升前夕'] and result['评分'] >= min_score:
                self.results.append({
                    '代码': code,
                    '名称': name,
                    '当前价': round(current_price, 2),
                    '评分': result['评分'],
                    '信号数量': result['信号数量'],
                    '信号列表': result['信号列表'],
                    '详情': result['详细信号']
                })
                print(" ✅ 发现！")
            else:
                print(" ❌")

            time.sleep(0.1)

        self.results.sort(key=lambda x: x['评分'], reverse=True)
        print(f"\n✅ 扫描完成！共发现 {len(self.results)} 只")
        return self.results

    def print_results(self, results=None):
        if results is None:
            results = self.results

        if not results:
            print("\n❌ 未发现符合条件的股票")
            return

        print("\n" + "=" * 70)
        print(f"🎯 主升前夕潜力股列表（共 {len(results)} 只）")
        print(f"📅 数据日期: {self.analyzer.get_latest_trading_day()}")
        print("=" * 70)

        for i, stock in enumerate(results, 1):
            print(f"\n{i}. 【{stock['代码']}】{stock['名称']}")
            print(f"   当前价: {stock['当前价']:.2f} 元")
            print(f"   评分: {stock['评分']} 分")
            print(f"   信号: {', '.join(stock['信号列表'])}")
            if stock.get('详情'):
                print(f"   详情: {', '.join(stock['详情'])}")
            print("   " + "-" * 50)

    def export_to_csv(self, filename=None):
        if not self.results:
            print("没有结果可导出")
            return

        if filename is None:
            latest_day = self.analyzer.get_latest_trading_day().replace('-', '')
            filename = f"主升前夕_{latest_day}.csv"

        df = pd.DataFrame(self.results)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n✅ 结果已导出到: {filename}")
        return filename

    def filter_by_score(self, min_score=8):
        return [r for r in self.results if r['评分'] >= min_score]


# ==================== 主程序 ====================
def choose_market():
    """让用户选择要扫描的板块"""
    print("\n请选择要扫描的板块：")
    print("  1. 全部 A 股（沪市 + 深市 + 创业板 + 北证）")
    print("  2. 沪市主板（6 开头）")
    print("  3. 深市主板（0 开头，不含创业板）")
    print("  4. 创业板（3 开头）")
    print("  5. 北证（4/8 开头）")
    print("  6. 自定义组合（如：sh,cyb 或 sz,cyb,bj）")
    print("  0. 返回")

    choice = input("\n请输入选项 (0-6): ").strip()

    if choice == '1':
        return 'all'
    elif choice == '2':
        return 'sh'
    elif choice == '3':
        return 'sz'
    elif choice == '4':
        return 'cyb'
    elif choice == '5':
        return 'bj'
    elif choice == '6':
        custom = input("请输入组合（sh/sz/cyb/bj，用逗号分隔）: ").strip().lower()
        valid = {'sh', 'sz', 'cyb', 'bj'}
        parts = [p.strip() for p in custom.split(',') if p.strip() in valid]
        if not parts:
            print("⚠️ 输入无效，默认使用全部 A 股")
            return 'all'
        return ','.join(parts)
    else:
        return None


def main():
    scanner = AutoScanner()

    try:
        while True:
            print("\n" + "=" * 70)
            print("🤖 主升前夕全自动扫描系统")
            print("=" * 70)
            print("1. 🔍 全市场自动扫描（推荐）")
            print("2. 📊 自定义股票池扫描")
            print("3. 📈 查看上次扫描结果")
            print("4. 💾 导出结果到CSV")
            print("5. 🚀 按评分筛选结果")
            print("6. ❌ 退出")
            print("=" * 70)

            choice = input("\n请选择 (1-6): ").strip()

            if choice == '6':
                scanner.analyzer._logout()
                print("感谢使用，再见！")
                break

            elif choice == '1':
                print("\n" + "=" * 70)
                print("🔍 全市场自动扫描")
                print("=" * 70)

                # 先选板块
                market = choose_market()
                if market is None:
                    continue

                print(f"\n📌 已选择板块: {market}")
                print("⚠️ 注意：扫描数量越多耗时越长")
                print("💡 建议：可输入测试数量先试试")

                test_mode = input("\n是否测试模式？(y/n，测试模式仅扫描100只): ").strip().lower()
                max_stocks = 100 if test_mode == 'y' else None

                min_score = input("请输入最低评分阈值（默认8分）: ").strip()
                min_score = int(min_score) if min_score.isdigit() else 8

                results = scanner.scan_all_stocks(
                    min_score=min_score,
                    max_stocks=max_stocks,
                    market=market
                )
                scanner.print_results()

                if results:
                    auto_export = input("\n是否自动导出结果？(y/n): ").strip().lower()
                    if auto_export == 'y':
                        scanner.export_to_csv()

            elif choice == '2':
                print("\n请输入股票代码列表（用逗号分隔）")
                print("例如：000001,600519,300750,000858")
                stock_input = input("股票列表: ").strip()
                stock_codes = [s.strip() for s in stock_input.split(',') if s.strip().isdigit()]

                if not stock_codes:
                    print("❌ 请输入有效的股票代码")
                    continue

                min_score = input("请输入最低评分阈值（默认8分）: ").strip()
                min_score = int(min_score) if min_score.isdigit() else 8

                results = scanner.scan_stock_list(stock_codes, min_score=min_score)
                scanner.print_results()

            elif choice == '3':
                if not scanner.results:
                    print("\n❌ 暂无扫描结果，请先执行扫描")
                    continue
                scanner.print_results()

            elif choice == '4':
                if not scanner.results:
                    print("\n❌ 暂无结果可导出，请先执行扫描")
                    continue
                scanner.export_to_csv()

            elif choice == '5':
                if not scanner.results:
                    print("\n❌ 暂无结果，请先执行扫描")
                    continue

                print("\n当前结果评分分布:")
                scores = [r['评分'] for r in scanner.results]
                if scores:
                    print(f"  最高分: {max(scores)}")
                    print(f"  最低分: {min(scores)}")
                    print(f"  平均分: {sum(scores) / len(scores):.1f}")

                min_score = input("\n请输入筛选最低评分: ").strip()
                if min_score.isdigit():
                    min_score = int(min_score)
                    filtered = scanner.filter_by_score(min_score)
                    print(f"\n筛选结果: {len(filtered)} 只")
                    scanner.print_results(filtered)

            else:
                print("无效选择，请重新输入")
    finally:
        scanner.analyzer._logout()


# ==================== 快捷批量扫描函数 ====================
def quick_scan(market='all'):
    scanner = AutoScanner()
    try:
        results = scanner.scan_all_stocks(min_score=8, max_stocks=50, market=market)
        scanner.print_results()
        return results
    finally:
        scanner.analyzer._logout()


def scan_my_stocks():
    scanner = AutoScanner()
    try:
        my_stocks = ['000001', '600519', '300750', '000858', '002475', '600036', '601318']
        results = scanner.scan_stock_list(my_stocks, min_score=8)
        scanner.print_results()
        return results
    finally:
        scanner.analyzer._logout()


if __name__ == "__main__":
    main()