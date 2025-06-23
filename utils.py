import re
import logging

logger = logging.getLogger(__name__)

def parse_comma_number(text):
    try:
        return int(re.sub(r"[^\d]", "", str(text)))
    except:
        return 0

def parse_korean_number(text: str) -> int:
    text = str(text).replace(",", "").strip()
    total = 0
    
    eok_match = re.search(r"(\d+)\s*억", text)
    if eok_match:
        total += int(eok_match.group(1)) * 10000
        text = text.replace(eok_match.group(0), "")
        
    man_match = re.search(r"(\d+)\s*만", text)
    if man_match:
        total += int(man_match.group(1))
        text = text.replace(man_match.group(0), "")
        
    if total == 0:
        try:
            return int(re.sub(r"[^\d]", "", text))
        except (ValueError, TypeError):
            return 0
            
    return total

def convert_won_to_manwon(amount_text):
    """
    원 단위 금액을 만원 단위로 변환
    예: "363,000,000" -> 36300
    """
    try:
        # 콤마 제거하고 숫자만 추출
        clean_amount = re.sub(r"[^\d]", "", str(amount_text))
        if not clean_amount:
            return 0
        
        won_amount = int(clean_amount)
        # 원을 만원으로 변환 (10,000으로 나누기)
        manwon_amount = won_amount // 10000
        return manwon_amount
    except (ValueError, TypeError):
        return 0

def calculate_principal_from_ratio(max_amount, ratio):
    """
    채권최고액과 비율을 기반으로 원금 계산
    예: max_amount=36300만원, ratio=120% -> 원금=30250만원
    """
    try:
        max_amt = float(max_amount) if max_amount else 0
        ratio_val = float(ratio) if ratio else 100
        
        if ratio_val <= 0:
            return 0
            
        # 원금 = 채권최고액 / (비율/100)
        principal = int(max_amt / (ratio_val / 100))
        return principal
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

def auto_convert_loan_amounts(loan_data):
    """
    대출 데이터의 금액을 자동 변환
    - 채권최고액: 원 단위 -> 만원 단위 변환
    - 원금: 채권최고액과 비율로 자동 계산
    """
    try:
        # 채권최고액 변환 (원 -> 만원)
        if 'max_amount' in loan_data:
            original_amount = loan_data['max_amount']
            converted_amount = convert_won_to_manwon(original_amount)
            loan_data['max_amount'] = str(converted_amount)
        
        # 원금 자동 계산
        max_amount = float(loan_data.get('max_amount', 0))
        ratio = float(loan_data.get('ratio', 100))
        
        if max_amount > 0 and ratio > 0:
            calculated_principal = calculate_principal_from_ratio(max_amount, ratio)
            loan_data['principal'] = str(calculated_principal)
        
        return loan_data
    except Exception as e:
        logger.error(f"대출 금액 자동 변환 중 오류: {e}")
        return loan_data

# 기존의 핵심 LTV 계산 로직
def calculate_ltv_limit(total_value, deduction, principal_sum, maintain_maxamt_sum, ltv, is_senior=True):
    if is_senior:
        limit = int(total_value * (ltv / 100) - deduction)
        available = int(limit - principal_sum)
    else:
        limit = int(total_value * (ltv / 100) - maintain_maxamt_sum - deduction)
        available = int(limit - principal_sum)

    limit = (limit // 10) * 10
    available = (available // 10) * 10
    return limit, available
