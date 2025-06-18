import os
import requests
from utils import parse_korean_number

# --- [수정] Notion API 설정 (사용자 정보 반영) ---
NOTION_TOKEN = "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"
CUSTOMER_DB_ID = "20eebdf111b580ad9004c7e82d290cbc"
LOAN_DB_ID = "210ebdf111b580c4a36fd9edbb0ff8ec"

# --- Notion DB 속성 이름 ---
CUSTOMER_DB_TITLE_PROPERTY = "고객명"
LOAN_DB_RELATION_PROPERTY = "고객명" 

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- Notion 데이터 파싱 헬퍼 함수 ---
def get_rich_text(props, name):
    prop = props.get(name, {})
    rich_text = prop.get("rich_text", [])
    return rich_text[0].get("text", {}).get("content", "") if rich_text else ""
def get_title(props, name):
    prop = props.get(name, {})
    title = prop.get("title", [])
    return title[0].get("text", {}).get("content", "") if title else ""
def get_number(props, name):
    return props.get(name, {}).get("number")

# --- Notion DB 조회 함수 ---
def fetch_all_customers():
    customers = []
    try:
        query_url = f"https://api.notion.com/v1/databases/{CUSTOMER_DB_ID}/query"
        has_more = True; next_cursor = None
        while has_more:
            payload = {"page_size": 100}
            if next_cursor: payload["start_cursor"] = next_cursor
            res = requests.post(query_url, headers=NOTION_HEADERS, json=payload)
            res.raise_for_status()
            data = res.json()
            for page in data.get("results", []):
                props = page.get("properties", {})
                customer_name = get_title(props, CUSTOMER_DB_TITLE_PROPERTY)
                if customer_name: customers.append({"id": page["id"], "name": customer_name})
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
        return customers
    except Exception as e:
        print(f"Error fetching customers: {e}"); return []

def fetch_customer_details(page_id):
    try:
        res = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS)
        res.raise_for_status()
        props = res.json().get("properties", {})
        customer_details = {
            "customer_name": get_title(props, CUSTOMER_DB_TITLE_PROPERTY),
            "address": get_rich_text(props, "주소"), 
            "birth_date": get_rich_text(props, "생년월일"),
            "kb_price": get_number(props, "KB시세"),
            "area": get_rich_text(props, "전용면적"), "deduction_region": get_rich_text(props, "방공제지역"),
            "ltv1": get_rich_text(props, "LTV비율1"), "ltv2": get_rich_text(props, "LTV비율2"),
            "consult_amt": get_number(props, "컨설팅금액"), "consult_rate": get_number(props, "컨설팅수수료율"),
            "bridge_amt": get_number(props, "브릿지금액"), "bridge_rate": get_number(props, "브릿지수수료율"),
        }
        loan_query_url = f"https://api.notion.com/v1/databases/{LOAN_DB_ID}/query"
        payload = {"filter": {"property": LOAN_DB_RELATION_PROPERTY, "relation": {"contains": page_id}}}
        res = requests.post(loan_query_url, headers=NOTION_HEADERS, json=payload)
        res.raise_for_status()
        loan_items = []
        for item in res.json().get("results", []):
            loan_props = item.get("properties", {})
            loan_items.append({
                "lender": get_title(loan_props, "설정자"), "status": get_rich_text(loan_props, "진행구분"),
                "max_amount": get_number(loan_props, "채권최고액"), "principal": get_number(loan_props, "원금"),
                "ratio": get_number(loan_props, "설정비율"),
            })
        customer_details["loans"] = loan_items
        return customer_details
    except Exception as e:
        print(f"Error fetching details: {e}"); return None

