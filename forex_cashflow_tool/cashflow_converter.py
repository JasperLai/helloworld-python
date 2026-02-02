#!/usr/bin/env python3
"""
外汇交易现金流转换工具
根据需求文档实现从外汇交易明细数据中提取、计算并汇总现金流的功能
"""

import csv
import json
import argparse
import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from collections import defaultdict


def parse_decimal(s: str) -> Decimal:
    """解析字符串为Decimal对象，移除千分位逗号"""
    if not s:
        return Decimal('0')
    s = s.replace(',', '')
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


def parse_pair(pair: str) -> Tuple[str, str]:
    """解析货币对，格式: 货币1/货币2"""
    pair = pair.upper()
    if '/' in pair:
        ccy1, ccy2 = pair.split('/', 1)
        return ccy1.strip(), ccy2.strip()
    return pair[:3], pair[3:]


def is_jpy_base(pair: str) -> bool:
    """判断货币对是否以JPY为基础货币"""
    ccy1, _ = parse_pair(pair)
    return ccy1 == 'JPY'


def points_divisor_by_pair(pair: str) -> int:
    """根据货币对获取除数规则"""
    if is_jpy_base(pair):
        return 1000000
    return 10000


def normalize_cashflow(ccy: str, amt: Decimal) -> Decimal:
    """标准化现金流金额，JPY取整到个位，其他货币保持精度"""
    if ccy == 'JPY':
        return amt.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    else:
        return amt


