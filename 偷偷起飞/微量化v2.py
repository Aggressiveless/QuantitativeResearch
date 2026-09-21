# -*- coding: utf-8 -*-
"""
主升前夕全自动扫描系统 v2（实时增强版）
依赖: pip install baostock pandas numpy requests
"""

import os
import re
import json
import time
import threading
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import baostock as bs

import csv
import glob
from pathlib import Path


# ============================================================
# 实时行情（新浪财经）
# ============================================================
class RealtimeQuote:
    URL = "http://hq.sinajs.cn/list={}"
    HEADERS = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }

    @classmethod
    def _to_sina_code(cls, code):
        code = str(code).strip()
        if code.startswith('6'):
            return f"sh{code}"
        if code.startswith(('0', '3')):
            return f"sz{code}"
        if code.startswith(('4', '8')):
            return f"bj{code}"
        return f"sh{code}"

    @classmethod
    def fetch(cls, codes):
        """批量获取实时行情，返回 {code: {...}}"""
        if not codes:
            return {}
        sina_codes = [cls._to_sina_code(c) for c in codes]
        result = {}
        for i in range(0, len(sina_codes), 100):
            batch = sina_codes[i:i + 100]
            url = cls.URL.format(",".join(batch))
            try:
                r = requests.get(url, headers=cls.HEADERS, timeout=6)
                r.encoding = 'gbk'
                for line in r.text.strip().split('\n'):
                    m = re.match(r'var hq_str_(\w+)="(.*)";', line.strip())
                    if not m:
                        continue
                    sina_code, content = m.group(1), m.group(2)
                    if not content:
                        continue
                    fields = content.split(',')
                    if len(fields) < 32:
                        continue
                    code = sina_code[2:]
                    try:
                        result[code] = {
                            'name': fields[0],
                            'open': float(fields[1] or 0),
                            'preclose': float(fields[2] or 0),
                            'price': float(fields[3] or 0),
                            'high': float(fields[4] or 0),
                            'low': float(fields[5] or 0),
                            'volume': float(fields[8] or 0),   # 股
                            'amount': float(fields[9] or 0),   # 元
                            'date': fields[30],
                            'time': fields[31],
                        }
                    except (ValueError, IndexError):
                        continue
            except Exception as e:
                print(f"⚠️ 实时行情获取失败: {e}")
            time.sleep(0.1)
        return result


# ============================================================
# baostock 历史数据
# ============================================================
class StockAnalyzer:
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
        if code.startswith(('0', '3')):
            return f"sz.{code}"
        if code.startswith(('4', '8')):
            return f"bj.{code}"
        return f"sh.{code}"

    def get_all_stock_list(self):
        if self._stock_list_cache is not None:
            return self._stock_list_cache
        self._ensure_login()
        stocks, found_day = [], None
        for offset in range(0, 15):
            query_day = (datetime.now() - timedelta(days=offset)).strftime('%Y-%m-%d')
            try:
                rs = bs.query_all_stock(day=query_day)
            except Exception:
                continue
            if rs.error_code != '0':
                continue
            temp = []
            while rs.next():
                row = rs.get_row_data()
                code_full, name = row[0], row[2]
                if code_full.startswith(('sh.6', 'sz.0', 'sz.3')):
                    code = code_full.split('.')[1]
                    if 'ST' in name or '退' in name:
                        continue
                    temp.append({'code': code, 'name': name})
            print(f"  📅 {query_day}: {len(temp)} 只")
            if len(temp) > 100:
                stocks, found_day = temp, query_day
                break
        if stocks:
            print(f"✅ 使用 {found_day} 列表，共 {len(stocks)} 只")
        self._stock_list_cache = stocks
        return stocks

    def get_stock_history(self, code, days=250):
        """获取历史日线（含换手率、涨跌幅），带重试"""
        self._ensure_login()
        bs_code = self._convert_code(code)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

        for attempt in range(3):
            try:
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,open,high,low,close,preclose,volume,amount,turn,pctChg",
                    start_date=start_date, end_date=end_date,
                    frequency="d", adjustflag="2"
                )
                if rs.error_code != '0':
                    return None
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                if not data_list:
                    return None
                df = pd.DataFrame(data_list, columns=rs.fields)
                for col in ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'turn', 'pctChg']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.dropna(subset=['close', 'volume']).reset_index(drop=True)
                if len(df) > days:
                    df = df.iloc[-days:].reset_index(drop=True)
                return df
            except Exception as e:
                print(f"\n⚠️ {code} 第 {attempt+1} 次失败: {e}")
                time.sleep(1.5)
                try:
                    bs.logout()
                except Exception:
                    pass
                self._logged_in = False
                self._ensure_login()
        return None

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


