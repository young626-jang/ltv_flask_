import fitz  # PyMuPDF 라이브러리
import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from legal_code_data import sigungu_map, bjdong_map  # 법정동코드 데이터 import

def extract_address(text):
    """
    텍스트에서 주소를 추출합니다.
    PDF에서 주소가 줄바꿈으로 분리되는 경우가 있으므로,
    [집합건물] 이후 "제~호"까지 포함하여 추출합니다.
    """
    # 모든 [집합건물] 위치 찾기
    pattern = r'\[집합건물\]\s*'
    positions = [(m.end(), m.start()) for m in re.finditer(pattern, text)]

    best_address = ""

    for i, (start_pos, _) in enumerate(positions):
        # 다음 [집합건물] 위치까지 또는 텍스트 끝까지
        if i + 1 < len(positions):
            end_pos = positions[i + 1][1]  # 다음 [집합건물]의 시작 위치
        else:
            end_pos = min(start_pos + 500, len(text))  # 최대 500자까지만

        block = text[start_pos:end_pos]

        # 이 블록 내에서 "제~호"로 끝나는 주소 찾기
        # 줄바꿈 포함하여 "제~호"까지 추출
        match = re.search(r'^(.+?제\d+호)', block, re.DOTALL)
        if match:
            # 줄바꿈을 공백으로 치환하고 연속 공백 제거
            address = re.sub(r'\s+', ' ', match.group(1)).strip()
            # "열 람 용", "열람일시" 등 불필요한 텍스트 제거
            address = re.sub(r'\s*열\s*람\s*용.*$', '', address).strip()
            address = re.sub(r'\s*열람일시.*$', '', address).strip()
            # 가장 짧은 완전한 주소 선택 (불필요한 데이터 제외)
            if not best_address or len(address) < len(best_address):
                best_address = address

    if best_address:
        return best_address

    # 패턴 2: 줄바꿈 없이 한 줄에 있는 경우 (기존 방식)
    matches = re.findall(r"\[집합건물\]\s*([^\n]+)", text)
    if matches:
        # "제~호"로 끝나는 주소 우선, 없으면 가장 긴 것
        complete = [m.strip() for m in matches if re.search(r'제\d+호', m)]
        if complete:
            result = min(complete, key=len)  # 가장 짧은 완전한 주소
            # "열 람 용", "열람일시" 등 불필요한 텍스트 제거
            result = re.sub(r'\s*열\s*람\s*용.*$', '', result).strip()
            result = re.sub(r'\s*열람일시.*$', '', result).strip()
            return result
        return max([m.strip() for m in matches], key=len)

    # 패턴 3: 소재지 패턴
    match = re.search(r"소재지\s*[:：]?\s*([^\n]+)", text)
    if match:
        return match.group(1).strip()
    return ""


