# 外汇交易现金流转换工具

根据需求文档完全重新实现的外汇交易现金流转换工具，支持多种外汇交易类型（Spot/FX Swap/Outright Forward），并可根据远期点表进行损益计算。

## 项目结构

```
forex_cashflow_tool/
├── cashflow_converter.py      # 主要的现金流转换器
├── points_interpolator.py     # 远期点插值模块
├── template.html              # 基础现金流HTML模板
├── template_horizon_summary.html # 期限汇总HTML模板
├── sample_trade_detail.csv    # 示例交易明细数据
├── fwd_points_sample.csv      # 示例远期点数据
├── filter.json               # 过滤配置文件
├── README.md                 # 项目说明
└── requirements.txt          # 依赖声明
```

## 功能特性

- 支持 Spot、FX Swap、Outright Forward 三种交易类型的现金流计算
- 根据远期点表进行插值计算和损益计算
- 支持文件夹过滤功能
- 生成聚合现金流 CSV 报告
- 生成现金流 HTML 报告
- 生成期限汇总 HTML 报告

## 使用方法

### 安装依赖
```bash
pip install -r requirements.txt
```

### 基本使用
```bash
python cashflow_converter.py --input dataSource/tradeDetail.csv
```

### 完整参数示例
```bash
python cashflow_converter.py \
    --input dataSource/tradeDetail.csv \
    --points_csv dataSource/fwd_points_sample.csv \
    --ignore_folders "JSH_SWPPOS,ZF-FXSWAP" \
    --filter_config filter.json \
    --out_dir generatedFile
```

## 依赖库

- Python 3.x
- 标准库: `csv`, `json`, `argparse`, `datetime`, `decimal`, `pathlib`, `typing`

## 开发说明

该工具完全按照需求文档重新实现，具有以下特点：

1. 高精度数值计算（使用Decimal类型）
2. 模块化设计，易于维护
3. 完整的错误处理机制
4. 支持UTF-8 with BOM编码
5. 灵活的配置选项