import re
import requests

_KB_HEADERS = {
    'origin': 'https://kbland.kr',
    'referer': 'https://kbland.kr/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    'accept': 'application/json, text/plain, */*',
    'webservice': '1',
}


def _search_complex_candidates(keyword, limit=5):
    """아파트명으로 KB 단지 검색. 후보 리스트 전체 반환 (동명이인 단지 구분용)."""
    r = requests.get(
        'https://api.kbland.kr/land-complex/serch/intgraSerch',
        params={
            '검색설정명': 'SRC_NTOTAL',
            '검색키워드': keyword,
            '출력갯수': str(limit),
            '페이지설정값': '1',
        },
        headers=_KB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    return data.get('dataBody', {}).get('data', {}).get('data', {}).get('HSCM', {}).get('data', [])


def _search_complex(keyword):
    """아파트명으로 KB 단지 검색. 첫 번째 결과 반환."""
    items = _search_complex_candidates(keyword)
    return items[0] if items else None


def _get_price(complex_no, sqrmsr_no):
    """단지번호 + 면적일련번호로 KB 시세 조회. 매매일반가(만원) 반환."""
    r = requests.get(
        'https://api.kbland.kr/land-price/price/BasePrcInfoNew',
        params={'단지기본일련번호': complex_no, '면적일련번호': sqrmsr_no},
        headers=_KB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    시세목록 = data.get('dataBody', {}).get('data', {}).get('시세', [])
    if not 시세목록:
        return None

    항목 = 시세목록[0]
    return {
        '매매일반가': 항목.get('매매일반거래가') or 0,
        '매매상한가': 항목.get('매매상한가') or 0,
        '매매하한가': 항목.get('매매하한가') or 0,
        '전용면적':   항목.get('전용면적') or 0,
        '면적일련번호': 항목.get('면적일련번호') or 0,
    }


def _find_best_sqrmsr(complex_no, target_area_m2, tolerance=0.01):
    """typInfo API로 전용면적과 정확히 일치(오차 tolerance 이내)하는 면적일련번호를 반환.

    일치하는 면적이 없으면 None을 반환한다. 가장 가까운 값으로 임의 대체하지 않는다 -
    다른 평형의 시세를 요청한 평형의 시세인 것처럼 반환하면 안 되기 때문.
    """
    r = requests.get(
        'https://api.kbland.kr/land-complex/complex/typInfo',
        params={'단지기본일련번호': complex_no},
        headers=_KB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    items = r.json().get('dataBody', {}).get('data', [])
    if not items:
        return None

    for item in items:
        try:
            exclusive_area = float(item.get('전용면적') or 0)
            sqrmsr_no = item.get('면적일련번호')
        except (ValueError, TypeError):
            continue
        if not sqrmsr_no or not exclusive_area:
            continue
        if abs(exclusive_area - target_area_m2) <= tolerance:
            return sqrmsr_no

    return None


def _get_complex_main(complex_no):
    """complex/main API로 단지 상세정보(사용승인일, 세대수, 동수, 층수 등) 조회."""
    r = requests.get(
        'https://api.kbland.kr/land-complex/complex/main',
        params={'단지기본일련번호': complex_no},
        headers=_KB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    body = r.json().get('dataBody', {}).get('data', {})
    if not body:
        return {}

    use_apr_day = body.get('준공년월일', '')
    total_households = body.get('총세대수', 0)
    dong_cnt = body.get('총동수', 0)
    max_floor = body.get('최고층수', 0)
    min_floor = body.get('최저층수', 0)

    # "2023.04.17" → "2023-04-17"
    completion_date = ''
    if use_apr_day and isinstance(use_apr_day, str) and '.' in use_apr_day:
        completion_date = use_apr_day.replace('.', '-')

    return {
        'completion_date': completion_date,
        'total_households': int(total_households) if total_households else 0,
        'dong_cnt': int(dong_cnt) if dong_cnt else 0,
        'max_floor': int(max_floor) if max_floor else 0,
        'min_floor': int(min_floor) if min_floor else 0,
    }


def _get_rcns_info(complex_no):
    """rcnsInfo API로 재건축 현재 진행 단계 조회. 재건축 아니면 None 반환."""
    r = requests.get(
        'https://api.kbland.kr/land-complex/complex/rcnsInfo',
        params={'단지기본일련번호': complex_no},
        headers=_KB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    body = r.json().get('dataBody', {})
    if body.get('resultCode') != 11000 or not body.get('data'):
        return None
    vals = list(body['data'].values())
    step_no = vals[23] if len(vals) > 23 else 0
    step_name = vals[13] if len(vals) > 13 else ''
    if not step_no:
        return None
    step_names = {
        1: '기본계획수립', 2: '재건축진단', 3: '정비구역지정',
        4: '추진위원회승인', 5: '조합설립인가', 6: '사업시행인가',
        7: '관리처분인가', 8: '이주및철거', 9: '일반분양',
    }
    return {
        'step_no': step_no,
        'step_name': step_names.get(step_no, step_name),
    }


def get_kb_info(address, target_area_m2=None):
    """
    주소(또는 아파트명)와 전용면적으로 KB 시세/세대수/준공일 조회.

    Args:
        address (str): 전체 주소 또는 아파트명 (예: "광명삼익아파트" 또는 전체 주소)
        target_area_m2 (float|None): 전용면적(㎡). None이면 대표면적 사용.

    Returns:
        dict: {
            'success': bool,
            'kb_price': int,        # 매매일반가 (만원)
            'kb_price_high': int,   # 매매상한가 (만원)
            'kb_price_low': int,    # 매매하한가 (만원)
            'total_households': int,# 세대수
            'completion_date': str, # 준공년월 (YYYY-MM 형식)
            'complex_no': str,      # KB 단지번호
            'complex_name': str,    # 단지명
            'area_m2': float,       # 조회된 전용면적
        }
    """
    result = {
        'success': False,
        'kb_price': 0,
        'kb_price_high': 0,
        'kb_price_low': 0,
        'total_households': 0,
        'completion_date': '',
        'complex_no': '',
        'complex_name': '',
        'area_m2': 0.0,
        'dong_cnt': 0,
        'max_floor': 0,
        'min_floor': 0,
        'rcns_info': None,
        'error': '',
    }

    try:
        # 주소에서 구성요소 추출
        sigungu_match = re.search(r'([가-힣]+시\s*[가-힣]*구|[가-힣]+시|[가-힣]+군)', address)
        dong_match = re.search(r'([가-힣]+[동읍면리가](?:\d가)?)', address)
        beonji_match = re.search(r'[동읍면리가]\s+(\d+(?:-\d+)?)', address)
        sigungu = sigungu_match.group(1).replace(' ', '') if sigungu_match else ''
        dong = dong_match.group(1) if dong_match else ''
        beonji = beonji_match.group(1) if beonji_match else ''

        # 아파트명 추출 (아파트 접미사 제거)
        apt_match = re.search(
            r'([가-힣a-zA-Z0-9]+(?:아파트|파크|타운|빌|캐슬|스카이뷰|힐스테이트|자이|푸르지오|래미안|e편한세상|센트럴|더샵|롯데캐슬|시티|타워|하이츠|빌라|맨션|팰리스|삼익|현대|대우|주공|한양|한신|두산|벽산|LG|lg)[가-힣a-zA-Z0-9]*)',
            address
        )
        apt_keyword = ''
        if apt_match:
            apt_keyword = re.sub(r'아파트$', '', apt_match.group(1)).strip()

        # 도로명주소 + 괄호 병기 형식 처리 (예: "영동대로 220, 7동 1001호 (대치동, 쌍용아파트)")
        # 괄호 안에 실제 행정동명과 정확한 건물명(차수 포함)이 병기되는 관행을 우선 활용.
        # 괄호 밖 정규식은 "영동대로"의 "영동"을 동으로, "1001호"를 번지로 오인식하는 등
        # 도로명 표기를 지번 표기로 착각하기 쉬우므로, 괄호 정보가 있으면 그쪽을 신뢰한다.
        paren_match = re.search(r'\(([^)]+)\)', address)
        paren_dong = ''
        paren_apt_keyword = ''
        if paren_match:
            paren_content = paren_match.group(1)
            paren_dong_match = re.search(r'([가-힣]+[동읍면리](?:\d가)?)', paren_content)
            if paren_dong_match:
                paren_dong = paren_dong_match.group(1)
            paren_apt_match = re.search(
                r'([가-힣a-zA-Z0-9]+(?:\d+차)?(?:아파트|파크|타운|빌|캐슬|스카이뷰|힐스테이트|자이|푸르지오|래미안|e편한세상|센트럴|더샵|롯데캐슬|시티|타워|하이츠|빌라|맨션|팰리스|삼익|현대|대우|주공|한양|한신|두산|벽산|LG|lg)[가-힣a-zA-Z0-9]*)',
                paren_content
            )
            if paren_apt_match:
                paren_apt_keyword = re.sub(r'아파트$', '', paren_apt_match.group(1)).strip()

        # 괄호 정보가 있으면 동/건물명을 그쪽으로 교체 (더 신뢰도 높음).
        # 괄호 밖에서 뽑은 번지(beonji)는 도로명 표기를 오인식한 값(예: "1001호"→"1001")일
        # 수 있어 신뢰할 수 없으므로 함께 버린다.
        if paren_dong:
            dong = paren_dong
            beonji = ''
        if paren_apt_keyword:
            apt_keyword = paren_apt_keyword

        def _is_address_match(item, check_beonji=False, check_dong=False):
            """시군구/동 일치 여부 확인. check_beonji=True면 번지 정확 일치도 확인."""
            bub_addr = item.get('BUBADDR', '') or item.get('NEWADDRESS', '') or ''
            if sigungu and sigungu[:3] not in bub_addr:
                return False
            if check_dong and dong and dong not in bub_addr:
                return False
            if check_beonji and beonji:
                arno_raw = (item.get('ARNO', '') or '').strip()
                # KB는 ARNO를 "65", "102-3" 같은 순수 번지 외에 "65번지 일대"처럼
                # 서술형으로도 반환하므로, 앞쪽 숫자(-숫자) 패턴만 뽑아 비교한다.
                arno_match = re.match(r'(\d+(?:-\d+)?)', arno_raw)
                arno = arno_match.group(1) if arno_match else arno_raw
                # ARNO가 원본 번지와 정확히 일치하거나 원본 번지로 시작해야 함
                # 예: beonji="102-3", arno="102-3" → 일치
                # 예: beonji="736", arno="736-24" → 불일치 (736이 포함된 다른 번지)
                if arno and arno != beonji and not arno.startswith(beonji + '-'):
                    return False
            return True

        ambiguous_no_area_match = False  # 동명이인 후보가 여럿인데 어느 곳에도 목표 면적이 없었던 경우

        def _pick_among_candidates(keyword, check_beonji, check_dong):
            """검색 결과 후보들을 주소로 1차 필터링한 뒤, 후보가 여럿이고
            target_area_m2가 주어졌으면 실제 면적일련번호가 존재하는 후보를 우선 채택한다.
            (동명이인 단지 - 예: "쌍용대치1차" vs "쌍용2차" - 를 면적으로 구분)
            """
            nonlocal ambiguous_no_area_match
            candidates = _search_complex_candidates(keyword)
            matched = [c for c in candidates if _is_address_match(c, check_beonji=check_beonji, check_dong=check_dong)]
            if not matched:
                return None
            if len(matched) == 1:
                return matched[0]
            if not target_area_m2:
                # 후보가 여럿인데 면적 정보가 없어 구분 불가 - 1순위로 폴백하되 불확실함을 남긴다.
                print(f"[KB API] 경고: 후보 {len(matched)}개 중 면적 정보 없이 1순위로 임의 선택")
                ambiguous_no_area_match = True
                return matched[0]
            for cand in matched:
                try:
                    if _find_best_sqrmsr(cand['COMPLEX_NO'], target_area_m2):
                        print(f"[KB API] 후보 {len(matched)}개 중 면적 일치로 선택: {cand.get('HSCM_NM')} ({cand['COMPLEX_NO']})")
                        return cand
                except Exception:
                    continue
            # 어느 후보에도 목표 면적이 없으면 1순위 후보로 폴백하되, 불확실했다는 사실을 남긴다.
            print(f"[KB API] 경고: 후보 {len(matched)}개 모두 면적({target_area_m2}㎡) 불일치 - 1순위로 임의 폴백")
            ambiguous_no_area_match = True
            return matched[0]

        item = None

        # 1순위: 동+번지 검색 (예: "작전동 102-3"), 번지 + 건물명 교차 검증
        if dong and beonji:
            kw1 = f"{dong} {beonji}"
            print(f"[KB API] 1순위 검색 (동+번지): {kw1}")
            item = _search_complex(kw1)
            if item:
                if not _is_address_match(item, check_beonji=True):
                    print(f"[KB API] 번지 불일치 ('{item.get('ARNO')}' ≠ '{beonji}'), 무시")
                    item = None
                elif apt_keyword:
                    # 건물명이 있으면 단지명에 핵심 키워드가 포함되는지 교차 확인
                    complex_nm = item.get('HSCM_NM', '')
                    # apt_keyword의 앞 2~3글자가 단지명에 포함되면 일치로 판단
                    apt_core = apt_keyword[:3]
                    if apt_core and apt_core not in complex_nm:
                        print(f"[KB API] 건물명 불일치 ('{complex_nm}' ≠ '{apt_keyword}'), 2순위로")
                        item = None

        # 2순위: 동+건물명 검색 (예: "대치동 쌍용2차") - 번지를 신뢰할 수 없을 때(도로명주소 등)
        # 건물명이 흔한 이름이라도 동명을 함께 검증해 동명이인 단지를 걸러낸다.
        # 동일 동에 같은 이름 계열 단지가 여럿이면(예: 쌍용대치1차/쌍용2차) 면적으로 재구분한다.
        if not item and dong and apt_keyword:
            kw2 = f"{dong} {apt_keyword}"
            print(f"[KB API] 2순위 검색 (동+건물명): {kw2}")
            item = _pick_among_candidates(kw2, check_beonji=False, check_dong=True)
            if not item:
                print(f"[KB API] 2순위 매칭 실패, 3순위로")

        # 3순위: 건물명(아파트 제거)만 검색 (예: "뉴서울", "광명삼익"), 시군구+동 검증
        if not item and apt_keyword:
            print(f"[KB API] 3순위 검색 (건물명): {apt_keyword}")
            item = _pick_among_candidates(apt_keyword, check_beonji=False, check_dong=True)

        if not item:
            print(f"[KB API] 단지 검색 실패")
            return result

        complex_no = item['COMPLEX_NO']
        complex_name = item.get('HSCM_NM', '')
        sqrmsr_no = item.get('RPSNT_SQRMSR_NO')
        households = int(item.get('THS_NUM', 0) or 0)

        print(f"[KB API] 단지: {complex_name} (번호: {complex_no}, 면적번호: {sqrmsr_no})")

        # complex/main으로 사용승인일·세대수·동수·층수 조회
        main_data = {}
        try:
            main_data = _get_complex_main(complex_no)
            print(f"[KB API] 사용승인일={main_data.get('completion_date')}, 세대수={main_data.get('total_households')}, 동수={main_data.get('dong_cnt')}, 최고층={main_data.get('max_floor')}")
        except Exception as e:
            print(f"[KB API] complex/main 조회 실패: {e}")

        result['complex_no'] = complex_no
        result['complex_name'] = complex_name
        result['total_households'] = main_data.get('total_households') or households
        result['completion_date'] = main_data.get('completion_date', '')
        result['dong_cnt'] = main_data.get('dong_cnt', 0)
        result['max_floor'] = main_data.get('max_floor', 0)
        result['min_floor'] = main_data.get('min_floor', 0)

        # 3. 전용면적에 맞는 면적일련번호 찾기 (정확히 일치해야 함 - 근사치 대체 금지)
        if target_area_m2:
            found = _find_best_sqrmsr(complex_no, target_area_m2)
            if found:
                sqrmsr_no = found
                print(f'[KB API] 면적 매칭: target={target_area_m2}㎡ → 면적번호={sqrmsr_no}')
            else:
                print(f'[KB API] 면적 매칭 실패: target={target_area_m2}㎡ 와 일치하는 타입이 단지에 없음')
                if ambiguous_no_area_match:
                    result['error'] = (
                        f'동일한 이름의 단지가 여러 곳 검색되었고, 어느 곳에도 '
                        f'요청 전용면적({target_area_m2}㎡)과 일치하는 타입이 없어 단지를 특정할 수 없습니다. '
                        f'"{complex_name}"(으)로 임의 선택했으니 반드시 확인하세요.'
                    )
                else:
                    result['error'] = f'요청 전용면적({target_area_m2}㎡)과 일치하는 타입이 KB 시세에 없습니다.'
                result['complex_no'] = complex_no
                result['complex_name'] = complex_name
                return result
        elif ambiguous_no_area_match:
            # 면적 정보 없이 동명이인 후보 중 하나를 임의로 골랐으므로, 시세가 나와도 확인이 필요함을 알린다.
            result['error'] = f'참고: "{complex_name}"과(와) 이름이 비슷한 단지가 여러 곳 검색되어 임의로 선택했습니다. 단지가 맞는지 확인하세요.'

        # 4. 시세 조회
        if sqrmsr_no:
            price_data = _get_price(complex_no, sqrmsr_no)
            if price_data:
                kb_price = price_data.get('매매일반가') or 0
                result['kb_price'] = int(kb_price) if kb_price else 0
                result['kb_price_high'] = int(price_data.get('매매상한가') or 0)
                result['kb_price_low'] = int(price_data.get('매매하한가') or 0)
                result['area_m2'] = float(price_data.get('전용면적') or 0)
                print(f"[KB API] 시세: {result['kb_price']}만원 ({result['area_m2']}㎡)")

        # 5. 재건축/재개발 단계 조회
        try:
            rcns = _get_rcns_info(complex_no)
            if rcns:
                result['rcns_info'] = rcns
                print(f"[KB API] 재건축 단계: {rcns['step_no']}단계 {rcns['step_name']}")
        except Exception:
            pass

        result['success'] = True
        return result

    except Exception as e:
        print(f"[KB API 오류] {e}")
        import traceback
        traceback.print_exc()
        return result


# 테스트
if __name__ == "__main__":
    tests = [
        ("경기도 광명시 소하동 45-3 광명삼익아파트 제101동 제1406호", 84.98),
        ("서울특별시 강남구 역삼동 736 역삼래미안 제101동 제101호", 80.87),
        ("인천광역시 계양구 작전동 102-3 뉴서울아파트 제1동 제6층 제602호", 39.24),
    ]
    for addr, area in tests:
        print(f"\n{'='*50}")
        print(f"주소: {addr}")
        r = get_kb_info(addr, area)
        print(f"결과: KB시세={r['kb_price']}만원, 세대수={r['total_households']}, 준공={r['completion_date']}, 성공={r['success']}")