# ============================================================
# 技术指标计算
# ============================================================
class TechnicalAnalyzer:
    """计算一整套技术指标，并输出结构化结果"""

    @staticmethod
    def calc_macd(close, fast=12, slow=26, signal=9):
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = (dif - dea) * 2
        return dif, dea, macd

    @staticmethod
    def calc_kdj(high, low, close, n=9, m1=3, m2=3):
        low_n = low.rolling(n).min()
        high_n = high.rolling(n).max()
        rsv = (close - low_n) / (high_n - low_n).replace(0, np.nan) * 100
        rsv = rsv.fillna(50)
        k = rsv.ewm(com=m1 - 1, adjust=False).mean()
        d = k.ewm(com=m2 - 1, adjust=False).mean()
        j = 3 * k - 2 * d
        return k, d, j

    @staticmethod
    def calc_rsi(close, n=14):
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(com=n - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=n - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs)
        return rsi.fillna(50)

    @staticmethod
    def calc_boll(close, n=20, k=2):
        mid = close.rolling(n).mean()
        std = close.rolling(n).std()
        return mid + k * std, mid, mid - k * std

    @staticmethod
    def calc_ma(close, n):
        return close.rolling(n).mean()

    def analyze(self, df):
        """输入日线 df，输出技术面结论 dict"""
        if df is None or len(df) < 60:
            return None

        close = df['close']
        high = df['high']
        low = df['low']
        open_ = df['open']
        volume = df['volume']

        ma5 = self.calc_ma(close, 5).iloc[-1]
        ma10 = self.calc_ma(close, 10).iloc[-1]
        ma20 = self.calc_ma(close, 20).iloc[-1]
        ma60 = self.calc_ma(close, 60).iloc[-1]
        price = close.iloc[-1]

        dif, dea, macd = self.calc_macd(close)
        dif_v, dea_v, macd_v = dif.iloc[-1], dea.iloc[-1], macd.iloc[-1]
        dif_prev, dea_prev = dif.iloc[-2], dea.iloc[-2]

        k, d, j = self.calc_kdj(high, low, close)
        k_v, d_v, j_v = k.iloc[-1], d.iloc[-1], j.iloc[-1]
        k_prev, d_prev = k.iloc[-2], d.iloc[-2]

        rsi = self.calc_rsi(close)
        rsi_v = rsi.iloc[-1]

        boll_up, boll_mid, boll_low = self.calc_boll(close)
        bu, bm, bl = boll_up.iloc[-1], boll_mid.iloc[-1], boll_low.iloc[-1]

        # 均线排列
        ma_bull = ma5 > ma10 > ma20 > ma60
        ma_bear = ma5 < ma10 < ma20 < ma60

        # MACD 金叉/死叉
        macd_gold = dif_prev <= dea_prev and dif_v > dea_v
        macd_dead = dif_prev >= dea_prev and dif_v < dea_v

        # KDJ 金叉/死叉
        kdj_gold = k_prev <= d_prev and k_v > d_v
        kdj_dead = k_prev >= d_prev and k_v < d_v

        # 量能
        avg_vol_20 = volume.iloc[-21:-1].mean() if len(volume) >= 21 else volume.mean()
        vol_ratio = volume.iloc[-1] / avg_vol_20 if avg_vol_20 > 0 else 1
        is_up = close.iloc[-1] > close.iloc[-2]
        vol_expand_up = vol_ratio > 1.5 and is_up
        vol_expand_down = vol_ratio > 1.5 and not is_up

        # 位置（120 日）
        if len(close) >= 120:
            min120, max120 = close.iloc[-120:].min(), close.iloc[-120:].max()
            position = (price - min120) / (max120 - min120) if max120 > min120 else 0.5
        else:
            position = 0.5

        return {
            'price': price,
            'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60,
            'ma_bull': ma_bull, 'ma_bear': ma_bear,
            'dif': dif_v, 'dea': dea_v, 'macd': macd_v,
            'macd_gold': macd_gold, 'macd_dead': macd_dead,
            'k': k_v, 'd': d_v, 'j': j_v,
            'kdj_gold': kdj_gold, 'kdj_dead': kdj_dead,
            'rsi': rsi_v,
            'boll_up': bu, 'boll_mid': bm, 'boll_low': bl,
            'vol_ratio': vol_ratio,
            'vol_expand_up': vol_expand_up,
            'vol_expand_down': vol_expand_down,
            'position_120': position,
        }