def extract_search_address(full_address):
    """
    전체 주소에서 KB시세 검색용 축약 주소를 추출합니다.

    우선순위:
    1. 시군구 + 동 + 지번 (예: "남양주시 평내동 87")
    2. 시군구 + 동 + 아파트명 (예: "미추홀구 용현동 용현자이크레스트")

    Args:
        full_address (str): 등기부등본에서 추출한 전체 주소

    Returns:
        str: 검색용 축약 주소
    """
    if not full_address:
        return ""

    try:
        # 1. 시군구 추출
        sigungu_match = re.search(r'([가-힣]+[시군구])', full_address)
        sigungu = sigungu_match.group(1) if sigungu_match else ""

        # 2. 동/읍/면/리 추출
        dong_match = re.search(r'([가-힣]+[동읍면리])(?:\s|$|\d)', full_address)
        dong = dong_match.group(1) if dong_match else ""

        # 패턴 1: 시군구 + 동 + 지번 (가장 이상적인 형태)
        pattern1 = r'([가-힣]+[시군구])\s+([가-힣]+[동읍면리])\s+(\d+(?:-\d+)?)'
        match1 = re.search(pattern1, full_address)

        if match1:
            sigungu = match1.group(1)
            dong = match1.group(2)
            jibun = match1.group(3)
            result = f"{sigungu} {dong} {jibun}"
            print(f"[검색주소 추출] 패턴1(지번) 매칭: {result}")
            return result

        # 패턴 2: 지번이 없는 경우 아파트명 추출
        # 아파트명 패턴: ~아파트, ~자이, ~힐스테이트, ~푸르지오, ~래미안, ~e편한세상 등
        apt_patterns = [
            r'([가-힣]+자이[가-힣]*)',           # 자이, 자이크레스트 등
            r'([가-힣]+아파트)',                 # ~아파트
            r'([가-힣]+힐스테이트)',             # 힐스테이트
            r'([가-힣]+푸르지오)',               # 푸르지오
            r'([가-힣]+래미안)',                 # 래미안
            r'([가-힣]+e편한세상)',              # e편한세상
            r'([가-힣]+센트럴)',                 # ~센트럴
            r'([가-힣]+파크)',                   # ~파크
            r'([가-힣]+타운)',                   # ~타운
            r'([가-힣]+빌)',                     # ~빌
            r'([가-힣]+캐슬)',                   # ~캐슬
            r'([가-힣]+스카이뷰)',               # ~스카이뷰
        ]

        apt_name = ""
        for apt_pattern in apt_patterns:
            apt_match = re.search(apt_pattern, full_address)
            if apt_match:
                apt_name = apt_match.group(1)
                break

        if sigungu and dong and apt_name:
            result = f"{sigungu} {dong} {apt_name}"
            print(f"[검색주소 추출] 패턴2(아파트명) 매칭: {result}")
            return result

        # 패턴 3: 시군구 + 동만 추출 가능한 경우
        if sigungu and dong:
            result = f"{sigungu} {dong}"
            print(f"[검색주소 추출] 패턴3(동만) 매칭: {result}")
            return result

        # 매칭 실패 시 원본 반환
        print(f"[검색주소 추출] 패턴 매칭 실패, 원본 사용: {full_address}")
        return full_address

    except Exception as e:
        print(f"[검색주소 추출 오류] {e}")
        return full_address

