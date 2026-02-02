"""
外汇交易现金流转换工具
根据需求文档实现完整的现金流转换功能
"""
import csv
import json
import argparse
import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from points_interpolator import PointsInterpolator


def parse_decimal(s: str) -> Decimal:
    """
    解析字符串为Decimal，移除千分位逗号
    
    Args:
        s: 输入字符串
        
    Returns:
        Decimal对象
    """
    if not s:
        return Decimal('0')
    # 移除千分位逗号
    cleaned = str(s).replace(',', '')
    try:
        return Decimal(cleaned)
    except:
        return Decimal('0')


def parse_date_safe(s: str) -> Optional[datetime.date]:
    """
    安全解析日期字符串
    
    Args:
        s: 日期字符串，格式为 DD/MM/YYYY
        
    Returns:
        日期对象或None
    """
    if not s:
        return None
    try:
        return datetime.datetime.strptime(str(s), '%d/%m/%Y').date()
    except ValueError:
        try:
            # 尝试其他可能的格式
            return datetime.datetime.strptime(str(s), '%Y-%m-%d').date()
        except ValueError:
            return None


def parse_pair(pair: str) -> Tuple[str, str]:
    """
    解析货币对字符串
    
    Args:
        pair: 货币对字符串，格式为 'CCY1/CCY2'
        
    Returns:
        (基础货币, 计价货币) 元组
    """
    if '/' in pair:
        parts = pair.split('/')
        if len(parts) >= 2:
            return parts[0].upper(), parts[1].upper()
    # 如果没有分隔符，尝试其他分割方式
    pair = pair.upper()
    if len(pair) == 6:
        return pair[:3], pair[3:]
    return pair, ''


def is_jpy_base(pair: str) -> bool:
    """
    判断货币对是否以JPY为基础货币
    
    Args:
        pair: 货币对字符串
        
    Returns:
        是否以JPY为基础货币
    """
    base_ccy, _ = parse_pair(pair)
    return base_ccy.startswith('JPY')


def points_divisor_by_pair(pair: str) -> int:
    """
    根据货币对确定除数
    
    Args:
        pair: 货币对字符串
        
    Returns:
        除数值
    """
    if is_jpy_base(pair):
        return 1000000  # JPY基准货币对
    else:
        return 10000    # 非JPY基准货币对


def normalize_cashflow(ccy: str, amt: Decimal) -> Decimal:
    """
    标准化现金流金额
    
    Args:
        ccy: 货币代码
        amt: 金额
        
    Returns:
        标准化后的金额
    """
    if ccy.upper() == 'JPY':
        # JPY金额取整到个位
        return amt.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    else:
        # 其他货币保持原有精度
        return amt