# --- Notion DB 저장/수정/삭제 함수 ---
def format_properties_payload(data):
    inputs = data.get('inputs', {}); fees = data.get('fees', {}); ltv_rates = inputs.get("ltv_rates", ["", ""])
    return {
        CUSTOMER_DB_TITLE_PROPERTY: {"title": [{"text": {"content": inputs.get("customer_name", "")}}]},
        "주소": {"rich_text": [{"text": {"content": inputs.get("address", "")}}]},
        "KB시세": {"number": parse_korean_number(inputs.get("kb_price", "0"))},
        "전용면적": {"rich_text": [{"text": {"content": inputs.get("area", "")}}]},
        "방공제지역": {"rich_text": [{"text": {"content": inputs.get("deduction_region_text", "")}}]},
        "LTV비율1": {"rich_text": [{"text": {"content": ltv_rates[0]}}]},
        "LTV비율2": {"rich_text": [{"text": {"content": ltv_rates[1] if len(ltv_rates) > 1 else ""}}]},
        "컨설팅금액": {"number": parse_korean_number(fees.get("consult_amt", "0"))},
        "컨설팅수수료율": {"number": float(fees.get("consult_rate", "0") or 0)},
        "브릿지금액": {"number": parse_korean_number(fees.get("bridge_amt", "0"))},
        "브릿지수수료율": {"number": float(fees.get("bridge_rate", "0") or 0)},
    }
def save_loan_items(customer_page_id, loans_data):
    loan_query_url = f"https://api.notion.com/v1/databases/{LOAN_DB_ID}/query"
    payload = {"filter": {"property": LOAN_DB_RELATION_PROPERTY, "relation": {"contains": customer_page_id}}}
    res = requests.post(loan_query_url, headers=NOTION_HEADERS, json=payload)
    if res.ok:
        for page in res.json().get("results", []):
            requests.patch(f"https://api.notion.com/v1/pages/{page['id']}", headers=NOTION_HEADERS, json={"archived": True})
    for loan in loans_data:
        lender = loan.get("lender", "").strip()
        if not lender: continue
        loan_payload = {
            "parent": {"database_id": LOAN_DB_ID},
            "properties": {
                "설정자": {"title": [{"text": {"content": lender}}]},
                "채권최고액": {"number": parse_korean_number(loan.get("max_amount", "0"))},
                "설정비율": {"number": int(loan.get("ratio") or 0)},
                "원금": {"number": parse_korean_number(loan.get("principal", "0"))},
                "진행구분": {"rich_text": [{"text": {"content": loan.get("status", "유지")}}]},
                LOAN_DB_RELATION_PROPERTY: {"relation": [{"id": customer_page_id}]}
            }
        }
        requests.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=loan_payload)

def create_new_customer(data):
    customer_name = data.get("inputs", {}).get("customer_name", "").strip()
    if not customer_name: return {"success": False, "message": "고객명이 입력되지 않았습니다."}
    try:
        existing_customers = fetch_all_customers()
        if any(c['name'] == customer_name for c in existing_customers):
             return {"success": False, "message": f"'{customer_name}' 이름의 고객이 이미 존재합니다."}
        properties = format_properties_payload(data)
        payload = {"parent": {"database_id": CUSTOMER_DB_ID}, "properties": properties}
        res = requests.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=payload)
        res.raise_for_status()
        new_page_id = res.json().get("id")
        if new_page_id: save_loan_items(new_page_id, data.get("loans", []))
        return {"success": True, "message": f"'{customer_name}' 고객 정보가 새로 저장되었습니다."}
    except Exception as e: return {"success": False, "message": f"신규 저장 실패: {e}"}

def update_customer(page_id, data):
    customer_name = data.get("inputs", {}).get("customer_name", "").strip()
    if not customer_name: return {"success": False, "message": "고객명이 입력되지 않았습니다."}
    try:
        properties = format_properties_payload(data)
        res = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS, json={"properties": properties})
        res.raise_for_status()
        save_loan_items(page_id, data.get("loans", []))
        return {"success": True, "message": f"'{customer_name}' 고객 정보가 수정되었습니다."}
    except Exception as e: return {"success": False, "message": f"수정 실패: {e}"}

def delete_customer(page_id):
    try:
        loan_query_url = f"https://api.notion.com/v1/databases/{LOAN_DB_ID}/query"
        payload = {"filter": {"property": LOAN_DB_RELATION_PROPERTY, "relation": {"contains": page_id}}}
        res = requests.post(loan_query_url, headers=NOTION_HEADERS, json=payload)
        if res.ok:
            for page in res.json().get("results", []):
                requests.patch(f"https://api.notion.com/v1/pages/{page['id']}", headers=NOTION_HEADERS, json={"archived": True})
        res = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS, json={"archived": True})
        res.raise_for_status()
        return {"success": True, "message": "고객 정보가 삭제(보관)되었습니다."}
    except Exception as e: return {"success": False, "message": f"고객 삭제 실패: {e}"}
