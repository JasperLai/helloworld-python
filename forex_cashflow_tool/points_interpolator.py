"""
远期点插值模块
用于根据起息日和到期日查找匹配的期限，并使用线性插值计算中间期限的点值
"""

import csv
import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Tuple


def parse_decimal(s: str) -> Decimal:
    """解析字符串为Decimal对象"""
    if not s:
        return Decimal('0')
    s = str(s).replace(',', '')
    try:
        return Decimal(s)
    except:
        return Decimal('0')


def parse_date_safe(s: str) -> Optional[datetime.date]:
    """安全解析日期，格式: DD/MM/YYYY"""
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s, '%d/%m/%Y').date()
    except ValueError:
        return None


class PointsInterpolator:
    """远期点插值器"""
    
    def __init__(self, points_csv_path: str):
        self.points_data = {}
        self.spot_rates = {}  # 存储即期汇率
        self.tenor_days_map = self._get_tenor_days_map()
        self._load_points_data(points_csv_path)
    
    def _get_tenor_days_map(self) -> Dict[str, int]:
        """获取标准期限对应的天数映射"""
        return {
            'ON': 1,   # Overnight
            'TN': 2,   # Tomorrow Next
            'SP': 2,   # Spot (通常T+2)
            'SN': 3,   # Spot Next
            '1W': 7,   # 1 Week
            '2W': 14,  # 2 Weeks
            '1M': 30,  # 1 Month
            '2M': 60,  # 2 Months
            '3M': 90,  # 3 Months
            '6M': 180, # 6 Months
            '9M': 270, # 9 Months
            '1Y': 365, # 1 Year
            '2Y': 730, # 2 Years
            '3Y': 1095, # 3 Years
            '5Y': 1825 # 5 Years
        }
    
    def _load_points_data(self, points_csv_path: str):
        """加载远期点数据"""
        if not Path(points_csv_path).exists():
            print(f"警告: 远期点报表文件不存在: {points_csv_path}")
            return
        
        with open(points_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            # 尝试识别货币对列标题
            currency_pair_header = None
            for header in headers:
                if 'Tenor' in header and ' ' in header:
                    currency_pair_header = header
                    break
            
            for row in reader:
                # 获取货币对
                if currency_pair_header:
                    full_header = row.get(currency_pair_header, '').strip()
                    currency_pair = full_header.split(' Tenor')[0] if ' Tenor' in full_header else full_header
                else:
                    # 如果没有找到带Tenor的标题，则尝试从其他可能的字段获取
                    currency_pair = row.get('Currency Pair', '').strip() or row.get('Pair', '').strip()
                
                if not currency_pair:
                    continue
                
                tenor = row.get('Tenor', '').strip()
                settlement_date = row.get('SettlementDate', '').strip()
                
                if tenor:
                    # 初始化货币对数据结构
                    if currency_pair not in self.points_data:
                        self.points_data[currency_pair] = {}
                    
                    # 解析点数数据
                    bid_points_str = row.get('BidPoints', '')
                    ask_points_str = row.get('AskPoints', '')
                    bid_outright = row.get('BidOutright', '')
                    ask_outright = row.get('AskOutright', '')
                    
                    # 存储即期汇率
                    if tenor == 'SP' and (bid_outright or ask_outright):
                        if bid_outright:
                            self.spot_rates[f"{currency_pair}_bid"] = parse_decimal(bid_outright)
                        if ask_outright:
                            self.spot_rates[f"{currency_pair}_ask"] = parse_decimal(ask_outright)
                    
                    # 存储远期点
                    bid_points = parse_decimal(bid_points_str) if bid_points_str else None
                    ask_points = parse_decimal(ask_points_str) if ask_points_str else None
                    
                    if bid_points is not None or ask_points is not None:
                        # 如果只有一个点数，两个都用相同的值
                        if bid_points is None:
                            bid_points = ask_points
                        if ask_points is None:
                            ask_points = bid_points
                        
                        self.points_data[currency_pair][tenor] = {
                            'bid': bid_points,
                            'ask': ask_points,
                            'settlement_date': parse_date_safe(settlement_date) if settlement_date else None
                        }
    
    def get_points_by_tenor(self, currency_pair: str, tenor: str) -> Optional[Dict[str, Decimal]]:
        """根据货币对和期限获取点数"""
        if currency_pair not in self.points_data:
            return None
        
        if tenor not in self.points_data[currency_pair]:
            return None
        
        points_info = self.points_data[currency_pair][tenor]
        return {
            'bid': points_info['bid'],
            'ask': points_info['ask']
        }
    
    def interpolate_points_by_date(self, currency_pair: str, target_date: datetime.date) -> Optional[Dict[str, Decimal]]:
        """根据目标日期插值计算远期点数"""
        if currency_pair not in self.points_data:
            return None
        
        # 获取当前日期作为参考
        reference_date = datetime.date.today()
        
        # 计算目标日期与参考日期的天数差
        days_diff = (target_date - reference_date).days
        
        # 获取可用的期限和点数数据
        available_data = []
        for tenor, points_info in self.points_data[currency_pair].items():
            if tenor in self.tenor_days_map:
                days = self.tenor_days_map[tenor]
                available_data.append((days, points_info))
        
        if not available_data:
            return None
        
        # 按天数排序
        available_data.sort(key=lambda x: x[0])
        
        # 如果目标天数小于最小天数，使用最小天数的数据（外推）
        if days_diff <= available_data[0][0]:
            _, points_info = available_data[0]
            return {
                'bid': points_info['bid'],
                'ask': points_info['ask']
            }
        
        # 如果目标天数大于最大天数，使用最大天数的数据（外推）
        if days_diff >= available_data[-1][0]:
            _, points_info = available_data[-1]
            return {
                'bid': points_info['bid'],
                'ask': points_info['ask']
            }
        
        # 找到相邻的两个期限进行线性插值
        for i in range(len(available_data) - 1):
            low_days, low_points = available_data[i]
            high_days, high_points = available_data[i + 1]
            
            if low_days <= days_diff <= high_days:
                # 线性插值计算
                ratio = (days_diff - low_days) / (high_days - low_days)
                
                bid_interp = low_points['bid'] + (high_points['bid'] - low_points['bid']) * Decimal(str(ratio))
                ask_interp = low_points['ask'] + (high_points['ask'] - low_points['ask']) * Decimal(str(ratio))
                
                return {
                    'bid': bid_interp,
                    'ask': ask_interp
                }
        
        return None
    
    def interpolate_points_by_value_and_maturity_dates(
        self, 
        currency_pair: str, 
        value_date: datetime.date, 
        maturity_date: datetime.date
    ) -> Optional[Dict[str, Decimal]]:
        """根据起息日和到期日插值计算远期点数（用于FX Swap等）"""
        if currency_pair not in self.points_data:
            return None
        
        # 计算远期天数
        reference_date = datetime.date.today()
        value_days = (value_date - reference_date).days
        maturity_days = (maturity_date - reference_date).days
        
        # 分别插值近端和远端的点数
        near_points = self.interpolate_points_by_date(currency_pair, value_date)
        far_points = self.interpolate_points_by_date(currency_pair, maturity_date)
        
        # 返回远端点数（对于FX Swap，主要是远端的点数重要）
        return far_points
    
    def get_spot_rate(self, currency_pair: str) -> Optional[Dict[str, Decimal]]:
        """获取即期汇率"""
        bid_key = f"{currency_pair}_bid"
        ask_key = f"{currency_pair}_ask"
        
        spot_rate = {}
        if bid_key in self.spot_rates:
            spot_rate['bid'] = self.spot_rates[bid_key]
        if ask_key in self.spot_rates:
            spot_rate['ask'] = self.spot_rates[ask_key]
        
        return spot_rate if spot_rate else None


def test_interpolator():
    """测试函数"""
    # 这是一个测试函数，用于验证插值器的基本功能
    pass


if __name__ == "__main__":
    test_interpolator()