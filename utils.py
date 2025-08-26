import re
import logging

logger = logging.getLogger(__name__)

def parse_comma_number(text):
    try:
        return int(re.sub(r"[^\d]", "", str(text)))
    except:
        return 0

def parse_korean_number(text: str) -> int:
    """기존 한글 숫자 파싱 함수 유지"""
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

def parse_advanced_amount(text: str) -> int:
    """
    고급 금액 파싱 함수
    - 9억 → 90000
    - 737,000,000원 → 73700  
    - 1억2천만원 → 12000
    - 3억6천만원 → 36000
    - 90,000 → 90000
    """
    if not text:
        return 0
        
    clean_text = str(text).replace(",", "").strip()
    
    # 1. 한글 금액 처리 (억, 만, 천, 원 포함)
    if re.search(r'억|만|천|원', clean_text):
        return parse_korean_amount_advanced(clean_text)
    
    # 2. 원 단위 금액 처리 (8자리 이상이거나 '원'으로 끝나는 경우)
    if clean_text.endswith('원') or len(re.sub(r'[^\d]', '', clean_text)) >= 8:
        num_only = re.sub(r'[^\d]', '', clean_text)
        if num_only:
            won_amount = int(num_only)
            # 원을 만원으로 변환
            return won_amount // 10000
    
    # 3. 일반 숫자 처리
    num_only = re.sub(r'[^\d]', '', clean_text)
    return int(num_only) if num_only else 0

def parse_korean_amount_advanced(text: str) -> int:
    """한글 금액 고급 파싱"""
    total = 0
    remaining_text = text
    
    # 억 단위 처리
    eok_match = re.search(r'(\d+)억', remaining_text)
    if eok_match:
        total += int(eok_match.group(1)) * 10000
        remaining_text = remaining_text.replace(eok_match.group(0), '')
    
    # 천만 단위 처리 (예: 2천만 = 2000만)
    cheonman_match = re.search(r'(\d+)천만', remaining_text)
    if cheonman_match:
        total += int(cheonman_match.group(1)) * 1000
        remaining_text = remaining_text.replace(cheonman_match.group(0), '')
    
    # 만 단위 처리
    man_match = re.search(r'(\d+)만', remaining_text)
    if man_match:
        total += int(man_match.group(1))
        remaining_text = remaining_text.replace(man_match.group(0), '')
    
    # 천 단위 처리 (만원 단위로 변환)
    cheon_match = re.search(r'(\d+)천', remaining_text)
    if cheon_match:
        total += int(cheon_match.group(1)) / 10  # 천원을 만원으로 변환
        remaining_text = remaining_text.replace(cheon_match.group(0), '')
    
    return int(total)

def convert_won_to_manwon(amount_text):
    """
    원 단위 금액을 만원 단위로 변환
    예: "363,000,000" -> 36300
    """
    try:
        # 고급 파싱 함수 사용
        return parse_advanced_amount(amount_text)
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
    - 채권최고액: 고급 파싱으로 변환
    - 원금: 채권최고액과 비율로 자동 계산
    """
    try:
        # 채권최고액 변환 (고급 파싱 사용)
        if 'max_amount' in loan_data:
            original_amount = loan_data['max_amount']
            converted_amount = parse_advanced_amount(original_amount)
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
        # 선순위: limit 과 available 모두 계산
        limit = int(total_value * (ltv / 100) - deduction)
        available = int(limit - principal_sum)
    else:
        # 후순위: 가용은 무의미 → limit 만 계산
        limit = int(total_value * (ltv / 100) - maintain_maxamt_sum - deduction)
        available = None  # 후순위에서는 사용하지 않음

    import math
    limit = math.floor(limit / 100) * 100
    if available is not None:
        available = math.floor(available / 100) * 100
    return limit, available


def calculate_individual_ltv_limits(total_value, owners, ltv, maintain_maxamt_sum=0, existing_principal=0, is_senior=True):
    results = []
    for owner in owners:
        share_percent = float(owner["지분율"].replace("%", ""))
        share_ratio = share_percent / 100

        equity_value = int(total_value * share_ratio)

        if is_senior:
            ltv_limit = int(equity_value * (ltv / 100))
        else:
            # ### 이 로직이 정확한 계산식입니다 ###
            # 후순위 한도 = (개별 지분가치 * LTV) - (부동산의 전체 유지 채권최고액)
            ltv_limit = int((equity_value * (ltv / 100)) - maintain_maxamt_sum)
            # ### -------------------------- ###

        ltv_limit = (ltv_limit // 100) * 100
        available = ltv_limit - existing_principal if is_senior else None

        result = {
            "이름": owner["이름"],
            "지분율": owner["지분율"],
            "지분가치(만원)": equity_value,
            "지분LTV한도(만원)": ltv_limit,
            "대출구분": "선순위" if is_senior else "후순위"
        }
        if available is not None:
            result["가용자금(만원)"] = available

        results.append(result)

    return results
