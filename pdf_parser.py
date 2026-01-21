import fitz  # PyMuPDF 라이브러리
import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

def extract_address(text):
    """텍스트에서 주소를 추출합니다."""
    match = re.search(r"\[집합건물\]\s*([^\n]+)", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"소재지\s*[:：]?\s*([^\n]+)", text)
    if match:
        return match.group(1).strip()
    return ""

def extract_area(text):
    """텍스트에서 전용 면적을 추출합니다."""
    area_section_match = re.search(r"전유부분의 건물의 표시([\s\S]*?)대지권의 표시", text)
    search_text = area_section_match.group(1) if area_section_match else text

    # 줄바꿈으로 분리된 면적 처리 (박규생님 등기 등)
    clean_text = re.sub(r'구조(\d+)\s*\n\s*\.', r'구조\1.', search_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)

    matches = re.findall(r"(\d+\.\d+)\s*㎡", clean_text)
    # 가장 큰 면적을 선택 (경로당, 경비실 등 작은 면적 제외)
    if matches:
        largest_area = max(matches, key=lambda x: float(x))
        return f"{largest_area}㎡"
    return ""

def extract_property_type(text):
    """
    텍스트에서 물건유형을 추출합니다. (표제부 전체 및 주소 분석)

    Returns:
        dict: {
            'type': 'APT' | 'Non-APT',
            'detail': '아파트' | '오피스텔' | '다세대주택' | '연립주택' | '도시형생활주택' | 'Unknown'
        }
    """
    # 1. 검색 범위 설정: '표제부' 전체를 가져오기 위해 '갑구' 이전까지의 텍스트를 추출
    # 갑구가 없는 경우(드물지만) 전체 텍스트 사용
    header_section_match = re.search(r"([\s\S]*?)(갑\s*구|을\s*구)", text)
    search_text = header_section_match.group(1) if header_section_match else text

    # 2. 텍스트 정제 (줄바꿈 제거하여 검색 용이하게)
    clean_text = re.sub(r'\s+', ' ', search_text)

    # 3. 상세 유형 판단 로직 (우선순위 중요)

    # 3-1. 오피스텔 (전유부분이나 1동의 건물 표시에 명시됨)
    if re.search(r'오피스텔', clean_text, re.IGNORECASE):
        return {'type': 'Non-APT', 'detail': '오피스텔'}

    # 3-2. 도시형생활주택 (요즘 많이 등장, 아파트/다세대와 혼용되므로 우선 체크)
    if re.search(r'도시형\s*생활\s*주택', clean_text, re.IGNORECASE):
        # 도시형생활주택은 아파트형과 원룸형이 섞여있으나 보통 Non-APT로 분류하거나 별도 관리
        return {'type': 'Non-APT', 'detail': '도시형생활주택'}

    # 3-3. 아파트
    # 건물 내역에 '아파트'가 있거나, 주소/건물명에 '아파트'가 포함된 경우
    # 단, '빌라'인데 이름만 'XX아파트'인 경우를 배제하기 위해 건물내역(구조) 키워드를 우선 봄
    # [수정] '(아파트)' 형태를 인식하기 위해 패턴에 '[\(\[]' 추가
    if re.search(r'건물\s*내역.*?아파트', clean_text) or re.search(r'[\d\s\(\[]아파트', clean_text):
        return {'type': 'APT', 'detail': '아파트'}

    # 3-4. 연립/다세대
    if re.search(r'연립\s*주택', clean_text, re.IGNORECASE):
        return {'type': 'Non-APT', 'detail': '연립주택'}

    if re.search(r'다세대\s*주택', clean_text, re.IGNORECASE):
        return {'type': 'Non-APT', 'detail': '다세대주택'}

    # 4. 보조 수단: 건물 명칭(주소)에서 키워드 검색
    # 위 구조 내역에서 못 찾았을 경우 주소 텍스트를 분석
    address_match = extract_address(text) # 기존에 정의된 함수 활용
    if address_match:
        if '아파트' in address_match:
            return {'type': 'APT', 'detail': '아파트'}
        if '오피스텔' in address_match:
            return {'type': 'Non-APT', 'detail': '오피스텔'}
        if '빌라' in address_match or '맨션' in address_match:
            return {'type': 'Non-APT', 'detail': '다세대주택'}

    # 5. 기본값
    return {'type': 'APT', 'detail': 'Unknown'}