def extract_area(text):
    """텍스트에서 전용 면적을 추출합니다."""
    # 패턴 1: "전유부분의 건물의 표시" ~ "갑 구" 또는 "대지권의 표시" 사이
    # 괄호로 감싸져 있을 수 있음: ( 전유부분의 건물의 표시 )
    area_section_match = re.search(
        r"전유부분의\s*건물의\s*표시\s*\)?([\s\S]*?)(?:갑\s*구|대지권의\s*표시)",
        text
    )
    search_text = area_section_match.group(1) if area_section_match else ""

    if search_text:
        # 전유부분 섹션 내에서 면적 찾기
        matches = re.findall(r"(\d+\.\d+)\s*㎡", search_text)
        if matches:
            # 전유부분은 보통 한 개의 면적만 있음 (여러 개면 가장 큰 것)
            largest_area = max(matches, key=lambda x: float(x))
            return f"{largest_area}㎡"

    # 패턴 2: 전유부분 섹션을 못 찾은 경우, 기존 방식 (전체 텍스트에서)
    # 줄바꿈으로 분리된 면적 처리
    clean_text = re.sub(r'구조(\d+)\s*\n\s*\.', r'구조\1.', text)
    clean_text = re.sub(r'\s+', ' ', clean_text)

    matches = re.findall(r"(\d+\.\d+)\s*㎡", clean_text)
    if matches:
        # 아파트 전용면적 범위 (20~200㎡) 내에서 가장 큰 면적 선택
        valid_areas = [m for m in matches if 20 <= float(m) <= 200]
        if valid_areas:
            largest_area = max(valid_areas, key=lambda x: float(x))
            return f"{largest_area}㎡"
        # 유효 범위 없으면 가장 큰 면적
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
    # 건물 내역에 '아파트' 또는 '공동주택'이 있거나, 주소/건물명에 포함된 경우
    # 단, '빌라'인데 이름만 'XX아파트'인 경우를 배제하기 위해 건물내역(구조) 키워드를 우선 봄
    # [수정] '(아파트)', '공동주택', '층아파트' 형태도 인식
    if (re.search(r'건물\s*내역.*?아파트', clean_text) or
        re.search(r'[\d\s\(\[]아파트', clean_text) or
        re.search(r'층아파트', clean_text) or
        re.search(r'공동주택', clean_text)):
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
        if '아파트' in address_match or '공동주택' in address_match:
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
    """
    말소된 등기(삭제된 권리)를 자동으로 제외하고, 현재 유효한 근저당권만 추출합니다.
    순위번호 N(M) 형태 (예: 2(1), 2(2))를 별개로 처리합니다.
    """

    # 1. 주요 등기사항 요약 > 을구 테이블 우선 사용 (가장 정확 - 말소된 것 이미 제외)
    # 형식: "3. (근)저당권 및 전세권 등 ( 을구 )" 섹션
    summary_eul_match = re.search(
        r'3\.\s*\(?근?\)?저당권\s*및\s*전세권\s*등\s*\(\s*을구\s*\)([\s\S]*?)(?:\[\s*참\s*고|$)',
        full_text
    )

    # 을구 본문도 함께 추출 (채무자 정보용)
    eul_gu_body_match = re.search(r'【\s*을\s*구\s*】([\s\S]*?)(?:【|주요\s*등기사항|$)', full_text)
    if not eul_gu_body_match:
        eul_gu_body_match = re.search(r'을\s+구[\s\S]*?소유권\s*이외의\s*권리에\s*관한\s*사항\s*\)([\s\S]*?)(?:주요\s*등기사항\s*요약|$)', full_text)
    eul_gu_body = eul_gu_body_match.group(1) if eul_gu_body_match else ""

    if summary_eul_match:
        # 주요 등기사항 요약 테이블에서 추출 (말소된 것은 이미 제외됨)
        target_text = summary_eul_match.group(1)
        use_summary_mode = True
    else:
        # 을구 본문에서 추출 (말소 필터링 필요)
        target_text = eul_gu_body if eul_gu_body else full_text
        use_summary_mode = False

    if not target_text:
        target_text = full_text
        use_summary_mode = False

    # 2. [핵심] '말소'된 순위 번호 미리 찾기 (Kill List 생성) - 요약 모드가 아닐 때만
    killed_ranks = set()

    if not use_summary_mode:
        clean_all = re.sub(r'\s+', '', target_text)

        # 패턴1: "N번근저당권설정등기...기말소" (전체 말소)
        malso_full = re.findall(r'\d(\d+)번근저당권설정등\d{4}년\d{1,2}월\d{1,2}일\d{4}년\d{1,2}월\d{1,2}일기말소', clean_all)
        for rank in malso_full:
            killed_ranks.add(rank)

        # 패턴2: "N번(M)근저당권설정...일부말소" 또는 "기말소" (부분 말소)
        malso_partial = re.findall(r'\d(\d+)번\((\d+)\)근저당권설정[등기]*.*?(?:일부말소|기말소)', clean_all)
        for main, sub in malso_partial:
            killed_ranks.add(f"{main}({sub})")

        # 패턴3: 전체 텍스트에서 "N번근저당권설정" 뒤에 "말소"가 나오는 경우
        malso_blocks = re.findall(r'((?:\d+번근저당권설정[,]*)+)(?:등기)?말소', clean_all)
        for block in malso_blocks:
            ranks_in_block = re.findall(r'(\d+)번근저당권설정', block)
            for rank in ranks_in_block:
                killed_ranks.add(rank)

    # 3. 순위번호 단위로 텍스트 분리 (N, N-M 형태 모두 포함)
    entries = re.split(r'\n(?=\d+(?:-\d+)?\n)', target_text)

    mortgage_map = {}

    for entry in entries:
        clean_entry = re.sub(r'\s+', ' ', entry).strip()
        if not clean_entry:
            continue

        # 순위번호 파싱: "2 (1)근저당권설정" 또는 "2 근저당권설정" 또는 "2-2 2번(1)근저당권변경"
        rank_match = re.match(r'^(\d+)(?:-(\d+))?\s+(?:\((\d+)\))?', clean_entry)
        if not rank_match:
            continue

        main_rank = rank_match.group(1)
        dash_sub = rank_match.group(2)  # N-M의 M (변경등기 순번)
        paren_sub = rank_match.group(3)  # (N)의 N

        # 변경등기인 경우 (N-M 형태): 대상 순위번호(N)의 금액 업데이트
        # 예: "6-2 근저당권변경" -> main_rank=6의 금액을 업데이트
        if dash_sub and '변경' in clean_entry:
            target_key = main_rank  # N-M에서 N이 대상 순위번호

            # 해당 키가 존재하면 금액 업데이트 (감액/증액 반영)
            if target_key in mortgage_map and target_key not in killed_ranks:
                amount_match = re.search(r'채권최고액\s*금?\s*([\d,]+)\s*원', clean_entry)
                if amount_match:
                    mortgage_map[target_key]['amount_str'] = f"금{amount_match.group(1)}원"
            continue  # 변경등기는 여기서 처리 완료

        # 키 생성: "2" 또는 "2(1)"
        rank_key = f"{main_rank}({paren_sub})" if paren_sub else main_rank

        # [필터링 1] 말소된 순위 건너뜀
        if rank_key in killed_ranks:
            continue
        if main_rank in killed_ranks and not paren_sub:
            continue

        # [필터링 2] 말소 등기 건너뜀
        if '말소' in clean_entry:
            continue

        # 근저당권/질권만 처리
        if "근저당" not in clean_entry and "질권" not in clean_entry:
            continue

        # --- 데이터 추출 ---
        amount_match = re.search(r'채권최고액\s*금?\s*([\d,]+)\s*원', clean_entry)
        current_amount = amount_match.group(1) if amount_match else None

        # 채무자 추출: "채무자 홍길동" 또는 요약 테이블의 "대상소유자" 컬럼
        debtor_match = re.search(r'채무자\s+([가-힣a-zA-Z주식회사]+)', clean_entry)
        if not debtor_match:
            # 주요등기사항 요약 테이블: 마지막 한글 이름이 대상소유자(채무자)
            # 패턴: "근저당권자 OOO  홍길동" (채권자 뒤에 이름)
            debtor_match = re.search(r'근저당권자\s+\S+\s+([가-힣]{2,4})(?:\s|$)', clean_entry)
        current_debtor = debtor_match.group(1) if debtor_match else None

        # 근저당권자/채권자 추출 (은행명에 포함된 지역명은 종료 조건에서 제외)
        # 패턴: "근저당권자 주식회사부산은행" → "주식회사부산은행" 전체 추출
        # 종료 조건: 주민번호(6자리-), 지역명+시/구/동, 또는 문자열 끝
        creditor_match = re.search(r'(?:근저당권자|채권자)\s+([가-힣a-zA-Z0-9\s주식회사은행농협신협새마을금고캐피탈저축]+?)(?=\s+\d{6}-|\s+[가-힣]+[시구동]\s|$)', clean_entry)
        current_creditor = creditor_match.group(1).strip() if creditor_match else None

        date_match = re.search(r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)', clean_entry)
        formatted_date = ""
        if date_match:
            nums = re.findall(r'\d+', date_match.group(1))
            if len(nums) >= 3:
                formatted_date = f"{nums[0]}-{nums[1].zfill(2)}-{nums[2].zfill(2)}"

        # --- 병합 로직 ---
        if rank_key not in mortgage_map:
            mortgage_map[rank_key] = {
                'main_key': main_rank,
                'sub_key': paren_sub,
                'rank_key': rank_key,
                'amount_str': '',
                'debtor': '',
                'creditor': '',
                'date': ''
            }

        if current_amount:
            mortgage_map[rank_key]['amount_str'] = f"금{current_amount}원"
        # 채무자는 최초 설정 값만 사용 (변경등기에서 덮어쓰지 않음)
        if current_debtor and not mortgage_map[rank_key]['debtor']:
            mortgage_map[rank_key]['debtor'] = current_debtor
        # 근저당권자도 최초 설정 값만 사용 (채권자 변경등기에서 덮어쓰지 않음)
        if current_creditor and not mortgage_map[rank_key]['creditor']:
            mortgage_map[rank_key]['creditor'] = current_creditor
        if formatted_date and not mortgage_map[rank_key]['date']:
            mortgage_map[rank_key]['date'] = formatted_date

    # 4. 변경등기 반영 (N-M 형태)
    for entry in entries:
        clean_entry = re.sub(r'\s+', ' ', entry).strip()

        # "2-2 2번(1)근저당권변경" 패턴
        change_match = re.match(r'^(\d+)-(\d+)\s+(\d+)번(?:\((\d+)\))?근저당권변경', clean_entry)
        if change_match:
            target_main = change_match.group(3)
            target_sub = change_match.group(4)
            target_key = f"{target_main}({target_sub})" if target_sub else target_main

            if target_key in mortgage_map and target_key not in killed_ranks:
                amount_match = re.search(r'채권최고액\s*금?\s*([\d,]+)\s*원', clean_entry)
                if amount_match:
                    mortgage_map[target_key]['amount_str'] = f"금{amount_match.group(1)}원"

    # 5. 채무자가 비어있으면 을구 본문에서 찾기
    if eul_gu_body:
        for rank_key, data in mortgage_map.items():
            if not data['debtor']:
                # 을구 본문에서 해당 순위번호의 채무자 찾기
                # 패턴: "순위번호 근저당권설정 ... 채무자 홍길동"
                main_rank = data['main_key']
                # 순위번호 N으로 시작하는 블록에서 채무자 찾기
                debtor_pattern = rf'\n{main_rank}\n[\s\S]*?채무자\s+([가-힣]{{2,4}})'
                debtor_match = re.search(debtor_pattern, eul_gu_body)
                if debtor_match:
                    data['debtor'] = debtor_match.group(1)

    # --- 결과 반환 ---
    results = []

    def sort_key(k):
        data = mortgage_map[k]
        main = int(data['main_key'])
        sub = int(data['sub_key']) if data['sub_key'] else 0
        return (main, sub)

    for key in sorted(mortgage_map.keys(), key=sort_key):
        data = mortgage_map[key]
        if data['amount_str'] or data['creditor']:
            info_parts = []
            if data['amount_str']:
                info_parts.append(f"채권최고액 {data['amount_str']}")
            if data['creditor']:
                info_parts.append(f"근저당권자 {data['creditor']}")

            results.append({
                'main_key': data['rank_key'],
                '설정일자': data['date'],
                '채무자': data['debtor'],
                '주요등기사항': " ".join(info_parts)
            })

    return {"근저당권": results}


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


