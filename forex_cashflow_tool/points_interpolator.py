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
        
        # 尝试按原有多部分格式解析
        sections = content.split('\n\n')
        
        # 检查是否为标准CSV格式（第一行包含列标题）
        first_line = content.split('\n')[0]
        if 'Tenor' in first_line and 'SettlementDate' in first_line:
            # 这是标准CSV格式，需要推断货币对
            self._parse_standard_csv(content)
        else:
            # 按原有多部分格式解析
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
    
    def _parse_standard_csv(self, content: str):
        """
        解析标准CSV格式的远期点数据
        
        Args:
            content: CSV内容
        """
        lines = content.strip().split('\n')
        
        # 检查第一行是否包含货币对信息
        header = lines[0]
        if 'EURUSD' in header or ('Tenor' in header and 'SettlementDate' in header):
            # 从列名中推断货币对，比如 "EURUSD Tenor" 可以提取出 EURUSD
            if 'EURUSD' in header:
                inferred_pair = 'EURUSD'
            elif 'USD' in header and '/' in header:
                # 如果标题中有类似 "USD/CAD Tenor" 的格式
                parts = header.split()
                if len(parts) > 0:
                    potential_pair = parts[0]
                    if '/' in potential_pair:
                        inferred_pair = potential_pair.replace('Tenor', '').strip()
                    else:
                        # 从完整标题中尝试提取货币对
                        for part in parts:
                            if '/' in part:
                                inferred_pair = part.replace('Tenor', '').strip()
                                break
                        else:
                            inferred_pair = 'UNKNOWN'
                else:
                    inferred_pair = 'UNKNOWN'
            else:
                # 尝试从数据中推断货币对
                inferred_pair = 'UNKNOWN'
            
            # 解析CSV内容
            reader = csv.DictReader(lines)
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
                            self.spot_rates[inferred_pair] = spot_rate
            
            if tenor_data:
                self.points_data[inferred_pair] = sorted(tenor_data, key=lambda x: x['settlement_date'])
    
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
        使用"Value Date -> 天数 -> 线性插值"方法
        
        Args:
            pair: 货币对
            start_date: 起息日 (Value Date)
            end_date: 到期日 (Mat Date)
            
        Returns:
            插值计算的远期点数，如果无法计算则返回None
        """
        if pair not in self.points_data:
            return None
        
        tenor_data = self.points_data[pair]
        
        # 计算目标天数，表示从 Value Date 到 Mat Date 的天数差
        target_days = (end_date - start_date).days
        
        # 构建天数-点数序列，基于报价的结算日期与 Value Date 的天数差
        series = []
        for td in tenor_data:
            # 计算每条报价的天数差，基于报价的结算日期与 Value Date
            q_days = (td['settlement_date'] - start_date).days
            # 只考虑结算日期晚于 Value Date 的报价，避免无效或负天数数据
            if q_days <= 0:
                continue
            # 计算 mid_points，作为 bid_points 和 ask_points 的平均值，减少买卖价差影响
            bid_points = td['bid_points']
            ask_points = td['ask_points']
            if bid_points is not None and ask_points is not None:
                mid = (bid_points + ask_points) / Decimal("2")
                # 将天数和对应 mid_points 组成元组，准备插值数据序列
                series.append((q_days, mid))
        
        if not series:
            return None
        
        # 按天数升序排列，便于后续查找插值区间
        series.sort(key=lambda x: x[0])
        
        # clamp 边界处理：
        # 如果目标天数小于最小报价天数，直接返回最小端点点数，避免外推
        if target_days <= series[0][0]:
            return series[0][1]
        
        # 如果目标天数大于最大报价天数，直接返回最大端点点数，避免外推
        if target_days >= series[-1][0]:
            return series[-1][1]
        
        # 线性插值计算：
        # 在相邻两个报价点之间，计算目标天数对应的点数
        # 插值公式：p = p0 + (p1 - p0) * w
        # 其中权重 w = (target_days - d0) / (d1 - d0)，表示目标天数在区间中的相对位置
        for (d0, p0), (d1, p1) in zip(series, series[1:]):
            if d0 <= target_days <= d1:
                if d1 == d0:  # 避免除零错误，若两个点天数相同则直接返回 p0
                    return p0
                w = Decimal(target_days - d0) / Decimal(d1 - d0)
                return p0 + (p1 - p0) * w
        
        # 若未能找到合适区间进行插值，返回None
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