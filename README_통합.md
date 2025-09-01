# LTV 프로젝트 통합 백업

## 📋 프로젝트 개요
부동산 담보대출 LTV(Loan to Value) 계산 및 관리 시스템

## 📁 파일 구조
```
LTV_프로젝트_통합백업/
├── app.py                          # Flask 메인 애플리케이션
├── history_manager_flask.py        # 고객 관리 (Notion 연동)
├── ltv_map.py                      # 지역별 방공제 정보
├── pdf_parser.py                   # PDF 파싱 (기본버전)
├── pdf_parser_fixed.py             # PDF 파싱 (개선버전)
├── utils.py                        # 유틸리티 함수들
├── requirements.txt                # Python 패키지 의존성
├── notion_integration.py           # Notion API 통합
├── CLAUDE.md                       # Claude 작업 히스토리
├── static/                         # 정적 파일들
│   ├── css/style.css              # 스타일시트
│   └── js/script.js               # JavaScript
├── templates/                      # HTML 템플릿
│   ├── entry.html                 # 기본 입력 페이지
│   ├── simple_entry.html          # 단순 입력 페이지 (추천)
│   └── manifest.json              # 웹앱 매니페스트
├── uploads/                        # PDF 업로드 폴더
├── debug_pdf_text.py              # PDF 텍스트 디버깅 도구
├── fixed_area_extraction.py       # 면적 추출 개선 도구
├── robust_area_extractor.py       # 강화된 면적 추출기
├── test_area_extraction.py        # 면적 추출 테스트
├── test_pdf_parsing.py            # PDF 파싱 테스트
└── notion_setup_guide.md          # Notion 설정 가이드
```

## 🚀 주요 기능

### 1. LTV 계산기
- **KB시세 기반 계산**: 담보물 가치 평가
- **방공제 자동 적용**: 지역별 방공제 금액 자동 설정
- **다중 LTV 비율**: 동시에 여러 비율로 계산
- **대출 상태 관리**: 대환/선말소/유지 등 상태별 분류

### 2. PDF 자동 파싱
- **등기부등본 업로드**: 드래그 앤 드롭으로 간편 업로드
- **자동 정보 추출**: 고객명, 주소, 면적 자동 추출
- **PDF 뷰어 내장**: 업로드한 문서를 바로 확인

### 3. 고객 관리 시스템
- **Notion 데이터베이스 연동**: 고객 정보 자동 저장
- **상담 이력 관리**: 계산 결과 및 메모 저장
- **검색 및 조회**: 기존 고객 정보 빠른 검색

### 4. AI 상담 기능
- **OpenAI GPT 연동**: 실시간 LTV 상담
- **컨텍스트 인식**: 현재 입력 데이터 기반 맞춤 답변
- **전문 용어 설명**: 방공제, 대환, 선말소 등 용어 해설

## 🔧 설치 및 실행

### 1. 환경 설정
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
# .env 파일 생성
OPENAI_API_KEY=your_openai_api_key_here
NOTION_API_KEY=your_notion_api_key_here
NOTION_DATABASE_ID=your_database_id_here
```

### 3. 실행
```bash
python app.py
```

## 📱 사용법

### 기본 워크플로우
1. **PDF 업로드**: 등기부등본을 드래그 앤 드롭으로 업로드
2. **정보 확인**: 자동 추출된 정보 확인 및 수정
3. **KB시세 입력**: 현재 시세 정보 입력
4. **방공제 설정**: 지역 선택으로 자동 설정
5. **대출 정보 입력**: 기존 대출 정보 등록
6. **LTV 계산**: 원클릭으로 한도 및 가용액 계산
7. **결과 확인**: 상세한 계산 결과 및 메모 생성

### 추천 템플릿
- **simple_entry.html**: 사용하기 쉬운 인터페이스
- 좌우 분할 레이아웃으로 PDF와 입력 폼 동시 확인
- 크기 조절 가능한 반응형 디자인

## 🛠️ 기술 스택
- **Backend**: Flask, Python
- **Frontend**: HTML5, Bootstrap 5, JavaScript
- **AI**: OpenAI GPT-4
- **Database**: Notion API
- **PDF Processing**: PyPDF2, pdfplumber
- **File Upload**: Werkzeug

## 📋 업데이트 히스토리

### v2.0 (통합 백업)
- 여러 백업 폴더 통합
- PDF 파싱 성능 개선
- AI 상담 기능 추가
- 면적 추출 알고리즘 강화

### v1.5 (개선 버전)
- Notion 연동 기능 추가
- PDF 뷰어 내장
- 반응형 UI 개선

### v1.0 (초기 버전)
- 기본 LTV 계산 기능
- PDF 업로드 및 파싱
- 간단한 웹 인터페이스

## 🔍 디버깅 도구
- **debug_pdf_text.py**: PDF 텍스트 추출 확인
- **test_area_extraction.py**: 면적 추출 테스트
- **test_pdf_parsing.py**: 전체 파싱 프로세스 테스트

## 📞 지원 및 문의
이 통합 백업은 여러 버전의 LTV 프로젝트를 하나로 합친 것입니다.
각 파일의 기능과 사용법은 개별 파일의 주석을 참고하세요.

---
**최종 업데이트**: 2025년 8월 29일
**통합 버전**: v2.0