def check_land_ownership_right(text):
    """
    등기부등본에서 소유권대지권 존재 여부를 확인합니다.
    '대지권의 표시' 영역에서 '소유권 대지권' 텍스트가 있는지 확인합니다.

    Returns:
        bool: True=소유권대지권 있음, False=없음
    """
    try:
        # 대지권의 표시 영역 찾기
        land_section = re.search(
            r"대지권의\s*표시([\s\S]*?)(?:갑\s*구|【\s*갑\s*구|$)",
            text
        )
        if land_section:
            section_text = land_section.group(1)
            # '소유권 대지권' 또는 '소유권대지권' 패턴 검색
            if re.search(r"소유권\s*대지권", section_text):
                print("[DEBUG] 소유권대지권 확인됨")
                return True

        # 대지권의 표시 영역 자체가 없는 경우도 없음으로 처리
        print("[DEBUG] 소유권대지권 없음 또는 대지권 영역 미발견")
        return False
    except Exception as e:
        print(f"소유권대지권 확인 중 오류: {e}")
        return False


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
            # entry 전체에서 '말소' 키워드 확인 (여러 줄에 걸쳐 있을 수 있음)
            if '말소' in entry:
                # 여러 개의 압류/가압류가 한꺼번에 말소될 수 있음
                # 예: "5번가압류, 6번가압류, 7번가압류, 8번가압류, 9번임의경매개시결정 등기말소"
                cancelled_matches = re.findall(r'(\d{1,2})번(?:가압류|압류)', entry)
                for rank in cancelled_matches:
                    cancelled_ranks.add(rank)
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

