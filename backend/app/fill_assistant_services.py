import io
from collections import defaultdict
from zipfile import BadZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .ad_services import _find, _has_column, _number, normalize_product_name, parse_plan_name, parse_upload


CAMPAIGN_REQUIRED_COLUMNS = {
    "plan_name": "广告计划名称",
    "spend": "成本",
    "orders": "SKU 订单数",
    "revenue": "总收入",
    "actual_roi": "ROI",
}


def _strict_number(row, key, label, row_number, *, integer=False):
    raw_value = _find(row, key)
    value = _number(raw_value, None)
    if value is None:
        raise ValueError(f"Excel 第 {row_number} 行{label}为空或不是数字")
    if value < 0:
        raise ValueError(f"Excel 第 {row_number} 行{label}不能为负数")
    if integer and not value.is_integer():
        raise ValueError(f"Excel 第 {row_number} 行{label}必须是整数")
    return int(value) if integer else value


def analyze_product_campaign(filename, content, target_settings, known_products=()):
    rows = parse_upload(filename, content)
    if not rows:
        raise ValueError("文件没有可计算的数据")
    missing = [label for key, label in CAMPAIGN_REQUIRED_COLUMNS.items() if not _has_column(rows[0], key)]
    if missing:
        raise ValueError(f"Excel 缺少必需列：{'、'.join(missing)}")

    configured_products = [setting.product_name for setting in target_settings]
    product_candidates = list(known_products) + configured_products
    target_map = {
        (setting.product_key, setting.strategy_code): float(setting.target_roi)
        for setting in target_settings
    }
    grouped = defaultdict(list)
    zero_cost_rows = 0

    for row_number, row in enumerate(rows, start=2):
        campaign_name = str(_find(row, "plan_name") or "").strip()
        if not campaign_name:
            raise ValueError(f"Excel 第 {row_number} 行广告计划名称为空")
        strategy_code, product_name = parse_plan_name(campaign_name, product_candidates)
        if not strategy_code or not product_name:
            raise ValueError(f"Excel 第 {row_number} 行广告计划名称无法识别：{campaign_name}")

        cost = _strict_number(row, "spend", "成本", row_number)
        orders = _strict_number(row, "orders", "SKU 订单数", row_number, integer=True)
        revenue = _strict_number(row, "revenue", "总收入", row_number)
        actual_roi = _strict_number(row, "actual_roi", "ROI", row_number)
        budget_raw = _find(row, "budget")
        current_budget = None
        if budget_raw is not None and str(budget_raw).strip() != "":
            current_budget = _strict_number(row, "budget", "Current budget", row_number)

        if cost == 0:
            zero_cost_rows += 1
            continue

        target_roi = target_map.get((normalize_product_name(product_name), strategy_code))
        payout_eligible = orders > 21
        payout_roi = target_roi * 0.9 if target_roi is not None else None
        if not payout_eligible:
            payout_amount = 0.0
            payout_status = "not_eligible"
        elif target_roi is None:
            payout_amount = None
            payout_status = "target_roi_pending"
        else:
            payout_amount = max(cost - revenue / payout_roi, 0.0)
            payout_status = "calculated"

        grouped[product_name].append({
            "row_number": row_number,
            "campaign_name": campaign_name,
            "strategy_code": strategy_code,
            "product_name": product_name,
            "cost": cost,
            "orders": orders,
            "revenue": revenue,
            "actual_roi": actual_roi,
            "current_budget": current_budget,
            "target_roi": target_roi,
            "payout_roi": payout_roi,
            "payout_amount": payout_amount,
            "payout_eligible": payout_eligible,
            "payout_status": payout_status,
        })

    products = []
    for product_name, details in grouped.items():
        missing_count = sum(item["payout_status"] == "target_roi_pending" for item in details)
        products.append({
            "product_name": product_name,
            "plan_count": len(details),
            "total_revenue": sum(item["revenue"] for item in details),
            "total_consumption": sum(item["cost"] for item in details),
            "estimated_payout": None if missing_count else sum(item["payout_amount"] or 0 for item in details),
            "missing_target_roi_count": missing_count,
            "details": details,
        })
    products.sort(key=lambda item: (-item["total_consumption"], item["product_name"]))
    details = [item for product in products for item in product["details"]]
    return {
        "filename": filename,
        "total_rows": len(rows),
        "zero_cost_rows": zero_cost_rows,
        "effective_rows": len(details),
        "product_count": len(products),
        "total_consumption": sum(item["cost"] for item in details),
        "payout_eligible_plans": sum(item["payout_eligible"] for item in details),
        "calculated_payout_plans": sum(item["payout_status"] == "calculated" for item in details),
        "missing_target_roi_plans": sum(item["payout_status"] == "target_roi_pending" for item in details),
        "products": products,
    }


