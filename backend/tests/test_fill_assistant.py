import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from app.db import Base, engine
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def workbook_bytes(headers, rows, *, leading_row=None):
    workbook = Workbook()
    sheet = workbook.active
    if leading_row:
        sheet.append(leading_row)
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def campaign_workbook(rows):
    return workbook_bytes(
        ["Campaign ID", "广告计划名称", "成本", "Current budget", "SKU 订单数", "总收入", "ROI"],
        rows,
    )


def create_roi_settings(include_d=True):
    values = {"A": 3.2, "B": 4.2, "C": 3.0, "D": 2.7}
    if not include_d:
        values.pop("D")
    for code, target in values.items():
        response = client.post("/api/ads/target-roi-settings", json={
            "product_name": "微波炉蒸蛋器", "strategy_code": code, "target_roi": target,
        })
        assert response.status_code == 201


def sample_campaign():
    return campaign_workbook([
        ["1", "A*9.9微波炉蒸蛋器0.82", "10", "100", 21, "10", "1.0"],
        ["2", "B*9.10微波炉蒸蛋器0.82", "20", "100", 22, "18", "0.9"],
        ["3", "C*9.10微波炉蒸蛋器1.23", "10", "100", 30, "100", "10"],
        ["4", "D*9.10微波炉蒸蛋器1.23", "0", "100", 40, "0", "0"],
        ["5", "D*9.11微波炉蒸蛋器1.23.", "5", "100", 25, "0", "0"],
    ])


def test_full_consumption_and_payout_boundaries():
    create_roi_settings()
    response = client.post("/api/fill-assistant/analyze", files={
        "file": ("campaign.xlsx", sample_campaign(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    })
    assert response.status_code == 200
    result = response.json()
    assert result["total_rows"] == 5
    assert result["zero_cost_rows"] == 1
    assert result["effective_rows"] == 4
    assert result["product_count"] == 1
    assert result["total_consumption"] == 45
    assert result["payout_eligible_plans"] == 3
    product = result["products"][0]
    assert product["product_name"] == "微波炉蒸蛋器"
    assert product["plan_count"] == 4
    details = {item["strategy_code"]: item for item in product["details"]}
    assert details["A"]["payout_status"] == "not_eligible"
    assert details["A"]["payout_amount"] == 0
    assert details["B"]["payout_roi"] == pytest.approx(3.78)
    assert details["B"]["payout_amount"] == pytest.approx(20 - 18 / 3.78)
    assert details["C"]["payout_amount"] == 0
    assert details["D"]["payout_amount"] == 5
    assert product["estimated_payout"] == pytest.approx((20 - 18 / 3.78) + 5)


def test_missing_roi_marks_only_eligible_row_pending():
    create_roi_settings(include_d=False)
    result = client.post("/api/fill-assistant/analyze", files={"file": ("campaign.xlsx", sample_campaign())}).json()
    product = result["products"][0]
    assert product["estimated_payout"] is None
    assert product["missing_target_roi_count"] == 1
    assert result["missing_target_roi_plans"] == 1
    assert next(item for item in product["details"] if item["strategy_code"] == "D")["payout_status"] == "target_roi_pending"


def test_payout_config_import_upserts_a_b_c_d():
    content = workbook_bytes(
        [None, "产品名称", "总收入", "目标ROI", "赔付ROI", "实际消耗", "赔付金额"],
        [
            [None, "D*9.10微波炉蒸蛋器1.23", 0, 2.7, None, 0, None],
            [None, "A*9.10微波炉蒸蛋器0.82", 0, 3.2, None, 0, None],
            [None, "C*9.10微波炉蒸蛋器1.23", 0, 3.0, None, 0, None],
            [None, "B*9.10微波炉蒸蛋器0.82", 0, 4.2, None, 0, None],
            [None, "泰国", None, None, None, None, None],
        ],
        leading_row=[None, "填写", "填写", "填写", "/", "填写", "/"],
    )
    imported = client.post("/api/fill-assistant/import-payout-config", files={"file": ("赔付.xlsx", content)})
    assert imported.status_code == 200
    assert imported.json()["created"] == 4
    settings = client.get("/api/ads/target-roi-settings").json()
    assert {(item["strategy_code"], item["target_roi"]) for item in settings} == {
        ("A", 3.2), ("B", 4.2), ("C", 3.0), ("D", 2.7),
    }
    imported_again = client.post("/api/fill-assistant/import-payout-config", files={"file": ("赔付.xlsx", content)})
    assert imported_again.json()["created"] == 0
    assert imported_again.json()["updated"] == 4


def test_exports_match_analyzed_values():
    create_roi_settings()
    analysis = client.post("/api/fill-assistant/analyze", files={"file": ("campaign.xlsx", sample_campaign())}).json()
    consumption = client.post("/api/fill-assistant/export-consumption", json=analysis)
    assert consumption.status_code == 200
    workbook = load_workbook(io.BytesIO(consumption.content), data_only=True)
    assert workbook.sheetnames == ["全域消耗"]
    assert workbook["全域消耗"]["C2"].value == 45
    payout = client.post("/api/fill-assistant/export-payout", json=analysis)
    assert payout.status_code == 200
    workbook = load_workbook(io.BytesIO(payout.content), data_only=True)
    assert workbook.sheetnames == ["产品汇总", "计划明细"]
    assert workbook["产品汇总"]["D2"].value == pytest.approx(analysis["products"][0]["estimated_payout"])


@pytest.mark.parametrize("content, expected", [
    (b"not a workbook", "无效或已损坏"),
    (campaign_workbook([["1", "A*9.10微波炉蒸蛋器0.82", "bad", 10, 1, 2, 2]]), "成本为空或不是数字"),
    (campaign_workbook([["1", "无法解析的计划", 1, 10, 1, 2, 2]]), "广告计划名称无法识别"),
])
def test_analysis_rejects_invalid_input(content, expected):
    response = client.post("/api/fill-assistant/analyze", files={"file": ("campaign.xlsx", content)})
    assert response.status_code == 400
    assert expected in response.json()["detail"]


def test_analysis_rejects_missing_required_column():
    content = workbook_bytes(["广告计划名称", "成本", "SKU 订单数", "ROI"], [["A*9.10产品0.8", 1, 1, 1]])
    response = client.post("/api/fill-assistant/analyze", files={"file": ("campaign.xlsx", content)})
    assert response.status_code == 400
    assert "总收入" in response.json()["detail"]


def test_payout_config_rejects_broken_or_missing_headers():
    broken = client.post("/api/fill-assistant/import-payout-config", files={"file": ("赔付.xlsx", b"broken")})
    assert broken.status_code == 400
    assert "无效或已损坏" in broken.json()["detail"]
    missing = workbook_bytes(["产品名称", "其他字段"], [["A*9.10产品0.8", 2]])
    response = client.post("/api/fill-assistant/import-payout-config", files={"file": ("赔付.xlsx", missing)})
    assert response.status_code == 400
    assert "目标ROI" in response.json()["detail"]
