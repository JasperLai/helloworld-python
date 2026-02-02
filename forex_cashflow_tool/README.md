# 外汇交易现金流转换工具

## 功能概述

本工具用于从外汇交易明细数据中提取、计算并汇总现金流，生成可用于风险分析和资金规划的现金流报告。支持多种外汇交易类型（Spot/FX Swap/Outright Forward），并可根据远期点表进行损益计算。

## 文件结构

```
forex_cashflow_tool/
├── cashflow_converter.py     # 主要转换工具
├── points_interpolator.py    # 远期点插值模块
├── template.html             # 基础HTML报告模板
├── template_horizon_summary.html  # 期限汇总HTML模板
├── sample_trade_detail.csv   # 示例交易明细数据
├── fwd_points_sample.csv     # 示例远期点数据
├── filter.json               # 过滤配置示例
└── README.md                 # 本说明文件
```

## 安装和运行

### 前提条件
- Python 3.7+

### 运行示例

```bash
# 基础用法
python cashflow_converter.py --input sample_trade_detail.csv

# 完整参数示例
python cashflow_converter.py \
  --input sample_trade_detail.csv \
  --points_csv fwd_points_sample.csv \
  --ignore_folders "JSH_SWPPOS,ZF-FXSWAP" \
  --filter_config filter.json \
  --out_dir generatedFile
```

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | 必填 | 交易明细 CSV 文件路径 |
| `--template` | `template.html` | HTML 模板文件路径 |
| `--out_csv` | `cashflows_agg.csv` | 聚合现金流输出文件名 |
| `--out_html` | `cashflows.html` | 现金流 HTML 输出文件名 |
| `--template_summary` | `template_horizon_summary.html` | 期限汇总 HTML 模板 |
| `--out_html_summary` | `cashflows_horizon_summary.html` | 期限汇总 HTML 输出 |
| `--out_dir` | `generatedFile` | 输出目录 |
| `--ignore_folders` | 空 | 忽略的文件夹列表（逗号分隔） |
| `--filter_config` | 空 | 过滤规则 JSON 文件 |
| `--points_csv` | 空 | 远期点报表 CSV 路径 |

## 输入数据格式

### 交易明细文件 (tradeDetail.csv)

| 字段名 | 必填 | 说明 |
|--------|------|------|
| Deal Id | ✅ | 交易唯一标识，格式: `VAL_IMP:数字` |
| Cpty. | ✅ | 交易对手方简称 |
| Type of Deal | ✅ | 交易类型：FX Swap / Spot / Outright Forward |
| Folder | ✅ | 交易组合/文件夹名称（用于过滤） |
| Security | ✅ | 货币对，格式：`货币1/货币2` |
| Amount1 | ✅ | 标的货币金额（可为负数） |
| Amount2 | ✅ | 计价货币金额（可为负数） |
| Trade Date | ✅ | 交易日期，格式：`DD/MM/YYYY` |
| Value Date | ✅ | 起息日/近端交割日，格式：`DD/MM/YYYY` |
| Mat. Date | | 远端到期日，格式：`DD/MM/YYYY` |

### 远期点报表文件 (fwd_points_sample.csv)

| 字段名 | 说明 |
|--------|------|
| `<货币对> Tenor` | 货币对名称，如 `EURUSD Tenor` |
| Tenor | 期限，如 `SP`, `1W`, `1M` 等 |
| SettlementDate | 结算日期 |
| BidPoints | 买入点数 |
| AskPoints | 卖出点数 |
| BidOutright | 买入 outright 汇率 |
| AskOutright | 卖出 outright 汇率 |

## 支持的交易类型

| 交易类型 | 英文标识 | 特征 |
|----------|----------|------|
| 即期交易 | Spot | 单时点、双货币 |
| 外汇掉期 | FX Swap | 双时点、双货币、金额相反 |
| 远期交易 | Outright Forward | 单时点（远端）、双货币 |

## 输出文件

- `cashflows_agg.csv` - 聚合现金流 CSV 文件
- `cashflows.html` - 现金流 HTML 报告
- `cashflows_horizon_summary.html` - 期限汇总 HTML 报告
- `generatedFile/` - 输出目录（默认）

## 使用示例

以下是如何使用该工具的示例：

```python
# 处理包含三种不同类型交易的文件
python cashflow_converter.py \
  --input dataSource/tradeDetail.csv \
  --points_csv dataSource/fwd_points_sample.csv \
  --ignore_folders "JSH_SWPPOS,ZF-FXSWAP" \
  --filter_config filter.json \
  --out_dir generatedFile
```

## 错误处理

工具会处理以下错误情况：
- 必需字段缺失
- 文件未找到
- 配置格式错误