def parse_payout_config(content):
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except (BadZipFile, OSError, ValueError) as exc:
        raise ValueError("赔付配置 Excel 文件无效或已损坏") from exc
    sheet = workbook.active
    if sheet.calculate_dimension() == "A1:A1":
        sheet.reset_dimensions()
    rows = list(sheet.iter_rows(values_only=True))
    header_index = None
    product_column = None
    target_column = None
    for index, row in enumerate(rows):
        normalized = [str(value or "").replace(" ", "").upper() for value in row]
        if "产品名称" in normalized and "目标ROI" in normalized:
            header_index = index
            product_column = normalized.index("产品名称")
            target_column = normalized.index("目标ROI")
            break
    if header_index is None:
        raise ValueError("赔付配置 Excel 缺少“产品名称”或“目标ROI”表头")

    settings = {}
    for row_number, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        campaign_name = row[product_column] if product_column < len(row) else None
        target_raw = row[target_column] if target_column < len(row) else None
        if campaign_name in (None, "") or target_raw in (None, ""):
            continue
        target_roi = _number(target_raw, None)
        if target_roi is None or target_roi <= 0:
            raise ValueError(f"赔付配置第 {row_number} 行目标 ROI 必须是大于 0 的数字")
        strategy_code, product_name = parse_plan_name(str(campaign_name))
        if not strategy_code or not product_name:
            raise ValueError(f"赔付配置第 {row_number} 行计划名称无法识别：{campaign_name}")
        key = (normalize_product_name(product_name), strategy_code)
        if key in settings and settings[key]["target_roi"] != target_roi:
            raise ValueError(f"赔付配置中 {product_name} · {strategy_code} 存在冲突的目标 ROI")
        settings[key] = {
            "product_name": product_name,
            "product_key": key[0],
            "strategy_code": strategy_code,
            "target_roi": target_roi,
            "source_row": row_number,
        }
    if not settings:
        raise ValueError("赔付配置 Excel 中没有可导入的目标 ROI")
    return list(settings.values())


HEADER_FILL = PatternFill("solid", fgColor="173F3A")
SUBHEADER_FILL = PatternFill("solid", fgColor="DDECE8")


def _write_table(sheet, headers, rows, number_columns=()):
    sheet.append(headers)
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in number_columns:
        for cell in sheet[column][1:]:
            cell.number_format = "0.00"
    for index, header in enumerate(headers, start=1):
        values = [str(header)] + [str(sheet.cell(row=row, column=index).value or "") for row in range(2, sheet.max_row + 1)]
        sheet.column_dimensions[get_column_letter(index)].width = min(max(max(map(len, values)) + 2, 12), 42)


def export_consumption_workbook(result):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "全域消耗"
    rows = [[item.product_name, item.plan_count, item.total_consumption] for item in result.products]
    _write_table(sheet, ["产品名称", "计划数量", "全域总消耗"], rows, ("C",))
    stream = io.BytesIO(); workbook.save(stream); stream.seek(0)
    return stream


def export_payout_workbook(result):
    workbook = Workbook()
    summary = workbook.active
    summary.title = "产品汇总"
    summary_rows = [[
        item.product_name, item.total_revenue, item.total_consumption,
        item.estimated_payout, item.missing_target_roi_count,
    ] for item in result.products]
    _write_table(summary, ["产品名称", "总收入", "全域总消耗", "预估赔付", "待设置目标ROI计划数"], summary_rows, ("B", "C", "D"))

    details = workbook.create_sheet("计划明细")
    detail_rows = []
    for product in result.products:
        for item in product.details:
            detail_rows.append([
                item.strategy_code, item.campaign_name, item.product_name, item.orders,
                item.revenue, item.target_roi, item.payout_roi, item.cost,
                item.payout_amount, item.actual_roi, item.current_budget,
            ])
    _write_table(details, [
        "编号", "广告计划名称", "产品", "SKU订单数", "总收入", "目标ROI",
        "赔付ROI", "实际消耗", "赔付金额", "实际ROI", "Current budget",
    ], detail_rows, ("E", "F", "G", "H", "I", "J", "K"))
    stream = io.BytesIO(); workbook.save(stream); stream.seek(0)
    return stream