def extract_owner_info(text):

    summary_section_match = re.search(r"주요 등기사항 요약([\s\S]*)", text)
    if not summary_section_match:
        return ""

    summary_text = summary_section_match.group(1)
    lines = [line.strip() for line in summary_text.splitlines() if line.strip()]

    owner_details = []
    for i, line in enumerate(lines):
        # '소유자' 또는 '공유자' 키워드가 있는 라인에서 이름(한글)을 찾습니다.
        owner_match = re.search(r"([가-힣]{2,})\s*\(?(소유자|공유자)\)?", line)
        if owner_match and i + 1 < len(lines):
            name = owner_match.group(1)
            
            # 바로 다음 줄에서 'nnnnnn-' 형태의 생년월일을 찾습니다.
            birth_match = re.search(r"(\d{6})-", lines[i+1])
            if birth_match:
                birth = birth_match.group(1)
                owner_details.append(f"{name} {birth}")
    
    return ", ".join(owner_details)

def extract_viewing_datetime(text):
    """텍스트에서 열람일시를 추출합니다."""
    patterns = [
        r'열람일시\s*[:：]?\s*(\d{4})년(\d{2})월(\d{2})일\s*(\d{2})시(\d{2})분(\d{2})초',
        r'열람일시\s*[:：]?\s*(\d{4})[년/\-](\d{1,2})[월/\-](\d{1,2})[일]?\s*(\d{1,2})[시:](\d{1,2})[분:](\d{1,2})[초]?'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day, hour, minute, second = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute.zfill(2)}:{second.zfill(2)}"
    
    return ""