class CashFlowConverter:
    """
    外汇交易现金流转换器
    """
    
    def __init__(self, ignore_folders: List[str] = None, points_file: str = None):
        """
        初始化转换器
        
        Args:
            ignore_folders: 需要忽略的文件夹列表
            points_file: 远期点报表文件路径
        """
        self.ignore_folders = ignore_folders or []
        self.points_interpolator = None
        if points_file:
            try:
                self.points_interpolator = PointsInterpolator(points_file)
            except Exception as e:
                print(f"警告: 无法加载远期点报表 {points_file}: {e}")
    
    def load_filter_config(self, config_file: str) -> List[str]:
        """
        从配置文件加载过滤设置
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            忽略的文件夹列表
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            ignore_folders = config.get('ignore_folders', [])
            if not isinstance(ignore_folders, list):
                raise ValueError("ignore_folders must be a list")
            return ignore_folders
        except Exception as e:
            print(f"警告: 无法加载过滤配置 {config_file}: {e}")
            return []
    
    def calculate_pnl(self, deal_type: str, pair: str, amount1: Decimal, 
                     rate_price: Decimal, curve_points: Decimal) -> Tuple[str, Decimal]:
        """
        计算损益
        
        Args:
            deal_type: 交易类型
            pair: 货币对
            amount1: 标的货币金额
            rate_price: 交易记录中的汇率/点数
            curve_points: 曲线插值的远期点数
            
        Returns:
            (货币, 损益金额) 元组
        """
        if not curve_points or not rate_price:
            return '', Decimal('0')
        
        # 损益归属到计价货币
        _, quote_ccy = parse_pair(pair)
        
        # 计算损益：pnl = -amt1 × (curve_pts - pts) / divisor
        divisor = points_divisor_by_pair(pair)
        pnl = -amount1 * (curve_points - rate_price) / Decimal(divisor)
        
        return quote_ccy, pnl
    
    def process_trade_detail(self, input_file: str) -> List[Dict[str, Any]]:
        """
        处理交易明细文件
        
        Args:
            input_file: 交易明细文件路径
            
        Returns:
            现金流列表
        """
        cashflows = []
        pnls = {}
        
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # 过滤文件夹
                folder = row.get('Folder', '').strip()
                if folder in self.ignore_folders:
                    continue
                
                # 提取基本信息
                deal_id = row.get('Deal Id', '').strip()
                deal_type = row.get('Type of Deal', '').strip()
                security = row.get('Security', '').strip()
                
                if not all([deal_id, deal_type, security]):
                    continue
                
                # 解析金额
                amount1 = parse_decimal(row.get('Amount1', '0'))
                amount2 = parse_decimal(row.get('Amount2', '0'))
                
                # 解析日期
                trade_date = parse_date_safe(row.get('Trade Date', ''))
                value_date = parse_date_safe(row.get('Value Date', ''))
                mat_date = parse_date_safe(row.get('Mat. Date', ''))
                
                if not value_date:
                    continue  # 必须有起息日
                
                # 解析汇率/点数
                rate_price = parse_decimal(row.get('Rate/Price', '0'))
                
                # 解析货币对
                base_ccy, quote_ccy = parse_pair(security)
                
                # 根据交易类型生成现金流
                if deal_type.lower() == 'spot':
                    # Spot: 近端 (Value Date): Amount1 + Amount2
                    cashflows.extend([
                        {
                            'date': value_date,
                            'currency': base_ccy,
                            'amount': normalize_cashflow(base_ccy, amount1),
                            'deal_id': deal_id,
                            'type': 'spot'
                        },
                        {
                            'date': value_date,
                            'currency': quote_ccy,
                            'amount': normalize_cashflow(quote_ccy, amount2),
                            'deal_id': deal_id,
                            'type': 'spot'
                        }
                    ])
                
                elif deal_type.lower() == 'fx swap':
                    # FX Swap: 
                    # - 近端 (Value Date): Amount1 + Amount2
                    # - 远端 (Mat. Date): -Amount1 + (-Amount1 × far_rate)
                    
                    if not mat_date:
                        print(f"警告: FX Swap {deal_id} 缺少到期日")
                        continue
                    
                    if amount1 == 0:
                        print(f"警告: FX Swap {deal_id} 的Amount1为0")
                        continue
                    
                    # 近端现金流
                    cashflows.extend([
                        {
                            'date': value_date,
                            'currency': base_ccy,
                            'amount': normalize_cashflow(base_ccy, amount1),
                            'deal_id': deal_id,
                            'type': 'fx_swap_near'
                        },
                        {
                            'date': value_date,
                            'currency': quote_ccy,
                            'amount': normalize_cashflow(quote_ccy, amount2),
                            'deal_id': deal_id,
                            'type': 'fx_swap_near'
                        }
                    ])
                    
                    # 计算远端现金流
                    # 远端汇率计算: far_rate = near_rate + (points / divisor)
                    near_rate = amount2 / amount1 if amount1 != 0 else Decimal('0')
                    far_rate = near_rate
                    
                    # 尝试使用远期点插值计算远端汇率
                    if self.points_interpolator:
                        curve_points = self.points_interpolator.interpolate_points(
                            security, value_date, mat_date
                        )
                        
                        if curve_points is not None:
                            divisor = points_divisor_by_pair(security)
                            far_rate = near_rate + (curve_points / Decimal(divisor))
                            
                            # 计算P&L
                            quote_ccy_pnl, pnl_amount = self.calculate_pnl(
                                deal_type, security, amount1, rate_price, curve_points
                            )
                            if quote_ccy_pnl and pnl_amount:
                                if quote_ccy_pnl not in pnls:
                                    pnls[quote_ccy_pnl] = Decimal('0')
                                pnls[quote_ccy_pnl] += pnl_amount
                    
                    far_amount2 = -amount1 * far_rate
                    
                    # 远端现金流
                    cashflows.extend([
                        {
                            'date': mat_date,
                            'currency': base_ccy,
                            'amount': normalize_cashflow(base_ccy, -amount1),
                            'deal_id': deal_id,
                            'type': 'fx_swap_far'
                        },
                        {
                            'date': mat_date,
                            'currency': quote_ccy,
                            'amount': normalize_cashflow(quote_ccy, far_amount2),
                            'deal_id': deal_id,
                            'type': 'fx_swap_far'
                        }
                    ])
                
                elif deal_type.lower() == 'outright forward':
                    # Outright Forward: 远端 (Mat. Date): Amount1 + Amount2
                    if not mat_date:
                        print(f"警告: Outright Forward {deal_id} 缺少到期日")
                        continue
                    
                    cashflows.extend([
                        {
                            'date': mat_date,
                            'currency': base_ccy,
                            'amount': normalize_cashflow(base_ccy, amount1),
                            'deal_id': deal_id,
                            'type': 'outright_forward'
                        },
                        {
                            'date': mat_date,
                            'currency': quote_ccy,
                            'amount': normalize_cashflow(quote_ccy, amount2),
                            'deal_id': deal_id,
                            'type': 'outright_forward'
                        }
                    ])
                    
                    # 如果有远期点插值，则计算P&L
                    if self.points_interpolator:
                        curve_points = self.points_interpolator.interpolate_points(
                            security, value_date, mat_date
                        )
                        
                        if curve_points is not None:
                            quote_ccy_pnl, pnl_amount = self.calculate_pnl(
                                deal_type, security, amount1, rate_price, curve_points
                            )
                            if quote_ccy_pnl and pnl_amount:
                                if quote_ccy_pnl not in pnls:
                                    pnls[quote_ccy_pnl] = Decimal('0')
                                pnls[quote_ccy_pnl] += pnl_amount
        
        return cashflows, pnls
    
    def aggregate_cashflows(self, cashflows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        聚合现金流
        
        Args:
            cashflows: 现金流列表
            
        Returns:
            聚合后的现金流列表
        """
        aggregated = {}
        
        for cf in cashflows:
            date_key = cf['date']
            currency = cf['currency']
            key = (date_key, currency)
            
            if key not in aggregated:
                aggregated[key] = {
                    'date': date_key,
                    'currency': currency,
                    'amount': Decimal('0')
                }
            
            aggregated[key]['amount'] += cf['amount']
        
        result = list(aggregated.values())
        # 按日期和货币排序
        result.sort(key=lambda x: (x['date'], x['currency']))
        
        return result
    
    def generate_csv_report(self, cashflows: List[Dict[str, Any]], output_file: str):
        """
        生成CSV报告
        
        Args:
            cashflows: 聚合后的现金流列表
            output_file: 输出文件路径
        """
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Currency', 'Cashflow'])
            
            for cf in cashflows:
                writer.writerow([
                    cf['date'].strftime('%d/%m/%Y'),
                    cf['currency'],
                    float(cf['amount'])
                ])
    
    def generate_html_report(self, cashflows: List[Dict[str, Any]], pnls: Dict[str, Decimal],
                           template_file: str, output_file: str, fx_rates: Dict[str, Decimal] = None):
        """
        生成HTML报告
        
        Args:
            cashflows: 现金流列表
            pnls: P&L字典
            template_file: HTML模板文件
            output_file: 输出文件路径
            fx_rates: 即期汇率字典
        """
        if fx_rates is None:
            fx_rates = {}
        
        with open(template_file, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # 准备数据
        cashflow_rows = []
        for cf in cashflows:
            cashflow_rows.append(
                f'<tr><td>{cf["date"].strftime("%Y-%m-%d")}</td><td>{cf["currency"]}</td>'
                f'<td>{float(cf["amount"]):,.2f}</td></tr>'
            )
        
        cashflow_table = ''.join(cashflow_rows)
        
        # 准备P&L数据
        pnl_rows = []
        for currency, pnl in pnls.items():
            pnl_rows.append(
                f'<tr><td>{currency}</td><td>{float(pnl):,.2f}</td></tr>'
            )
        pnl_table = ''.join(pnl_rows) if pnl_rows else '<tr><td colspan="2">无P&L数据</td></tr>'
        
        # 准备即期汇率数据
        fx_rows = []
        for pair, rate in fx_rates.items():
            fx_rows.append(
                f'<tr><td>{pair}</td><td>{float(rate):.6f}</td></tr>'
            )
        fx_table = ''.join(fx_rows) if fx_rows else '<tr><td colspan="2">无即期汇率数据</td></tr>'
        
        # 替换模板中的占位符
        html_content = template_content.replace('{{CASHFLOW_TABLE}}', cashflow_table)
        html_content = html_content.replace('{{PNL_TABLE}}', pnl_table)
        html_content = html_content.replace('{{FX_RATES_TABLE}}', fx_table)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def generate_horizon_summary_html(self, cashflows: List[Dict[str, Any]], 
                                    pnls: Dict[str, Decimal], template_file: str, 
                                    output_file: str, fx_rates: Dict[str, Decimal] = None):
        """
        生成期限汇总HTML报告
        
        Args:
            cashflows: 现金流列表
            pnls: P&L字典
            template_file: HTML模板文件
            output_file: 输出文件路径
            fx_rates: 即期汇率字典
        """
        if fx_rates is None:
            fx_rates = {}
        
        with open(template_file, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # 按时间段分组现金流
        today = datetime.date.today()
        periods = {
            'Today': today,
            'Next 1W': today + datetime.timedelta(days=7),
            'Next 1M': today + datetime.timedelta(days=30),
            'Next 3M': today + datetime.timedelta(days=90),
            'Next 6M': today + datetime.timedelta(days=180),
            'Next 1Y': today + datetime.timedelta(days=365),
            'Beyond 1Y': None
        }
        
        period_totals = {}
        for period, end_date in periods.items():
            period_totals[period] = {}
        
        for cf in cashflows:
            cf_date = cf['date']
            cf_currency = cf['currency']
            cf_amount = cf['amount']
            
            # 确定时间段
            if cf_date <= today:
                period = 'Today'
            elif end_date and cf_date <= end_date:
                period = [k for k, v in periods.items() if v == end_date][0]
            else:
                period = 'Beyond 1Y'
            
            if cf_currency not in period_totals[period]:
                period_totals[period][cf_currency] = Decimal('0')
            period_totals[period][cf_currency] += cf_amount
        
        # 生成时间段汇总表格
        period_rows = []
        currencies = set()
        for period_currencies in period_totals.values():
            currencies.update(period_currencies.keys())
        currencies = sorted(list(currencies))
        
        period_rows.append('<tr><th>Period</th>')
        for currency in currencies:
            period_rows.append(f'<th>{currency}</th>')
        period_rows.append('</tr>\n')
        
        for period, totals in period_totals.items():
            period_rows.append('<tr>')
            period_rows.append(f'<td>{period}</td>')
            for currency in currencies:
                amount = totals.get(currency, Decimal('0'))
                period_rows.append(f'<td>{float(amount):,.2f}</td>')
            period_rows.append('</tr>\n')
        
        period_table = ''.join(period_rows)
        
        # 准备P&L数据
        pnl_items = [(currency, float(pnl)) for currency, pnl in pnls.items()]
        
        # 替换模板中的占位符
        html_content = template_content.replace('{{PERIOD_TABLE}}', period_table)
        html_content = html_content.replace('{{PNL_ITEMS}}', 
            ', '.join([f'["{cur}", {pnl}]' for cur, pnl in pnl_items]) if pnl_items else '[]')
        html_content = html_content.replace('{{FX_RATES}}', 
            str([[pair, float(rate)] for pair, rate in fx_rates.items()]) if fx_rates else '[]')
        
        with open(output_file, 'w', encoding='utf-8') as f:
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
    parser.add_argument('--ignore_folders', help='忽略的文件夹列表（逗号分隔）')
    parser.add_argument('--filter_config', help='过滤规则 JSON 文件')
    parser.add_argument('--points_csv', help='远期点报表 CSV 路径')
    
    args = parser.parse_args()
    
    # 解析忽略文件夹
    ignore_folders = []
    if args.filter_config:
        # 如果提供了配置文件，从中加载
        converter = CashFlowConverter()
        ignore_folders = converter.load_filter_config(args.filter_config)
    
    if args.ignore_folders:
        # 命令行参数优先级更高
        ignore_folders = [f.strip() for f in args.ignore_folders.split(',')]
    
    # 创建输出目录
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    
    # 初始化转换器
    converter = CashFlowConverter(ignore_folders, args.points_csv)
    
    # 处理交易明细
    cashflows, pnls = converter.process_trade_detail(args.input)
    
    # 聚合现金流
    aggregated_cashflows = converter.aggregate_cashflows(cashflows)
    
    # 获取即期汇率（如果有远期点插值器）
    fx_rates = {}
    if converter.points_interpolator:
        # 遍历所有货币对获取即期汇率
        for pair in converter.points_interpolator.spot_rates:
            rate = converter.points_interpolator.get_spot_rate(pair)
            if rate:
                fx_rates[pair] = rate
    
    # 生成输出文件路径
    csv_path = out_dir / args.out_csv
    html_path = out_dir / args.out_html
    html_summary_path = out_dir / args.out_html_summary
    
    # 生成报告
    converter.generate_csv_report(aggregated_cashflows, csv_path)
    converter.generate_html_report(aggregated_cashflows, pnls, args.template, html_path, fx_rates)
    converter.generate_horizon_summary_html(aggregated_cashflows, pnls, args.template_summary, 
                                          html_summary_path, fx_rates)
    
    print(f"处理完成！")
    print(f"聚合现金流CSV: {csv_path}")
    print(f"现金流HTML: {html_path}")
    print(f"期限汇总HTML: {html_summary_path}")
    print(f"处理了 {len(aggregated_cashflows)} 条聚合现金流记录")
    print(f"P&L统计: {dict((k, float(v)) for k, v in pnls.items())}")


if __name__ == '__main__':
    main()