# ============================================================
# 操作建议引擎
# ============================================================
class StockAdvisor:
    """
    结合技术面 + 持仓状态，输出操作建议
    持仓状态: '空仓' / '持仓'
    """

    def score_technical(self, tech):
        """技术面打分，范围约 -100 ~ +100"""
        s = 0
        reasons = []

        # 均线系统
        if tech['ma_bull']:
            s += 20
            reasons.append("均线多头排列(+20)")
        elif tech['ma_bear']:
            s -= 20
            reasons.append("均线空头排列(-20)")

        # 价格 vs 均线
        if tech['price'] > tech['ma20']:
            s += 5
        else:
            s -= 5

        # MACD
        if tech['macd_gold']:
            s += 15
            reasons.append("MACD金叉(+15)")
        elif tech['macd_dead']:
            s -= 15
            reasons.append("MACD死叉(-15)")
        if tech['dif'] > 0:
            s += 5
        else:
            s -= 5

        # KDJ
        if tech['kdj_gold'] and tech['k'] < 80:
            s += 10
            reasons.append("KDJ金叉(+10)")
        elif tech['kdj_dead']:
            s -= 10
            reasons.append("KDJ死叉(-10)")
        if tech['j'] > 100:
            s -= 5
        elif tech['j'] < 0:
            s += 5

        # RSI
        if tech['rsi'] > 70:
            s -= 10
            reasons.append("RSI超买(-10)")
        elif tech['rsi'] < 30:
            s += 10
            reasons.append("RSI超卖(+10)")

        # 布林带
        if tech['price'] <= tech['boll_low']:
            s += 10
            reasons.append("触及布林下轨(+10)")
        elif tech['price'] >= tech['boll_up']:
            s -= 10
            reasons.append("触及布林上轨(-10)")

        # 量能
        if tech['vol_expand_up']:
            s += 10
            reasons.append("放量上涨(+10)")
        elif tech['vol_expand_down']:
            s -= 10
            reasons.append("放量下跌(-10)")

        # 位置
        if tech['position_120'] < 0.3:
            s += 10
            reasons.append("低位(+10)")
        elif tech['position_120'] > 0.8:
            s -= 10
            reasons.append("高位(-10)")

        return s, reasons

    def advise(self, code, name, tech, position_state='空仓', cost=None, shares=0):
        """
        position_state: '空仓' 或 '持仓'
        cost: 持仓成本价
        shares: 持仓数量
        返回 dict
        """
        score, reasons = self.score_technical(tech)
        price = tech['price']

        # 浮盈浮亏
        profit_pct = 0
        if position_state == '持仓' and cost:
            profit_pct = (price - cost) / cost * 100

        action = "观望"
        advice_reason = []

        if position_state == '空仓':
            if score >= 60:
                action = "买入"
            elif score >= 40:
                action = "建仓（小仓试探）"
            elif score >= 20:
                action = "关注/轻仓"
            elif score >= 0:
                action = "观望"
            else:
                action = "回避"
        else:  # 持仓
            # 止损优先
            if profit_pct <= -8:
                action = "止损卖出"
                advice_reason.append(f"浮亏{profit_pct:.1f}%，触发止损")
            elif score >= 60:
                action = "加仓/坚定持有"
            elif score >= 30:
                action = "继续持有"
            elif score >= 0:
                action = "减仓观望"
            else:
                action = "卖出"
                advice_reason.append("技术面转弱")

            # 高位 + 死叉提醒
            if tech['position_120'] > 0.8 and tech['macd_dead']:
                if action.startswith("继续持有") or action.startswith("加仓"):
                    action = "减仓"
                    advice_reason.append("高位MACD死叉，建议减仓")

        return {
            'code': code,
            'name': name,
            'price': price,
            'score': score,
            'action': action,
            'reasons': reasons + advice_reason,
            'profit_pct': profit_pct if position_state == '持仓' else None,
            'tech': tech,
        }


# ============================================================
# 持仓管理（JSON 持久化）
# ============================================================
class PositionManager:
    def __init__(self, path="positions.json"):
        self.path = path
        self.positions = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.positions = json.load(f)
            except Exception:
                self.positions = {}

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.positions, f, ensure_ascii=False, indent=2)

    def set_position(self, code, cost, shares, name=''):
        self.positions[code] = {'cost': cost, 'shares': shares, 'name': name}
        self.save()

    def remove(self, code):
        if code in self.positions:
            del self.positions[code]
            self.save()

    def get(self, code):
        return self.positions.get(code)

    def list_all(self):
        return self.positions


# ============================================================
# 主升前夕检测器（保留原版）
# ============================================================
class PreMainRiseDetector:
    def __init__(self, analyzer):
        self.analyzer = analyzer

    def _check_extreme_volume(self, df):
        if len(df) < 60: return 0
        v = df['volume'].values
        avg = np.mean(v[-140:-20]) if len(v) >= 140 else np.mean(v[:-20])
        ratio = v[-1] / avg if avg > 0 else 1
        return 3 if ratio < 0.4 else (2 if ratio < 0.6 else 0)

    def _check_ma_convergence(self, df):
        if len(df) < 60: return 0
        c = df['close'].values
        mas = [np.mean(c[-5:]), np.mean(c[-10:]), np.mean(c[-20:]), np.mean(c[-60:])]
        mean_ma = np.mean(mas)
        if mean_ma == 0: return 0
        disp = np.std(mas) / mean_ma
        return 3 if disp < 0.03 else (2 if disp < 0.05 else 0)

    def _check_pattern_convergence(self, df):
        if len(df) < 60: return 0
        c = df['close'].values
        r = np.std(c[-20:] / np.mean(c[-20:]))
        o = np.std(c[-60:-20] / np.mean(c[-60:-20])) if len(c) >= 60 else r
        ratio = r / o if o > 0 else 1
        return 3 if ratio < 0.5 else (2 if ratio < 0.7 else 0)

    def _check_higher_low(self, df):
        if len(df) < 60: return 0
        low = df['low'].values
        lows = []
        for i in range(-30, 0):
            if -len(low) < i < -1 and low[i] < low[i-1] and low[i] < low[i+1]:
                lows.append((i, low[i]))
        if len(lows) >= 3:
            l3 = lows[-3:]
            if l3[1][1] > l3[0][1] and l3[2][1] > l3[1][1]:
                return 2
        return 0

    def _check_low_position(self, df):
        if len(df) < 120: return 0
        c = df['close'].values
        mn, mx = np.min(c[-120:]), np.max(c[-120:])
        pos = (c[-1] - mn) / (mx - mn) if mx > mn else 0.5
        return 1 if pos < 0.3 else 0

    def detect(self, df):
        if df is None or len(df) < 60:
            return None
        score = 0
        signals = []
        for name, fn in [
            ("地量", self._check_extreme_volume),
            ("均线粘合", self._check_ma_convergence),
            ("形态收敛", self._check_pattern_convergence),
            ("低点抬高", self._check_higher_low),
            ("低位", self._check_low_position),
        ]:
            v = fn(df)
            if v > 0:
                score += v
                signals.append(name)
        return {
            '是否主升前夕': score >= 5,
            '评分': score,
            '信号数量': len(signals),
            '信号列表': signals,
        }



# ============================================================
# 日志管理器
# ============================================================
class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


