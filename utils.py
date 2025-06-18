import re

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