class PointsInterpolator:
    """远期点插值器"""
    
    def __init__(self, points_csv_path: str):
        self.points_data = {}
        self.spot_rates = {}  # 存储即期汇率
        self._load_points_data(points_csv_path)
    
    def _load_points_data(self, points_csv_path: str):
        """加载远期点数据"""
        if not Path(points_csv_path).exists():
            return
        
        with open(points_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                currency_pair = row.get('EURUSD Tenor') or row.get('Currency Pair')
                if not currency_pair:
                    continue
                
                tenor = row.get('Tenor', '').strip()
                settlement_date = row.get('SettlementDate', '').strip()
                
                if tenor and settlement_date:
                    bid_points_str = row.get('BidPoints', '')
                    ask_points_str = row.get('AskPoints', '')
                    
                    # 存储远期点数据
                    if currency_pair not in self.points_data:
                        self.points_data[currency_pair] = {}
                    
                    # 对于即期，存储即期汇率
                    if tenor == 'SP':
                        bid_outright = row.get('BidOutright', '')
                        ask_outright = row.get('AskOutright', '')
                        if bid_outright:
                            self.spot_rates[f"{currency_pair}_bid"] = Decimal(bid_outright)
                        if ask_outright:
                            self.spot_rates[f"{currency_pair}_ask"] = Decimal(ask_outright)
                    
                    # 存储远期点
                    if bid_points_str:
                        self.points_data[currency_pair][tenor] = {
                            'bid': parse_decimal(bid_points_str),
                            'ask': parse_decimal(ask_points_str) if ask_points_str else parse_decimal(bid_points_str)
                        }
    
    def interpolate_points(self, currency_pair: str, target_date: datetime.date) -> Optional[Dict[str, Decimal]]:
        """根据目标日期插值计算远期点数"""
        if currency_pair not in self.points_data:
            return None
        
        # 简化插值逻辑，查找最接近的数据
        points_dict = self.points_data[currency_pair]
        
        # 按照标准期限映射日期差异
        standard_tenors = {
            'ON': 1,  # Overnight
            'TN': 2,  # Tomorrow Next
            'SP': 2,  # Spot (通常T+2)
            'SN': 3,  # Spot Next
            '1W': 7,  # 1 Week
            '2W': 14, # 2 Weeks
            '1M': 30, # 1 Month
            '2M': 60, # 2 Months
            '3M': 90, # 3 Months
            '6M': 180, # 6 Months
            '9M': 270, # 9 Months
            '1Y': 365, # 1 Year
            '2Y': 730, # 2 Years
            '3Y': 1095, # 3 Years
            '5Y': 1825  # 5 Years
        }
        
        # 这里简化处理，直接返回最近的数据点
        # 实际应用中需要更复杂的插值算法
        if 'SP' in points_dict:
            return points_dict['SP']
        
        # 返回第一个可用的点数
        for tenor, points in points_dict.items():
            return points
        
        return None


def load_filter_config(filter_config_path: str) -> Dict:
    """加载过滤配置文件"""
    if not Path(filter_config_path).exists():
        return {}
    
    with open(filter_config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def should_ignore_folder(folder: str, ignore_folders: List[str], filter_config: Dict) -> bool:
    """判断是否应该忽略某个文件夹"""
    # 优先使用命令行参数
    if ignore_folders and folder in ignore_folders:
        return True
    
    # 其次使用配置文件
    config_ignore = filter_config.get('ignore_folders', [])
    if isinstance(config_ignore, list) and folder in config_ignore:
        return True
    
    return False


def process_trade_detail(
    trade_detail_path: str,
    points_interpolator: Optional[PointsInterpolator],
    ignore_folders: List[str],
    filter_config: Dict
) -> List[Dict]:
    """处理交易明细文件，生成现金流"""
    cashflows = []
    trades = []
    
    with open(trade_detail_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
    
    for trade in trades:
        folder = trade.get('Folder', '').strip()
        if should_ignore_folder(folder, ignore_folders, filter_config):
            continue
        
        deal_id = trade.get('Deal Id', '').strip()
        deal_type = trade.get('Type of Deal', '').strip().lower()
        security = trade.get('Security', '').strip()
        amount1_str = trade.get('Amount1', '').strip()
        amount2_str = trade.get('Amount2', '').strip()
        value_date_str = trade.get('Value Date', '').strip()
        mat_date_str = trade.get('Mat. Date', '').strip()
        rate_price_str = trade.get('Rate/Price', '').strip()
        
        if not all([deal_id, deal_type, security, amount1_str, amount2_str, value_date_str]):
            continue
        
        amount1 = parse_decimal(amount1_str)
        amount2 = parse_decimal(amount2_str)
        value_date = parse_date_safe(value_date_str)
        mat_date = parse_date_safe(mat_date_str) if mat_date_str else None
        rate_price = parse_decimal(rate_price_str) if rate_price_str else None
        
        ccy1, ccy2 = parse_pair(security)
        
        if deal_type == 'spot':
            # Spot交易现金流
            cashflows.extend([
                {
                    'date': value_date,
                    'currency': ccy1,
                    'cashflow': normalize_cashflow(ccy1, amount1),
                    'deal_id': deal_id,
                    'type': 'Spot'
                },
                {
                    'date': value_date,
                    'currency': ccy2,
                    'cashflow': normalize_cashflow(ccy2, amount2),
                    'deal_id': deal_id,
                    'type': 'Spot'
                }
            ])
        
        elif deal_type == 'fx swap':
            # FX Swap交易现金流
            if not mat_date:
                print(f"Warning: FX Swap {deal_id} missing maturity date, skipping")
                continue
            
            # 近端现金流
            cashflows.extend([
                {
                    'date': value_date,
                    'currency': ccy1,
                    'cashflow': normalize_cashflow(ccy1, amount1),
                    'deal_id': deal_id,
                    'type': 'FX Swap Near'
                },
                {
                    'date': value_date,
                    'currency': ccy2,
                    'cashflow': normalize_cashflow(ccy2, amount2),
                    'deal_id': deal_id,
                    'type': 'FX Swap Near'
                }
            ])
            
            # 远端现金流
            # 远端汇率计算
            if points_interpolator and rate_price is not None:
                # 获取远期点插值
                interpolated_points = points_interpolator.interpolate_points(security, mat_date)
                if interpolated_points:
                    # 使用插值的点数计算远端汇率
                    curve_points = (interpolated_points['bid'] + interpolated_points['ask']) / 2
                    divisor = points_divisor_by_pair(security)
                    far_rate = rate_price + (curve_points / divisor)
                    far_amount2 = -amount1 * far_rate
                else:
                    # 回退到交易记录中的汇率
                    far_amount2 = -amount1 * rate_price
            else:
                # 没有远期点数据时，简单反向
                far_amount2 = -amount2
            
            cashflows.extend([
                {
                    'date': mat_date,
                    'currency': ccy1,
                    'cashflow': normalize_cashflow(ccy1, -amount1),
                    'deal_id': deal_id,
                    'type': 'FX Swap Far'
                },
                {
                    'date': mat_date,
                    'currency': ccy2,
                    'cashflow': normalize_cashflow(ccy2, far_amount2),
                    'deal_id': deal_id,
                    'type': 'FX Swap Far'
                }
            ])
        
        elif deal_type == 'outright forward':
            # Outright Forward交易现金流
            if not mat_date:
                print(f"Warning: Outright Forward {deal_id} missing maturity date, skipping")
                continue
            
            cashflows.extend([
                {
                    'date': mat_date,
                    'currency': ccy1,
                    'cashflow': normalize_cashflow(ccy1, amount1),
                    'deal_id': deal_id,
                    'type': 'Outright Forward'
                },
                {
                    'date': mat_date,
                    'currency': ccy2,
                    'cashflow': normalize_cashflow(ccy2, amount2),
                    'deal_id': deal_id,
                    'type': 'Outright Forward'
                }
            ])
    
    return cashflows


def calculate_pnl(cashflows: List[Dict], points_interpolator: Optional[PointsInterpolator]) -> Dict[str, Decimal]:
    """计算损益"""
    pnl_by_currency = defaultdict(Decimal)
    
    # 这里简化处理，实际应用中需要根据远期点插值来计算P&L
    for cf in cashflows:
        # P&L通常归因于计价货币(CCY2)
        # 由于我们在这里主要是生成现金流，P&L计算可以作为扩展功能
        pass
    
    return dict(pnl_by_currency)


def aggregate_cashflows(cashflows: List[Dict]) -> List[Dict]:
    """按日期和货币聚合现金流"""
    aggregated = defaultdict(Decimal)
    
    for cf in cashflows:
        key = (cf['date'], cf['currency'])
        aggregated[key] += cf['cashflow']
    
    result = []
    for (date, currency), total_cashflow in aggregated.items():
        result.append({
            'date': date,
            'currency': currency,
            'cashflow': normalize_cashflow(currency, total_cashflow)
        })
    
    # 按日期排序
    result.sort(key=lambda x: (x['date'], x['currency']))
    
    return result


def generate_html_report(cashflows: List[Dict], template_path: str, output_path: str):
    """生成HTML报告"""
    # 读取模板
    if Path(template_path).exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    else:
        # 创建默认模板
        template_content = """<!DOCTYPE html>
<html>
<head>
    <title>现金流报告</title>
    <style>
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>现金流报告</h1>
    <table>
        <thead>
            <tr>
                <th>日期</th>
                <th>货币</th>
                <th>现金流</th>
            </tr>
        </thead>
        <tbody>
            {{cashflows_table}}
        </tbody>
    </table>
</body>
</html>"""
    
    # 生成现金流表格行
    rows = []
    for cf in cashflows:
        rows.append(f"<tr><td>{cf['date']}</td><td>{cf['currency']}</td><td>{cf['cashflow']}</td></tr>")
    
    cashflows_table = "\n".join(rows)
    html_content = template_content.replace('{{cashflows_table}}', cashflows_table)
    
    # 写入输出文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def main():
    parser = argparse.ArgumentParser(description='外汇交易现金流转换工具')
    parser.add_argument('--input', required=True, help='交易明细 CSV 文件路径')
    parser.add_argument('--template', default='template.html', help='HTML 模板文件路径')
    parser.add_argument('--out_csv', default='cashflows_agg.csv', help='聚合现金流输出文件名')
    parser.add_argument('--out_html', default='cashflows.html', help='现金流 HTML 输出文件名')
    parser.add_argument('--template_summary', default='template_horizon_summary.html', help='期限汇总 HTML 模板')
    parser.add_argument('--out_html_summary', default='cashflows_horizon_summary.html', help='期限汇总 HTML 输出')
    parser.add_argument('--out_dir', default='generatedFile', help='输出目录')
    parser.add_argument('--ignore_folders', default='', help='忽略的文件夹列表（逗号分隔）')
    parser.add_argument('--filter_config', default='', help='过滤规则 JSON 文件')
    parser.add_argument('--points_csv', default='', help='远期点报表 CSV 路径')
    
    args = parser.parse_args()
    
    # 解析忽略文件夹列表
    ignore_folders = [f.strip() for f in args.ignore_folders.split(',') if f.strip()]
    
    # 加载过滤配置
    filter_config = {}
    if args.filter_config:
        filter_config = load_filter_config(args.filter_config)
    
    # 初始化远期点插值器
    points_interpolator = None
    if args.points_csv:
        points_interpolator = PointsInterpolator(args.points_csv)
    
    # 创建输出目录
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    
    # 处理交易明细
    cashflows = process_trade_detail(
        args.input,
        points_interpolator,
        ignore_folders,
        filter_config
    )
    
    # 聚合现金流
    aggregated_cashflows = aggregate_cashflows(cashflows)
    
    # 计算P&L
    pnl = calculate_pnl(cashflows, points_interpolator)
    
    # 保存聚合现金流到CSV
    csv_output_path = out_dir / args.out_csv
    with open(csv_output_path, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['Date', 'Currency', 'Cashflow']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cf in aggregated_cashflows:
            writer.writerow({
                'Date': cf['date'].strftime('%d/%m/%Y') if cf['date'] else '',
                'Currency': cf['currency'],
                'Cashflow': str(cf['cashflow'])
            })
    
    # 生成HTML报告
    html_output_path = out_dir / args.out_html
    generate_html_report(aggregated_cashflows, args.template, html_output_path)
    
    print(f"处理完成！")
    print(f"聚合现金流已保存至: {csv_output_path}")
    print(f"HTML报告已保存至: {html_output_path}")
    print(f"共处理 {len(cashflows)} 条现金流记录")
    print(f"聚合后剩余 {len(aggregated_cashflows)} 条记录")


if __name__ == '__main__':
    main()