class LogManager:
    """
    实时监控日志管理器

    - segment: 'hourly' / 'daily' / 'weekly' / 'monthly'
    - filename_template: 例如 "{date}_{hour}.csv"
        可用占位符: {date} {time} {datetime} {year} {month} {day}
                    {hour} {minute} {week} {segment} {code} {name}
    - retention_days: 超过 N 天自动删除（0 或 None = 不限）
    - retention_files: 最多保留 N 个文件（0 或 None = 不限）
    - flush_every_seconds: 每个文件最多写多少秒后轮转（与 segment 无关，仅用于强制轮转）
      实际未使用，保留扩展
    """

    DEFAULT_COLUMNS = [
        ('时间',       'time'),
        ('代码',       'code'),
        ('名称',       'name'),
        ('现价',       'price'),
        ('涨跌幅%',    'chg_pct'),
        ('技术评分',   'score'),
        ('操作建议',   'action'),
        ('浮盈%',      'profit_pct'),
        ('MA5',        'ma5'),
        ('MA10',       'ma10'),
        ('MA20',       'ma20'),
        ('MA60',       'ma60'),
        ('MACD_DIF',   'dif'),
        ('MACD_DEA',   'dea'),
        ('MACD',       'macd'),
        ('KDJ_K',      'k'),
        ('KDJ_D',      'd'),
        ('KDJ_J',      'j'),
        ('RSI',        'rsi'),
        ('量比',       'vol_ratio'),
        ('120日位置%', 'position_120'),
        ('均线形态',   'ma_state'),
        ('MACD信号',   'macd_signal'),
        ('KDJ信号',    'kdj_signal'),
        ('依据',       'reasons_str'),
    ]

    CONFIG_PATH = "log_config.json"

    def __init__(self, log_dir="logs", filename_template="{date}_{hour}.csv",
                 segment="hourly", retention_days=7, retention_files=50):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.filename_template = filename_template
        self.segment = segment
        self.retention_days = retention_days
        self.retention_files = retention_files
        self._current_segment = None
        self._current_file = None

    # ---------------- 配置持久化 ----------------
    def save_config(self):
        cfg = {
            'log_dir': str(self.log_dir),
            'filename_template': self.filename_template,
            'segment': self.segment,
            'retention_days': self.retention_days,
            'retention_files': self.retention_files,
        }
        with open(self.CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_config(cls):
        if os.path.exists(cls.CONFIG_PATH):
            try:
                with open(cls.CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                return cls(**cfg)
            except Exception:
                pass
        return cls()

    # ---------------- 时间段计算 ----------------
    def _segment_key(self, now: datetime):
        if self.segment == 'hourly':
            return now.strftime("%Y%m%d_%H")
        if self.segment == 'daily':
            return now.strftime("%Y%m%d")
        if self.segment == 'weekly':
            y, w, _ = now.isocalendar()
            return f"{y}W{w:02d}"
        if self.segment == 'monthly':
            return now.strftime("%Y%m")
        return now.strftime("%Y%m%d")

    def _build_filename(self, now: datetime, **extra):
        y, w, _ = now.isocalendar()
        mapping = {
            'date':     now.strftime("%Y%m%d"),
            'time':     now.strftime("%H%M%S"),
            'datetime': now.strftime("%Y%m%d_%H%M%S"),
            'year':     now.strftime("%Y"),
            'month':    now.strftime("%m"),
            'day':      now.strftime("%d"),
            'hour':     now.strftime("%H"),
            'minute':   now.strftime("%M"),
            'week':     f"{y}W{w:02d}",
            'segment':  self._segment_key(now),
        }
        mapping.update(extra)
        name = self.filename_template.format_map(_SafeDict(mapping))
        if not name.lower().endswith('.csv'):
            name += '.csv'
        return name

    # ---------------- 清理 ----------------
    def _cleanup(self):
        files = sorted(self.log_dir.glob("*.csv"),
                       key=lambda p: p.stat().st_mtime, reverse=True)

        # 按天数
        if self.retention_days and self.retention_days > 0:
            cutoff = time.time() - self.retention_days * 86400
            for f in files:
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                except Exception:
                    pass
            # 重新读取
            files = sorted(self.log_dir.glob("*.csv"),
                           key=lambda p: p.stat().st_mtime, reverse=True)

        # 按文件数
        if self.retention_files and self.retention_files > 0:
            for f in files[self.retention_files:]:
                try:
                    f.unlink()
                except Exception:
                    pass

    # ---------------- 写入 ----------------
    def write_records(self, records, **extra):
        """records: list[dict]，每个 dict 的 key 对应 DEFAULT_COLUMNS 的英文名"""
        if not records:
            return None

        now = datetime.now()
        seg = self._segment_key(now)

        # 段切换 -> 新文件
        if seg != self._current_segment:
            self._current_segment = seg
            self._current_file = self._build_filename(now, **extra)
            self._cleanup()   # 每次切段时清理一次

        path = self.log_dir / self._current_file
        need_header = (not path.exists()) or path.stat().st_size == 0

        fieldnames = [c[0] for c in self.DEFAULT_COLUMNS]
        with open(path, 'a', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            if need_header:
                w.writeheader()
            for rec in records:
                row = {cn: rec.get(en, '') for cn, en in self.DEFAULT_COLUMNS}
                w.writerow(row)

        return str(path)

    # ---------------- 结果转换 ----------------
    @staticmethod
    def to_record(result: dict):
        """把 analyze_one 返回的 result 转成日志行"""
        tech = result.get('tech', {})
        rt = result.get('realtime', {}) or {}
        chg_pct = ''
        if rt.get('preclose'):
            chg_pct = round((rt['price'] - rt['preclose']) / rt['preclose'] * 100, 2)

        ma_state = '多头' if tech.get('ma_bull') else ('空头' if tech.get('ma_bear') else '震荡')
        macd_sig = '金叉' if tech.get('macd_gold') else ('死叉' if tech.get('macd_dead') else '')
        kdj_sig = '金叉' if tech.get('kdj_gold') else ('死叉' if tech.get('kdj_dead') else '')

        return {
            'time':         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'code':         result.get('code', ''),
            'name':         result.get('name', ''),
            'price':        round(result.get('price', 0), 3),
            'chg_pct':      chg_pct,
            'score':        result.get('score', ''),
            'action':       result.get('action', ''),
            'profit_pct':   (round(result['profit_pct'], 2)
                             if result.get('profit_pct') is not None else ''),
            'ma5':          round(tech.get('ma5', 0), 3),
            'ma10':         round(tech.get('ma10', 0), 3),
            'ma20':         round(tech.get('ma20', 0), 3),
            'ma60':         round(tech.get('ma60', 0), 3),
            'dif':          round(tech.get('dif', 0), 4),
            'dea':          round(tech.get('dea', 0), 4),
            'macd':         round(tech.get('macd', 0), 4),
            'k':            round(tech.get('k', 0), 2),
            'd':            round(tech.get('d', 0), 2),
            'j':            round(tech.get('j', 0), 2),
            'rsi':          round(tech.get('rsi', 0), 2),
            'vol_ratio':    round(tech.get('vol_ratio', 0), 2),
            'position_120': round(tech.get('position_120', 0) * 100, 2),
            'ma_state':     ma_state,
            'macd_signal':  macd_sig,
            'kdj_signal':   kdj_sig,
            'reasons_str':  '; '.join(result.get('reasons', [])),
        }



# ============================================================
# 实时监控器
# ============================================================
class RealtimeMonitor:
    def __init__(self, analyzer, advisor, positions, log_manager=None):
        self.analyzer = analyzer
        self.advisor = advisor
        self.positions = positions
        self.log_manager = log_manager

    def analyze_one(self, code, use_realtime=True):
        name = self.analyzer.get_stock_name(code)
        df = self.analyzer.get_stock_history(code, days=250)
        if df is None or len(df) < 60:
            return None

        realtime = None
        if use_realtime:
            realtime = RealtimeQuote.fetch([code]).get(code)
            if realtime and realtime['price'] > 0:
                df.loc[df.index[-1], 'close'] = realtime['price']
                df.loc[df.index[-1], 'open'] = realtime['open'] or df['open'].iloc[-1]
                df.loc[df.index[-1], 'high'] = realtime['high'] or df['high'].iloc[-1]
                df.loc[df.index[-1], 'low'] = realtime['low'] or df['low'].iloc[-1]
                df.loc[df.index[-1], 'volume'] = realtime['volume'] or df['volume'].iloc[-1]

        tech = TechnicalAnalyzer().analyze(df)
        if tech is None:
            return None

        pos = self.positions.get(code)
        if pos:
            result = self.advisor.advise(
                code, name, tech,
                position_state='持仓',
                cost=pos['cost'],
                shares=pos['shares']
            )
        else:
            result = self.advisor.advise(code, name, tech, position_state='空仓')

        if realtime:
            result['realtime'] = realtime
        return result

    def monitor_loop(self, codes, interval=60, rounds=None):
        """实时监控 + 自动写日志"""
        round_count = 0
        try:
            while True:
                round_count += 1
                os.system('cls' if os.name == 'nt' else 'clear')
                print("=" * 78)
                print(f"📡 实时监控  第 {round_count} 轮  "
                      f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 78)

                log_records = []

                for code in codes:
                    r = self.analyze_one(code, use_realtime=True)
                    if not r:
                        print(f"❌ {code} 数据获取失败")
                        continue

                    rt = r.get('realtime', {})
                    chg = 0
                    if rt.get('preclose'):
                        chg = (rt['price'] - rt['preclose']) / rt['preclose'] * 100

                    print(f"\n【{r['code']}】{r['name']}   {r['price']:.2f}  ({chg:+.2f}%)")
                    print(f"  技术评分: {r['score']}  |  建议: {r['action']}")
                    if r['profit_pct'] is not None:
                        print(f"  持仓浮盈: {r['profit_pct']:+.2f}%")
                    print(f"  依据: {'; '.join(r['reasons'][:5])}")

                    # 收集日志行
                    if self.log_manager:
                        log_records.append(LogManager.to_record(r))

                # 写日志
                if self.log_manager and log_records:
                    saved = self.log_manager.write_records(log_records)
                    if saved:
                        print(f"\n📝 日志已写入: {saved}  (本轮 {len(log_records)} 条)")

                print("\n" + "-" * 78)
                print(f"⏱️  下一轮 {interval} 秒后刷新，按 Ctrl+C 退出监控")

                if rounds and round_count >= rounds:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n⏹️  已退出实时监控")

# ============================================================
# 扫描器（保留原版，简化）
# ============================================================
class AutoScanner:
    def __init__(self):
        self.analyzer = StockAnalyzer()
        self.detector = PreMainRiseDetector(self.analyzer)
        self.results = []

    def _filter_by_market(self, stocks, market):
        if not market or market == 'all':
            return stocks
        ms = [m.strip().lower() for m in market.split(',') if m.strip()]
        def match(c):
            if 'sh' in ms and c.startswith('6'): return True
            if 'sz' in ms and c.startswith('0'): return True
            if 'cyb' in ms and c.startswith('3'): return True
            if 'bj' in ms and c.startswith(('4', '8')): return True
            return False
        return [s for s in stocks if match(s['code'])]

    def scan_all_stocks(self, min_score=8, max_stocks=None, market='all'):
        print("\n📊 获取股票列表...")
        all_stocks = self.analyzer.get_all_stock_list()
        if not all_stocks:
            print("❌ 无法获取股票列表")
            return []
        all_stocks = self._filter_by_market(all_stocks, market)
        print(f"✅ 板块: {market}，共 {len(all_stocks)} 只")
        if max_stocks:
            all_stocks = all_stocks[:max_stocks]

        self.results = []
        total = len(all_stocks)
        for i, s in enumerate(all_stocks, 1):
            code, name = s['code'], s['name']
            print(f"  [{i}/{total}] {code} {name}...", end="", flush=True)
            df = self.analyzer.get_stock_history(code, days=250)
            if df is None or len(df) < 60:
                print(" 无数据")
                continue
            r = self.detector.detect(df)
            if r and r['是否主升前夕'] and r['评分'] >= min_score:
                self.results.append({
                    '代码': code, '名称': name,
                    '当前价': round(df['close'].iloc[-1], 2),
                    '评分': r['评分'],
                    '信号列表': r['信号列表'],
                })
                print(" ✅")
            else:
                print("")
            time.sleep(0.15)
        self.results.sort(key=lambda x: x['评分'], reverse=True)
        print(f"\n✅ 扫描完成，共 {len(self.results)} 只")
        return self.results

    def print_results(self, results=None):
        results = results if results is not None else self.results
        if not results:
            print("\n❌ 无结果")
            return
        print("\n" + "=" * 70)
        for i, s in enumerate(results, 1):
            print(f"{i}. 【{s['代码']}】{s['名称']}  价: {s['当前价']}  评分: {s['评分']}")
            print(f"   信号: {', '.join(s['信号列表'])}")

    def export_to_csv(self, filename=None):
        if not self.results:
            print("无结果可导出")
            return
        if filename is None:
            filename = f"主升前夕_{datetime.now().strftime('%Y%m%d')}.csv"
        pd.DataFrame(self.results).to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"✅ 已导出: {filename}")

    def filter_by_score(self, min_score=8):
        return [r for r in self.results if r['评分'] >= min_score]


# ============================================================
# 主程序
# ============================================================
def choose_market():
    print("\n请选择扫描板块：")
    print("  1. 全部A股   2. 沪市   3. 深市主板   4. 创业板   5. 北证   6. 自定义")
    c = input("选项 (1-6): ").strip()
    return {'1': 'all', '2': 'sh', '3': 'sz', '4': 'cyb', '5': 'bj'}.get(c) or (
        ','.join([p for p in input("组合(sh/sz/cyb/bj): ").strip().lower().split(',')
                  if p in {'sh', 'sz', 'cyb', 'bj'}]) or 'all'
        if c == '6' else None
    )


def print_single_analysis(r):
    """美化打印单只股票分析"""
    if not r:
        print("❌ 分析失败")
        return
    print("\n" + "=" * 78)
    print(f"📊 【{r['code']}】{r['name']}   现价: {r['price']:.2f}")
    print("=" * 78)

    rt = r.get('realtime')
    if rt and rt.get('preclose'):
        chg = (rt['price'] - rt['preclose']) / rt['preclose'] * 100
        print(f"实时: {rt['price']:.2f}  涨跌: {chg:+.2f}%   "
              f"今开: {rt['open']:.2f}  最高: {rt['high']:.2f}  最低: {rt['low']:.2f}")
        print(f"时间: {rt['date']} {rt['time']}")

    t = r['tech']
    print(f"\n📈 均线: MA5={t['ma5']:.2f}  MA10={t['ma10']:.2f}  "
          f"MA20={t['ma20']:.2f}  MA60={t['ma60']:.2f}")
    print(f"   {'多头排列' if t['ma_bull'] else ('空头排列' if t['ma_bear'] else '震荡')}")

    print(f"📉 MACD: DIF={t['dif']:.3f}  DEA={t['dea']:.3f}  MACD={t['macd']:.3f}"
          f"   {'金叉' if t['macd_gold'] else ('死叉' if t['macd_dead'] else '')}")
    print(f"📊 KDJ: K={t['k']:.2f}  D={t['d']:.2f}  J={t['j']:.2f}"
          f"   {'金叉' if t['kdj_gold'] else ('死叉' if t['kdj_dead'] else '')}")
    print(f"📐 RSI: {t['rsi']:.2f}")
    print(f"🎯 BOLL: 上轨={t['boll_up']:.2f}  中轨={t['boll_mid']:.2f}  下轨={t['boll_low']:.2f}")
    print(f"📦 量比: {t['vol_ratio']:.2f}")
    print(f"📍 120日位置: {t['position_120']*100:.1f}%")

    print(f"\n🎯 技术评分: {r['score']}  |  【建议操作: {r['action']}】")
    if r['profit_pct'] is not None:
        print(f"💼 持仓浮盈: {r['profit_pct']:+.2f}%")
    print("\n📌 依据:")
    for reason in r['reasons']:
        print(f"   · {reason}")


def log_settings_menu(log_manager: LogManager):
    """日志配置菜单"""
    while True:
        print("\n" + "=" * 70)
        print("📝 日志设置")
        print("=" * 70)
        print(f"  1. 日志目录       : {log_manager.log_dir}")
        print(f"  2. 文件名模板     : {log_manager.filename_template}")
        print(f"  3. 时间段划分     : {log_manager.segment}")
        print(f"      (hourly=每小时 / daily=每天 / weekly=每周 / monthly=每月)")
        print(f"  4. 留存天数       : {log_manager.retention_days} 天 (0=不限)")
        print(f"  5. 最多保留文件数 : {log_manager.retention_files} 个 (0=不限)")
        print(f"  6. 查看当前日志文件列表")
        print(f"  7. 立即清理一次超期日志")
        print(f"  8. 保存并返回")
        print("=" * 70)

        c = input("请选择 (1-8): ").strip()

        if c == '1':
            d = input("新日志目录（回车保持）: ").strip()
            if d:
                log_manager.log_dir = Path(d)
                log_manager.log_dir.mkdir(parents=True, exist_ok=True)
        elif c == '2':
            print("可用占位符: {date} {time} {datetime} {year} {month} {day} "
                  "{hour} {minute} {week} {segment} {code} {name}")
            print("示例: {date}_{hour}.csv -> 20250921_14.csv")
            print("      {year}{month}{day}_{segment}.csv -> 20250921_20250921_14.csv")
            t = input("新模板（回车保持）: ").strip()
            if t:
                log_manager.filename_template = t
        elif c == '3':
            s = input("选择 hourly/daily/weekly/monthly: ").strip().lower()
            if s in ('hourly', 'daily', 'weekly', 'monthly'):
                log_manager.segment = s
            else:
                print("⚠️ 无效，保持原值")
        elif c == '4':
            n = input("留存天数（0 表示不限）: ").strip()
            if n.isdigit():
                log_manager.retention_days = int(n)
        elif c == '5':
            n = input("最多保留文件数（0 表示不限）: ").strip()
            if n.isdigit():
                log_manager.retention_files = int(n)
        elif c == '6':
            files = sorted(log_manager.log_dir.glob("*.csv"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            if not files:
                print("📂 无日志文件")
            else:
                print(f"\n📂 {log_manager.log_dir} 下共 {len(files)} 个日志文件：")
                for f in files[:30]:
                    kb = f.stat().st_size / 1024
                    mt = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    print(f"  {f.name:40s}  {kb:8.1f} KB  {mt}")
                if len(files) > 30:
                    print(f"  ... 还有 {len(files)-30} 个")
        elif c == '7':
            before = len(list(log_manager.log_dir.glob("*.csv")))
            log_manager._cleanup()
            after = len(list(log_manager.log_dir.glob("*.csv")))
            print(f"🧹 清理完成：{before} -> {after} 个文件")
        elif c == '8':
            log_manager.save_config()
            print("✅ 已保存到 log_config.json")
            return


def main():
    analyzer = StockAnalyzer()
    advisor = StockAdvisor()
    positions = PositionManager()

    log_manager = LogManager.load_config()                   #加载日志配置

    monitor = RealtimeMonitor(analyzer, advisor, positions)
    scanner = AutoScanner()

    try:
        while True:
            print("\n" + "=" * 78)
            print("🤖 主升前夕全自动扫描系统 v2（实时增强版）")
            print("=" * 78)
            print("1. 🔍 全市场扫描（日线，慢）")
            print("2. 📊 自定义股票池扫描")
            print("3. 📈 单只股票实时技术面研判")
            print("4. 📡 实时监控（多只循环刷新，自动写日志）")
            print("5. 💼 持仓管理")
            print("6. 📋 查看持仓 + 实时建议")
            print("7. 💾 导出上次扫描结果")
            print("8. 📝 日志设置")
            print("9. ❌ 退出")
            print("=" * 78)

            choice = input("\n请选择 (1-9): ").strip()

            if choice == '9':
                break

            elif choice == '1':
                market = choose_market()
                if market is None:
                    continue
                test = input("测试模式(仅100只)? (y/n): ").strip().lower()
                max_n = 100 if test == 'y' else None
                s = input("最低评分(默认8): ").strip()
                min_score = int(s) if s.isdigit() else 8
                scanner.scan_all_stocks(min_score=min_score, max_stocks=max_n, market=market)
                scanner.print_results()

            elif choice == '2':
                codes = [x.strip() for x in
                         input("输入代码(逗号分隔): ").strip().split(',') if x.strip().isdigit()]
                if not codes:
                    print("❌ 无有效代码")
                    continue
                s = input("最低评分(默认8): ").strip()
                min_score = int(s) if s.isdigit() else 8
                # 复用 scanner 接口
                results = []
                total = len(codes)
                for i, c in enumerate(codes, 1):
                    print(f"  [{i}/{total}] {c}...", end="", flush=True)
                    name = analyzer.get_stock_name(c)
                    df = analyzer.get_stock_history(c, days=250)
                    if df is None or len(df) < 60:
                        print(" 无数据"); continue
                    r = scanner.detector.detect(df)
                    if r and r['是否主升前夕'] and r['评分'] >= min_score:
                        results.append({
                            '代码': c, '名称': name,
                            '当前价': round(df['close'].iloc[-1], 2),
                            '评分': r['评分'], '信号列表': r['信号列表'],
                        })
                        print(" ✅")
                    else:
                        print("")
                    time.sleep(0.15)
                scanner.results = sorted(results, key=lambda x: x['评分'], reverse=True)
                scanner.print_results()

            elif choice == '3':
                code = input("请输入股票代码: ").strip()
                if not code.isdigit():
                    print("❌ 无效代码")
                    continue
                print(f"\n🔍 正在分析 {code} ...")
                r = monitor.analyze_one(code, use_realtime=True)
                print_single_analysis(r)

            elif choice == '4':
                codes_raw = input("输入监控代码(逗号分隔): ").strip()
                codes = [x.strip() for x in codes_raw.split(',') if x.strip().isdigit()]
                if not codes:
                    print("❌ 无有效代码")
                    continue
                s = input("刷新间隔秒数(默认60): ").strip()
                interval = int(s) if s.isdigit() else 60
                print(f"\n📡 开始监控 {codes}，每 {interval} 秒刷新，Ctrl+C 退出")
                time.sleep(1)
                monitor.monitor_loop(codes, interval=interval)

            elif choice == '5':
                print("\n当前持仓:")
                for c, p in positions.list_all().items():
                    print(f"  {c} {p.get('name','')}: 成本{p['cost']} × {p['shares']}股")
                print("\n操作: 1=添加/修改  2=删除  3=返回")
                op = input("选择: ").strip()
                if op == '1':
                    code = input("代码: ").strip()
                    if not code.isdigit():
                        print("❌ 无效")
                        continue
                    try:
                        cost = float(input("成本价: ").strip())
                        shares = int(input("股数: ").strip())
                    except ValueError:
                        print("❌ 输入错误")
                        continue
                    name = analyzer.get_stock_name(code)
                    positions.set_position(code, cost, shares, name)
                    print(f"✅ 已记录 {code} {name}")
                elif op == '2':
                    code = input("要删除的代码: ").strip()
                    positions.remove(code)
                    print("✅ 已删除")

            elif choice == '6':
                pos = positions.list_all()
                if not pos:
                    print("❌ 当前无持仓")
                    continue
                print(f"\n💼 共 {len(pos)} 只持仓，正在获取实时建议...")
                for code, p in pos.items():
                    r = monitor.analyze_one(code, use_realtime=True)
                    if r:
                        print(f"\n【{code}】{p.get('name','')}  "
                              f"成本{p['cost']}  现价{r['price']:.2f}  "
                              f"浮盈{r['profit_pct']:+.2f}%")
                        print(f"  评分:{r['score']}  建议:{r['action']}")

            elif choice == '7':
                scanner.export_to_csv()

            elif choice == '8':
                log_settings_menu(log_manager)

            else:
                print("无效选择")
    finally:
        analyzer._logout()

def log_settings_menu(log_manager: LogManager):
    """日志配置菜单"""
    while True:
        print("\n" + "=" * 70)
        print("📝 日志设置")
        print("=" * 70)
        print(f"  1. 日志目录       : {log_manager.log_dir}")
        print(f"  2. 文件名模板     : {log_manager.filename_template}")
        print(f"  3. 时间段划分     : {log_manager.segment}")
        print(f"      (hourly=每小时 / daily=每天 / weekly=每周 / monthly=每月)")
        print(f"  4. 留存天数       : {log_manager.retention_days} 天 (0=不限)")
        print(f"  5. 最多保留文件数 : {log_manager.retention_files} 个 (0=不限)")
        print(f"  6. 查看当前日志文件列表")
        print(f"  7. 立即清理一次超期日志")
        print(f"  8. 保存并返回")
        print("=" * 70)

        c = input("请选择 (1-8): ").strip()

        if c == '1':
            d = input("新日志目录（回车保持）: ").strip()
            if d:
                log_manager.log_dir = Path(d)
                log_manager.log_dir.mkdir(parents=True, exist_ok=True)
        elif c == '2':
            print("可用占位符: {date} {time} {datetime} {year} {month} {day} "
                  "{hour} {minute} {week} {segment} {code} {name}")
            print("示例: {date}_{hour}.csv -> 20250921_14.csv")
            print("      {year}{month}{day}_{segment}.csv -> 20250921_20250921_14.csv")
            t = input("新模板（回车保持）: ").strip()
            if t:
                log_manager.filename_template = t
        elif c == '3':
            s = input("选择 hourly/daily/weekly/monthly: ").strip().lower()
            if s in ('hourly', 'daily', 'weekly', 'monthly'):
                log_manager.segment = s
            else:
                print("⚠️ 无效，保持原值")
        elif c == '4':
            n = input("留存天数（0 表示不限）: ").strip()
            if n.isdigit():
                log_manager.retention_days = int(n)
        elif c == '5':
            n = input("最多保留文件数（0 表示不限）: ").strip()
            if n.isdigit():
                log_manager.retention_files = int(n)
        elif c == '6':
            files = sorted(log_manager.log_dir.glob("*.csv"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            if not files:
                print("📂 无日志文件")
            else:
                print(f"\n📂 {log_manager.log_dir} 下共 {len(files)} 个日志文件：")
                for f in files[:30]:
                    kb = f.stat().st_size / 1024
                    mt = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    print(f"  {f.name:40s}  {kb:8.1f} KB  {mt}")
                if len(files) > 30:
                    print(f"  ... 还有 {len(files)-30} 个")
        elif c == '7':
            before = len(list(log_manager.log_dir.glob("*.csv")))
            log_manager._cleanup()
            after = len(list(log_manager.log_dir.glob("*.csv")))
            print(f"🧹 清理完成：{before} -> {after} 个文件")
        elif c == '8':
            log_manager.save_config()
            print("✅ 已保存到 log_config.json")
            return




if __name__ == "__main__":
    main()