def check_registration_age(viewing_datetime):
    """등기 열람일시가 한 달 이상 오래되었는지 확인"""
    if not viewing_datetime:
        return {"is_old": False, "age_days": 0, "message": "열람일시를 찾을 수 없습니다"}

    try:
        # 열람일시를 datetime 객체로 변환
        viewing_date = datetime.strptime(viewing_datetime, "%Y-%m-%d %H:%M:%S")
        current_date = datetime.now()
        
        # 날짜 차이 계산 (실제 경과 일수로 계산)
        age_delta = current_date - viewing_date
        age_days = round(age_delta.total_seconds() / 86400)
        
        # 한 달(30일) 이상 차이나는지 확인
        is_old = age_days >= 30
        
        if is_old:
            message = f"⚠️ 주의: 등기가 {age_days}일 전 데이터입니다 (한 달 이상 경과)"
        elif age_days > 7:
            message = f"등기가 {age_days}일 전 데이터입니다"
        else:
            message = f"최신 등기 데이터입니다 ({age_days}일 전)"
            
        return {
            "is_old": is_old,
            "age_days": age_days,
            "message": message,
            "viewing_date": viewing_datetime,
            "current_date": current_date.strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        return {"is_old": False, "age_days": 0, "message": f"날짜 분석 오류: {str(e)}"}

def _extract_text_from_pdf(filepath: str) -> str:
    """PDF 파일에서 텍스트를 추출합니다."""
    try:
        doc = fitz.open(filepath)
        full_text = ""
        for page in doc:
            full_text += page.get_text("text")
        doc.close()
        return full_text
    except Exception as e:
        print(f"PDF 텍스트 추출 중 오류 발생: {e}")
        return ""

def parse_pdf_for_ltv(pdf_path):
    try:
        full_text = _extract_text_from_pdf(pdf_path)
        if not full_text:
            return {}

        # 1. 텍스트를 구조화된 섹션으로 분리
        sections = _split_text_into_sections(full_text)

        # 2. 섹션 기반으로 정보 추출
        address = _parse_address(sections.get('full', ''))
        area = _parse_area(sections.get('full', ''))
        customer_details = _parse_owners(sections)

        # 열람일시와 나이 검사 추가
        viewing_datetime = extract_viewing_datetime(full_text)
        age_check = check_registration_age(viewing_datetime)

        # 3. 섹션 기반으로 심사 기준 분석 실행
        eligibility_checks = analyze_eligibility_from_sections(sections)

        return {
            "customer_name": customer_details,
            "birth_date": "",
            "address": address,
            "area": area,
            "viewing_datetime": viewing_datetime,
            "age_check": age_check,
            "eligibility_checks": eligibility_checks
        }
    except Exception as e:
        print(f"PDF 파싱 중 오류 발생: {e}")
        return {}

def extract_owner_shares_linewise(pdf_path):
    """
    PDF에서 각 라인별로 소유자 이름, 주민등록번호, 지분율을 추출합니다.
    기존 함수들과 독립적으로 동작합니다.
    """
    try:
        doc = fitz.open(pdf_path)
        full_text = "\n".join([page.get_text("text") for page in doc])
        doc.close()

        # "주요 등기사항 요약" 이후 부분만 사용
        summary_match = re.search(r"주요 등기사항 요약([\s\S]*)", full_text)
        if not summary_match:
            return []

        summary_text = summary_match.group(1)
        lines = [line.strip() for line in summary_text.splitlines() if line.strip()]

        results = []
        for line in lines:
            # 이름 + 주민번호 + 지분율이 한 줄에 있는 경우 매칭
            match = re.search(
                r"([가-힣]{2,})\s*\(공유자\)\s*(\d{6}-\*+|\d{6}-\d{7})\s*지분\s*(\d+)분의\s*(\d+)",
                line
            )
            if match:
                name = match.group(1)
                rrn = match.group(2)
                denom, num = int(match.group(3)), int(match.group(4))
                percent = round(num / denom * 100, 2)
                results.append({
                    "이름": name,
                    "주민번호": rrn,
                    "지분": f"{num}/{denom}",
                    "지분율": f"{percent}%"
                })
        return results
    
    except Exception as e:
        print(f"PDF 파싱 중 오류 발생: {e}")
        return []


def extract_owner_shares_with_birth(full_text):
    """
    등기부등본 텍스트에서 '이름 생년월일 지분율' 형태로 추출합니다.
    (예: '이승욱 810319 지분율 1/2 (50.0%)')

    Args:
        full_text (str): PDF에서 추출된 전체 텍스트

    Returns:
        list: 소유자별 지분 정보 리스트
    """
    try:
        # '주요 등기사항 요약' 섹션으로 검색 범위를 좁혀 정확도 향상
        summary_match = re.search(r"주요 등기사항 요약([\s\S]*)", full_text)
        if not summary_match:
            return []
        summary_text = summary_match.group(1)
        lines = [line.strip() for line in summary_text.splitlines() if line.strip()]

        owner_details = []
        num_owners = 0
        # 먼저 공유자 수를 센다
        for line in lines:
            if re.search(r"([가-힣]{2,})\s*\((소유자|공유자)\)", line):
                num_owners += 1

        results = []
        # 소유자 정보를 순차적으로 파싱
        for i, line in enumerate(lines):
            name_match = re.search(r"([가-힣]{2,})\s*\((소유자|공유자)\)", line)
            if name_match:
                name = name_match.group(1)
                birth = ""
                share_info = ""

                # 다음 줄에서 생년월일 찾기
                if i + 1 < len(lines) and re.search(r"^\d{6}-", lines[i+1]):
                    birth = re.search(r"(\d{6})-", lines[i+1]).group(1)

                # 다음 두 줄 내에서 지분 정보 찾기
                for j in range(i + 1, min(i + 3, len(lines))):
                    share_match = re.search(r"지분\s*(\d+)\s*분의\s*(\d+)", lines[j])
                    if share_match:
                        denom, num = int(share_match.group(1)), int(share_match.group(2))
                        percent = round(num / denom * 100, 1)
                        share_info = f"지분율 {num}/{denom} ({percent}%)"
                        break
                
                # 지분 정보가 없으면 단독/공동 소유에 따라 처리
                if not share_info:
                    if num_owners > 1:
                        percent = round(100 / num_owners, 1)
                        share_info = f"지분율 1/{num_owners} ({percent}%)"
                    else:
                        share_info = "지분율 1/1 (100.0%)"

                if name and birth:
                    results.append(f"{name} {birth}  {share_info}")

        return results

    except Exception as e:
        print(f"PDF 파싱 중 오류 발생: {e}")
        return []
    
# <<< 여기에 근저당권 분석 함수를 추가합니다 >>>
def extract_rights_info(full_text):
    
    # 1. '시작/종료 마커'로 테이블 영역을 정확히 추출
    table_match = re.search(
        r'3\.\s*\([근|전].*?대상소유자([\s\S]*?)\[\s*참\s*고\s*사\s*항\s*\]',
        full_text,
        re.DOTALL
    )
    if not table_match:
        return {"근저당권": []}
    
    table_text = table_match.group(1)

    # 2. 테이블 내용을 '순위번호' 기준으로 모든 항목을 임시 리스트에 저장
    entries = re.split(r'\n\s*(?=(?:\d{1,2}-\d{1,2}|\d{1,2})\s)', table_text)
    
    all_entries = []
    for entry_text in entries:
        clean_text = ' '.join(entry_text.split())
        if not clean_text: continue

        seq_match = re.search(r'^\s*(\d{1,2}(?:-\d{1,2})?)', entry_text)
        if not seq_match: continue
        
        seq = seq_match.group(1)
        main_key = seq.split('-')[0]

        date_match = re.search(r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)', clean_text)
        amount_match = re.search(r'채권최고액\s*금\s*([\d,]+)원', clean_text)
        creditor_match = re.search(r'근저당권자\s*(\S+)', clean_text)

        info_parts = []
        if amount_match:
            info_parts.append(f"채권최고액 금{amount_match.group(1)}원")
        if creditor_match:
            info_parts.append(f"근저당권자 {creditor_match.group(1)}")
        
        if info_parts:
            all_entries.append({
                'main_key': main_key,
                '접수일': date_match.group(1).strip() if date_match else "",
                '주요등기사항': " ".join(info_parts)
            })

    # 3. [수정됨] 이력 덮어쓰기 로직: 누락된 정보를 원본에서 가져와 병합
    final_mortgages = {}
    for entry in reversed(all_entries):
        if entry['main_key'] not in final_mortgages:
            # 원본 항목(보통 채권최고액이 명시된 첫 항목)을 찾음
            original_info = next((item for item in all_entries if item['main_key'] == entry['main_key'] and '채권최고액' in item['주요등기사항']), None)
            
            if original_info:
                # 현재 항목에 '채권최고액'이 없으면 원본에서 가져와 맨 앞에 추가
                if '채권최고액' not in entry['주요등기사항']:
                    amount_part = re.search(r'채권최고액\s*금[\d,]+원', original_info['주요등기사항'])
                    if amount_part:
                        entry['주요등기사항'] = amount_part.group(0) + " " + entry['주요등기사항']
                
                # 현재 항목에 '근저당권자'가 없으면 원본에서 가져와 뒤에 추가
                if '근저당권자' not in entry['주요등기사항']:
                    creditor_part = re.search(r'근저당권자\s*\S+', original_info['주요등기사항'])
                    if creditor_part:
                        entry['주요등기사항'] += " " + creditor_part.group(0)

            final_mortgages[entry['main_key']] = entry
            
    # 4. 원래 순서대로 정렬하여 반환
    sorted_final_list = sorted(list(final_mortgages.values()), key=lambda x: int(x['main_key']))

    return {"근저당권": sorted_final_list}


def extract_construction_date(text):
    """
    [신규] 표제부 접수일자(준공일/사용승인일 추정) 추출

    Args:
        text (str): PDF 전체 텍스트

    Returns:
        str: 준공일자 (YYYY-MM-DD 형식) 또는 빈 문자열
    """
    try:
        # 표제부 (1동의 건물의 표시) 영역 찾기
        header_match = re.search(r"표제부.*?\(1동의 건물의 표시\)([\s\S]*?)대지권의\s*목적", text)
        if not header_match:
            header_match = re.search(r"표제부.*?\(1동의 건물의 표시\)([\s\S]*?)(갑\s*구|을\s*구)", text)

        if header_match:
            section_text = header_match.group(1)
            # 가장 먼저 나오는 날짜가 통상 보존등기 접수일
            date_match = re.search(r"(\d{4})년(\d{1,2})월(\d{1,2})일", section_text)
            if date_match:
                y, m, d = date_match.groups()
                return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception as e:
        print(f"준공일자 추출 오류: {e}")
    return ""


def extract_last_transfer_info(text):
    """
    [개선판] 갑구에서 가장 최신(높은 순위번호) 소유권 이전 내역을 추출합니다.
    따옴표 유무와 상관없이 날짜와 거래가액을 찾아냅니다.
    """
    result = {"date": "", "reason": "", "price": ""}
    try:
        # 1. 갑구 영역 추출 (소유권에 관한 사항)
        gap_gu_match = re.search(r"【\s*갑\s*구\s*】([\s\S]*?)(?:【\s*을\s*구\s*】|주요\s*등기사항|$)", text)
        if not gap_gu_match:
            return result
        
        gap_gu_text = gap_gu_match.group(1)

        # 2. 모든 소유권 이전 내역 찾기 (따옴표 " 가 있어도 없어도 찾을 수 있도록 수정)
        # 패턴 설명: 순위번호, 소유권 이전, 접수일자를 순서대로 탐색
        pattern = r'["\']?(\d+)["\']?\s*,\s*["\']?소유권\s*이전["\']?\s*,\s*["\']?(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)'
        all_transfers = re.findall(pattern, gap_gu_text)

        if not all_transfers:
            # 패턴 2: 쉼표 없이 공백으로 구분된 경우를 위한 예비 패턴
            pattern2 = r'(\d+)\s+소유권\s*이전\s+(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)'
            all_transfers = re.findall(pattern2, gap_gu_text)

        if not all_transfers:
            return result

        # 3. 순위번호가 가장 큰(최신) 항목 선택
        latest_entry = max(all_transfers, key=lambda x: int(x[0]))
        target_rank = latest_entry[0]  # 순위번호
        raw_date = latest_entry[1]     # 날짜 문자열

        # 날짜 포맷팅 (YYYY-MM-DD)
        date_nums = re.findall(r'\d+', raw_date)
        if len(date_nums) >= 3:
            result["date"] = f"{date_nums[0]}-{date_nums[1].zfill(2)}-{date_nums[2].zfill(2)}"

        # 4. 해당 순위번호 주변에서 거래가액과 원인 추출 (범위 600자로 확대)
        rank_pattern = rf'["\']?{target_rank}["\']?'
        rank_start_pos = gap_gu_text.find(target_rank)
        context = gap_gu_text[rank_start_pos : rank_start_pos + 600]

        # 원인 판별
        if "매매" in context:
            result["reason"] = "매매"
            # 거래가액 추출 (숫자 사이의 콤마 무시)
            p_match = re.search(r"거래가액\s*금?\s*([\d,]+)\s*원", context)
            if p_match:
                price_won = int(p_match.group(1).replace(',', ''))
                result["price"] = str(price_won // 10000) # 만원 단위
        elif "보존" in context:
            result["reason"] = "소유권보존"
        elif "상속" in context:
            result["reason"] = "상속"

        print(f"[DEBUG] 소유권 이전 정보 추출 성공: {result}")

    except Exception as e:
        print(f"소유권 이전 정보 추출 중 오류 발생: {e}")

    return result


def extract_seizure_info(full_text):
    """
    갑구에서 압류/가압류 정보를 추출합니다.

    Returns:
        dict: {
            'total_count': int,  # 총 압류 이력 건수 (말소된 것 포함)
            'active_count': int,  # 현재 유효한 압류 건수
            'active_seizures': [  # 현재 유효한 압류 목록
                {
                    'rank': str,  # 순위번호
                    'type': str,  # 압류 또는 가압류
                    'creditor': str,  # 채권자
                    'date': str,  # 접수일
                    'amount': str  # 금액 (있는 경우)
                }
            ]
        }
    """
    result = {
        'total_count': 0,
        'active_count': 0,
        'active_seizures': []
    }

    try:
        # 갑구 영역 추출
        gap_gu_match = re.search(r"【\s*갑\s*구\s*】([\s\S]*?)(?:【\s*을\s*구\s*】|주요\s*등기사항|$)", full_text)
        if not gap_gu_match:
            return result

        gap_gu_text = gap_gu_match.group(1)

        # 모든 항목 파싱
        seizures = {}  # {순위번호: 압류정보}
        cancelled_ranks = set()  # 말소된 순위번호 집합

        # 순위번호 기준으로 항목 분리
        entries = re.split(r'\n(?=\d{1,2}(?:-\d{1,2})?\s+)', gap_gu_text)

        for entry in entries:
            if not entry.strip():
                continue

            # 순위번호와 등기목적 추출
            first_line_match = re.match(r'^\s*(\d{1,2}(?:-\d{1,2})?)\s+([^\s]+)', entry)
            if not first_line_match:
                continue

            rank = first_line_match.group(1)
            purpose = first_line_match.group(2)

            # 말소 등기인지 확인 ("N번압류등기말소", "N번가압류등기말소")
            if '말소' in purpose:
                cancelled_match = re.search(r'(\d{1,2})번(?:압류|가압류)등기말소', entry)
                if cancelled_match:
                    cancelled_ranks.add(cancelled_match.group(1))
                continue

            # 압류 또는 가압류 등기인지 확인
            if purpose == '압류' or purpose == '가압류':
                # 날짜 추출
                date_match = re.search(r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)', entry)
                date = date_match.group(1) if date_match else ''

                # 채권자 추출
                creditor = ''
                creditor_match = re.search(r'권리자\s+([^\n]+)', entry)
                if creditor_match:
                    creditor = creditor_match.group(1).strip()

                # 금액 추출 (가압류의 경우)
                amount = ''
                if purpose == '가압류':
                    amount_match = re.search(r'청구금액\s+금([\d,]+)\s*원', entry)
                    if amount_match:
                        amount = amount_match.group(1)

                seizures[rank] = {
                    'rank': rank,
                    'type': purpose,
                    'creditor': creditor,
                    'date': date,
                    'amount': amount
                }

        # 총 건수
        result['total_count'] = len(seizures)

        # 현재 유효한 압류 (말소되지 않은 것만)
        for rank, info in seizures.items():
            if rank not in cancelled_ranks:
                result['active_count'] += 1
                result['active_seizures'].append(info)

        print(f"[DEBUG] 압류 정보 추출: 총 {result['total_count']}건, 현재 유효 {result['active_count']}건")
        print(f"[DEBUG] 말소된 순위: {sorted(cancelled_ranks)}")

    except Exception as e:
        print(f"압류 정보 추출 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    return result

import requests
import xml.etree.ElementTree as ET
from urllib.parse import unquote
import re

def get_legal_code_from_kakao(address):
    """카카오 API를 통해 주소를 10자리 법정동코드로 변환합니다."""
    # 사용자님의 카카오 REST API 키
    KAKAO_REST_API_KEY = "7105bf011f69bc4cb521ec9b1ea496e0" 
    
    # [정제] "동/호" 정보가 포함되면 검색에 실패하므로 번지수까지만 잘라냅니다.
    clean_match = re.search(r'^(.*?\d+(?:-\d+)?)\b', address)
    search_query = clean_match.group(1) if clean_match else address

    print(f"[카카오 API] 원본 주소: {address}")
    print(f"[카카오 API] 검색 쿼리: {search_query}")

    url = 'https://dapi.kakao.com/v2/local/search/address.json'
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {'query': search_query}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        print(f"[카카오 API] 응답 코드: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"[카카오 API] 응답 데이터: {data}")

            # 'address' 필드에서 10자리 법정동코드(b_code) 추출
            if data['documents'] and data['documents'][0].get('address'):
                b_code = data['documents'][0]['address'].get('b_code', '')
                print(f"[카카오 API] 법정동코드 추출 성공: {b_code}")
                return b_code
            else:
                print(f"[카카오 API] 검색 결과 없음")
        else:
            print(f"[카카오 API] 비정상 응답: {response.text}")
        return ""
    except Exception as e:
        print(f"[카카오 API 오류] {e}")
        import traceback
        traceback.print_exc()
        return ""

def parse_address_for_building_api(address):
    """주소를 파싱하여 건축물대장 API에 필요한 파라미터(시군구, 법정동, 번, 지)를 추출합니다."""
    result = {'sigunguCd': '', 'bjdongCd': '', 'bun': '', 'ji': '', 'success': False}

    try:
        print(f"[주소 파싱] 원본 주소: {address}")

        # 시군구 코드 매핑 테이블
        sigungu_map = {
            '남양주시': '41360',
            '서울특별시 강남구': '11680',
            '서울특별시 강동구': '11740',
            '서울특별시 강북구': '11305',
            '서울특별시 강서구': '11500',
        }

        # 법정동 코드 매핑 (더 구체적인 것부터 매칭)
        bjdong_map = [
            (('41360', '창현리'), '25628'),  # 남양주시 화도읍 창현리
            (('41360', '화도읍'), '25600'),  # 남양주시 화도읍 (기본값)
        ]

        # 1. 시군구 코드 찾기
        sigungu_cd = None
        for city, code in sigungu_map.items():
            if city in address:
                sigungu_cd = code
                print(f"[주소 파싱] 시군구 매칭: {city} -> {code}")
                break

        if not sigungu_cd:
            print(f"[주소 파싱] 시군구 코드를 찾을 수 없습니다")
            return result

        result['sigunguCd'] = sigungu_cd

        # 2. 법정동 코드 찾기 (리스트 순서대로, 더 구체적인 것 우선)
        bjdong_cd = None
        for (sig_cd, dong_name), code in bjdong_map:
            if sig_cd == sigungu_cd and dong_name in address:
                bjdong_cd = code
                print(f"[주소 파싱] 법정동 매칭: {dong_name} -> {code}")
                break

        if not bjdong_cd:
            print(f"[주소 파싱] 법정동 코드를 찾을 수 없습니다")
            return result

        result['bjdongCd'] = bjdong_cd

        # 3. 번지 추출
        bungi_match = re.search(r'[리동]\s*(\d+)(?:-(\d+))?', address)
        if bungi_match:
            result['bun'] = bungi_match.group(1).zfill(4)
            result['ji'] = bungi_match.group(2).zfill(4) if bungi_match.group(2) else '0000'
            print(f"[주소 파싱] 번지 추출: {result['bun']}-{result['ji']}")
            result['success'] = True
        else:
            print(f"[주소 파싱] 번지를 추출할 수 없습니다")

        print(f"[주소 파싱] 최종 결과: {result}")

    except Exception as e:
        print(f"[주소 파싱 오류] {e}")
        import traceback
        traceback.print_exc()

    return result

def get_building_info(address):
    """주소를 기반으로 건축물대장 API를 호출하여 세대수와 준공일자를 조회합니다."""
    result = {
        'success': False, 
        'total_households': 0, 
        'completion_date': '', 
        'raw_completion_date': '', 
        'buildings': []
    }
    try:
        # 1. 주소 파싱 실행
        parsed = parse_address_for_building_api(address)
        if not parsed['success']:
            print(f"[건축물대장] 주소 분석 실패: {address}")
            return result

        # 2. 공공데이터포털 건축물대장 API 호출
        url = 'https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo'
        service_key = "B6F8mdWu8MpnYUwgzs84AWBmkZG3B2l+ItDSFbeL64CxbxJORed+4LpR5uMHxebO/v7LSHBXm1FHFJ8XE6UHqA=="

        params = {
            'serviceKey': unquote(service_key),
            'sigunguCd': parsed['sigunguCd'],
            'bjdongCd': parsed['bjdongCd'],
            'platGbCd': '0',
            'bun': parsed['bun'],
            'ji': parsed['ji'],
            'numOfRows': '100',
            'pageNo': '1'
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            # 결과 코드가 '00'(성공)인지 확인
            if root.findtext('.//resultCode') == '00':
                items = root.findall('.//item')
                if items:
                    total_hhld = 0
                    comp_date = ""

                    # 주거용 아파트만 필터링 (주상가, 상가, 관리동 등 제외)
                    exclude_keywords = ['주상가', '상가', '관리동', '부대시설', '커뮤니티', '관리', '근린생활']

                    for item in items:
                        dong_nm = item.findtext('dongNm') or ''
                        etc_purps = item.findtext('etcPurps') or ''
                        h_cnt = item.findtext('hhldCnt') or '0'
                        u_date = item.findtext('useAprDay') or item.findtext('useAprvDe') or ''

                        # 주거용이 아닌 건물 제외 (동명칭 또는 기타용도에 제외 키워드 포함)
                        is_excluded = any(keyword in dong_nm or keyword in etc_purps for keyword in exclude_keywords)

                        if not is_excluded and h_cnt.isdigit():
                            total_hhld += int(h_cnt)

                        # 가장 먼저 발견되는 사용승인일을 대표 날짜로 사용
                        if u_date and not comp_date:
                            comp_date = u_date

                    result['success'] = True
                    result['total_households'] = total_hhld
                    result['raw_completion_date'] = comp_date
                    if len(comp_date) == 8:
                        result['completion_date'] = f"{comp_date[:4]}-{comp_date[4:6]}-{comp_date[6:8]}"

                    print(f"[건축물대장] 조회 성공: {total_hhld}세대 (주거용만), 준공일 {result['completion_date']}")
            else:
                msg = root.findtext('.//resultMsg')
                print(f"[건축물대장] API 응답 오류: {msg}")
        
    except Exception as e:
        print(f"[건축물대장 조회 오류] {e}")
    return result