def get_legal_code_from_juso_api(address):
    """행정안전부 도로명주소 API를 통해 주소를 10자리 법정동코드로 변환합니다."""
    JUSO_API_KEY = "U01TX0FVVEgyMDI2MDEyMTE0MjUwMzExNzQ3MTg="

    # 주소에서 건물명 추출 (아파트명 등)
    building_pattern = r'([가-힣a-zA-Z0-9]+(?:아파트|파크|타운|빌|캐슬|스카이뷰|힐스테이트|자이|푸르지오|래미안|e편한세상|센트럴|더샵|롯데캐슬|트리풀시티|시티|타워|하이츠|빌라|맨션|팰리스|프라자)[가-힣a-zA-Z0-9]*)'
    building_match = re.search(building_pattern, address)
    building_name = building_match.group(1) if building_match else ''

    # 시군구 추출
    sigungu_match = re.search(r'([가-힣]+시\s+[가-힣]+구|[가-힣]+시|[가-힣]+군)', address)
    sigungu = sigungu_match.group(1) if sigungu_match else ''

    # 검색 키워드: 시군구 + 건물명
    search_keyword = f"{sigungu} {building_name}".strip() if building_name else address.split()[0:3]
    if isinstance(search_keyword, list):
        search_keyword = ' '.join(search_keyword)

    print(f"[행정안전부 API] 검색 키워드: {search_keyword}")

    params = {
        'keyword': search_keyword,
        'confmKey': JUSO_API_KEY,
        'countPerPage': '5',
        'resultType': 'json'
    }

    try:
        response = requests.post('https://business.juso.go.kr/addrlink/addrLinkApi.do',
                                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                                data=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get('results', {}).get('juso'):
                juso = data['results']['juso'][0]
                # admCd가 10자리 행정동코드
                adm_cd = juso.get('admCd', '')
                # bdMgtSn에서 법정동코드 추출 (앞 10자리가 시군구+법정동)
                bd_mgt_sn = juso.get('bdMgtSn', '')

                if bd_mgt_sn and len(bd_mgt_sn) >= 10:
                    # bdMgtSn 구조: 시군구(5) + 법정동(5) + 대지구분(1) + 번(4) + 지(4) + 기타
                    legal_code = bd_mgt_sn[:10]
                    print(f"[행정안전부 API] 법정동코드 추출 성공: {legal_code}")
                    return legal_code

                print(f"[행정안전부 API] bdMgtSn 없음 또는 형식 오류")
            else:
                print(f"[행정안전부 API] 검색 결과 없음")
        else:
            print(f"[행정안전부 API] 응답 오류: {response.status_code}")

    except Exception as e:
        print(f"[행정안전부 API 오류] {e}")

    return ""

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

        # 시군구 코드와 법정동 코드는 legal_code_data.py에서 import됨
        # (sigungu_map: 시군구 86개, bjdong_map: 법정동 2,892개)

        # 1. 시군구 코드 찾기 (가장 긴 매칭을 찾아서 더 구체적인 주소 우선)
        sigungu_cd = None
        matched_city = ""
        for city, code in sigungu_map.items():
            if city in address and len(city) > len(matched_city):
                sigungu_cd = code
                matched_city = city

        if not sigungu_cd:
            print(f"[주소 파싱] 시군구 코드를 찾을 수 없습니다")
            return result

        print(f"[주소 파싱] 시군구 매칭: {matched_city} -> {sigungu_cd}")
        result['sigunguCd'] = sigungu_cd

        # 2. 법정동 코드 찾기 (가장 구체적인 매칭 우선: 리/동 > 읍/면)
        bjdong_cd = None
        matched_dong = ""
        matched_priority = 0  # 0: 없음, 1: 읍/면, 2: 리/동

        for (sig_cd, dong_name), code in bjdong_map:
            if sig_cd == sigungu_cd and dong_name in address:
                # 우선순위 계산: 리/동이 읍/면보다 높음
                priority = 2 if dong_name.endswith(('리', '동')) else 1

                # 더 높은 우선순위이거나, 같은 우선순위에서 더 긴 매칭
                if priority > matched_priority or (priority == matched_priority and len(dong_name) > len(matched_dong)):
                    bjdong_cd = code
                    matched_dong = dong_name
                    matched_priority = priority

        if not bjdong_cd:
            print(f"[주소 파싱] 법정동 코드를 찾을 수 없습니다")
            return result

        print(f"[주소 파싱] 법정동 매칭: {matched_dong} -> {bjdong_cd}")
        result['bjdongCd'] = bjdong_cd

        # 3. 번지 추출
        # 패턴: "동1가 46-8", "동 123-45", "리 67" 등
        # - 법정동명 뒤의 번지를 추출
        # - 법정동명이 정확히 매칭된 위치 이후에서 번지 찾기
        bungi_match = None

        # 매칭된 법정동 이후 위치에서 번지 찾기
        if matched_dong:
            dong_pos = address.find(matched_dong)
            if dong_pos != -1:
                after_dong = address[dong_pos + len(matched_dong):]
                # 법정동 바로 뒤의 번지 추출 (공백 + 숫자)
                bungi_match = re.search(r'^\s+(\d+)(?:-(\d+))?', after_dong)

        # fallback: 기존 방식 (리/동/가/로 뒤의 번지)
        if not bungi_match:
            bungi_match = re.search(r'[리동가로]\s+(\d+)(?:-(\d+))?', address)
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

    def call_building_api(params):
        """건축물대장 API 호출 헬퍼 함수"""
        service_key = "B6F8mdWu8MpnYUwgzs84AWBmkZG3B2l+ItDSFbeL64CxbxJORed+4LpR5uMHxebO/v7LSHBXm1FHFJ8XE6UHqA=="
        params['serviceKey'] = unquote(service_key)
        params['platGbCd'] = '0'
        params['numOfRows'] = '100'
        params['pageNo'] = '1'

        # 총괄표제부 API 호출
        url = 'https://apis.data.go.kr/1613000/BldRgstHubService/getBrRecapTitleInfo'
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            root = ET.fromstring(response.text)
            if root.findtext('.//resultCode') == '00':
                items = root.findall('.//item')
                if items:
                    total_hhld = 0
                    comp_date = ""
                    for item in items:
                        h_cnt = item.findtext('hhldCnt') or '0'
                        u_date = item.findtext('useAprDay') or ''
                        if h_cnt.isdigit():
                            total_hhld += int(h_cnt)
                        if u_date and not comp_date:
                            comp_date = u_date
                    return {'success': True, 'households': total_hhld, 'date': comp_date}

        # 표제부 API fallback
        url = 'https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo'
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            root = ET.fromstring(response.text)
            if root.findtext('.//resultCode') == '00':
                items = root.findall('.//item')
                if items:
                    total_hhld = 0
                    comp_date = ""
                    exclude_keywords = ['주상가', '상가', '관리동', '부대시설', '커뮤니티', '관리', '근린생활']
                    for item in items:
                        dong_nm = item.findtext('dongNm') or ''
                        etc_purps = item.findtext('etcPurps') or ''
                        h_cnt = item.findtext('hhldCnt') or '0'
                        u_date = item.findtext('useAprDay') or ''
                        is_excluded = any(keyword in dong_nm or keyword in etc_purps for keyword in exclude_keywords)
                        if not is_excluded and h_cnt.isdigit():
                            total_hhld += int(h_cnt)
                        if u_date and not comp_date:
                            comp_date = u_date
                    if total_hhld > 0:
                        return {'success': True, 'households': total_hhld, 'date': comp_date}

        return {'success': False, 'households': 0, 'date': ''}

    try:
        # 1. 주소 파싱 실행
        parsed = parse_address_for_building_api(address)
        if not parsed['success']:
            print(f"[건축물대장] 주소 분석 실패: {address}")
            return result

        params = {
            'sigunguCd': parsed['sigunguCd'],
            'bjdongCd': parsed['bjdongCd'],
            'bun': parsed['bun'],
            'ji': parsed['ji'],
        }

        # 2. 첫 번째 시도: 파싱된 법정동 코드로 조회
        api_result = call_building_api(params.copy())

        if api_result['success']:
            result['success'] = True
            result['total_households'] = api_result['households']
            result['raw_completion_date'] = api_result['date']
            if len(api_result['date']) == 8:
                result['completion_date'] = f"{api_result['date'][:4]}-{api_result['date'][4:6]}-{api_result['date'][6:8]}"
            print(f"[건축물대장] 조회 성공: {result['total_households']}세대, 준공일 {result['completion_date']}")
            return result

        # 3. 두 번째 시도: 행정안전부 도로명주소 API로 정확한 법정동코드 가져와서 재시도
        print(f"[건축물대장] 첫 번째 시도 실패, 행정안전부 API로 법정동코드 재조회...")
        b_code = get_legal_code_from_juso_api(address)

        if b_code and len(b_code) == 10:
            # 행정안전부 API의 10자리 법정동코드에서 시군구(5자리)와 법정동(5자리) 추출
            juso_sigungu = b_code[:5]
            juso_bjdong = b_code[5:]

            print(f"[건축물대장] 행정안전부 API 법정동코드: 시군구={juso_sigungu}, 법정동={juso_bjdong}")

            params['sigunguCd'] = juso_sigungu
            params['bjdongCd'] = juso_bjdong

            api_result = call_building_api(params.copy())

            if api_result['success']:
                result['success'] = True
                result['total_households'] = api_result['households']
                result['raw_completion_date'] = api_result['date']
                if len(api_result['date']) == 8:
                    result['completion_date'] = f"{api_result['date'][:4]}-{api_result['date'][4:6]}-{api_result['date'][6:8]}"
                print(f"[건축물대장] 행정안전부 API 재시도 성공: {result['total_households']}세대, 준공일 {result['completion_date']}")
                return result

        print(f"[건축물대장] 조회 실패: {address}")

    except Exception as e:
        print(f"[건축물대장 조회 오류] {e}")
        import traceback
        traceback.print_exc()
    return result
