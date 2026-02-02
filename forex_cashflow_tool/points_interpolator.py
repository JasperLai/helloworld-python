"""
远期点插值模块
根据期限表插值计算远期点数
"""
import csv
import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple


class PointsInterpolator:
    """
    远期点插值器，用于根据起息日和到期日插值计算远期点数
    """
    
    def __init__(self, points_file: str):
        """
        初始化插值器
        
        Args:
            points_file: 远期点报表文件路径
        """
        self.points_data = {}
        self.spot_rates = {}  # 存储即期汇率
        self._load_points_data(points_file)
    
    def _load_points_data(self, points_file: str):
        """
        加载远期点数据
        
        Args:
            points_file: 远期点报表文件路径
        """
        with open(points_file, 'r', encoding='utf-8-sig') as f:
            content = f.read().strip()
        
        sections = content.split('\n\n')
        
        for section in sections:
            lines = section.strip().split('\n')
            if not lines:
                continue
                
            # 第一行是货币对
            pair = lines[0].strip()
            if len(lines) <= 1:
                continue
            
            # 解析后续行
            reader = csv.DictReader(lines[1:])
            tenor_data = []
            
            for row in reader:
                if 'Tenor' in row and 'SettlementDate' in row:
                    tenor = row['Tenor'].strip()
                    settlement_date_str = row['SettlementDate'].strip()
                    
                    # 尝试解析结算日期
                    try:
                        settlement_date = datetime.datetime.strptime(settlement_date_str, '%Y/%m/%d').date()
                    except ValueError:
                        try:
                            settlement_date = datetime.datetime.strptime(settlement_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            continue
                    
                    # 提取点数
                    bid_points = self._safe_parse_decimal(row.get('BidPoints', ''))
                    ask_points = self._safe_parse_decimal(row.get('AskPoints', ''))
                    bid_outright = self._safe_parse_decimal(row.get('BidOutright', ''))
                    ask_outright = self._safe_parse_decimal(row.get('AskOutright', ''))
                    
                    tenor_data.append({
                        'tenor': tenor,
                        'settlement_date': settlement_date,
                        'bid_points': bid_points,
                        'ask_points': ask_points,
                        'bid_outright': bid_outright,
                        'ask_outright': ask_outright
                    })
                    
                    # 如果是即期(Spot)，存储即期汇率
                    if tenor == 'SP':
                        # 使用中间价作为即期汇率
                        if bid_outright and ask_outright:
                            spot_rate = (bid_outright + ask_outright) / 2
                            self.spot_rates[pair] = spot_rate
            
            if tenor_data:
                self.points_data[pair] = sorted(tenor_data, key=lambda x: x['settlement_date'])
    
    def _safe_parse_decimal(self, s: str) -> Optional[Decimal]:
        """
        安全解析字符串为Decimal
        
        Args:
            s: 字符串
            
        Returns:
            Decimal对象或None
        """
        if not s or s.strip() == '':
            return None
        try:
            return Decimal(s.strip())
        except:
            return None
    
    def interpolate_points(self, pair: str, start_date: datetime.date, 
                          end_date: datetime.date) -> Optional[Decimal]:
        """
        根据起息日和到期日插值计算远期点数
        
        Args:
            pair: 货币对
            start_date: 起息日
            end_date: 到期日
            
        Returns:
            插值计算的远期点数，如果无法计算则返回None
        """
        if pair not in self.points_data:
            return None
        
        tenor_data = self.points_data[pair]
        
        # 找到最接近的两个点进行线性插值
        relevant_data = [td for td in tenor_data if td['settlement_date'] >= start_date]
        
        if not relevant_data:
            return None
        
        # 按日期排序
        relevant_data.sort(key=lambda x: x['settlement_date'])
        
        # 如果到期日在第一个点之前，使用最近的点
        if end_date <= relevant_data[0]['settlement_date']:
            return relevant_data[0]['bid_points'] or relevant_data[0]['ask_points']
        
        # 如果到期日在最后一个点之后，使用最后的点
        if end_date >= relevant_data[-1]['settlement_date']:
            return relevant_data[-1]['bid_points'] or relevant_data[-1]['ask_points']
        
        # 找到相邻的两个点进行线性插值
        for i in range(len(relevant_data) - 1):
            if relevant_data[i]['settlement_date'] <= end_date <= relevant_data[i+1]['settlement_date']:
                d1 = relevant_data[i]['settlement_date']
                d2 = relevant_data[i+1]['settlement_date']
                p1 = relevant_data[i]['bid_points'] or relevant_data[i]['ask_points']
                p2 = relevant_data[i+1]['bid_points'] or relevant_data[i+1]['ask_points']
                
                if p1 is None or p2 is None:
                    continue
                
                # 计算时间权重
                total_days = (d2 - d1).days
                if total_days == 0:
                    return p1
                
                elapsed_days = (end_date - d1).days
                weight = Decimal(elapsed_days) / Decimal(total_days)
                
                interpolated_points = p1 + (p2 - p1) * weight
                return interpolated_points
        
        return None
    
    def get_spot_rate(self, pair: str) -> Optional[Decimal]:
        """
        获取即期汇率
        
        Args:
            pair: 货币对
            
        Returns:
            即期汇率，如果不存在则返回None
        """
        return self.spot_rates.get(pair)


def parse_tenor_to_days(tenor: str) -> int:
    """
    将期限标识转换为天数
    
    Args:
        tenor: 期限标识 (如 '1D', '1W', '1M', '1Y')
        
    Returns:
        对应的天数
    """
    # 简化的期限转换，实际应用中可能需要更复杂的逻辑
    if tenor == 'ON':
        return 1
    elif tenor == 'TN':
        return 2
    elif tenor == 'SP':
        return 2  # 即期通常为T+2
    elif tenor == 'SN':
        return 3
    elif tenor.endswith('D'):
        return int(tenor[:-1])
    elif tenor.endswith('W'):
        return int(tenor[:-1]) * 7
    elif tenor.endswith('M'):
        return int(tenor[:-1]) * 30  # 简化计算
    elif tenor.endswith('Y'):
        return int(tenor[:-1]) * 365
    else:
        # 默认返回30天
        return 30