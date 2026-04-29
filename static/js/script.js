/**
 * ============================================================
 * LTV 계산기 메인 스크립트
 * ============================================================
 * 파일 구조:
 * 1. 초기화 변수 (라인 1-3)
 * 2. 기본 UI 함수 (라인 4-170)
 * 3. 파싱/포맷팅 유틸 함수 (라인 249-320)
 * 4. 클라이언트 계산 함수 (라인 321-435)
 * 5. UI/UX 함수 - 드래그, 리사이즈, 레이아웃 (라인 332-1800)
 * 6. 대출 항목 관련 함수 (라인 386-500)
 * 7. 이벤트 리스너 함수 (라인 622-1476)
 * 8. 서버 API 호출 함수 (라인 718-1955)
 * 9. 기타 유틸 함수 (라인 1970-2100)
 * ============================================================
 */

    let loanItemCounter = 0;
    let memoDebounceTimeout;
    let meritzRegion = '1gun'; // 메리츠 지역 선택 (1gun = 1군, 2gun = 2군)

    // ========================================================
    // 1. Helper 함수 - 안전한 요소 접근
    // ========================================================
    function safeSetValue(elementId, value) {
        const el = document.getElementById(elementId);
        if (el) {
            el.value = value;
        } else {
            console.warn(`⚠️ Element not found: ${elementId}`);
        }
    }

    // ========================================================
    // 2. 기본 UI 함수
    // ========================================================
    // 커스텀 알림창 함수 (닫기 버튼으로 즉시 닫힘)
    function showCustomAlert(message, callback = null) {
        // 기존 알림창이 있으면 제거
        const existingAlert = document.getElementById('custom-alert-overlay');
        if (existingAlert) {
            existingAlert.remove();
        }

        // 오버레이와 모달 생성
        const overlay = document.createElement('div');
        overlay.id = 'custom-alert-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
        `;

        const modal = document.createElement('div');
        modal.style.cssText = `
            background: white;
            border-radius: 8px;
            padding: 24px;
            max-width: 400px;
            margin: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            text-align: center;
        `;

        const messageDiv = document.createElement('div');
        messageDiv.textContent = message;
        messageDiv.style.cssText = `
            margin-bottom: 20px;
            font-size: 16px;
            line-height: 1.4;
            color: #333;
        `;

        const closeBtn = document.createElement('button');
        closeBtn.textContent = '닫기';
        closeBtn.style.cssText = `
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
        `;

        closeBtn.addEventListener('click', () => {
            overlay.remove();
            if (callback) callback();
        });

        // ESC 키로도 닫기
        const handleKeydown = (e) => {
            if (e.key === 'Escape') {
                overlay.remove();
                document.removeEventListener('keydown', handleKeydown);
                if (callback) callback();
            }
        };
        document.addEventListener('keydown', handleKeydown);

        // 모달 조립 및 표시
        modal.appendChild(messageDiv);
        modal.appendChild(closeBtn);
        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // 버튼에 포커스
        closeBtn.focus();
    }

    // 등기 경고 표시 함수
    function displayRegistrationWarning(ageCheck) {
        const warningElement = document.getElementById('registration-warning');
        const titleElement = document.getElementById('warning-title');
        const messageElement = document.getElementById('warning-message');
        const datetimeElement = document.getElementById('warning-datetime');
        
        if (!ageCheck || !warningElement) {
            return;
        }
        
        if (ageCheck.is_old) {
            // 경고 표시
            titleElement.textContent = '⚠️ 주의: 오래된 등기 데이터';
            messageElement.textContent = `이 등기는 ${ageCheck.age_days}일 전 데이터입니다 (한 달 이상 경과)`;
            datetimeElement.textContent = `열람일시: ${ageCheck.viewing_date || '-'}`;
            warningElement.style.display = 'block';
            
            // 자동 스크롤하여 경고가 보이도록
            setTimeout(() => {
                warningElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 300);
        } else {
            // 경고 숨김
            warningElement.style.display = 'none';
        }
    }
    
    // 경고 숨김 함수
    function hideRegistrationWarning() {
        const warningElement = document.getElementById('registration-warning');
        if (warningElement) {
            warningElement.style.display = 'none';
        }
    }

    // 압류 경고 표시 함수
    function displaySeizureWarning(seizureInfo) {
        const warningElement = document.getElementById('seizure-warning');
        const summaryElement = document.getElementById('seizure-summary');
        const detailsElement = document.getElementById('seizure-details');

        if (!seizureInfo || !warningElement) {
            return;
        }

        const totalCount = seizureInfo.total_count || 0;
        const activeCount = seizureInfo.active_count || 0;
        const activeSeizures = seizureInfo.active_seizures || [];
        const cancelledCount = totalCount - activeCount; // 말소된 건수

        // 압류 정보가 하나라도 있으면 표시
        if (totalCount > 0) {
            // 요약 정보
            summaryElement.textContent = `과거 이력 (말소됨): ${cancelledCount}건\n현재 유효: ${activeCount}건`;

            // 상세 정보 (현재 유효한 압류만)
            if (activeCount > 0) {
                const detailsHTML = activeSeizures.map(s => {
                    const amountText = s.amount ? ` (${s.amount}원)` : '';
                    return `순위 ${s.rank}: ${s.creditor} ${s.type} (${s.date})${amountText}`;
                }).join('<br>');
                detailsElement.innerHTML = detailsHTML;
            } else {
                detailsElement.textContent = '';
            }

            warningElement.style.display = 'block';

            // 자동 스크롤하여 경고가 보이도록
            setTimeout(() => {
                warningElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 500);
        } else {
            // 압류 정보가 없으면 숨김
            warningElement.style.display = 'none';
        }
    }

    // 압류 경고 숨김 함수
    function hideSeizureWarning() {
        const warningElement = document.getElementById('seizure-warning');
        if (warningElement) {
            warningElement.style.display = 'none';
        }
    }

    // 소유권이전일이 3개월 미만인 경우 빨강색으로 표시
    function checkTransferDateColor(dateString) {
        const field = document.getElementById('ownership_transfer_date');

        if (!field) {
            console.warn('ownership_transfer_date 필드를 찾을 수 없습니다');
            return;
        }

        // 날짜가 없으면 스타일 초기화
        if (!dateString || dateString.trim() === '') {
            field.removeAttribute('style');
            field.classList.remove('red-highlight');
            return;
        }

        try {
            const transferDate = new Date(dateString);

            // 유효한 날짜인지 확인
            if (isNaN(transferDate.getTime())) {
                console.warn('유효하지 않은 날짜 형식:', dateString);
                return;
            }

            // 3개월 전 날짜
            const threeMonthsAgo = new Date();
            threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3);

            console.log(`📅 소유권이전일: ${dateString}, 3개월 이전: ${threeMonthsAgo.toISOString().split('T')[0]}`);

            // 소유권이전일이 3개월 이내면 빨강색
            if (transferDate >= threeMonthsAgo) {
                // CSS를 직접 적용해서 다른 스타일을 덮어씌운다
                field.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
                field.classList.add('red-highlight');
                console.log('🔴 3개월 이내 - 빨강색 적용됨:', dateString);
            } else {
                field.removeAttribute('style');
                field.classList.remove('red-highlight');
                console.log('⚪ 3개월 이상 - 스타일 제거됨:', dateString);
            }
        } catch (e) {
            console.error('날짜 색상 체크 중 오류:', e);
            field.removeAttribute('style');
            field.classList.remove('red-highlight');
        }
    }

    // 레이아웃 설정 저장/복원 기능
    function saveLayoutSettings() {
        const pdfColumn = document.getElementById('pdf-column');
        const formColumn = document.getElementById('form-column-wrapper');
        const mainContainer = document.querySelector('.main-container');

        if (!pdfColumn || !formColumn || !mainContainer) {
            console.warn('⚠️ 레이아웃 설정 저장 실패: 필수 요소를 찾을 수 없습니다');
            return;
        }

        const layoutSettings = {
            pdfColumnFlex: pdfColumn.style.flex || '2',
            formColumnFlex: formColumn.style.flex || '3',
            isHorizontalMode: mainContainer.classList.contains('horizontal-layout'),
            timestamp: Date.now()
        };

        localStorage.setItem('ltvLayoutSettings', JSON.stringify(layoutSettings));
        console.log('💾 레이아웃 설정 저장됨:', layoutSettings);
    }

    function loadLayoutSettings() {
        try {
            const mainContainer = document.querySelector('.main-container');
            const pdfColumn = document.getElementById('pdf-column');
            const formColumn = document.getElementById('form-column-wrapper');

            if (!pdfColumn || !formColumn || !mainContainer) {
                console.warn('⚠️ 레이아웃 설정 로드 실패: 필수 요소를 찾을 수 없습니다');
                return;
            }

            const saved = localStorage.getItem('ltvLayoutSettings');
            const isMobile = window.matchMedia('(max-width: 768px)').matches;

            // 1. 저장된 설정이 있으면 우선 적용
            if (saved) {
                const settings = JSON.parse(saved);

                // 저장된 설정이 24시간 이내인지 확인
                const isRecent = (Date.now() - settings.timestamp) < (24 * 60 * 60 * 1000);
                if (isRecent) {
                    // 컬럼 크기 복원
                    if (settings.pdfColumnFlex) {
                        pdfColumn.style.flex = settings.pdfColumnFlex;
                    }
                    if (settings.formColumnFlex) {
                        formColumn.style.flex = settings.formColumnFlex;
                    }

                    // 가로 모드 복원
                    if (settings.isHorizontalMode) {
                        mainContainer.classList.add('horizontal-layout');
                        const btn = document.getElementById('layout-toggle-btn');
                        if (btn) {
                            btn.innerHTML = '<i class="bi bi-distribute-vertical"></i> 세로 모드';
                        }
                        console.log('📋 저장된 레이아웃 복원됨');
                    }
                    return; // 저장된 설정이 적용되었으므로 여기서 종료
                }
            }

            // 2. 저장된 설정이 없거나 만료된 경우
            // 모바일이면 가로 모드로 자동 시작
            if (isMobile) {
                mainContainer.classList.add('horizontal-layout');
                const btn = document.getElementById('layout-toggle-btn');
                if (btn) {
                    btn.innerHTML = '<i class="bi bi-distribute-vertical"></i> 세로 모드';
                }
                console.log('📱 모바일 감지 - 가로 모드로 자동 시작됨');
            } else {
                console.log('🖥️ PC 화면 - 세로 모드로 시작됨');
            }

        } catch (error) {
            console.error('레이아웃 설정 로드 실패:', error);
        }
    }

    // PDF 컬럼 컴팩트/확장 함수들
    function setPdfColumnCompact() {
        const pdfColumn = document.getElementById('pdf-column');
        const formColumn = document.getElementById('form-column-wrapper');
        if (pdfColumn && formColumn) {
            pdfColumn.classList.add('compact');
            // 컴팩트 모드에서도 리사이즈 가능하도록 flex 설정
            pdfColumn.style.flex = '1';
            formColumn.style.flex = '2.5';
        }
    }

    function setPdfColumnExpanded() {
        const pdfColumn = document.getElementById('pdf-column');
        const formColumn = document.getElementById('form-column-wrapper');
        if (pdfColumn && formColumn) {
            pdfColumn.classList.remove('compact');
            // 확장 모드에서의 기본 비율
            // 모바일에서는 30vh 높이로 설정하여 폼 영역이 보이도록 함
            if (window.matchMedia('(max-width: 768px)').matches) {
                 pdfColumn.style.flex = '0 0 auto';
                 pdfColumn.style.height = '30vh'; // 모바일에서 화면 아래 폼이 보이도록 30vh
                 formColumn.style.flex = '1';
            } else {
                 pdfColumn.style.flex = '2';
                 formColumn.style.flex = '3';
            }
        }
    }

    // ========================================================
    // 3. 파싱/포맷팅 유틸 함수
    // ========================================================
    // 고급 금액 파싱 함수
    // [관련 함수] formatManwonValue(라인 539), formatNumberWithCommas(라인 2011) 참고
    function parseAdvancedAmount(text) {
        if (!text) return 0;
        
        let cleanText = text.replace(/,/g, '').trim();
        
        // 1. 한글 금액 처리 (억, 만, 천, 원 포함)
        if (/억|만|천|원/.test(cleanText)) {
            return parseKoreanAmountAdvanced(cleanText);
        }
        
        // 2. 원 단위 금액 처리 (7자리 이상이거나 '원'으로 끝나는 경우)
        if (cleanText.endsWith('원') || cleanText.replace(/[^\d]/g, '').length >= 7) {
            const numOnly = cleanText.replace(/[^\d]/g, '');
            if (numOnly) {
                const wonAmount = parseInt(numOnly);
                // 원을 만원으로 변환
                return Math.floor(wonAmount / 10000);
            }
        }
        
        // 3. 일반 숫자 처리
        const numOnly = cleanText.replace(/[^\d]/g, '');
        return numOnly ? parseInt(numOnly) : 0;
    }

    // 한글 금액 고급 파싱
    function parseKoreanAmountAdvanced(text) {
        let total = 0;
        let remainingText = text;

        // 억 단위 처리 (개선: 억 뒤의 숫자도 함께 파싱)
        // 예: "6억 5,500" → 6억(60000만) + 5500만 = 65500만
        const eokMatch = remainingText.match(/(\d+)억\s*([,\d]+)?/);
        if (eokMatch) {
            total += parseInt(eokMatch[1]) * 10000;
            remainingText = remainingText.replace(eokMatch[0], '');

            // 억 뒤의 숫자가 있으면 만 단위로 추가
            if (eokMatch[2]) {
                const afterEok = parseInt(eokMatch[2].replace(/,/g, ''));
                if (!isNaN(afterEok)) {
                    total += afterEok;
                }
            }
        }

        // 천만 단위 처리 (예: 2천만 = 2000만)
        const cheonmanMatch = remainingText.match(/(\d+)천만/);
        if (cheonmanMatch) {
            total += parseInt(cheonmanMatch[1]) * 1000;
            remainingText = remainingText.replace(cheonmanMatch[0], '');
        }

        // 만 단위 처리
        const manMatch = remainingText.match(/(\d+)만/);
        if (manMatch) {
            total += parseInt(manMatch[1]);
            remainingText = remainingText.replace(manMatch[0], '');
        }

        // 천 단위 처리 (만원 단위로 변환)
        const cheonMatch = remainingText.match(/(\d+)천/);
        if (cheonMatch) {
            total += parseInt(cheonMatch[1]) / 10; // 천원을 만원으로 변환
            remainingText = remainingText.replace(cheonMatch[0], '');
        }

        return Math.floor(total);
    }

    // 한글 금액 파싱 헬퍼 함수 (기존 호환성 유지)
    function parseKoreanNumberString(text) {
        return parseAdvancedAmount(text);
    }

    // 원 단위를 만원 단위로 변환하는 함수
    function convertWonToManwon(wonAmount) {
        return parseAdvancedAmount(wonAmount);
    }

    // ========================================================
    // 4. 클라이언트 계산 함수 (서버 호출 없음)
    // ========================================================
    // 채권최고액과 비율로 원금 계산하는 함수
    // [관련 계산] calculateSimpleInterest(라인 472), calculateIndividualShare(라인 1279), calculateLTVFromRequiredAmount(라인 1929), calculateBalloonLoan(라인 2034) 참고
    function calculatePrincipalFromRatio(maxAmount, ratio) {
        const maxAmt = parseFloat(String(maxAmount).replace(/,/g, '')) || 0;
        const ratioVal = parseFloat(ratio) || 120;
        
        if (ratioVal <= 0) return 0;
        
        // 원금 = 채권최고액 ÷ (비율/100)
        return Math.round(maxAmt / (ratioVal / 100));
    }

    // ========================================================
    // 5. UI/UX 함수 - 드래그, 리사이즈, 레이아웃
    // ========================================================
    // ✨ 드래그앤드롭 기능 추가 - Material Design 스타일
    // [관련 함수] PDF 드래그앤드롭 처리는 라인 1404 참고
    function initializeDragAndDrop() {
        const container = document.getElementById('loan-items-container');
        
        // 드래그 핸들에만 드래그 이벤트 추가
        container.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('md-drag-handle') || e.target.classList.contains('drag-handle')) {
                const loanItem = e.target.closest('.loan-item');
                loanItem.draggable = true;
            }
        });
        
        container.addEventListener('mouseup', (e) => {
            // 마우스를 떼면 모든 항목의 draggable을 false로
            container.querySelectorAll('.loan-item').forEach(item => {
                item.draggable = false;
            });
        });
        
        container.addEventListener('dragstart', (e) => {
            if (e.target.classList.contains('loan-item')) {
                e.target.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/html', e.target.outerHTML);
            }
        });
        
        container.addEventListener('dragend', (e) => {
            if (e.target.classList.contains('loan-item')) {
                e.target.classList.remove('dragging');
            }
        });
        
        container.addEventListener('dragover', (e) => {
            e.preventDefault();
            const draggingItem = container.querySelector('.dragging');
            
            // ✨ [수정] 드래그 중인 아이템이 없으면 에러 방지를 위해 즉시 중단합니다.
            if (!draggingItem) return; 

            const siblings = [...container.querySelectorAll('.loan-item:not(.dragging)')];
            
            // 현재 마우스 위치에 따라 어느 항목 사이에 끼워 넣을지 결정
            const nextSibling = siblings.find(sibling => {
                return e.clientY <= sibling.getBoundingClientRect().top + sibling.getBoundingClientRect().height / 2;
            });

            container.insertBefore(draggingItem, nextSibling || null);
        });
    }

    // ========================================================
    // 6. 대출 항목 관련 함수
    // ========================================================
    // createLoanItemHTML 함수 - 드래그 핸들 추가, 설정일자/채무자 필드 추가
    function createLoanItemHTML(index, loan = {}) {
        const formatValue = (val) => {
            if (!val) return '';
            const numValue = Number(String(val).replace(/,/g, ''));
            return numValue ? numValue.toLocaleString() : '';
        };

        return `
        <div id="loan-item-${index}" class="loan-item py-2 border-bottom" draggable="false">
            <input type="hidden" name="rank" value="${loan.rank || ''}">
            <div class="loan-col loan-col-drag">
                <div class="drag-handle md-drag-handle" title="드래그하여 순서 변경">⋮⋮</div>
            </div>
            <div class="loan-col loan-col-date">
                <div class="mobile-label">설정일자</div>
                <input type="text" class="form-control form-control-sm loan-input form-field md-loan-input" name="setup_date" placeholder="설정일자" value="${loan.setup_date || ''}">
            </div>
            <div class="loan-col loan-col-lender">
                <div class="mobile-label">설정자</div>
                <input type="text" class="form-control form-control-sm loan-input form-field md-loan-input" name="lender" placeholder="설정자" value="${loan.lender || ''}">
            </div>
            <div class="loan-col loan-col-debtor">
                <div class="mobile-label">채무자</div>
                <input type="text" class="form-control form-control-sm loan-input form-field md-loan-input" name="debtor" placeholder="채무자" value="${loan.debtor || ''}" style="width: 70px;">
            </div>
            <div class="loan-col loan-col-max-amount">
                <div class="mobile-label">채권최고액(만)</div>
                <input type="text" class="form-control form-control-sm loan-input form-field manwon-format md-loan-input" name="max_amount" placeholder="채권최고액(만)" value="${formatValue(loan.max_amount)}">
            </div>
            <div class="loan-col loan-col-ratio">
                <div class="mobile-label">비율(%)</div>
                <input type="text" class="form-control form-control-sm loan-input form-field md-loan-input" name="ratio" placeholder="비율(%)" value="${loan.ratio || '120'}">
            </div>
            <div class="loan-col loan-col-principal">
                <div class="mobile-label">원금(만)</div>
                <input type="text" class="form-control form-control-sm loan-input form-field manwon-format md-loan-input" name="principal" placeholder="원금(만)" value="${formatValue(loan.principal)}">
            </div>
            <div class="loan-col loan-col-status">
                <div class="mobile-label">구분</div>
                <select class="form-select form-select-sm loan-input form-field md-loan-select" name="status">
                    <option value="" selected>구분 선택...</option>
                    <option value="유지" ${loan.status === '유지' ? 'selected' : ''}>유지</option>
                    <option value="대환" ${loan.status === '대환' ? 'selected' : ''}>대환</option>
                    <option value="선말소" ${loan.status === '선말소' ? 'selected' : ''}>선말소</option>
                    <option value="퇴거자금" ${loan.status === '퇴거자금' ? 'selected' : ''}>퇴거자금</option>
                    <option value="동의" ${loan.status === '동의' ? 'selected' : ''}>동의</option>
                    <option value="비동의" ${loan.status === '비동의' ? 'selected' : ''}>비동의</option>
                </select>
            </div>
            <div class="loan-col loan-col-action">
                <div style="display: flex; gap: 4px; justify-content: center; align-items: center;">
                    <button type="button" class="md-btn md-btn-secondary" onclick="addLoanItem()" style="padding: 4px 8px; font-size: 12px; min-width: 24px;">+</button>
                    <button type="button" class="md-btn md-btn-primary" aria-label="Close" onclick="removeLoanItem(${index})" style="padding: 4px 8px; font-size: 12px; min-width: 24px;">×</button>
                </div>
            </div>
        </div>`;
    }

    // ✨ [신규] 단순 이자 계산 함수
    // [관련 계산] calculatePrincipalFromRatio(라인 349), calculateIndividualShare(라인 1279), calculateLTVFromRequiredAmount(라인 1929), calculateBalloonLoan(라인 2034) 참고
    function calculateSimpleInterest() {
        // 입력 요소에서 값 가져오기
        const loanAmountInput = document.getElementById('interest-loan-amount');
        const annualRateInput = document.getElementById('interest-annual-rate');

        // 콤마(,) 제거하고 숫자로 변환
        const principalManwon = parseInt(loanAmountInput.value.replace(/,/g, '')) || 0;
        const principal = principalManwon * 10000; // 원 단위로 변환
        const annualRate = parseFloat(annualRateInput.value) || 0;

        // 결과 표시 요소 가져오기
        const dailyResultEl = document.getElementById('interest-daily-result');
        const monthlyResultEl = document.getElementById('interest-monthly-result');
        const yearlyResultEl = document.getElementById('interest-yearly-result');
        const explanationEl = document.getElementById('interest-calc-explanation');

        // 입력값이 유효할 때만 계산
        if (principal > 0 && annualRate > 0) {
            const yearlyInterest = Math.floor(principal * (annualRate / 100));
            const dailyInterest = Math.floor(yearlyInterest / 365);

            // 라디오 버튼에서 선택된 계산 방식 확인
            const calcMethod = document.querySelector('input[name="interestCalcMethod"]:checked')?.value || 'monthly';

            let monthlyInterest;
            let explanation = '';

            if (calcMethod === 'monthly') {
                // 월할계산: 연 이자 ÷ 12
                monthlyInterest = Math.floor(yearlyInterest / 12);
                explanation = `예) 1년 이자 ${yearlyInterest.toLocaleString()}원 ÷ 12개월 = ${monthlyInterest.toLocaleString()}원`;
            } else {
                // 일할계산: 현재 월의 일수로 계산
                const today = new Date();
                const year = today.getFullYear();
                const month = today.getMonth();
                // 다음 달 1일에서 하루 빼면 이번 달 마지막 날 = 이번 달 일수
                const daysInMonth = new Date(year, month + 1, 0).getDate();
                // 정확한 계산: 연 이자 × (실제일수 ÷ 365)
                monthlyInterest = Math.floor(yearlyInterest * daysInMonth / 365);
                explanation = `예) 1년 이자 ${yearlyInterest.toLocaleString()}원 × ${daysInMonth}일 ÷ 365일 = ${monthlyInterest.toLocaleString()}원 (${month + 1}월 기준)`;
            }

            // 계산된 값을 콤마와 함께 '원' 단위로 표시
            yearlyResultEl.value = yearlyInterest.toLocaleString() + '원';
            monthlyResultEl.value = monthlyInterest.toLocaleString() + '원';
            dailyResultEl.value = dailyInterest.toLocaleString() + '원';
            explanationEl.textContent = explanation;
        } else {
            // 입력값이 없거나 0이면 결과를 ''으로 초기화
            yearlyResultEl.value = '';
            monthlyResultEl.value = '';
            dailyResultEl.value = '';
            explanationEl.textContent = '';
        }
    }

    // ✨ 누락되었던 함수
    function addLoanItem(loan = {}) {
        const container = document.getElementById('loan-items-container');
        container.insertAdjacentHTML('beforeend', createLoanItemHTML(loanItemCounter++, loan));
        attachEventListenersForLoanItems();
    }

    // 대출 항목 제거
    function removeLoanItem(index) {
        const container = document.getElementById('loan-items-container');
        const allItems = container.querySelectorAll('.loan-item');
        
        // 마지막 하나 남은 경우, 필드 값만 지우고 항목은 유지
        if (allItems.length === 1) {
            const item = document.getElementById(`loan-item-${index}`);
            if (item) {
                // 모든 input 필드 값 지우기
                item.querySelectorAll('input, select').forEach(field => {
                    field.value = '';
                });
            }
        } else {
            // 2개 이상인 경우 항목 완전 제거
            document.getElementById(`loan-item-${index}`)?.remove();
        }
        
        triggerMemoGeneration();
    }
    
    // 숫자 자동 포맷 (개선된 고급 금액 처리)
    // [관련 함수] parseAdvancedAmount(라인 273), formatNumberWithCommas(라인 2011) 참고
    function formatManwonValue(e) {
        const field = e.target;
        let value = field.value.trim();
        let parsedValue = 0;

        // 빈 값 처리
        if (!value) {
            field.value = '';
            triggerMemoGeneration();
            return;
        }

        // '+' 기호가 있는지 확인하여 계산
        if (value.includes('+')) {
            const terms = value.split('+');
            parsedValue = terms.reduce((acc, term) => {
                return acc + parseAdvancedAmount(term.trim());
            }, 0);
        } else {
            parsedValue = parseAdvancedAmount(value);
        }
        
        // 계산된 값을 입력창에 다시 설정
        field.value = parsedValue > 0 ? parsedValue.toLocaleString() : '';

        // 메모 업데이트 함수 호출
        triggerMemoGeneration();
    }

    // [수정됨] 대출 항목 자동 계산 (원금-최고액) - 클라이언트 사이드
    function handleAutoLoanCalc(event) {
        const target = event.target;
        const loanItem = target.closest('.loan-item');
        if (!loanItem) return;

        const maxAmountInput = loanItem.querySelector('[name="max_amount"]');
        const ratioInput = loanItem.querySelector('[name="ratio"]');
        const principalInput = loanItem.querySelector('[name="principal"]');

        let maxAmount = parseFloat(maxAmountInput.value.replace(/,/g, '')) || 0;
        let ratio = parseFloat(ratioInput.value) || 0;
        let principal = parseFloat(principalInput.value.replace(/,/g, '')) || 0;

        if (target.name === 'principal') {
            // 원금이 바뀌면 비율에 따라 최고액 역산
            if (principal > 0 && ratio > 0) {
                maxAmount = Math.round(principal * (ratio / 100));
                maxAmountInput.value = maxAmount.toLocaleString();
            }
        } else {
            // 최고액 또는 비율이 바뀌면 원금 계산
            if (maxAmount > 0 && ratio > 0) {
                principal = Math.round(maxAmount / (ratio / 100));
                principalInput.value = principal.toLocaleString();
            }
        }
        triggerMemoGeneration();
    }
    
    // [신규] 채권최고액 입력 시 서버 API를 통해 금액 변환 및 원금 자동계산
    async function handleApiLoanConversion(event) {
        const maxAmountInput = event.target;
        const loanItem = maxAmountInput.closest('.loan-item');
        if (!loanItem) return;

        const ratioInput = loanItem.querySelector('[name="ratio"]');
        const principalInput = loanItem.querySelector('[name="principal"]');

        // ✅ [수정] 값이 변경되지 않았으면 API 호출 건너뛰기 (마우스 커서만 올린 경우)
        const currentValue = maxAmountInput.value;
        const lastValue = maxAmountInput.dataset.lastValue || '';
        if (currentValue === lastValue) {
            return; // 값이 같으면 아무것도 하지 않음
        }
        maxAmountInput.dataset.lastValue = currentValue;

        const loanData = {
            max_amount: maxAmountInput.value,
            ratio: ratioInput.value
        };

        try {
            const response = await fetch('/api/convert_loan_amount', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(loanData)
            });

            if (!response.ok) throw new Error('API call failed');
            const result = await response.json();

            if (result.success && result.converted_data) {
                const data = result.converted_data;
                const newMaxAmount = data.max_amount ? parseInt(data.max_amount).toLocaleString() : '0';
                const newPrincipal = data.principal ? parseInt(data.principal).toLocaleString() : '0';
                maxAmountInput.value = newMaxAmount;
                maxAmountInput.dataset.lastValue = newMaxAmount; // 변환된 값도 저장
                principalInput.value = newPrincipal;
            }
        } catch (error) {
            console.error('Error during loan conversion:', error);
            // API 호출 실패 시, 클라이언트 사이드 계산으로 대체
            handleAutoLoanCalc(event);
        } finally {
            triggerMemoGeneration();
        }
    }
    
    // ✨ [신규] 방공제 및 임차인(동의/비동의) 상태에 따른 경고 메시지 표시 함수
    function checkTenantDeductionWarning() {
        const deductionRegionSelect = document.getElementById('deduction_region');
        // "지역 선택..." 또는 "방공제 없음" 등의 기본값(value="0")이 아닌 경우를 확인합니다.
        const isDeductionSelected = deductionRegionSelect.value && deductionRegionSelect.value !== '0';

        if (!isDeductionSelected) {
            return; // 방공제 지역이 선택되지 않았으면 검사를 중단합니다.
        }

        const tenantStatuses = ['동의', '비동의'];
        let hasTenantLoan = false;
        // 현재 화면에 있는 모든 대출 항목의 '진행' 상태를 확인합니다.
        document.querySelectorAll('.loan-item [name="status"]').forEach(statusSelect => {
            if (tenantStatuses.includes(statusSelect.value)) {
                hasTenantLoan = true;
            }
        });

        // 방공제 지역이 선택되었고, '동의' 또는 '비동의' 상태의 대출이 하나라도 있다면 경고 메시지를 표시합니다.
        if (hasTenantLoan) {
            alert("임차인이 거주하고 있는 물건지는 방공제금액을 입력할 수 없습니다. 전세퇴거여부를 확인해주세요");
        }
    }

    // ========================================================
    // 7. 이벤트 리스너 부착 함수
    // ========================================================
    // [수정됨] 동적 생성된 대출 항목에 이벤트 리스너 연결
    function attachEventListenersForLoanItems() {
        document.querySelectorAll('.loan-item').forEach(item => {
            const maxAmountInput = item.querySelector('[name="max_amount"]');
            const ratioInput = item.querySelector('[name="ratio"]');
            const principalInput = item.querySelector('[name="principal"]');
            
            // 기존 이벤트 리스너를 모두 제거하여 중복 방지
            const newMaxAmountInput = maxAmountInput.cloneNode(true);
            const newRatioInput = ratioInput.cloneNode(true);
            const newPrincipalInput = principalInput.cloneNode(true);

            maxAmountInput.parentNode.replaceChild(newMaxAmountInput, maxAmountInput);
            ratioInput.parentNode.replaceChild(newRatioInput, ratioInput);
            principalInput.parentNode.replaceChild(newPrincipalInput, principalInput);

            // [핵심] 채권최고액: 포커스가 벗어날 때 서버 API로 변환 요청
            newMaxAmountInput.addEventListener('blur', handleApiLoanConversion);
            
            // 비율: 값이 변경될 때 클라이언트에서 원금 즉시 재계산
            newRatioInput.addEventListener('change', handleAutoLoanCalc);
            
            // 원금: 포커스가 벗어날 때 숫자 포맷팅 / 값이 변경될 때 최고액 역산
            newPrincipalInput.addEventListener('blur', formatManwonValue);
            newPrincipalInput.addEventListener('change', handleAutoLoanCalc);

            // 모든 항목의 값이 변경되면 메모 업데이트
            item.querySelectorAll('.loan-input').forEach(input => {
                // ✨ [수정] 'change' 이벤트에 경고 확인 로직 추가
                input.addEventListener('change', (e) => {
                    // 만약 변경된 필드가 'status'라면, 임차인/방공제 경고를 확인합니다.
                    if (e.target.name === 'status') {
                        checkTenantDeductionWarning();

                        // ✅ [신규] 상태 변경 시 필요금액 초기화 (한도 재계산 필요)
                        const requiredAmountField = document.getElementById('required_amount');
                        if (requiredAmountField && requiredAmountField.value) {
                            requiredAmountField.value = '';
                            console.log('🔄 대출 상태 변경 → 필요금액 초기화 (한도 재계산)');
                        }

                        // ✅ [신규] 아이엠 질권 체크 시 LTV 재계산 (선순위/후순위 자동 반영)
                        const hopeCheckbox = document.getElementById('hope-collateral-loan');
                        const ltv1Field = document.getElementById('ltv1');

                        if (hopeCheckbox && hopeCheckbox.checked && ltv1Field) {
                            // 선순위/후순위 판단
                            const maintainStatus = ['유지', '동의', '비동의'];
                            let hasSubordinate = false;
                            document.querySelectorAll('.loan-item').forEach(loanItem => {
                                const status = loanItem.querySelector('[name="status"]')?.value || '-';
                                if (maintainStatus.includes(status)) {
                                    hasSubordinate = true;
                                }
                            });

                            if (!hasSubordinate) {
                                // 선순위: LTV 70%로 자동 설정
                                ltv1Field.value = '70';
                                console.log('📊 상태 변경 → 아이엠 선순위: LTV 70%로 자동 설정');
                            } else {
                                // 후순위: LTV 유지 (사용자 수동 조정)
                                console.log('📊 상태 변경 → 아이엠 후순위: LTV 수동 조정');
                            }
                        }

                        // 메리츠 질권 LTV 재계산 (아이엠이 체크되어 있으면 스킵)
                        if (!hopeCheckbox.checked) {
                            validateMeritzLoanConditions();
                        }

                        // ✅ [수정] 상태 변경 시 디바운스 타이머 클리어 후 즉시 메모 생성
                        clearTimeout(memoDebounceTimeout);
                        generateMemo();
                    } else {
                        // 다른 필드는 디바운스 적용
                        triggerMemoGeneration();
                    }
                });
            });
        });
    }


// 모든 폼 데이터 수집
function collectAllData() {
    const regionSelect = document.getElementById('deduction_region');
    const selectedRegionText = regionSelect.options[regionSelect.selectedIndex].text;
    const loanItems = Array.from(document.querySelectorAll('.loan-item')).map(item => ({
        setup_date: item.querySelector('[name="setup_date"]').value,
        lender: item.querySelector('[name="lender"]').value,
        debtor: item.querySelector('[name="debtor"]').value,
        status: item.querySelector('[name="status"]').value,
        max_amount: item.querySelector('[name="max_amount"]').value,
        principal: item.querySelector('[name="principal"]').value,
        ratio: item.querySelector('[name="ratio"]').value,
        rank: item.querySelector('[name="rank"]')?.value || '',
    }));

    // return 구문 바깥에서 변수를 먼저 선언합니다.
    // 고객명 & 생년월일을 함께 수집 (기존 입력 필드에는 이름과 생년월일이 함께 들어있음)
    const name1 = document.getElementById('customer_name').value.trim();
    const name2 = document.getElementById('customer_name_2').value.trim();
    
    // 두 개의 이름을 합쳐 하나의 문자열로 만듭니다. (빈 값은 알아서 제외됩니다)
    const combinedCustomerName = [name1, name2].filter(Boolean).join(', ');

    return {
        inputs: {
            // 위에서 만든 변수를 여기서 사용합니다.
            customer_name: combinedCustomerName,
            address: document.getElementById('address').value,
            property_type: document.getElementById('property_type').value,
            kb_price: document.getElementById('kb_price').value,
            area: document.getElementById('area').value,
            deduction_region_text: selectedRegionText,
            deduction_amount: document.getElementById('deduction_amount').value,

            // [복구] LTV1만 전송
            ltv_rates: [document.getElementById('ltv1').value],

            // [복구] 필요금액 전송 - 입력 시 한도에 반영
            required_amount: document.getElementById('required_amount').value,

            share_rate1: document.getElementById('share-customer-birth-1').value,
            share_rate2: document.getElementById('share-customer-birth-2').value,
            hope_collateral_checked: document.getElementById('hope-collateral-loan').checked,
            meritz_collateral_checked: document.getElementById('meritz-collateral-loan').checked,
            meritz_region: meritzRegion,
            ownership_transfer_date: document.getElementById('ownership_transfer_date').value,
            unit_count: document.getElementById('unit_count').value,
            completion_date: document.getElementById('completion_date').value,
            instant_business_operator: document.getElementById('instant-business-operator').checked,
            business_issue_date: document.getElementById('business_issue_date').value,
            business_registration_date: document.getElementById('business_registration_date').value,
            loan_available_date: document.getElementById('loan_available_date').value,
        },
        fees: {
            consult_amt: '0',
            consult_rate: '0',
            bridge_amt: '0',
            bridge_rate: '0',
        },
        loans: loanItems
    };
}

    
    // 메모 생성 요청 (디바운스 적용)
    function triggerMemoGeneration() {
        clearTimeout(memoDebounceTimeout);
        memoDebounceTimeout = setTimeout(generateMemo, 800);
        updateCollateralRateDisplay(); // 질권사 금리 실시간 업데이트
    }

    // 메모 생성 및 하안가/일반가 표시
    async function generateMemo() {
        const memoArea = document.getElementById('generated-memo');
        const data = collectAllData();
        const requestData = { inputs: data.inputs, loans: data.loans, fees: data.fees };
        try {
            const response = await fetch('/api/generate_text_memo', { 
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestData)
            });
            const result = await response.json();
            memoArea.value = result.memo
            
            const priceTypeField = document.getElementById('price_type_field');
            if (result.price_type) {
                priceTypeField.value = result.price_type;
                
                // ✨ 1. 기존 색상 클래스를 먼저 모두 제거합니다.
                priceTypeField.classList.remove('text-danger', 'text-primary', 'text-warning');

                // ✨ 2. 시세 타입에 따라 적절한 색상 클래스를 추가합니다.
                if (result.price_type.includes('일반가')) {
                    priceTypeField.classList.add('text-primary'); // '일반가'는 파란색
                } else if (result.price_type.includes('하안가')) {
                    priceTypeField.classList.add('text-danger');  // '하안가'는 빨간색
                }
            } else {
                // 내용이 없을 경우, 텍스트와 색상 클래스를 모두 제거합니다.
                priceTypeField.value = '';
                priceTypeField.classList.remove('text-danger', 'text-primary', 'text-warning');
            }
        } catch (error) {
            memoArea.value = `오류: 메모 생성 중 문제가 발생했습니다. (${error})`;
        }
    }
    
    // 고객 목록 불러오기
    async function loadCustomerList() {
        try {
            const response = await fetch('/api/customers');
            let customers = await response.json();
            const select = document.getElementById('customer-history');
            select.innerHTML = '<option value="" selected>기존 고객 불러오기...</option>';

            // customers가 배열이 아니면 빈 배열로 처리
            if (!Array.isArray(customers)) {
                console.warn('⚠️ 고객 목록이 배열이 아님:', customers);
                return;
            }

            customers.forEach(customer => {
                const option = document.createElement('option');
                option.value = customer.id;
                option.textContent = customer.name;
                select.appendChild(option);
            });
        } catch (error) {
            console.error("❌ 고객 목록 로딩 실패:", error);
        }
    }

    // ========================================================
    // 8. 서버 API 호출 함수 (async)
    // ========================================================

// 특정 고객 데이터 불러오기
// [API 호출 함수들] handleFileUpload(라인 1068), calculateIndividualShare(라인 1273), calculateLTVFromRequiredAmount(라인 1921) 참고
async function loadCustomerData() {
    const select = document.getElementById('customer-history');
    const pageId = select.value;
    if (!pageId) return;
    try {
        const response = await fetch(`/api/customer/${pageId}`);
        if (!response.ok) throw new Error(`서버 응답 오류: ${response.status}`);
        const data = await response.json();
        if (data.error) { alert(`데이터 로드 실패: ${data.error}`); return; }
        
        // --- ▼▼▼ 여기가 핵심 수정 부분입니다 ▼▼▼ ---
        // Notion에서 온 '홍길동 800101, 김철수 900202' 같은 데이터를 나눕니다.
        if (data.customer_name) {
            const owners = data.customer_name.split(',').map(name => name.trim());
            safeSetValue('customer_name', owners[0] || '');
            safeSetValue('customer_name_2', owners[1] || '');
        } else {
            safeSetValue('customer_name', '');
            safeSetValue('customer_name_2', '');
        }
        // --- ▲▲▲ 여기가 핵심 수정 부분입니다 ▲▲▲ ---

        // 안전한 요소 접근 (null 체크 포함)
        safeSetValue('address', data.address || '');
        safeSetValue('kb_price', (data.kb_price || '').toString().replace(/\B(?=(\d{3})+(?!\d))/g, ','));
        safeSetValue('area', data.area || '');
        safeSetValue('property_type', data.property_type || '');
        safeSetValue('ltv1', data.ltv1 || '80');

        // 소유권이전일 및 세대수 로드
        safeSetValue('ownership_transfer_date', data.ownership_transfer_date || '');
        if (data.ownership_transfer_date) {
            checkTransferDateColor(data.ownership_transfer_date);
        }
        safeSetValue('unit_count', data.unit_count || '');
        safeSetValue('completion_date', data.completion_date || '');

        // 즉발사업자 복원
        const instantBusinessCheckbox = document.getElementById('instant-business-operator');
        if (instantBusinessCheckbox && data.instant_business_operator) {
            instantBusinessCheckbox.checked = true;
            // 체크박스 이벤트 트리거하여 날짜 필드 표시
            instantBusinessCheckbox.dispatchEvent(new Event('change'));
        }

        // 즉발사업자 날짜 필드 복원
        safeSetValue('business_issue_date', data.business_issue_date || '');
        safeSetValue('business_registration_date', data.business_registration_date || '');
        safeSetValue('loan_available_date', data.loan_available_date || '');

        const regionSelect = document.getElementById('deduction_region');
        if (regionSelect) {
            const regionOption = Array.from(regionSelect.options).find(opt => opt.text === data.deduction_region);
            if(regionOption) {
                regionSelect.selectedIndex = Array.from(regionSelect.options).indexOf(regionOption);
            } else if(regionSelect.options.length > 0) {
                regionSelect.selectedIndex = 0;
            }
            safeSetValue('deduction_amount', (regionSelect.value || '').toLocaleString());
        }
        const loanContainer = document.getElementById('loan-items-container');
        if (loanContainer) {
            loanContainer.innerHTML = '';
            loanItemCounter = 0;

            if (data.loans && data.loans.length > 0) {
                data.loans.forEach(loan => addLoanItem(loan));
            } else {
                addLoanItem();
            }
        }

        // customer_name 데이터를 지분한도 계산기 탭 공유자 필드에 자동 입력
        if (data.customer_name) {
            const owners = data.customer_name.split(',').map(name => name.trim());
            if (owners.length >= 1) {
                safeSetValue('share-customer-name-1', owners[0]);
            }
            if (owners.length >= 2) {
                safeSetValue('share-customer-name-2', owners[1]);
            }
        }

        // 공유자 지분율 자동 입력
        if (data.share_rate1) {
            safeSetValue('share-customer-birth-1', data.share_rate1);
        }
        if (data.share_rate2) {
            safeSetValue('share-customer-birth-2', data.share_rate2);
        }

        // 아이엠질권 및 메리츠질권 체크박스 복원 (상호 배타적 - 아이엠 우선)
        const hopeCheckbox = document.getElementById('hope-collateral-loan');
        const meritzCheckbox = document.getElementById('meritz-collateral-loan');

        if (hopeCheckbox && data.hope_collateral_checked) {
            // 아이엠 체크 시 메리츠는 복원하지 않음 (상호 배타적)
            hopeCheckbox.checked = true;
            hopeCheckbox.dispatchEvent(new Event('change'));
            console.log('✅ 아이엠질권 복원 (메리츠 복원 생략)');
        } else if (meritzCheckbox && data.meritz_collateral_checked) {
            // 아이엠이 체크되지 않은 경우에만 메리츠 복원
            meritzCheckbox.checked = true;
            meritzCheckbox.dispatchEvent(new Event('change'));

            // 메리츠 지역 복원
            if (data.meritz_region) {
                meritzRegion = data.meritz_region;
                const regionLabel = meritzRegion === '1gun' ? '1군(일반)' : (meritzRegion === '2gun' ? '2군' : '3군');
                console.log(`🌍 메리츠 지역 복원: ${regionLabel}`);

                // 버튼 스타일 업데이트
                document.querySelectorAll('.meritz-loan-region-btn').forEach(btn => {
                    const btnRegion = btn.getAttribute('data-region');
                    if (btnRegion === meritzRegion) {
                        btn.style.backgroundColor = '#9CC3D5';
                        btn.style.color = '#0063B2';
                        btn.style.borderColor = '#9CC3D5';
                    } else {
                        btn.style.backgroundColor = '';
                        btn.style.color = '';
                        btn.style.borderColor = '';
                    }
                });
            }
            console.log('✅ 메리츠질권 복원');
        }

        triggerMemoGeneration();
        } catch (error) {
            alert(`고객 데이터를 불러오는 중 오류가 발생했습니다: ${error.message}`);
        }
    }

    
    // 지분율 자동 계산 함수 (개선됨)
    function autoCalculateShareRatio(inputIndex, targetIndex) {
        const inputField = document.getElementById(`share-customer-birth-${inputIndex}`);
        const targetField = document.getElementById(`share-customer-birth-${targetIndex}`);
        
        if (!inputField || !targetField) return;
        
        const inputValue = inputField.value.trim();
        if (inputValue === '') {
            targetField.value = '';
            return;
        }
        
        let inputRatio = 0;
        
        // 다양한 형태의 지분율 입력 처리
        if (inputValue.includes('/')) {
            // 분수 형태: "1/2", "3/4" 등
            const parts = inputValue.split('/');
            if (parts.length === 2) {
                const numerator = parseFloat(parts[0]);
                const denominator = parseFloat(parts[1]);
                if (!isNaN(numerator) && !isNaN(denominator) && denominator !== 0) {
                    inputRatio = (numerator / denominator) * 100;
                    // 원본 입력을 백분율로 포맷
                    inputField.value = `${parts[0]}/${parts[1]} (${inputRatio.toFixed(1)}%)`;
                }
            }
        } else if (inputValue.includes('(') && inputValue.includes('%')) {
            // 이미 괄호가 있는 형태: "1/2 (50%)" 등
            const percentMatch = inputValue.match(/\(([\d.]+)%?\)/);
            if (percentMatch) {
                inputRatio = parseFloat(percentMatch[1]);
            }
        } else {
            // 일반 숫자 입력: "50", "50%", "50.5" 등
            inputRatio = parseFloat(inputValue.replace(/[^0-9.]/g, ''));
            if (!isNaN(inputRatio) && inputRatio > 0 && inputRatio <= 100) {
                // 입력을 백분율 형태로 포맷
                inputField.value = `${inputRatio}%`;
            }
        }
        
        // 유효성 검사
        if (isNaN(inputRatio) || inputRatio <= 0 || inputRatio >= 100) return;
        
        // 나머지 지분율 계산
        const remainingRatio = 100 - inputRatio;
        
        // 분수와 백분율 형태로 대상 필드 설정
        if (inputRatio === 50) {
            targetField.value = `1/2 (${remainingRatio}%)`;
        } else if (inputRatio === 33.3 || Math.abs(inputRatio - 33.333) < 0.1) {
            targetField.value = `2/3 (${remainingRatio.toFixed(1)}%)`;
        } else if (inputRatio === 66.7 || Math.abs(inputRatio - 66.667) < 0.1) {
            targetField.value = `1/3 (${remainingRatio.toFixed(1)}%)`;
        } else if (inputRatio === 25) {
            targetField.value = `3/4 (${remainingRatio}%)`;
        } else if (inputRatio === 75) {
            targetField.value = `1/4 (${remainingRatio}%)`;
        } else {
            targetField.value = `${remainingRatio.toFixed(1)}%`;
        }
    }
    
    // 텍스트에리어 크기 자동 조절 함수
    function autoResizeTextarea(textarea) {
        // 높이 초기화
        textarea.style.height = 'auto';
        // 내용에 맞춰 높이 조절 (최소 15행, 최대 50행)
        const minHeight = 15 * 20; // 15행 * 대략적인 행 높이
        const maxHeight = 50 * 20; // 50행 * 대략적인 행 높이
        const newHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight);
        textarea.style.height = newHeight + 'px';
    }
    
    // ✨ 누락되었던 함수들
    async function saveNewCustomer() {
        const data = collectAllData();
        if (!data.inputs.customer_name) { 
            alert('고객명을 입력해주세요.'); 
            return; 
        }
        if (!confirm(`'${data.inputs.customer_name}' 이름으로 신규 저장하시겠습니까?`)) return;
        const response = await fetch('/api/customer/new', { 
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        alert(result.message);
        if (result.success) { 
            loadCustomerList(); 
        }
    }

    async function updateCustomer() {
        const selectedCustomerId = document.getElementById('customer-history').value;
        if (!selectedCustomerId) { 
            alert('수정할 고객을 목록에서 먼저 선택해주세요.'); 
            return; 
        }
        const data = collectAllData();
        if (!confirm(`'${data.inputs.customer_name}' 고객 정보를 수정하시겠습니까?`)) return;
        const url = `/api/customer/update/${selectedCustomerId}`;
        const response = await fetch(url, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        alert(result.message);
        if (result.success) { 
            loadCustomerList(); 
        }
    }

    async function deleteCustomer() {
        const select = document.getElementById('customer-history');
        const selectedCustomerId = select.value;

        if (!selectedCustomerId) {
            alert('삭제할 고객을 목록에서 먼저 선택해주세요.');
            return;
        }

        // --- ✨ 요청사항에 맞춰 암호 확인 로직을 수정했습니다 ---

        // 1. "암호를 입력하세요" 라는 메시지로 프롬프트 창을 띄웁니다.
        const enteredPassword = prompt("암호를 입력하세요");

        // 2. 사용자가 '취소' 버튼을 눌렀을 경우
        if (enteredPassword === null) {
            alert("취소되었습니다");
            return;
        }

        // 3. 암호가 일치하는지 확인
        const deletePassword = "1245"; // 요청하신 암호 "1245"
        if (enteredPassword === deletePassword) {
            // 암호가 일치하면 서버에 삭제 요청
            try {
                const url = `/api/customer/delete/${selectedCustomerId}`;
                const response = await fetch(url, { method: 'POST' });
                const result = await response.json();
                alert(result.message); // 서버의 응답 메시지 (예: '고객 정보가 삭제(보관)되었습니다.')
                if (result.success) {
                    location.reload();
                }
            } catch (error) {
                alert('삭제 처리 중 오류가 발생했습니다.');
                console.error('Delete error:', error);
            }
        } else {
            // 4. 암호가 일치하지 않을 경우
            alert("암호가 일치하지 않아 삭제 처리되지 않았습니다");
        }
    }

// PDF 파일 업로드 핸들러 (최종 완성본)
// [API 호출 함수들] loadCustomerData(라인 827), calculateIndividualShare(라인 1273), calculateLTVFromRequiredAmount(라인 1921) 참고
async function handleFileUpload(file) {
    const spinner = document.getElementById('upload-spinner');
    spinner.style.display = 'block';
    const formData = new FormData();
    formData.append('pdf_file', file);

    try {
        const response = await fetch('/api/upload', { method: 'POST', body: formData });
        if (!response.ok) {
            const errorResult = await response.json();
            throw new Error(errorResult.error || `서버 에러: ${response.status}`);
        }
        const result = await response.json();

        // 디버깅: 전체 응답 로그
        console.log('📥 API 응답:', result);

        if (result.success) {
            // 1. 서버가 보내준 데이터를 각각의 변수에 저장합니다.
            const scraped = result.scraped_data;  // 기본 정보 (주소, 소유자, 지분 등)
            const rights_info = result.rights_info; // 근저당권 정보
            const seizure_info = result.seizure_info; // [신규] 압류/가압류 정보
            const building_info = result.building_info; // [신규] 건축물대장 정보 (세대수, 준공일)

            // 디버깅: 추출된 데이터 로그
            console.log('📊 scraped_data:', scraped);
            console.log('📅 transfer_date:', scraped.transfer_date);
            console.log('⚠️ seizure_info:', seizure_info);
            console.log('🏢 building_info:', building_info);

            // --- 2. 추출된 기본 정보를 각 필드에 자동으로 채워 넣습니다. ---
            
            // 소유자 이름 & 생년월일 (2명까지 지원)
            if (scraped.customer_name) {
                const owners = scraped.customer_name.split(',').map(name => name.trim());
                safeSetValue('customer_name', owners[0] || '');
                safeSetValue('customer_name_2', owners[1] || '');
            } else {
                safeSetValue('customer_name', '');
                safeSetValue('customer_name_2', '');
            }

            safeSetValue('address', scraped.address || '');
            const areaValue = scraped.area || '';
            safeSetValue('area', areaValue.includes('㎡') ? areaValue : (areaValue ? `${areaValue}㎡` : ''));

            // 물건유형 추가 (자동 인식)
            safeSetValue('property_type', scraped.property_type || 'Unknown');

            // 소유권이전일 채우기
            safeSetValue('ownership_transfer_date', scraped.transfer_date || '');
            if (scraped.transfer_date) {
                checkTransferDateColor(scraped.transfer_date);
            }

            // 준공일자 채우기 (건축물대장 우선, 없으면 등기부등본)
            const completionDate = (building_info && building_info.success && building_info.completion_date)
                ? building_info.completion_date
                : (scraped.construction_date || '');
            safeSetValue('completion_date', completionDate);

            // [신규] 세대수 자동 입력 (건축물대장에서 조회)
            if (building_info && building_info.success && building_info.total_households > 0) {
                // HTML의 실제 ID인 'unit_count'에 값을 넣습니다.
                safeSetValue('unit_count', building_info.total_households);
                console.log(`✅ 세대수 자동 입력 성공: ${building_info.total_households}세대`);
            }

            // 등기 경고 표시 (오래된 등기인지 등)
            displayRegistrationWarning(scraped.age_check);

            // [신규] 압류 경고 표시
            displaySeizureWarning(seizure_info);

            // [신규] 소유권대지권 없음 경고
            if (scraped.has_land_ownership_right === false) {
                const addressField = document.getElementById('address');
                if (addressField) {
                    addressField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
                }
                showCustomAlert('⚠️ 소유권대지권 無\n\n이 등기부등본에 소유권대지권이 확인되지 않습니다.');
            }

            // 소유자별 지분 정보 (지분 한도 계산기 탭)
            if (scraped.owner_shares && scraped.owner_shares.length > 0) {
                scraped.owner_shares.forEach((line, idx) => {
                    // '이름 생년월일 지분율' 포맷에서 이름+생년월일과 지분율을 분리
                    const parts = line.split('  지분율 ');
                    if (parts.length === 2) {
                        const nameBirth = parts[0];
                        const shareInfo = parts[1];
                        const nameField = document.getElementById(`share-customer-name-${idx + 1}`);
                        const shareField = document.getElementById(`share-customer-birth-${idx + 1}`);
                        if (nameField) nameField.value = nameBirth;
                        if (shareField) shareField.value = shareInfo; // '1/2 (50.0%)' 같은 값
                    }
                });
            }

            // --- 3. 추출된 근저당권 정보를 대출 항목에 자동으로 채워 넣습니다. ---

            // 기존 대출 항목들을 모두 깨끗하게 지웁니다.
            document.getElementById('loan-items-container').innerHTML = '';
            loanItemCounter = 0;

            // 서버에서 받은 근저당권 정보가 있는지 확인합니다.
            if (rights_info && rights_info.근저당권 && rights_info.근저당권.length > 0) {
                // 각 근저당권 정보를 순회하면서 새 대출 항목을 만듭니다.
                rights_info.근저당권.forEach(mortgage => {
                    const details = mortgage.주요등기사항;
                    const amountMatch = details.match(/채권최고액\s*금([\d,]+)원/);
                    const lenderMatch = details.match(/근저당권자\s*(\S+)/);

                    const maxAmount = amountMatch ? amountMatch[1] : ''; // e.g., '238,800,000'
                    const lender = lenderMatch ? lenderMatch[1] : '';   // e.g., '신한은행'
                    const setupDate = mortgage.설정일자 || '';  // e.g., '2015-06-30'
                    const debtor = mortgage.채무자 || '';       // e.g., '홍길동'

                    addLoanItem({
                        setup_date: setupDate,
                        lender: lender,
                        debtor: debtor,
                        max_amount: maxAmount,
                        status: '유지',
                        rank: mortgage.main_key || ''
                    });
                });
            } else {
                // 근저당 정보가 없으면, 깨끗한 기본 대출 항목 하나만 추가합니다.
                addLoanItem();
            }

            // --- 4. 모든 자동 입력이 끝난 후, 후속 처리를 실행합니다. ---

            // 새로 추가된 모든 대출 항목의 금액 변환을 강제로 실행시킵니다.
            document.querySelectorAll('.loan-item [name="max_amount"]').forEach(input => {
                input.dispatchEvent(new Event('blur'));
            });

            // [신규] KB시세 창 자동 열기 (팝업 방식)
            if (scraped.search_address) {
                console.log(`🏠 KB시세 자동 검색: ${scraped.search_address}`);

                // 클립보드 복사 (백업)
                navigator.clipboard.writeText(scraped.search_address);

                // ★ 핵심: URL 파라미터로 검색 주소를 전달
                // content.js가 페이지 로드 시 파라미터를 감지하여 자동 검색 실행
                const encodedAddress = encodeURIComponent(scraped.search_address);
                const kbUrl = `https://kbland.kr/map?xy=37.5205559,126.9265729,16&autoSearch=${encodedAddress}`;

                // 팝업 창 크기 및 위치 설정
                const popupWidth = 1200;
                const popupHeight = 900;
                const left = (window.innerWidth - popupWidth) / 2;
                const top = (window.innerHeight - popupHeight) / 2;

                console.log(`📍 KB Land 팝업 열기: ${kbUrl}`);
                window.open(
                    kbUrl,
                    'kbLandPopup',
                    `width=${popupWidth},height=${popupHeight},left=${left},top=${top},resizable=yes,scrollbars=yes`
                );
            }

            // PDF 뷰어를 표시하고 파일 이름을 보여줍니다.
            const fileURL = URL.createObjectURL(file);
            const pdfViewer = document.getElementById('pdf-viewer');
            const uploadSection = document.getElementById('upload-section');
            const viewerSection = document.getElementById('viewer-section');
            const fileNameDisplay = document.getElementById('file-name-display');
            // ✅ [수정] PDF 직접 열기 버튼에 클릭 이벤트 추가
            const directViewBtn = document.getElementById('direct-view-pdf-btn');

            if (pdfViewer) pdfViewer.src = fileURL;
            // ✅ [수정] PDF 직접 열기 기능 구현 (모바일 iframe 문제 해결)
            if (directViewBtn) {
                directViewBtn.onclick = () => {
                    const isMobile = window.matchMedia('(max-width: 768px)').matches;
                    // 모바일: 새 탭, PC: 현재 창에서 열기
                    window.open(fileURL, isMobile ? '_blank' : '_self');
                };
            }

            if (uploadSection) uploadSection.style.display = 'none';
            if (viewerSection) viewerSection.style.display = 'block';
            if (fileNameDisplay) fileNameDisplay.textContent = file.name;
            setPdfColumnExpanded(); // PDF 업로드 시 PDF 컬럼 확장

            // 최종적으로 메모를 업데이트합니다.
            triggerMemoGeneration();

            // ✅ [신규] 질권 체크 상태에서 지방 물건이면 경고 표시
            checkRegionWarningForCollateral(scraped.address);

        } else {
            alert(`업로드 실패: ${result.error || '알 수 없는 오류'}`);
        }

    } catch (error) {
        alert(`업로드 중 오류가 발생했습니다: ${error.message}`);
    } finally {
        spinner.style.display = 'none';
    }
}

    // 레이아웃 토글 (가로/세로 모드 전환)
    function toggleLayout() {
        const mainContainer = document.querySelector('.main-container');
        const layoutToggleBtn = document.getElementById('layout-toggle-btn');
        const isMobile = window.matchMedia('(max-width: 768px)').matches;

        if (!mainContainer || !layoutToggleBtn) {
            console.error('❌ main-container 또는 layout-toggle-btn을 찾을 수 없습니다');
            return;
        }

        // 모바일 기기에서 가로 모드 상태일 때 변경 방지
        if (isMobile && mainContainer.classList.contains('horizontal-layout')) {
            console.warn('⚠️ 모바일에서는 가로 모드로만 사용할 수 있습니다');
            showCustomAlert('모바일에서는 가로 모드로만 사용할 수 있습니다');
            return;
        }

        // 가로 모드 토글
        mainContainer.classList.toggle('horizontal-layout');

        // 버튼 텍스트 업데이트
        if (mainContainer.classList.contains('horizontal-layout')) {
            layoutToggleBtn.innerHTML = '<i class="bi bi-distribute-vertical"></i> 세로 모드';
            console.log('✅ 가로 모드로 전환됨');
        } else {
            layoutToggleBtn.innerHTML = '<i class="bi bi-distribute-horizontal"></i> 가로 모드';
            console.log('✅ 세로 모드로 전환됨');
        }

        // 현재 레이아웃 설정 저장
        saveLayoutSettings();
    }

    // 전체 초기화
    function clearAllFields() {
        document.querySelectorAll('.form-field').forEach(field => {
            if(field.tagName === 'SELECT') {
                field.selectedIndex = 0;
            } else {
                field.value = '';
            }
        });

        safeSetValue('customer_name_2', '');
        safeSetValue('ltv1', '80');

        const deductionRegion = document.getElementById('deduction_region');
        if (deductionRegion) {
            const deductionRegionValue = deductionRegion.value;
            safeSetValue('deduction_amount', (deductionRegionValue !== '0' && deductionRegionValue) ?
                parseInt(deductionRegionValue).toLocaleString() : '');
        }

        const loanContainer = document.getElementById('loan-items-container');
        if (loanContainer) {
            loanContainer.innerHTML = '';
            loanItemCounter = 0;
            addLoanItem();
        }

        const fileInput = document.getElementById('file-input');
        if (fileInput) fileInput.value = null;

        const pdfViewer = document.getElementById('pdf-viewer');
        if (pdfViewer) pdfViewer.src = 'about:blank';

        // ✅ [수정] 직접 열기 버튼 이벤트 핸들러 초기화
        const directViewBtn = document.getElementById('direct-view-pdf-btn');
        if (directViewBtn) directViewBtn.onclick = null;

        const uploadSection = document.getElementById('upload-section');
        if (uploadSection) uploadSection.style.display = 'flex';

        // 지분한도 계산기 필드 초기화
        safeSetValue('share-customer-name-1', '');
        safeSetValue('share-customer-birth-1', '');
        safeSetValue('share-customer-name-2', '');
        safeSetValue('share-customer-birth-2', '');

        const viewerSection = document.getElementById('viewer-section');
        if (viewerSection) viewerSection.style.display = 'none';

        // 등기 경고 숨김
        hideRegistrationWarning();
        // 압류 경고 숨김
        hideSeizureWarning();

        setPdfColumnCompact(); // 전체 초기화 시 PDF 컬럼 컴팩트
        alert("모든 입력 내용이 초기화되었습니다.");
        triggerMemoGeneration();
    }
    
    // 개별 차주 지분 한도 계산
    // [API 호출 함수들] loadCustomerData(라인 827), handleFileUpload(라인 1070), calculateLTVFromRequiredAmount(라인 1929) 참고
    // [관련 계산] calculatePrincipalFromRatio(라인 349), calculateSimpleInterest(라인 472), calculateLTVFromRequiredAmount(라인 1929), calculateBalloonLoan(라인 2034) 참고
    async function calculateIndividualShare() {
        try {
            // 지분시세 자동 갱신
            updateSharePrice();

            // ✅ [수정] 먼저 차주 선택 여부를 확인 (라디오 버튼 체크)
            const selectedRadio = document.querySelector('input[name="share-borrower"]:checked');
            if (!selectedRadio) return; // 선택된 차주가 없으면 조용히 종료 (경고 없음)

            // 질권 체크 상태 확인
            const hopeCheckbox = document.getElementById('hope-collateral-loan');
            const meritzCheckbox = document.getElementById('meritz-collateral-loan');
            const isHopeChecked = hopeCheckbox && hopeCheckbox.checked;
            const isMeritzChecked = meritzCheckbox && meritzCheckbox.checked;

            // 주소 확인
            const address = document.getElementById('address').value.trim();
            if (!address) {
                showCustomAlert('주소를 입력해주세요.');
                return;
            }

            // ✅ 질권이 체크된 경우에만 급지 제한 적용
            if (isHopeChecked || isMeritzChecked) {
                const regionGrade = getRegionGradeFromAddress(address);
                if (regionGrade !== '1군') {
                    showCustomAlert('⚠️ 질권이 체크된 경우 지분한도 계산은 1군 지역만 가능합니다.\n현재 지역: ' + regionGrade);
                    return;
                }
            }

            const ownerIdx = selectedRadio.value;

            const kbPriceText = document.getElementById("kb_price").value.replace(/,/g,'') || "0";
            const kbPrice = parseInt(kbPriceText);

            // 면적도 함께 가져오기
            const areaText = document.getElementById('area').value.trim();
            const area = parseFloat(areaText) || null;

            // LTV 비율 수집 (지분용 share-ltv 사용)
            const ltvRates = [];
            const shareLtv = document.getElementById("share-ltv")?.value;
            if (shareLtv && shareLtv.trim()) ltvRates.push(parseFloat(shareLtv));
            if (ltvRates.length === 0) ltvRates.push(80); // 기본값 80%

            // 대출 데이터 수집
            let loans = [];
            document.querySelectorAll("#loan-items-container .loan-item").forEach(item => {
                const maxAmount = item.querySelector("input[name='max_amount']")?.value.replace(/,/g,'') || "0";
                const ratio = item.querySelector("input[name='ratio']")?.value || "120";
                const principal = item.querySelector("input[name='principal']")?.value.replace(/,/g,'') || "0";
                const status = item.querySelector("select[name='status']")?.value || "-";
                
                // 선말소 상태인 경우 선순위로 분류
                const loanType = (status === "선말소") ? "선순위" : "후순위";
                
                loans.push({
                    max_amount: parseInt(maxAmount) || 0,
                    ratio: parseFloat(ratio) || 120,
                    principal: parseInt(principal) || 0,
                    status: status,
                    type: loanType
                });
            });

            // 소유자 데이터 수집
            const nameField = document.getElementById(`share-customer-name-${ownerIdx}`);
            const shareField = document.getElementById(`share-customer-birth-${ownerIdx}`);
            
            if (!nameField || !shareField || !nameField.value.trim()) {
                return; // 정보가 없으면 조용히 종료
            }
            
            const shareText = shareField.value.trim();
            // 다양한 형태의 지분율 파싱
            let sharePercent = 0;
            if (shareText) {
                // 1. 괄호 안 퍼센트 우선 추출: "1/2 (50.0%)" -> 50.0
                const percentMatch = shareText.match(/\(([\d.]+)%?\)/);
                if (percentMatch) {
                    sharePercent = parseFloat(percentMatch[1]);
                } else {
                    // 2. 일반 숫자 추출: "50", "50%" -> 50
                    const numberMatch = shareText.match(/([\d.]+)%?/);
                    sharePercent = numberMatch ? parseFloat(numberMatch[1]) : 0;
                }
            }
            
            if (sharePercent === 0) {
                // 지분율이 입력되지 않은 경우 경고창 표시
                showCustomAlert("지분율을 선택해주세요");
                return;
            }
            
            let owners = [{
                "이름": nameField.value,
                "지분율": `${sharePercent}%`
            }];

            // 기존 지분 계산 메모 제거
            let currentMemo = document.getElementById('generated-memo').value;
            currentMemo = currentMemo.replace(/\n\n--- 개별 지분 한도 계산 ---[\s\S]*?$/g, '');
            
            // 대출 상태 확인해서 후순위/선순위 결정
            const maintainStatus = ['유지', '동의', '비동의'];
            const hasSubordinate = loans.some(loan => maintainStatus.includes(loan.status));
            const loanTypeInfo = hasSubordinate ? "후순위" : "선순위";
            
            let individualShareMemo = '\n\n--- 개별 지분 한도 계산 ---';
            let ownerName = '';

            // 각 LTV에 대해 계산
            for (let i = 0; i < ltvRates.length; i++) {
                let ltv = ltvRates[i];

                const payload = {
                    total_value: kbPrice,
                    ltv: ltv,
                    loans: loans,
                    owners: owners,
                    loan_type: loanTypeInfo,
                    address: address,
                    area: area,
                    is_meritz_checked: isMeritzChecked, // 메리츠 체크 여부 분리
                    is_hope_checked: isHopeChecked      // 아이엠 체크 여부 분리
                };

                const res = await fetch("/api/calculate_individual_share", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                
                if (!res.ok) continue; // 오류 시 다음 LTV로
                
                const data = await res.json();
                
                if (data.success && data.results.length > 0) {
                    const result = data.results[0];
                    let shareLimit = result["지분LTV한도(만원)"];
                    let available = result["가용자금(만원)"];

                    // 필요금액이 입력된 경우 한도와 가용자금 덮어쓰기
                    const shareRequiredAmountField = document.getElementById('share-required-amount');
                    const shareRequiredAmountText = shareRequiredAmountField ? shareRequiredAmountField.value.replace(/,/g, '') : '';
                    const shareRequiredAmount = parseInt(shareRequiredAmountText) || 0;
                    if (shareRequiredAmount > 0) {
                        // 대환/선말소 원금 합계 계산
                        const replaceStatuses = ['대환', '선말소', '퇴거자금'];
                        let existingPrincipal = 0;
                        loans.forEach(loan => {
                            if (replaceStatuses.includes(loan.status)) {
                                existingPrincipal += (loan.principal || 0);
                            }
                        });
                        shareLimit = shareRequiredAmount;
                        available = shareRequiredAmount - existingPrincipal;
                    }

                    // 첫 번째 결과에서만 차주명과 지분율 표시
                    if (i === 0) {
                        ownerName = result.이름;
                        // 지분율 표시 방식 구분 (PDF 스크래핑 vs 수기입력)
                        const originalShareText = shareField.value.trim();
                        let displayShare;
                        
                        // PDF 스크래핑 시: 분수나 괄호가 포함된 경우 원본값 그대로
                        if (originalShareText.includes('/') || originalShareText.includes('(') || originalShareText.includes('%')) {
                            // 이미 "지분율"이 포함되어 있으면 그대로, 없으면 추가
                            if (originalShareText.includes('지분율')) {
                                displayShare = originalShareText;
                            } else {
                                displayShare = `지분율 ${originalShareText}`;
                            }
                        } else {
                            // 수기입력 시: 숫자에 % 추가
                            displayShare = `지분율 ${sharePercent}%`;
                        }
                        
                        individualShareMemo += `\n차주 ${ownerName} ${displayShare}`;
                    }
                    
                    // --- ### 여기부터 수정 ### ---
                    // 기본 메모 라인 (한도까지)
                    let memoLine = `\n${loanTypeInfo} LTV ${ltv}% 지분 ${shareLimit.toLocaleString()}만`;
                    
                    // 'available' 값이 존재할 경우 (즉, 선순위일 경우)에만 '가용' 금액 추가
                    if (available !== null && available !== undefined) {
                        memoLine += ` 가용 ${available.toLocaleString()}만`;
                    }
                    
                    individualShareMemo += memoLine;
                    // --- ### 여기까지 수정 ### ---
                }
            }

            // 아이엠 또는 메리츠가 체크된 경우, 고정 텍스트 섹션 추가 (변수는 함수 최상단에서 이미 선언됨)
            if (isHopeChecked || isMeritzChecked) {
                individualShareMemo += '\n';
                individualShareMemo += '\n*본심사시 금액 변동될수 있습니다.';
                individualShareMemo += '\n*사업자 담보대출 (사업자필)';
                individualShareMemo += '\n*계약 2년';
                individualShareMemo += '\n*중도 3%';
                individualShareMemo += '\n*연체이력 및 권리침해사항 1% 할증';
            }

            const memoTextarea = document.getElementById('generated-memo');
            memoTextarea.value = currentMemo + individualShareMemo;

            // 메모 크기 자동 조절
            autoResizeTextarea(memoTextarea);
        } catch (error) {
            console.error("지분 계산 오류:", error);
        }
    }
    
// 모든 이벤트 리스너 최초 연결
function attachAllEventListeners() {
    const uploadSection = document.getElementById('upload-section');
    const fileInput = document.getElementById('file-input');
    const reuploadBtn = document.getElementById('reupload-btn');

    if (!uploadSection || !fileInput) {
        console.error('⚠️ uploadSection 또는 fileInput을 찾을 수 없습니다');
        return;
    }

    uploadSection.addEventListener('click', () => fileInput.click());
    if (reuploadBtn) {
        reuploadBtn.addEventListener('click', () => fileInput.click());
    }
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFileUpload(fileInput.files[0]);
    });

    // [관련 함수] 대출 항목 드래그는 라인 362의 initializeDragAndDrop() 참고
    ['dragover','dragleave','drop'].forEach(eventName => {
        uploadSection.addEventListener(eventName, e => {
            e.preventDefault();
            e.stopPropagation();
        }, false);
    });

    uploadSection.addEventListener('dragover', () => uploadSection.classList.add('dragover'));
    uploadSection.addEventListener('dragleave', () => uploadSection.classList.remove('dragover'));
    uploadSection.addEventListener('drop', (e) => {
        uploadSection.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0]);
    });

    document.querySelectorAll('.manwon-format').forEach(input => {
        input.addEventListener('blur', formatManwonValue);
    });
    
    document.querySelectorAll('input[name="share-borrower"]').forEach(radio => {
        radio.addEventListener('change', function() {
            calculateIndividualShare();
            updateCollateralRateDisplay();
        });
        radio.addEventListener('click', function() {
            setTimeout(() => {
                calculateIndividualShare();
                updateCollateralRateDisplay();
            }, 50);
        });
    });
    

    // [정리 및 통합] 필요금액 변경 시 LTV 자동 계산을 최우선으로 실행

    // ✅ [수정] KB시세 입력 시에는 LTV 초기값(80)이 지워지지 않도록 이벤트 리스너 제거
    // 필요금액 역계산 시에만 LTV를 자동 계산하고 싶으면 필요금액 필드에만 이벤트 추가

    // 필요금액 변경 시: LTV 자동 계산 -> 지분 개별 계산
    document.getElementById('required_amount')?.addEventListener('change', calculateLTVFromRequiredAmount);
    document.getElementById('required_amount')?.addEventListener('blur', calculateLTVFromRequiredAmount);
    
    // 3. LTV1 변경 시 (수동 입력 또는 +/- 버튼): 필요금액 역계산 후 메모/지분 재계산
    document.getElementById('ltv1')?.addEventListener('change', function() {
        // LTV 수동 변경 시 필요금액 역계산
        calculateRequiredAmountFromLTV();
        calculateIndividualShare();
        validateHopeLoanConditions();  // 아이엠 선순위 LTV 70% 검증
        updateCollateralRateDisplay();
    });
    document.getElementById('ltv1')?.addEventListener('blur', function() {
        // LTV 수동 변경 시 필요금액 역계산
        calculateRequiredAmountFromLTV();
        calculateIndividualShare();
        validateHopeLoanConditions();  // 아이엠 선순위 LTV 70% 검증
        updateCollateralRateDisplay();
    });

    // 4. 지분용 LTV (share-ltv) 변경 시: 지분 개별 계산
    document.getElementById('share-ltv')?.addEventListener('change', calculateIndividualShare);
    document.getElementById('share-ltv')?.addEventListener('blur', calculateIndividualShare);

    // 5. 지분용 필요금액 (share-required-amount) 변경 시: LTV 역산 후 지분 계산
    document.getElementById('share-required-amount')?.addEventListener('change', calculateShareLTVFromRequiredAmount);
    document.getElementById('share-required-amount')?.addEventListener('blur', calculateShareLTVFromRequiredAmount);

    // 6. 지분율 변경 시: 지분 개별 계산 (기존 로직 유지)
    document.getElementById('share-customer-birth-1')?.addEventListener('change', function() {
        autoCalculateShareRatio(1, 2);
        calculateIndividualShare();
    });
    document.getElementById('share-customer-birth-1')?.addEventListener('blur', function() {
        autoCalculateShareRatio(1, 2);
        calculateIndividualShare();
    });
    document.getElementById('share-customer-birth-2')?.addEventListener('change', function() {
        autoCalculateShareRatio(2, 1);
        calculateIndividualShare();
    });
    document.getElementById('share-customer-birth-2')?.addEventListener('blur', function() {
        autoCalculateShareRatio(2, 1);
        calculateIndividualShare();
    });
    
    // LTV1의 +/- 버튼 클릭 시에도 필요금액 역계산 후 메모/지분 재계산
    document.querySelectorAll('.md-ltv-btn').forEach(btn => {
        btn.addEventListener('click', () => {
             // LTV 수동 변경 시 필요금액 역계산
             calculateRequiredAmountFromLTV();
             // LTV1 값이 수동으로 변경된 후, 메모 및 지분 계산 트리거 호출
             triggerMemoGeneration();
             calculateIndividualShare();
        });
    });


    const loanAmountInput = document.getElementById('interest-loan-amount');
    const annualRateInput = document.getElementById('interest-annual-rate');
    const balloonPrincipalPctInput = document.getElementById('balloon-principal-pct');
    const balloonMonthsInput = document.getElementById('balloon-months');

    function updateAllInterestCalculators() {
        calculateSimpleInterest();
        calculateBalloonLoan();
    }
    loanAmountInput.addEventListener('keyup', updateAllInterestCalculators);
    annualRateInput.addEventListener('keyup', updateAllInterestCalculators);

    // 월할/일할 라디오 버튼 변경 시 재계산
    document.querySelectorAll('input[name="interestCalcMethod"]').forEach(radio => {
        radio.addEventListener('change', updateAllInterestCalculators);
    });

    loanAmountInput.addEventListener('blur', (e) => {
        const value = e.target.value.replace(/,/g, '');
        const num = parseInt(value, 10);
        if (!isNaN(num) && num > 0) {
            e.target.value = num.toLocaleString();
        } else {
            e.target.value = '';
        }
    });

    if (balloonPrincipalPctInput) {
       balloonPrincipalPctInput.addEventListener('input', calculateBalloonLoan);
       balloonMonthsInput.addEventListener('input', calculateBalloonLoan);
    }

    document.getElementById('load-customer-btn').addEventListener('click', loadCustomerData);
    document.getElementById('delete-customer-btn').addEventListener('click', deleteCustomer);
    document.getElementById('reset-btn').addEventListener('click', () => location.reload());
    document.getElementById('save-new-btn').addEventListener('click', saveNewCustomer);
    document.getElementById('update-btn').addEventListener('click', updateCustomer);
    document.getElementById('layout-toggle-btn').addEventListener('click', toggleLayout);

    // 방공제 지역 선택 시 자동 금액 설정
    document.getElementById('deduction_region').addEventListener('change', (e) => {
        document.getElementById('deduction_amount').value = e.target.value !== '0' ? 
            parseInt(e.target.value).toLocaleString() : '';
        checkTenantDeductionWarning(); 
        triggerMemoGeneration();
    });

    // 방공제 금액 수기 입력 시 지역 선택 확인
    document.getElementById('deduction_amount').addEventListener('input', (e) => {
        const deductionRegionSelect = document.getElementById('deduction_region');
        const deductionAmount = e.target.value.trim();
        
        // 방공제 금액이 입력되었는데 지역이 선택되지 않은 경우
        if (deductionAmount && (!deductionRegionSelect.value || deductionRegionSelect.value === '0')) {
            showCustomAlert("방공제지역을 선택하여 주세요", () => {
                // 확인/닫기 버튼 클릭 시 포커스를 지역 선택으로 이동
                deductionRegionSelect.focus();
            });
        }
        
        triggerMemoGeneration();
    });

    // 소유권이전일 입력 시 색상 변경
    document.getElementById('ownership_transfer_date').addEventListener('input', (e) => {
        checkTransferDateColor(e.target.value);
        triggerMemoGeneration();
    });

    document.querySelectorAll('.form-field:not(.loan-input)').forEach(field => {
       field.addEventListener('change', triggerMemoGeneration);
       if (field.type === 'text' && !field.classList.contains('manwon-format')) {
           field.addEventListener('keyup', triggerMemoGeneration);
       }
    });

    // 페이지 로드 시 소유권이전일이 있으면 색상 체크
    window.addEventListener('load', () => {
        const transferDateField = document.getElementById('ownership_transfer_date');
        if (transferDateField && transferDateField.value) {
            console.log('📄 페이지 로드 - ownership_transfer_date 색상 체크:', transferDateField.value);
            checkTransferDateColor(transferDateField.value);
        }
    });

    // 희망담보대부 적용 체크박스 이벤트
    const hopeCollateralCheckbox = document.getElementById('hope-collateral-loan');
    const regionButtonsDiv = document.getElementById('hope-loan-region-buttons');

    if (hopeCollateralCheckbox) {
        hopeCollateralCheckbox.addEventListener('change', (e) => {
            const ltv1Field = document.getElementById('ltv1');

            if (e.target.checked) {
                // 아이엠 체크 시, 메리츠 체크 해제 (이벤트 발생 없이 UI만 정리)
                const meritzCheckbox = document.getElementById('meritz-collateral-loan');
                const meritzRegionBtnsDiv = document.getElementById('meritz-loan-region-buttons');
                if (meritzCheckbox && meritzCheckbox.checked) {
                    meritzCheckbox.checked = false;
                    // 메리츠 지역 버튼 숨김 (이벤트 없이 직접 처리)
                    if (meritzRegionBtnsDiv) {
                        meritzRegionBtnsDiv.style.cssText = 'display: none !important;';
                    }
                    document.querySelectorAll('.meritz-loan-region-btn').forEach(b => {
                        b.style.backgroundColor = '';
                        b.style.color = '';
                        b.style.borderColor = '';
                    });
                    console.log('❌ 메리츠 체크 해제 (아이엠 전환)');
                }
                // 체크 되면 지역 버튼 표시
                regionButtonsDiv.style.cssText = 'display: flex !important;';
                // --- ▼▼▼ 방공제 없음으로 자동 선택 및 방공제(만) 금액 삭제 ▼▼▼ ---
                const deductionRegionField = document.getElementById('deduction_region');
                const deductionAmountField = document.getElementById('deduction_amount');
                if (deductionRegionField) {
                    deductionRegionField.value = '0';
                    console.log('💰 방공제 지역 - "방공제없음"으로 자동 선택');
                }
                if (deductionAmountField) {
                    deductionAmountField.value = '';  // 방공제(만) 필드의 금액 삭제
                    console.log('💰 방공제(만) - 금액 삭제');
                }
                // --- ▼▼▼ 주소 기반 지역 자동 선택 (서울/경기/인천) ▼▼▼ ---
                const addressField = document.getElementById('address');
                let regionFound = false;

                if (addressField && addressField.value) {
                    let regionToSelect = null;
                    const address = addressField.value;

                    // 주소에 포함된 지역 확인 (우선순위: 인천 > 경기 > 서울)
                    if (address.includes('인천')) {
                        regionToSelect = '인천';
                    } else if (address.includes('경기')) {
                        regionToSelect = '경기';
                    } else if (address.includes('서울')) {
                        regionToSelect = '서울';
                    }

                    if (regionToSelect) {
                        // 해당 지역 버튼 찾아서 자동 클릭
                        const button = document.querySelector(`.hope-loan-region-btn[data-region="${regionToSelect}"]`);
                        if (button) {
                            button.click();
                            console.log(`🌍 아이엠 지역 자동 선택: ${regionToSelect}`);
                            regionFound = true;
                        }
                    }
                }

                // --- ▼▼▼ 선순위/후순위 판단 및 LTV 자동 설정 ▼▼▼ ---
                // 유지/동의/비동의가 있으면 후순위, 없으면 선순위
                const maintainStatus = ['유지', '동의', '비동의'];
                let hasSubordinate = false;
                document.querySelectorAll('.loan-item').forEach(item => {
                    const status = item.querySelector('[name="status"]')?.value || '-';
                    if (maintainStatus.includes(status)) {
                        hasSubordinate = true;
                    }
                });

                if (ltv1Field) {
                    // ✅ 필요금액이 입력되어 있으면 역계산 LTV 유지
                    const requiredAmountField = document.getElementById('required_amount');
                    const hasRequiredAmount = requiredAmountField && requiredAmountField.value && parseKoreanNumberString(requiredAmountField.value) > 0;

                    if (hasRequiredAmount) {
                        // 필요금액이 입력되어 있으면 역계산 LTV 유지
                        console.log('📊 아이엠 체크 - 역계산 LTV 유지 (필요금액 입력됨)');
                    } else if (!hasSubordinate) {
                        // 선순위: LTV 70%로 자동 설정
                        ltv1Field.value = '70';
                        console.log('📊 아이엠 선순위 - LTV 70%로 자동 설정');
                    } else {
                        // 후순위: LTV 80%로 자동 설정
                        ltv1Field.value = '80';
                        console.log('📊 아이엠 후순위 - LTV 80%로 자동 설정');
                    }
                }
                // --- ▲▲▲ 여기까지가 추가된 코드 ▲▲▲ ---

                console.log('✅ 희망담보대부 적용 - 지역 버튼 표시');

                // ✅ [신규] 아이엠 체크 시 지방 물건 경고
                const currentAddress = document.getElementById('address')?.value || '';
                checkRegionWarningForCollateral(currentAddress);
            } else {
                // 체크 해제되면 지역 버튼 숨김
                regionButtonsDiv.style.cssText = 'display: none !important;';
                // 버튼 스타일 초기화
                document.querySelectorAll('.hope-loan-region-btn').forEach(b => {
                    b.style.backgroundColor = '';
                    b.style.color = '';
                    b.style.borderColor = '';
                });

                // --- LTV 비율 처리: 메리츠도 체크 안 되어 있으면 80%로 설정 ---
                const meritzCheckbox = document.getElementById('meritz-collateral-loan');
                const isMeritzChecked = meritzCheckbox && meritzCheckbox.checked;

                // ✅ [수정] 필요금액이 입력되어 있으면 역계산 LTV 유지
                const requiredAmountField = document.getElementById('required_amount');
                const hasRequiredAmount = requiredAmountField && requiredAmountField.value && parseKoreanNumberString(requiredAmountField.value) > 0;

                if (ltv1Field) {
                    if (hasRequiredAmount) {
                        // 필요금액이 입력되어 있으면 역계산 LTV 유지
                        console.log('📊 LTV 비율 ① - 역계산 LTV 유지 (필요금액 입력됨)');
                    } else if (!isMeritzChecked) {
                        // 메리츠도 체크 안 되어 있고, 필요금액도 없으면 기본 80%로 설정
                        ltv1Field.value = '80';
                        console.log('📊 LTV 비율 ① - 기본값 80%로 설정 (질권 없음)');
                    } else {
                        // 메리츠가 체크되어 있으면 LTV를 유지
                        console.log('📊 LTV 비율 ① - 메리츠 질권 유지');
                    }
                }
                console.log('❌ 희망담보대부 해제 - 지역 버튼 숨김');
            }
            // 희망담보대부 조건 검증
            validateHopeLoanConditions();
            updateCollateralRateDisplay();
            triggerMemoGeneration();
        });
    }

    // 세대수 입력 시 희망담보대부 조건 검증
    const unitCountField = document.getElementById('unit_count');
    if (unitCountField) {
        unitCountField.addEventListener('input', validateHopeLoanConditions);
        unitCountField.addEventListener('change', validateHopeLoanConditions);
    }

    // KB시세 입력 시 희망담보대부 조건 검증
    const kbPriceField = document.getElementById('kb_price');
    if (kbPriceField) {
        kbPriceField.addEventListener('input', validateHopeLoanConditions);
        kbPriceField.addEventListener('blur', validateHopeLoanConditions);
    }

    // 준공일자 입력 시 희망담보대부 조건 검증
    const completionDateField = document.getElementById('completion_date');
    if (completionDateField) {
        completionDateField.addEventListener('input', validateHopeLoanConditions);
        completionDateField.addEventListener('change', validateHopeLoanConditions);
    }

    // 희망담보대부 지역 선택 버튼 이벤트
    document.querySelectorAll('.hope-loan-region-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const region = e.target.getAttribute('data-region');

            // ✅ [수정] 지역 버튼은 금리 계산용 지역 정보만 제공, LTV는 변경하지 않음
            console.log(`🌍 아이엠 지역 선택: ${region} (금리 계산용)`);

            // 모든 버튼 스타일 초기화
            document.querySelectorAll('.hope-loan-region-btn').forEach(b => {
                b.style.backgroundColor = '';
                b.style.color = '';
                b.style.borderColor = '';
            });

            // 클릭된 버튼에만 스타일 적용
            e.target.style.backgroundColor = '#9CC3D5';
            e.target.style.color = '#0063B2';
            e.target.style.borderColor = '#9CC3D5';

            // 금리 계산을 위한 메모 업데이트
            triggerMemoGeneration();
        });
    });

    // 메리츠 질권 적용 체크박스 이벤트
    const meritzCollateralCheckbox = document.getElementById('meritz-collateral-loan');
    const meritzRegionButtonsDiv = document.getElementById('meritz-loan-region-buttons');

    if (meritzCollateralCheckbox) {
        meritzCollateralCheckbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                // 메리츠 체크 시, 아이엠 체크 해제 (이벤트 발생 없이 UI만 정리)
                const hopeCheckbox = document.getElementById('hope-collateral-loan');
                const hopeRegionButtonsDiv = document.getElementById('hope-loan-region-buttons');
                if (hopeCheckbox && hopeCheckbox.checked) {
                    hopeCheckbox.checked = false;
                    // 아이엠 지역 버튼 숨김 (이벤트 없이 직접 처리)
                    if (hopeRegionButtonsDiv) {
                        hopeRegionButtonsDiv.style.cssText = 'display: none !important;';
                    }
                    document.querySelectorAll('.hope-loan-region-btn').forEach(b => {
                        b.style.backgroundColor = '';
                        b.style.color = '';
                        b.style.borderColor = '';
                    });
                    console.log('❌ 아이엠 체크 해제 (메리츠 전환)');
                }

                // 체크 되면 메리츠 지역 버튼 표시
                if (meritzRegionButtonsDiv) {
                    meritzRegionButtonsDiv.style.cssText = 'display: flex !important;';
                }

                // --- ▼▼▼ 방공제 없음으로 자동 선택 및 방공제(만) 금액 삭제 ▼▼▼ ---
                const deductionRegionField = document.getElementById('deduction_region');
                const deductionAmountField = document.getElementById('deduction_amount');
                if (deductionRegionField) {
                    deductionRegionField.value = '0';
                    console.log('💰 방공제 지역 - "방공제없음"으로 자동 선택');
                }
                if (deductionAmountField) {
                    deductionAmountField.value = '';  // 방공제(만) 필드의 금액 삭제
                    console.log('💰 방공제(만) - 금액 삭제');
                }
                // --- ▲▲▲ 여기까지가 추가된 코드 ▲▲▲ ---

                // --- ▼▼▼ 주소 기반 1군/2군/3군 자동 선택 ▼▼▼ ---
                const addressField = document.getElementById('address');
                if (addressField && addressField.value) {
                    const region = determineMeritzRegionFromAddress(addressField.value);
                    if (region) {
                        // 자동으로 해당 버튼 클릭
                        let btnSelector;
                        let regionLabel;

                        if (region === '1gun') {
                            btnSelector = '.meritz-loan-region-btn[data-region="1gun"]';
                            regionLabel = '1군(일반)';
                        } else if (region === '2gun') {
                            btnSelector = '.meritz-loan-region-btn[data-region="2gun"]';
                            regionLabel = '2군';
                        } else if (region === '3gun') {
                            btnSelector = '.meritz-loan-region-btn[data-region="3gun"]';
                            regionLabel = '3군';
                        }

                        const button = document.querySelector(btnSelector);
                        if (button) {
                            button.click();
                            console.log(`🌍 메리츠 지역 자동 선택: ${regionLabel}`);
                        }
                    }
                }
                // --- ▲▲▲ 여기까지가 추가된 코드 ▲▲▲ ---

                console.log('✅ 메리츠질권적용 - 활성화');

                // ✅ [신규] 메리츠 체크 시 지방 물건 경고
                const currentAddress = document.getElementById('address')?.value || '';
                checkRegionWarningForCollateral(currentAddress);
            } else {
                // 체크 해제되면 메리츠 지역 버튼 숨김
                if (meritzRegionButtonsDiv) {
                    meritzRegionButtonsDiv.style.cssText = 'display: none !important;';
                }
                // 버튼 스타일 초기화
                document.querySelectorAll('.meritz-loan-region-btn').forEach(b => {
                    b.style.backgroundColor = '';
                    b.style.color = '';
                    b.style.borderColor = '';
                });

                // --- LTV 비율 처리: 아이엠도 체크 안 되어 있으면 80%로 설정 ---
                const hopeCheckbox = document.getElementById('hope-collateral-loan');
                const isHopeChecked = hopeCheckbox && hopeCheckbox.checked;
                const ltv1Field = document.getElementById('ltv1');

                // ✅ [수정] 필요금액이 입력되어 있으면 역계산 LTV 유지
                const requiredAmountField = document.getElementById('required_amount');
                const hasRequiredAmount = requiredAmountField && requiredAmountField.value && parseKoreanNumberString(requiredAmountField.value) > 0;

                if (ltv1Field) {
                    if (hasRequiredAmount) {
                        // 필요금액이 입력되어 있으면 역계산 LTV 유지
                        console.log('📊 LTV 비율 ① - 역계산 LTV 유지 (필요금액 입력됨)');
                    } else if (!isHopeChecked) {
                        // 아이엠도 체크 안 되어 있고, 필요금액도 없으면 기본 80%로 설정
                        ltv1Field.value = '80';
                        console.log('📊 LTV 비율 ① - 기본값 80%로 설정 (질권 없음)');
                    } else {
                        // 아이엠이 체크되어 있으면 LTV를 유지
                        console.log('📊 LTV 비율 ① - 아이엠 질권 유지');
                    }
                }

                console.log('❌ 메리츠질권적용 - 비활성화, 지역 버튼 숨김');
            }
            // 메리츠 조건 검증 (LTV 자동 설정)
            validateMeritzLoanConditions();
            // LTV 설정 완료 후 금리 표시 및 메모 생성 (DOM 업데이트 대기)
            setTimeout(() => {
                updateCollateralRateDisplay();
                triggerMemoGeneration();
            }, 50);
        });
    }

    // 면적 입력 시 메리츠 조건 검증
    const areaField = document.getElementById('area');
    if (areaField) {
        areaField.addEventListener('input', validateMeritzLoanConditions);
        areaField.addEventListener('change', validateMeritzLoanConditions);
    }

    // KB시세 입력 시 메리츠 조건 검증 (1억 이상 검증)
    if (kbPriceField) {
        kbPriceField.addEventListener('input', validateMeritzLoanConditions);
        kbPriceField.addEventListener('blur', validateMeritzLoanConditions);
    }

    // 세대수 입력 시 메리츠 조건 검증 (APT 300세대 이하 체크)
    const meritzUnitCountField = document.getElementById('unit_count');
    if (meritzUnitCountField) {
        meritzUnitCountField.addEventListener('input', validateMeritzLoanConditions);
        meritzUnitCountField.addEventListener('change', validateMeritzLoanConditions);
    }

    // 물건유형 변경 시 메리츠 조건 검증 및 희망담보대부 조건 검증
    const propertyTypeField = document.getElementById('property_type');
    if (propertyTypeField) {
        propertyTypeField.addEventListener('change', validateMeritzLoanConditions);
        propertyTypeField.addEventListener('change', validateHopeLoanConditions);
    }

    // 주소 변경 시 메리츠 조건 검증 (군 단위 지역 체크)
    const meritzAddressField = document.getElementById('address');
    if (meritzAddressField) {
        meritzAddressField.addEventListener('input', validateMeritzLoanConditions);
        meritzAddressField.addEventListener('change', validateMeritzLoanConditions);
    }

    // 메리츠 지역 선택 버튼 이벤트
    document.querySelectorAll('.meritz-loan-region-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const region = e.target.getAttribute('data-region');
            meritzRegion = region;

            const regionLabel = region === '1gun' ? '1군(일반)' : (region === '2gun' ? '2군' : '3군');
            console.log(`🌍 메리츠 지역 선택: ${regionLabel}`);

            // 모든 버튼 스타일 초기화
            document.querySelectorAll('.meritz-loan-region-btn').forEach(b => {
                b.style.backgroundColor = '';
                b.style.color = '';
                b.style.borderColor = '';
            });

            // 클릭된 버튼에만 스타일 적용
            e.target.style.backgroundColor = '#9CC3D5';
            e.target.style.color = '#0063B2';
            e.target.style.borderColor = '#9CC3D5';

            // 지역 변경으로 인한 LTV 재계산
            validateMeritzLoanConditions();
            triggerMemoGeneration();
        });
    });

} // <--- 이 닫는 괄호가 핵심입니다.



    // 리사이즈 바 기능 구현
    function initializeResizeBar() {
        const resizeBar = document.getElementById('resize-bar');
        const pdfColumn = document.getElementById('pdf-column');
        const formColumn = document.getElementById('form-column-wrapper');
        const mainContainer = document.querySelector('.main-container');
        const pdfViewer = document.getElementById('pdf-viewer');

        if (!resizeBar || !pdfColumn || !formColumn || !mainContainer) return;

        // 이미 초기화된 경우 중복 방지
        if (resizeBar.dataset.initialized === 'true') return;
        resizeBar.dataset.initialized = 'true';

        let isResizing = false;
        let startPos = 0;
        let startPdfSize = 0;

        // ✅ [수정] 수직 리사이징 모드 여부를 판단하는 헬퍼 함수
        // 가로 모드(상하 분할) 또는 모바일 화면(768px 이하)일 때 Y축 기반 리사이징
        const isVerticalResize = () => {
            const isHorizontalLayout = mainContainer.classList.contains('horizontal-layout');
            const isMobileSize = window.matchMedia('(max-width: 768px)').matches;
            return isHorizontalLayout || isMobileSize;
        };

        // 세로 모드만 지원 (가로 모드 제거)

        function startResize(clientX, clientY) { // clientY를 인자로 받도록 수정
            isResizing = true;

            // [수정 1] 드래그를 시작할 때 iframe의 마우스 이벤트를 '끈다'.
            if (pdfViewer) pdfViewer.style.pointerEvents = 'none';

            // 트랜지션 효과를 잠시 꺼서 드래그가 끊기지 않게 합니다.
            pdfColumn.style.transition = 'none';
            formColumn.style.transition = 'none';

            // 드래그 중 텍스트가 선택되는 것을 방지합니다.
            document.body.style.userSelect = 'none';

            if (isVerticalResize()) {
                // ✅ [수정] 가로 모드/모바일: 상하 분할 모드, 세로 리사이징 (Y축 기준)
                startPos = clientY;
                startPdfSize = pdfColumn.getBoundingClientRect().height; // 높이 사용
                document.body.style.cursor = 'row-resize'; // 상하 조절 커서
            } else {
                // PC/세로 모드: 좌우 분할 모드, 가로 리사이징 (X축 기준)
                startPos = clientX;
                startPdfSize = pdfColumn.getBoundingClientRect().width; // 너비 사용
                document.body.style.cursor = 'col-resize'; // 좌우 조절 커서
            }
        }

        function doResize(clientX, clientY) { // clientY를 인자로 받도록 수정
            if (!isResizing) return;

            const isVertical = isVerticalResize();
            const delta = isVertical ? clientY - startPos : clientX - startPos; // Y축 또는 X축 델타
            const containerSize = isVertical ? mainContainer.clientHeight : mainContainer.clientWidth; // 전체 높이 또는 너비
            const resizeBarSize = isVertical ? resizeBar.clientHeight : resizeBar.clientWidth;
            const availableSize = containerSize - resizeBarSize;
            const minSize = 150; // 최소 크기 (150px)

            // PDF 컬럼의 새로운 크기 계산 (최소/최대 제한 포함)
            let newPdfSize = startPdfSize + delta;
            newPdfSize = Math.max(minSize, newPdfSize);
            newPdfSize = Math.min(availableSize - minSize, newPdfSize);

            // 폼 컬럼의 새로운 크기 계산
            const newFormSize = availableSize - newPdfSize;

            // 계산된 크기 비율에 따라 flex 값을 동적으로 설정
            const totalFlexSize = newPdfSize + newFormSize;

            // 수직 리사이징(가로 모드/모바일): 높이 기반
            if (isVertical) {
                pdfColumn.style.flex = `0 0 ${newPdfSize}px`;
                pdfColumn.style.height = `${newPdfSize}px`;
                formColumn.style.flex = '1';
            } else {
                // 수평 리사이징(세로 모드): 너비 기반
                pdfColumn.style.flex = `0 0 ${newPdfSize}px`;
                pdfColumn.style.width = `${newPdfSize}px`;
                formColumn.style.flex = '1';
            }

        }

        function endResize() {
            if (!isResizing) return;
            isResizing = false;

            // [수정 2] 드래그가 끝나면 iframe의 마우스 이벤트를 다시 '켠다'.
            pdfViewer.style.pointerEvents = 'auto';

            // 부드러운 효과를 위해 트랜지션을 다시 활성화합니다.
            pdfColumn.style.transition = '';
            formColumn.style.transition = '';

            // 텍스트 선택 방지 및 마우스 커서 스타일을 원래대로 복원합니다.
            document.body.style.userSelect = '';
            document.body.style.cursor = '';

            // 리사이즈가 끝난 후 현재 레이아웃 상태를 저장합니다.
            saveLayoutSettings();
        }

        // --- 이벤트 리스너 등록 ---

        // 마우스 이벤트
        resizeBar.addEventListener('mousedown', (e) => {
            e.preventDefault();
            startResize(e.clientX, e.clientY);
        });

        document.addEventListener('mousemove', (e) => {
            if (isResizing) {
                e.preventDefault();
                doResize(e.clientX, e.clientY);
            }
        });

        document.addEventListener('mouseup', endResize);
        document.addEventListener('mouseleave', endResize); // 마우스가 창 밖으로 나가도 드래그가 멈추도록 추가

        // 터치 이벤트 (모바일)
        resizeBar.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            startResize(touch.clientX, touch.clientY);
        }, { passive: false });

        document.addEventListener('touchmove', (e) => {
            if (isResizing) {
                e.preventDefault();
                const touch = e.touches[0];
                doResize(touch.clientX, touch.clientY);
            }
        }, { passive: false });

        document.addEventListener('touchend', endResize);
        document.addEventListener('touchcancel', endResize);

        // 더블클릭으로 기본 비율 복원
        resizeBar.addEventListener('dblclick', () => {
            // ✅ [수정] 모드에 따라 기본 비율 복원
            if (isVerticalResize()) {
                // 가로 모드/모바일: 상하 분할 레이아웃
                pdfColumn.style.flex = '0 0 auto';
                formColumn.style.flex = '1';
                pdfColumn.style.height = '30vh'; // 화면 아래 폼이 보이도록 30vh
            } else {
                // 세로 모드: 좌우 분할 레이아웃
                pdfColumn.style.flex = '2';
                formColumn.style.flex = '3';
                pdfColumn.style.width = 'initial';
            }
            saveLayoutSettings();
        });
    }

// ✨ LTV 비율 조정 함수들
function adjustLtvValue(inputId, change) {
    const input = document.getElementById(inputId);
    let currentValue = parseInt(input.value) || 0;
    
    // 빈 값일 때 버튼별 동작
    if (input.value === '' || currentValue === 0) {
        if (change < 0) {
            // - 버튼 누르면 75로 설정
            input.value = 75;
        } else {
            // + 버튼 누르면 85로 설정
            input.value = 85;
        }
        triggerMemoGeneration();
        return;
    }
    
    let newValue = currentValue + change;
    
    // 0 미만이면 0으로, 200 초과하면 200으로 제한 (5 단위 조정)
    newValue = Math.max(0, Math.min(200, newValue));
    
    input.value = newValue;
    triggerMemoGeneration();
}

function clearLtvValue(inputId) {
    const input = document.getElementById(inputId);
    input.value = '';
    triggerMemoGeneration();
}

// 필요금액 +/- 조정 함수
function adjustRequiredAmount(change) {
    const input = document.getElementById('required_amount');
    if (!input) return;

    // 현재 값 파싱 (콤마 제거)
    let currentValue = parseKoreanNumberString(input.value) || 0;

    // 빈 값일 때 버튼별 동작
    if (input.value === '' || currentValue === 0) {
        if (change < 0) {
            // - 버튼 누르면 4500으로 설정
            input.value = '4,500';
        } else {
            // + 버튼 누르면 5500으로 설정
            input.value = '5,500';
        }
        calculateLTVFromRequiredAmount();
        return;
    }

    let newValue = currentValue + change;

    // 0 미만이면 0으로 제한
    newValue = Math.max(0, newValue);

    // 천 단위 콤마 포맷
    input.value = newValue.toLocaleString();
    calculateLTVFromRequiredAmount();
}

// 필요금액 초기화 함수
function clearRequiredAmount() {
    const input = document.getElementById('required_amount');
    if (input) {
        input.value = '';
    }
    triggerMemoGeneration();
}

// LTV에서 필요금액 역계산 함수
function calculateRequiredAmountFromLTV() {
    const kbPriceField = document.getElementById('kb_price');
    const ltv1Field = document.getElementById('ltv1');
    const requiredAmountField = document.getElementById('required_amount');

    if (!kbPriceField || !ltv1Field || !requiredAmountField) return;

    const kbPrice = parseKoreanNumberString(kbPriceField.value) || 0;
    const ltv = parseFloat(ltv1Field.value) || 0;

    // KB시세나 LTV가 없으면 필요금액 비우기
    if (kbPrice <= 0 || ltv <= 0) {
        requiredAmountField.value = '';
        return;
    }

    // 유지/동의/비동의 채권최고액 합산
    const maintainStatuses = ['유지', '동의', '비동의'];
    let maintainMaxAmountSum = 0;
    document.querySelectorAll('.loan-item').forEach(item => {
        const statusSelect = item.querySelector('[name="status"]');
        const maxAmountInput = item.querySelector('[name="max_amount"]');
        if (statusSelect && maintainStatuses.includes(statusSelect.value)) {
            maintainMaxAmountSum += parseKoreanNumberString(maxAmountInput?.value) || 0;
        }
    });

    // 방공제 금액
    const deductionAmount = parseKoreanNumberString(document.getElementById('deduction_amount')?.value) || 0;

    // 필요금액 = KB시세 × LTV% - 유지 채권최고액 - 방공제
    const requiredAmount = Math.round((kbPrice * ltv / 100) - maintainMaxAmountSum - deductionAmount);

    // 0 이하면 비우기, 아니면 콤마 포맷으로 표시
    if (requiredAmount <= 0) {
        requiredAmountField.value = '';
    } else {
        requiredAmountField.value = requiredAmount.toLocaleString();
    }
}

// 고객명 & 생년월일 자동 파싱 기능
function parseCustomerNames() {
    const customerNameField = document.getElementById('customer_name');
    if (!customerNameField) return;
    
    const fullText = customerNameField.value.trim();
    if (!fullText) return;

    const customers = fullText.split(',').map(item => item.trim()).filter(item => item);
    const totalShares = customers.length; // 단순히 동등분할 가정

    customers.forEach((customer, index) => {
        if (index < 2) {
            const parts = customer.split(' ').filter(part => part.trim());
            if (parts.length >= 2) {
                const name = parts[0];
                const birth = parts[1];
                
                const nameField = document.getElementById(`share-customer-name-${index + 1}`);
                const shareField = document.getElementById(`share-customer-birth-${index + 1}`);
                
                if (nameField) nameField.value = `${name} ${birth}`;
                if (shareField) shareField.value = `1/${totalShares} (${(100/totalShares).toFixed(1)}%)`;
            }
        }
    });
}

// 페이지 로드 완료 후 실행
document.addEventListener('DOMContentLoaded', () => {
   // --- LTV 초기값 설정: 질권이 체크되어 있지 않으면 80%로 ---
   const ltv1Field = document.getElementById('ltv1');
   const hopeCheckbox = document.getElementById('hope-collateral-loan');
   const meritzCheckbox = document.getElementById('meritz-collateral-loan');

   if (ltv1Field && !ltv1Field.value) {
       const isHopeChecked = hopeCheckbox && hopeCheckbox.checked;
       const isMeritzChecked = meritzCheckbox && meritzCheckbox.checked;

       if (!isHopeChecked && !isMeritzChecked) {
           ltv1Field.value = '80';
           console.log('📊 LTV 초기값 설정: 80% (질권 없음)');
       }
   }
   // ---

   addLoanItem();
   attachAllEventListeners();
   loadCustomerList();

   // Select2 초기화 (고객 검색 기능)
   $('#customer-history').select2({
       placeholder: '고객명 검색...',
       allowClear: true,
       width: '100%',
       language: {
           noResults: function() { return '검색 결과 없음'; },
           searching: function() { return '검색중...'; }
       }
   });

   triggerMemoGeneration();
   validateHopeLoanConditions(); // 페이지 로드 시 희망담보대부 조건 검증
   validateMeritzLoanConditions(); // 페이지 로드 시 메리츠질권 조건 검증
   updateCollateralRateDisplay(); // 페이지 로드 시 질권사 금리 표시
   initializeResizeBar(); // 리사이즈 바 초기화 추가
   initializeDragAndDrop(); // 드래그앤드롭 초기화 추가
   setPdfColumnCompact(); // 페이지 로드 시 PDF 컬럼 컴팩트
   
   // 저장된 레이아웃 설정 복원
   setTimeout(() => {
       loadLayoutSettings();
   }, 200);
   
   // 고객명 & 생년월일 필드에 이벤트 리스너 추가
   const customerNameField = document.getElementById('customer_name');
   if (customerNameField) {
       customerNameField.addEventListener('input', parseCustomerNames);
       customerNameField.addEventListener('change', parseCustomerNames);
       // 페이지 로드시에도 한번 실행
       parseCustomerNames();
   }

   // 도로명 주소 변환 버튼 이벤트 (양방향 토글)
   const convertRoadAddressBtn = document.getElementById('convert-road-address-btn');
   if (convertRoadAddressBtn) {
       // 원본 주소와 도로명 주소 저장용
       let savedOriginalAddress = '';  // 지번 주소 (등기부등본 원본)
       let savedRoadAddress = '';      // 도로명 주소
       let isShowingRoadAddress = false;  // 현재 도로명 표시 중인지

       convertRoadAddressBtn.addEventListener('click', async function() {
           const addressField = document.getElementById('address');
           if (!addressField || !addressField.value.trim()) {
               alert('주소를 먼저 입력해주세요.');
               return;
           }

           const currentAddress = addressField.value.trim();

           // 이미 변환된 상태면 토글 (원본으로 복원)
           if (isShowingRoadAddress && savedOriginalAddress) {
               addressField.value = savedOriginalAddress;
               convertRoadAddressBtn.textContent = '도로명';
               isShowingRoadAddress = false;
               console.log('원본 주소로 복원:', savedOriginalAddress);
               triggerMemoGeneration();
               return;
           }

           // 이미 도로명 주소가 저장되어 있으면 바로 표시
           if (!isShowingRoadAddress && savedRoadAddress && savedOriginalAddress === currentAddress) {
               addressField.value = savedRoadAddress;
               convertRoadAddressBtn.textContent = '지번';
               isShowingRoadAddress = true;
               console.log('저장된 도로명 주소 표시:', savedRoadAddress);
               triggerMemoGeneration();
               return;
           }

           // 새로운 주소면 API 호출
           savedOriginalAddress = currentAddress;
           convertRoadAddressBtn.disabled = true;
           convertRoadAddressBtn.textContent = '변환중...';

           try {
               const response = await fetch('/api/convert-to-road-address', {
                   method: 'POST',
                   headers: { 'Content-Type': 'application/json' },
                   body: JSON.stringify({ address: currentAddress })
               });

               const result = await response.json();

               if (result.success && result.road_address) {
                   savedRoadAddress = result.road_address;
                   addressField.value = result.road_address;
                   convertRoadAddressBtn.textContent = '지번';
                   isShowingRoadAddress = true;
                   console.log('도로명 변환 완료:', result.road_address);
                   triggerMemoGeneration();
               } else {
                   alert(result.error || '도로명 주소 변환에 실패했습니다.');
                   convertRoadAddressBtn.textContent = '도로명';
               }
           } catch (error) {
               console.error('도로명 변환 오류:', error);
               alert('도로명 주소 변환 중 오류가 발생했습니다.');
               convertRoadAddressBtn.textContent = '도로명';
           } finally {
               convertRoadAddressBtn.disabled = false;
           }
       });

       // 주소 필드가 수동으로 변경되면 저장된 주소 초기화
       const addressField = document.getElementById('address');
       if (addressField) {
           addressField.addEventListener('input', function() {
               savedOriginalAddress = '';
               savedRoadAddress = '';
               isShowingRoadAddress = false;
               convertRoadAddressBtn.textContent = '도로명';
           });
       }
   }

   // KB시세 버튼 클릭 시 확장프로그램으로 자동 검색 트리거
   const kbButtons = document.querySelectorAll('a[href*="kbland.kr"]');
   kbButtons.forEach(btn => {
       btn.addEventListener('click', (e) => {
           e.preventDefault();
           const addressField = document.getElementById('address');
           if (addressField && addressField.value.trim()) {
               const address = addressField.value.trim();
               console.log('🔍 KB시세 자동 검색 시작:', address);

               // CustomEvent 발생 - content_flask.js가 감지
               const event = new CustomEvent('START_KB_AUTO_SEARCH', {
                   detail: { address: address }
               });
               window.dispatchEvent(event);

               // KB Land 팝업 창 열기 (autoSearch 파라미터로 주소 전달)
               const encodedAddress = encodeURIComponent(address);
               const kbUrl = `https://kbland.kr/map?xy=37.5205559,126.9265729,16&autoSearch=${encodedAddress}`;
               window.open(kbUrl, 'kbLandPopup', 'width=1200,height=900,resizable=yes,scrollbars=yes');
           } else {
               console.warn('⚠️ 주소가 입력되지 않았습니다');
               alert('주소를 먼저 입력해주세요.');
           }
       });
   });
});

// [신규] 필요금액을 기준으로 LTV 비율을 계산하고 ltv1에 자동 입력
// [API 호출 함수들] loadCustomerData(라인 827), handleFileUpload(라인 1070), calculateIndividualShare(라인 1279) 참고
// [관련 계산] calculatePrincipalFromRatio(라인 349), calculateSimpleInterest(라인 472), calculateIndividualShare(라인 1279), calculateBalloonLoan(라인 2034) 참고
async function calculateLTVFromRequiredAmount() {
    const kbPriceField = document.getElementById('kb_price');
    const requiredAmtField = document.getElementById('required_amount');
    const ltv1Field = document.getElementById('ltv1');

    if (!kbPriceField || !requiredAmtField || !ltv1Field) return;

    const kbPrice = kbPriceField.value;
    const requiredAmt = requiredAmtField.value;

    // --- ▼▼▼ 필요금액 체크가 가장 먼저 실행됩니다 ▼▼▼ ---
    // '필요금액'을 숫자 값으로 파싱합니다.
    const requiredAmountValue = parseKoreanNumberString(requiredAmt);

    // 만약 필요금액이 0 이하(비어있거나 0)이면,
    // LTV 역산을 실행하지 않고 함수를 즉시 종료합니다.
    if (requiredAmountValue <= 0) {
        // 기존 메모 생성 로직만 호출하여 화면을 현재 LTV 기준으로 업데이트합니다.
        ltv1Field.value = ''; // LTV 필드를 명시적으로 비웁니다.
        triggerMemoGeneration();
        calculateIndividualShare();
        return; // 여기서 함수 실행을 멈추는 것이 중요합니다.
    }
    // --- ▲▲▲ 여기가 핵심 수정 부분입니다 ▲▲▲ ---

    // KB시세가 0이면 필요금액을 비우고 경고
    if (parseKoreanNumberString(kbPrice) === 0) {
        showCustomAlert("KB시세를 먼저 입력해야 LTV 자동 계산이 가능합니다.");
        requiredAmtField.value = '';
        ltv1Field.value = ''; // LTV 필드도 비워줍니다.
        triggerMemoGeneration();
        calculateIndividualShare();
        return;
    }

    // 대출 정보 수집
    const deductionAmount = document.getElementById('deduction_amount').value;
    const loans = [];
    document.querySelectorAll('.loan-item').forEach(item => {
        const maxAmount = item.querySelector('[name="max_amount"]')?.value || '0';
        const status = item.querySelector('[name="status"]')?.value || '-';

        loans.push({
            max_amount: maxAmount,
            status: status
        });
    });

    try {
        // 서버 API 호출 (이 부분은 이제 requiredAmountValue > 0 일 때만 실행됩니다)
        const response = await fetch('/api/calculate_ltv_from_required_amount', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                kb_price: kbPrice,
                required_amount: requiredAmt,
                loans: loans,
                deduction_amount: deductionAmount
            })
        });

        if (!response.ok) {
            console.error('API 응답 실패:', response.status);
            return;
        }

        const result = await response.json();

        if (result.success && result.ltv !== undefined) {
            ltv1Field.value = result.ltv > 0 ? result.ltv : '';
            triggerMemoGeneration();
            calculateIndividualShare();
        } else {
            console.error('LTV 계산 실패:', result.error);
            ltv1Field.value = '';
            triggerMemoGeneration();
            calculateIndividualShare();
        }
    } catch (error) {
        console.error('LTV 계산 중 오류:', error);
        ltv1Field.value = '';
        triggerMemoGeneration();
        calculateIndividualShare();
    }
}

// 지분시세 자동 계산 함수
function updateSharePrice() {
    const kbPriceField = document.getElementById('kb_price');
    const sharePriceField = document.getElementById('share-price');
    if (!kbPriceField || !sharePriceField) return 0;

    const kbPrice = parseInt(kbPriceField.value.replace(/,/g, '')) || 0;
    if (kbPrice <= 0) {
        sharePriceField.value = '-';
        return 0;
    }

    // 선택된 차주의 지분율 가져오기
    const selectedRadio = document.querySelector('input[name="share-borrower"]:checked');
    if (!selectedRadio) {
        sharePriceField.value = '-';
        return 0;
    }

    const ownerIdx = selectedRadio.value;
    const shareField = document.getElementById(`share-customer-birth-${ownerIdx}`);
    if (!shareField) {
        sharePriceField.value = '-';
        return 0;
    }

    // 지분율 파싱
    const shareText = shareField.value.trim();
    let sharePercent = 0;
    if (shareText) {
        const percentMatch = shareText.match(/\(([\d.]+)%?\)/);
        if (percentMatch) {
            sharePercent = parseFloat(percentMatch[1]);
        } else {
            const numberMatch = shareText.match(/([\d.]+)%?/);
            sharePercent = numberMatch ? parseFloat(numberMatch[1]) : 0;
        }
    }

    if (sharePercent <= 0) {
        sharePriceField.value = '-';
        return 0;
    }

    const sharePrice = Math.round(kbPrice * sharePercent / 100);
    sharePriceField.value = sharePrice.toLocaleString();
    return sharePrice;
}

// [수정] 지분용 필요금액을 기준으로 LTV 비율을 계산 (지분시세 기준)
function calculateShareLTVFromRequiredAmount() {
    const shareRequiredAmtField = document.getElementById('share-required-amount');
    const shareLtvField = document.getElementById('share-ltv');

    if (!shareRequiredAmtField || !shareLtvField) return;

    const requiredAmountValue = parseKoreanNumberString(shareRequiredAmtField.value);

    // 필요금액이 0 이하이면 LTV 역산 실행하지 않음
    if (requiredAmountValue <= 0) {
        shareLtvField.value = '80';
        calculateIndividualShare();
        return;
    }

    // 지분시세 계산
    const sharePrice = updateSharePrice();
    if (sharePrice <= 0) {
        showCustomAlert("KB시세와 지분율을 먼저 입력해주세요.");
        shareRequiredAmtField.value = '';
        shareLtvField.value = '80';
        calculateIndividualShare();
        return;
    }

    // 지분시세 기준 LTV 역산: 필요금액 / 지분시세 * 100
    const ltv = Math.round((requiredAmountValue / sharePrice) * 1000) / 10; // 소수점 1자리
    shareLtvField.value = ltv > 0 ? ltv : '80';
    console.log(`📊 지분 LTV 역산: 필요금액 ${requiredAmountValue}만 / 지분시세 ${sharePrice}만 = ${ltv}%`);
    calculateIndividualShare();
}

// 페이지를 떠날 때 자동 저장
window.addEventListener('beforeunload', () => {
    saveLayoutSettings();
});

// 페이지 숨김/표시 시 저장 (모바일 브라우저 대응)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        saveLayoutSettings();
    }
});

// ========================================================
// 9. 기타 유틸 함수 및 계산기
// ========================================================
// ✨ 원금 분할 계산기 함수들
// [관련 함수] parseAdvancedAmount(라인 273), formatManwonValue(라인 534) 참고
function formatNumberWithCommas(value) {
    if (value === null || value === undefined) return '';
    return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function parseFormattedNumber(value) {
    if (typeof value !== 'string') return 0;
    return Number(value.replace(/,/g, '')) || 0;
}

function calculateBalloonLoan() {
    // 이자 계산기 탭의 원금 분할 계산을 담당합니다.
    // [관련 계산] calculatePrincipalFromRatio(라인 349), calculateSimpleInterest(라인 472), calculateIndividualShare(라인 1279), calculateLTVFromRequiredAmount(라인 1929) 참고
    const loanAmountInput = document.getElementById('interest-loan-amount');
    const annualRateInput = document.getElementById('interest-annual-rate');
    const principalPctInput = document.getElementById('balloon-principal-pct');
    const monthsInput = document.getElementById('balloon-months');
    if (!loanAmountInput || !annualRateInput || !principalPctInput || !monthsInput) return;

    const loanManwon = parseFloat(loanAmountInput.value.replace(/,/g, '')) || 0;
    const loan = loanManwon * 10000;
    const annualRate = Number(annualRateInput.value) || 0;
    const principalPct = Math.max(0, Math.min(100, Number(principalPctInput.value) || 0));
    const months = Number(monthsInput.value) || 0;

    const monthlyRate = annualRate > 0 ? annualRate / 100 / 12 : 0;
    const principalPortion = loan * (principalPct / 100);
    const monthlyPrincipal = months > 0 ? principalPortion / months : 0;
    const firstMonthInterest = loan * monthlyRate;
    const firstMonthPayment = monthlyPrincipal + firstMonthInterest;

    const monthlyPrincipalEl = document.getElementById('balloon-monthly-principal');
    const firstPaymentEl = document.getElementById('balloon-first-payment');
    const breakdownEl = document.getElementById('balloon-first-breakdown');

    if (monthlyPrincipalEl) monthlyPrincipalEl.value = Math.round(monthlyPrincipal).toLocaleString() + ' 원';
    if (firstPaymentEl) firstPaymentEl.value = Math.round(firstMonthPayment).toLocaleString() + ' 원';
    if (breakdownEl) breakdownEl.textContent =
        `(원금 ${Math.round(monthlyPrincipal).toLocaleString()} + 이자 ${Math.round(firstMonthInterest).toLocaleString()})`;
}

// 가이드 팝업 윈도우 열기
function openGuidePopup() {
    const guideUrl = '/static/heuimang-loan-guide.html';
    const popupWidth = 1000;
    const popupHeight = 800;

    // 화면 중앙에 팝업 위치 계산
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;
    const left = (screenWidth - popupWidth) / 2;
    const top = (screenHeight - popupHeight) / 2;

    // 팝업 윈도우 열기
    window.open(
        guideUrl,
        'guidePopup',
        `width=${popupWidth},height=${popupHeight},left=${left},top=${top},resizable=yes,scrollbars=yes`
    );
    console.log('📖 가이드 팝업 열기:', guideUrl);
}

// ========================================================
// 질권사 금리 실시간 표시 (아이엠 / 메리츠)
// ========================================================
function updateCollateralRateDisplay() {
    const hopeCheckbox = document.getElementById('hope-collateral-loan');
    const meritzCheckbox = document.getElementById('meritz-collateral-loan');
    const hopeDisplay = document.getElementById('hope-rate-display');
    const meritzDisplay = document.getElementById('meritz-rate-display');

    if (!hopeDisplay || !meritzDisplay) return;

    const ltv = parseFloat(document.getElementById('ltv1')?.value) || 0;

    // 선순위/후순위 판단
    const maintainStatuses = ['유지', '동의', '비동의'];
    let hasSubordinate = false;
    document.querySelectorAll('.loan-item').forEach(item => {
        const statusSelect = item.querySelector('[name="status"]');
        if (statusSelect && maintainStatuses.includes(statusSelect.value)) {
            hasSubordinate = true;
        }
    });
    const isSenior = !hasSubordinate;

    // --- 아이엠 금리 ---
    if (hopeCheckbox?.checked) {
        let hopeRate = null;
        if (isSenior) {
            // 선순위: 70% 이하만 가능
            if (ltv <= 70) hopeRate = 6.8;
            // 70% 초과는 표시 안함
        } else {
            // 후순위
            if (ltv <= 70) hopeRate = 6.8;
            else if (ltv <= 75) hopeRate = 7.0;
            else if (ltv <= 80) hopeRate = 7.4;
        }

        if (hopeRate !== null) {
            const label = isSenior ? '선순위' : '후순위';
            hopeDisplay.textContent = `${label} ${hopeRate}%`;
            hopeDisplay.style.display = 'inline';
        } else {
            hopeDisplay.style.display = 'none';
        }
    } else {
        hopeDisplay.style.display = 'none';
    }

    // --- 메리츠 금리 ---
    if (meritzCheckbox?.checked) {
        const propertyType = document.getElementById('property_type')?.value || '';
        const isApt = propertyType.includes('아파트') || propertyType.includes('주상복합');
        const address = document.getElementById('address')?.value || '';
        const regionGrade = getRegionGradeFromAddress(address);
        const unitCount = parseInt((document.getElementById('unit_count')?.value || '0').replace(/,/g, '')) || 0;

        // 아파트는 세대수 관계없이 APT 기준 적용 (등기부 기준)
        const effectiveApt = isApt;

        // 메리츠 금리 계산 시점의 최신 LTV 값을 다시 읽음 (validateMeritzLoanConditions 반영)
        const meritzLtv = parseFloat(document.getElementById('ltv1')?.value) || 0;
        console.log(`🔍 [디버그] updateCollateralRateDisplay - meritzLtv: ${meritzLtv}, ltv1 필드값: "${document.getElementById('ltv1')?.value}"`);

        // 기본 금리 (2026.03 기준)
        let baseRate;
        if (effectiveApt) {
            if (meritzLtv <= 75) baseRate = 6.70;
            else if (meritzLtv <= 85) baseRate = 7.70;
            else baseRate = 9.20;
        } else {
            if (meritzLtv <= 75) baseRate = 8.90;
            else if (meritzLtv <= 85) baseRate = 9.90;
            else baseRate = 11.40;
        }

        // 가산금리
        let additional = 0;
        const addReasons = [];

        if (regionGrade === '2군') {
            additional += 0.5;
            addReasons.push('2군');
        } else if (regionGrade === '3군') {
            additional += 1.0;
            addReasons.push('3군');
        }

        if (isApt && unitCount > 0 && unitCount <= 100) {
            additional += 0.5;
            addReasons.push('100세대이하');
        }

        // 군(읍) 단위 소재
        if (/[가-힣]+군\s/.test(address) || /[가-힣]+읍\s/.test(address) || address.match(/[가-힣]+군$/)) {
            additional += 0.5;
            addReasons.push('군읍소재');
        }

        // 지분대출: 공유자 라디오 선택 시
        const shareBorrowerRadio = document.querySelector('input[name="share-borrower"]:checked');
        if (shareBorrowerRadio) {
            additional += 1.0;
            addReasons.push('지분');
        }

        const totalRate = baseRate + additional;
        let displayText = `${totalRate.toFixed(1)}%`;
        if (additional > 0) {
            displayText += ` (+${additional.toFixed(1)} ${addReasons.join(',')})`;
        }

        meritzDisplay.textContent = displayText;
        meritzDisplay.title = addReasons.length > 0 ? addReasons.map(r => r + ' 가산').join(', ') : '가산 없음';
        meritzDisplay.style.display = 'inline';
    } else {
        meritzDisplay.style.display = 'none';
    }
}

// 희망담보대부 조건 검증 (독립적인 두 조건)
// 조건 1: 희망담보대부 체크 AND 세대수 < 100 → 세대수 필드 빨간색
// 조건 2: 희망담보대부 체크 AND KB시세 < 3억 → KB시세 필드 빨간색
function validateHopeLoanConditions() {
    const hopeCheckbox = document.getElementById('hope-collateral-loan');
    const unitCountField = document.getElementById('unit_count');
    const kbPriceField = document.getElementById('kb_price');
    const propertyTypeField = document.getElementById('property_type');
    const addressField = document.getElementById('address');

    if (!hopeCheckbox || !unitCountField || !kbPriceField) return;

    // 희망담보대부가 체크되어 있는지 확인
    const isHopeChecked = hopeCheckbox.checked;

    // 세대수와 KB시세 값 가져오기 (값이 입력되지 않으면 0)
    // --- ▼▼▼ [수정] 세대수도 콤마를 제거하고 파싱합니다 ▼▼▼
    const unitCount = parseInt(unitCountField.value.replace(/,/g, '')) || 0;
    // --- ▲▲▲ [수정] ▲▲▲
    const kbPrice = parseInt(kbPriceField.value.replace(/,/g, '')) || 0;

    // 3억 = 30,000만 (KB시세는 만 단위)
    const THREE_HUNDRED_MILLION = 30000;

    // 조건 1: 희망담보대부 체크 AND 세대수 < 100
    const shouldHighlightUnitCount = isHopeChecked && unitCount > 0 && unitCount < 100;

    // 조건 2: 희망담보대부 체크 AND KB시세 < 3억 (30,000만)
    const shouldHighlightKbPrice = isHopeChecked && kbPrice > 0 && kbPrice < THREE_HUNDRED_MILLION;

    // 조건 3: 희망담보대부 체크 AND 준공일자 45년 이상 (2025년 기준 1980년 이전)
    const completionDateField = document.getElementById('completion_date');
    let shouldHighlightCompletionDate = false;

    if (completionDateField && isHopeChecked && completionDateField.value.trim()) {
        try {
            const completionDateStr = completionDateField.value.trim();
            // YYYY-MM-DD 또는 YYYY.MM.DD 형식 파싱
            const dateMatch = completionDateStr.match(/(\d{4})[.-]?(\d{2})?[.-]?(\d{2})?/);

            if (dateMatch) {
                const year = parseInt(dateMatch[1]);
                const currentYear = new Date().getFullYear();
                const buildingAge = currentYear - year;

                // 45년 이상이면 강조 (2025년 기준 1980년 이전)
                shouldHighlightCompletionDate = buildingAge >= 45;
                console.log(`🏢 준공연도: ${year}, 경과년수: ${buildingAge}년, 45년 이상: ${shouldHighlightCompletionDate}`);
            }
        } catch (e) {
            console.error('준공일자 파싱 오류:', e);
        }
    }

    // 조건 4: 희망담보대부 체크 AND NON-APT (아파트, 주상복합 외)
    let shouldHighlightPropertyType = false;
    if (propertyTypeField && isHopeChecked && propertyTypeField.value.trim()) {
        const propertyType = propertyTypeField.value.trim();
        // 아파트 또는 주상복합이 아니면 NON-APT (취급불가)
        const isNonApt = !propertyType.includes('아파트') && !propertyType.includes('주상복합');
        shouldHighlightPropertyType = isNonApt;
        if (isNonApt) {
            console.log(`🔴 경고: 아이엠질권 NON-APT 취급불가 - ${propertyType}`);
        }
    }

    // 조건 5: 희망담보대부 체크 AND 서울/경기/인천 외 지역
    let shouldHighlightAddress = false;
    if (addressField && isHopeChecked && addressField.value.trim()) {
        const address = addressField.value.trim();
        const isValidRegion = address.includes('서울') || address.includes('경기') || address.includes('인천');
        shouldHighlightAddress = !isValidRegion;
        if (!isValidRegion) {
            console.log(`🔴 경고: 아이엠질권 취급불가 지역 - ${address}`);
        }
    }

    // 조건 6: 희망담보대부 체크 AND 선순위 AND LTV >70%
    const ltv1Field = document.getElementById('ltv1');
    let shouldHighlightLTV = false;
    if (ltv1Field && isHopeChecked) {
        // 선순위/후순위 판단 (유지/동의/비동의가 있으면 후순위, 없으면 선순위)
        const maintainStatus = ['유지', '동의', '비동의'];
        let hasSubordinate = false;
        document.querySelectorAll('.loan-item').forEach(item => {
            const status = item.querySelector('[name="status"]')?.value || '-';
            if (maintainStatus.includes(status)) {
                hasSubordinate = true;
            }
        });

        // 선순위인 경우에만 LTV 70% 이하 검증
        if (!hasSubordinate) {
            const ltv = parseFloat(ltv1Field.value) || 0;
            shouldHighlightLTV = ltv > 70;
            if (shouldHighlightLTV) {
                console.log(`🔴 경고: 아이엠질권 선순위는 LTV 70% 이하만 가능 - 현재: ${ltv}%`);
            }
        }
    }

    console.log(`🔍 희망담보대부 검증 - 체크: ${isHopeChecked}, 세대수: ${unitCount}, KB시세: ${kbPrice}`);
    console.log(`   세대수 강조: ${shouldHighlightUnitCount}, KB시세 강조: ${shouldHighlightKbPrice}, 준공일자 강조: ${shouldHighlightCompletionDate}, 물건종류 강조: ${shouldHighlightPropertyType}, 주소 강조: ${shouldHighlightAddress}, LTV 강조: ${shouldHighlightLTV}`);

    // 세대수 필드 스타일 처리
    if (shouldHighlightUnitCount) {
        unitCountField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
        console.log('🔴 경고: 세대수 100 미만');
    } else {
        unitCountField.removeAttribute('style');
    }

    // KB시세 필드 스타일 처리
    if (shouldHighlightKbPrice) {
        kbPriceField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
        console.log('🔴 경고: KB시세 3억 미만');
        // 경고창 (한 번만 표시하기 위한 플래그)
        if (!window._hopePriceAlertShown) {
            window._hopePriceAlertShown = true;
            alert(`⚠️ 아이엠 취급불가\n\nKB시세 ${kbPrice.toLocaleString()}만원 (3억 미만)\n\n아이엠은 시세 3억 이상만 취급 가능합니다.`);
        }
    } else {
        kbPriceField.removeAttribute('style');
        window._hopePriceAlertShown = false;
    }

    // 준공일자 필드 스타일 처리
    if (shouldHighlightCompletionDate && completionDateField) {
        completionDateField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
        console.log('🔴 경고: 준공후 45년 이상');
        // 경고창 (한 번만 표시하기 위한 플래그)
        if (!window._hopeCompletionAlertShown) {
            window._hopeCompletionAlertShown = true;
            const year = completionDateField.value.match(/(\d{4})/)?.[1] || '';
            const buildingAge = new Date().getFullYear() - parseInt(year);
            alert(`⚠️ 아이엠 취급불가\n\n준공연도: ${year}년 (경과 ${buildingAge}년)\n\n아이엠은 45년 이상 노후주택 취급이 불가합니다.`);
        }
    } else if (completionDateField) {
        completionDateField.removeAttribute('style');
        window._hopeCompletionAlertShown = false;
    }

    // 물건종류 필드 스타일 처리 (NON-APT 취급불가)
    if (shouldHighlightPropertyType && propertyTypeField) {
        propertyTypeField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
    } else if (propertyTypeField) {
        propertyTypeField.removeAttribute('style');
    }

    // 주소 필드 스타일 처리 (서울/경기/인천 외 지역 취급불가)
    if (shouldHighlightAddress && addressField) {
        addressField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
    } else if (addressField && isHopeChecked) {
        // 아이엠 체크 시 정상 지역이면 스타일 제거 (메리츠 경고와 충돌 방지)
        addressField.removeAttribute('style');
    }

    // LTV 필드 스타일 처리 (아이엠 선순위 70% 초과 경고)
    if (shouldHighlightLTV && ltv1Field) {
        ltv1Field.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
        // 경고 메시지 표시 (콘솔에만)
        console.log('⚠️ 아이엠질권적용시 선순위는 70%이하만 적용 가능합니다');
    } else if (ltv1Field && isHopeChecked) {
        // 아이엠 체크 시 LTV가 정상이면 스타일 제거
        ltv1Field.removeAttribute('style');
    }
}

// ========================================================
// 메리츠 질권 적용 조건 검증 함수
// ========================================================
function validateMeritzLoanConditions() {
    const meritzCheckbox = document.getElementById('meritz-collateral-loan');
    const areaField = document.getElementById('area');
    const kbPriceField = document.getElementById('kb_price');
    const ltv1Field = document.getElementById('ltv1');

    if (!meritzCheckbox || !areaField || !kbPriceField || !ltv1Field) return;

    // ✅ [핵심] 아이엠 질권이 체크되어 있으면 메리츠 검증 스킵
    const hopeCheckbox = document.getElementById('hope-collateral-loan');
    if (hopeCheckbox && hopeCheckbox.checked) {
        console.log('⏭️ 아이엠 질권 활성화 - 메리츠 검증 스킵');
        return;
    }

    // 메리츠 질권이 체크되어 있는지 확인
    const isMeritzChecked = meritzCheckbox.checked;
    const regionButtonsDiv = document.getElementById('meritz-loan-region-buttons');

    if (!isMeritzChecked) {
        // 메리츠 미체크 시 KB시세 스타일 초기화 및 지역 버튼 숨김
        kbPriceField.style.removeProperty('background-color');
        kbPriceField.style.removeProperty('border');
        kbPriceField.style.removeProperty('box-shadow');

        if (regionButtonsDiv) {
            regionButtonsDiv.style.cssText = 'display: none !important;';
        }

        // 지역 버튼 스타일 초기화
        document.querySelectorAll('.meritz-loan-region-btn').forEach(b => {
            b.style.backgroundColor = '';
            b.style.color = '';
            b.style.borderColor = '';
        });

        return;
    }

    // 메리츠 체크 시 지역 버튼 표시
    if (regionButtonsDiv) {
        regionButtonsDiv.style.cssText = 'display: flex !important;';
    }

    // 면적값 가져오기
    const area = parseFloat(areaField.value.replace(/,/g, '')) || 0;
    // KB시세값 가져오기 (만 단위)
    const kbPrice = parseInt(kbPriceField.value.replace(/,/g, '')) || 0;
    // 물건유형 가져오기
    const propertyTypeField = document.getElementById('property_type');
    const propertyType = propertyTypeField ? propertyTypeField.value.trim() : 'APT';
    // 주소 가져오기
    const meritzAddressField = document.getElementById('address');
    const address = meritzAddressField ? meritzAddressField.value.trim() : '';

    // 선순위/후순위 판단 (유지/동의/비동의가 있으면 후순위, 없으면 선순위)
    const maintainStatus = ['유지', '동의', '비동의'];
    let hasSubordinate = false;
    document.querySelectorAll('.loan-item').forEach(item => {
        const status = item.querySelector('[name="status"]')?.value || '-';
        if (maintainStatus.includes(status)) {
            hasSubordinate = true;
        }
    });
    const priority = hasSubordinate ? 'second' : 'first';
    const priorityLabel = hasSubordinate ? '후순위' : '선순위';

    // 서울/경기/인천 + 광역시(메리츠 3군) 외 지역 검증
    let isInvalidRegion = false;
    if (address) {
        const meritzMetroCities = ['대전', '세종', '대구', '부산', '광주', '울산'];
        const isValidRegion = address.includes('서울') || address.includes('경기') || address.includes('인천') ||
                              meritzMetroCities.some(city => address.includes(city));
        isInvalidRegion = !isValidRegion;
        if (isInvalidRegion) {
            console.log(`🔴 메리츠 경고: 취급불가 지역 - ${address}`);
        }
    }

    console.log(`🔍 메리츠 질권 검증 - 면적: ${area}㎡, KB시세: ${kbPrice}만원, 물건유형: ${propertyType}, 순위: ${priorityLabel}`);

    // ========================================================
    // 1. KB시세 1억(10,000만) 미만 시 빨간색 표시
    // ========================================================
    const ONE_HUNDRED_MILLION = 10000; // 1억 = 10,000만
    const isKbPriceTooLow = kbPrice > 0 && kbPrice < ONE_HUNDRED_MILLION;

    if (isKbPriceTooLow) {
        kbPriceField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
        console.log('🔴 경고: KB시세 1억 미만');
    } else {
        kbPriceField.style.removeProperty('background-color');
        kbPriceField.style.removeProperty('border');
        kbPriceField.style.removeProperty('box-shadow');
    }

    // ========================================================
    // 2. 메리츠 면적에 따른 LTV 자동 설정 (지역 고려)
    // ========================================================

    // Non-APT 2군/3군 취급불가 검증
    const isNonApt = propertyType && !propertyType.includes('아파트');
    const isNonAptRestricted = isNonApt && (meritzRegion === '2gun' || meritzRegion === '3gun');

    if (isNonAptRestricted && propertyTypeField) {
        // Non-APT이면서 2군 또는 3군인 경우 빨간색 경고
        propertyTypeField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
        console.log(`🔴 메리츠 경고: Non-APT는 ${meritzRegion === '2gun' ? '2군' : '3군'} 취급불가`);
    } else if (propertyTypeField) {
        // 정상 조건이면 스타일 제거
        propertyTypeField.removeAttribute('style');
    }

    if (area > 0) {
        // 기본 LTV (선순위/후순위, 지역 고려, 물건유형 고려)
        let baseLtv = calculateMeritzLTV(area, priority, meritzRegion, propertyType);
        const regionName = meritzRegion === '1gun' ? '1군(일반)' : (meritzRegion === '2gun' ? '2군' : '3군');

        console.log(`📊 메리츠 면적별 LTV - 지역: ${regionName}, 순위: ${priorityLabel}, 면적: ${area}㎡, 물건유형: ${propertyType}, 설정LTV: ${baseLtv}%`);

        // ✅ [수정] 필요금액이 입력되어 있으면 역계산된 LTV를 유지 (덮어쓰기 방지)
        const requiredAmountField = document.getElementById('required_amount');
        const hasRequiredAmount = requiredAmountField && requiredAmountField.value && parseKoreanNumberString(requiredAmountField.value) > 0;
        const currentLtvValue = parseFloat(ltv1Field.value) || 0;

        if (hasRequiredAmount && currentLtvValue > 0) {
            console.log(`🔒 필요금액 역계산 LTV 유지: ${currentLtvValue}% (면적 기준 ${baseLtv}% 적용 안함)`);
        } else {
            // LTV 값 설정 (0이면 취급불가를 의미)
            ltv1Field.value = baseLtv;
        }

        // LTV가 0이면 LTV 필드도 빨간색 표시
        if (baseLtv === 0) {
            ltv1Field.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
            console.log('🔴 메리츠 경고: 취급불가 (LTV 0%)');
        } else {
            ltv1Field.removeAttribute('style');
        }

        // ========================================================
        // 3. 시세 15억(150,000만) 초과 시 LTV -5% 차감
        // ========================================================
        const FIFTEEN_HUNDRED_MILLION = 150000; // 15억 = 150,000만
        if (kbPrice > FIFTEEN_HUNDRED_MILLION) {
            // ✅ [수정] 역계산 LTV가 있으면 그 값에서 -5%, 없으면 baseLtv에서 -5%
            const currentLtvForDeduction = parseFloat(ltv1Field.value) || baseLtv;
            const deductedLtv = currentLtvForDeduction - 5;
            ltv1Field.value = deductedLtv;
            console.log(`💸 고가물건 조정: 시세 15억 초과 → LTV ${currentLtvForDeduction}% → ${deductedLtv}%`);
        }

        // ========================================================
        // 4. 1군 유의지역 max LTV 80% 상한 적용
        // ========================================================
        // 유의지역: 서울(중랑구, 관악구, 강북구, 성북구, 노원구, 도봉구), 경기(구리시, 남양주시), 인천1군 전체
        if (meritzRegion === '1gun' && address) {
            const cautionAreas = [
                // 서울 유의지역
                '중랑구', '관악구', '강북구', '성북구', '노원구', '도봉구',
                // 경기 유의지역
                '구리시', '구리', '남양주시', '남양주',
                // 인천 1군 전체
                '계양구', '계양', '부평구', '부평', '연수구', '연수', '미추홀구', '미추홀'
            ];

            const isCautionArea = cautionAreas.some(area => address.includes(area));

            if (isCautionArea) {
                const currentLtv = parseFloat(ltv1Field.value) || baseLtv;
                if (currentLtv > 80) {
                    ltv1Field.value = 80;
                    console.log(`⚠️ 1군 유의지역: ${address} → LTV ${currentLtv}% → 80% (Max 상한)`);
                }
            }
        }

        // ========================================================
        // 7. 40년 이상 노후주택 LTV 60% 상한 적용 (서버와 동일하게 월 고려)
        // ========================================================
        const completionField = document.getElementById('completion_date');
        if (completionField && completionField.value.trim()) {
            try {
                const completionDateStr = completionField.value.trim();
                const dateMatch = completionDateStr.match(/(\d{4})[.-]?(\d{2})?[.-]?(\d{2})?/);

                if (dateMatch) {
                    const completionYear = parseInt(dateMatch[1]);
                    const completionMonth = dateMatch[2] ? parseInt(dateMatch[2]) : 1;

                    const today = new Date();
                    const currentYear = today.getFullYear();
                    const currentMonth = today.getMonth() + 1; // 0-indexed

                    // 경과 년수 계산 (월 고려 - 서버와 동일 로직)
                    let buildingAge = currentYear - completionYear;
                    if (currentMonth < completionMonth) {
                        buildingAge -= 1;
                    }

                    if (buildingAge >= 40) {
                        const currentLtv = parseFloat(ltv1Field.value) || baseLtv;
                        if (currentLtv > 60) {
                            ltv1Field.value = 60;
                            console.log(`🏚️ 노후주택 조정: ${buildingAge}년 경과 → LTV ${currentLtv}% → 60% (Max 상한)`);
                        }
                    }
                }
            } catch (e) {
                console.error('노후주택 LTV 조정 오류:', e);
            }
        }

        // ========================================================
        // 8. 군 단위 신도시 -5% 차감
        // ========================================================
        const addressField = document.getElementById('address');
        if (addressField && addressField.value.trim()) {
            const address = addressField.value.trim();
            const hasGun = /\s군\s|\s군$|^.*군\s/.test(address);

            if (hasGun) {
                const newTownExceptions = [
                    '판교', '동탄', '광교', '위례', '평촌', '분당', '일산', '산본',
                    '중동', '정자', '수지', '죽전', '운정', '양주신도시', '화성동탄',
                    '김포한강신도시', '고덕', '위례신도시', '남양주왕숙', '하남감일',
                    '인천검단', '부천대장', '광명시흥', '성남판교', '용인흥덕'
                ];

                const isNewTown = newTownExceptions.some(town => address.includes(town));

                if (isNewTown) {
                    const currentLtv = parseFloat(ltv1Field.value) || baseLtv;
                    const deductedLtv = currentLtv - 5;
                    ltv1Field.value = deductedLtv;
                    console.log(`🏘️ 군 단위 신도시 조정: LTV ${currentLtv}% → ${deductedLtv}% (-5%)`);
                }
            }
        }

        triggerMemoGeneration();
    }


    // ========================================================
    // 4. 40년 이상 노후주택 체크 (LTV Max 60%)
    // ========================================================
    const meritzCompletionDateField = document.getElementById('completion_date');
    let is40YearsOld = false;

    if (meritzCompletionDateField && meritzCompletionDateField.value.trim()) {
        try {
            const completionDateStr = meritzCompletionDateField.value.trim();
            const dateMatch = completionDateStr.match(/(\d{4})[.-]?(\d{2})?[.-]?(\d{2})?/);

            if (dateMatch) {
                const year = parseInt(dateMatch[1]);
                const currentYear = new Date().getFullYear();
                const buildingAge = currentYear - year;

                // 40년 이상이면 경고 (2025년 기준 1985년 이전)
                is40YearsOld = buildingAge >= 40;

                if (is40YearsOld) {
                    meritzCompletionDateField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
                    console.log(`🏚️ 메리츠 경고: 40년 이상 노후주택 (${buildingAge}년) - LTV Max 60%`);
                } else {
                    // 아이엠 질권 조건과 겹치지 않도록 확인
                    const hopeCheckbox = document.getElementById('hope-collateral-loan');
                    const isHopeChecked = hopeCheckbox && hopeCheckbox.checked;

                    if (!isHopeChecked) {
                        meritzCompletionDateField.removeAttribute('style');
                    }
                }
            }
        } catch (e) {
            console.error('메리츠 준공일자 파싱 오류:', e);
        }
    }

    // ========================================================
    // 5. 지역 검증: 서울/경기/인천 외 지역 체크 및 군 단위 지역 체크 (신도시 예외)
    // ========================================================
    if (meritzAddressField && address) {
        // 서울/경기/인천 외 지역이면 빨간색 경고 (우선순위 높음)
        if (isInvalidRegion) {
            meritzAddressField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
            return; // 취급불가 지역이면 더 이상 검증 안 함
        }

        // 신도시/택지개발 예외 목록
        const newTownExceptions = [
            '판교', '동탄', '광교', '위례', '평촌', '분당', '일산', '산본',
            '중동', '정자', '수지', '죽전', '운정', '양주신도시', '화성동탄',
            '김포한강신도시', '고덕', '위례신도시', '남양주왕숙', '하남감일',
            '인천검단', '부천대장', '광명시흥', '성남판교', '용인흥덕'
        ];

        // 주소에 "군" 포함 여부 확인
        const hasGun = /\s군\s|\s군$|^.*군\s/.test(address);

        if (hasGun) {
            // 신도시 예외 확인
            const isNewTown = newTownExceptions.some(town => address.includes(town));

            // 군 단위는 노란색 경고 (+0.5% 가산금리)
            meritzAddressField.style.cssText = 'background-color: #fff3cd !important; border: 2px solid #ffc107 !important; box-shadow: 0 0 5px rgba(255,193,7,0.3) !important;';
            console.log(`⚠️ 메리츠 주의: 군(읍) 단위 소재 - 가산금리 +0.5%`);
        } else {
            // 군 단위가 아니고 유효한 지역이면 스타일 제거
            meritzAddressField.removeAttribute('style');
        }
    }
}

// ========================================================
// 메리츠 면적에 따른 LTV 계산 함수
// ========================================================
function calculateMeritzLTV(area, priority = 'first', region = '1gun', propertyType = 'APT') {
    // priority: 'first' = 선순위, 'second' = 후순위
    // region: '1gun' = 1군(일반), '2gun' = 2군, '3gun' = 3군
    // propertyType: 'APT' = 아파트, 'Non-APT' = 오피스텔 등

    let ltv;

    // Non-APT 물건 타입 확인 (오피스텔, 상가, 빌라 등)
    const isNonApt = propertyType && !propertyType.includes('아파트');

    if (region === '1gun') {
        if (isNonApt) {
            /**
             * 메리츠 질권 LTV 기준 - 1군 Non-APT (오피스텔 등)
             * 선/후순위 구분 없음
             * 62.8㎡ 이하:                75%
             * 62.8㎡ 초과 ~ 95.9㎡ 이하: 70%
             * 95.9㎡ 초과 ~ 135㎡ 이하:  60%
             * 135㎡ 초과:                 50%
             */
            if (area <= 62.8) {
                ltv = 75.0;
            } else if (area <= 95.9) {
                ltv = 70.0;
            } else if (area <= 135) {
                ltv = 60.0;
            } else {
                ltv = 50.0;
            }
        } else {
            /**
             * 메리츠 질권 LTV 기준 - 1군 APT (max 85%)
             * 서울, 경기1군(용인-수지/기흥, 과천, 광명, 구리, 군포, 부천, 성남, 수원, 안양, 의왕, 하남, 김포, 남양주), 인천1군(계양, 부평, 연수, 미추홀)
             *
             * APT 선순위:
             * 95.9㎡ 이하:                83.0%
             * 95.9㎡ 초과 ~ 135㎡ 이하:  75.0%
             * 135㎡ 초과:                 60.0%
             *
             * APT 후순위:
             * 95.9㎡ 이하:                85.0%
             * 95.9㎡ 초과 ~ 135㎡ 이하:  80.0%
             * 135㎡ 초과:                 70.0%
             */
            if (area <= 95.9) {
                ltv = priority === 'first' ? 83.0 : 85.0;
            } else if (area <= 135) {
                ltv = priority === 'first' ? 75.0 : 80.0;
            } else {
                ltv = priority === 'first' ? 60.0 : 70.0;
            }
        }
    } else if (region === '2gun') {
        if (isNonApt) {
            // 2군 Non-APT 취급불가
            ltv = 0;
        } else {
            /**
             * 메리츠 질권 LTV 기준 - 2군 APT
             * 경기2군(시흥, 안산, 화성, 용인-처인구, 의정부, 양주, 고양, 광주, 동두천, 오산, 이천, 파주), 인천2군(남동, 서, 동, 중)
             *
             * 선순위:
             * 95.9㎡ 이하:                75.0%
             * 95.9㎡ 초과 ~ 135㎡ 이하:  70.0%
             * 135㎡ 초과:                 55.0%
             *
             * 후순위:
             * 95.9㎡ 이하:                80.0%
             * 95.9㎡ 초과 ~ 135㎡ 이하:  75.0%
             * 135㎡ 초과:                 65.0%
             */
            if (area <= 95.9) {
                ltv = priority === 'first' ? 75.0 : 80.0;
            } else if (area <= 135) {
                ltv = priority === 'first' ? 70.0 : 75.0;
            } else {
                ltv = priority === 'first' ? 55.0 : 65.0;
            }
        }
    } else if (region === '3gun') {
        if (isNonApt) {
            // 3군 Non-APT 취급불가
            ltv = 0;
        } else {
            /**
             * 메리츠 질권 LTV 기준 - 3군 APT
             * 경기3군(평택, 안성, 여주, 포천) - 서울/경기/인천 중에서는 경기3군만 해당
             *
             * 선순위:
             * 95.9㎡ 이하:                70.0%
             * 95.9㎡ 초과 ~ 135㎡ 이하:  65.0%
             * 135㎡ 초과:                 50.0%
             *
             * 후순위:
             * 95.9㎡ 이하:                75.0%
             * 95.9㎡ 초과 ~ 135㎡ 이하:  70.0%
             * 135㎡ 초과:                 60.0%
             */
            if (area <= 95.9) {
                ltv = priority === 'first' ? 70.0 : 75.0;
            } else if (area <= 135) {
                ltv = priority === 'first' ? 65.0 : 70.0;
            } else {
                ltv = priority === 'first' ? 50.0 : 60.0;
            }
        }
    }

    return ltv;
}

// ========================================================
// 주소 기반 메리츠 지역 판단 함수
// ========================================================
    /**
     * 메리츠 지역 판단 기준 (PDF 기준)
     *
     * 1군 지역: 서울, 경기1군, 인천1군
     * - 서울: 강남, 서초, 송파, 강동, 마포, 서대문, 종로, 중구, 용산, 영등포, 동작, 관악, 성동, 광진, 동대문, 중랑, 성북, 강북, 노원, 도봉, 은평, 양천, 구로, 강서, 금천 (서울 전체 1군)
     * - 경기1군: 용인(수지, 기흥), 과천, 광명, 구리, 군포, 부천, 성남, 수원, 안양, 의왕, 하남, 김포, 남양주
     * - 인천1군: 계양구, 부평구, 연수구, 미추홀구
     *
     * 2군 지역: 경기2군, 인천2군
     * - 경기2군: 시흥, 안산, 화성, 용인(처인구), 의정부, 양주, 고양, 광주, 동두천, 오산, 이천, 파주
     * - 인천2군: 남동구, 서구, 동구, 중구
     *
     * 3군 지역: 경기3군 + 광역시
     * - 경기3군: 평택, 안성, 여주, 포천
     * - 광역시: 대전, 세종, 대구, 부산, 광주, 울산
     */
function determineMeritzRegionFromAddress(address) {
    if (!address) return null;

    // 지역 목록 (정확한 매칭을 위해 리스트 활용)
    const r3_gyeonggi = ['평택', '안성', '여주', '포천'];
    const r3_metro = ['대전', '세종', '대구'];  // 3군 광역시
    const r2_metro = ['부산', '울산', '광주'];  // 2군 광역시 (광주광역시도 2군)
    const r2 = ['시흥', '안산', '화성', '처인구', '의정부', '양주', '고양', '광주', '동두천', '오산', '이천', '파주', '김포', '부천'];  // 경기 2군, 김포/부천 2군 이동
    const r2_incheon = ['중구', '동구', '서구', '남동구', '연수구', '부평구', '계양구', '미추홀구'];  // 인천 전체 2군 (인천 포함 주소에서만 매칭)
    const r1 = ['강남구', '서초구', '송파구', '강동구', '마포구', '서대문구', '종로구', '중구', '용산구', '영등포구', '동작구', '관악구', '성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구', '노원구', '도봉구', '은평구', '양천구', '구로구', '강서구', '금천구',
                '수지구', '기흥구', '과천', '광명', '구리', '군포', '성남', '수원', '안양', '의왕', '하남', '남양주'];

    // ✅ 0. 인천 전체 2군 (가장 먼저 체크 - 인천 중구가 r1 중구와 충돌 방지)
    if (address.includes('인천')) return '2gun';

    // ✅ 1. 1군 확인 (서울 구 + 경기 1군)
    for (let reg of r1) {
        if (address.includes(reg)) return '1gun';
    }

    // ✅ 2. 2군 광역시 확인 (부산, 울산, 광주광역시)
    for (let reg of r2_metro) {
        if (reg === '광주') {
            if (address.includes('광주광역시')) return '2gun';
            continue;
        }
        if (address.includes(reg)) return '2gun';
    }

    // ✅ 2-1. 2군 확인 (경기 2군)
    for (let reg of r2) {
        if (address.includes(reg)) {
            // 경기도 광주와 광주광역시 구분
            if (reg === '광주' && address.includes('광주광역시')) continue;
            return '2gun';
        }
    }

    // ✅ 3. 3군 확인 (경기3군)
    for (let reg of r3_gyeonggi) {
        if (address.includes(reg)) return '3gun';
    }

    // ✅ 4. 3군 확인 (광역시)
    for (let reg of r3_metro) {
        if (address.includes(reg)) return '3gun';
    }
    // 광주광역시는 r2_metro에서 이미 2군 처리됨

    // ✅ 5. 용인 단독 처리
    if (address.includes('용인') && !address.includes('처인구')) return '1gun';

    return null;
}

// ========================================================
// 주소 기반 급지 판단 함수 (지분대출/기본 급지용)
// ========================================================
function getRegionGradeFromAddress(address) {
    if (!address) return "미분류";
    const addr = address.toUpperCase();

    // 인천은 별도 처리 (전체 2군)
    if (address.includes('인천')) return "2군";

    const CLASSIFICATION = {
        "1군": ["강남구", "서초구", "송파구", "강동구", "마포구", "서대문구", "종로구", "중구", "용산구", "영등포구", "동작구", "관악구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "노원구", "도봉구", "은평구", "양천구", "구로구", "강서구", "금천구", "수지구", "기흥구", "과천", "광명", "구리", "군포", "성남", "수원", "안양", "의왕", "하남", "남양주"],
        "2군": ["시흥", "안산", "화성", "처인구", "의정부", "양주", "고양", "광주", "동두천", "오산", "이천", "파주", "김포", "부천"],
        "2군_광역시": ["부산", "울산", "광주"],
        "3군_경기": ["평택", "안성", "여주", "포천"],
        "3군_광역시": ["대전", "세종", "대구"]
    };

    // ✅ 1. 1군 우선 확인
    for (let dist of CLASSIFICATION["1군"]) {
        if (addr.includes(dist.toUpperCase())) return "1군";
    }

    // ✅ 2. 2군 광역시 확인 (부산, 울산) - 서구/동구/중구보다 먼저 체크
    for (let dist of CLASSIFICATION["2군_광역시"]) {
        if (addr.includes(dist.toUpperCase())) return "2군";
    }

    // ✅ 2-1. 2군 확인 (서구 예외처리)
    for (let dist of CLASSIFICATION["2군"]) {
        if (addr.includes(dist.toUpperCase())) {
            if (dist === "서구" && addr.includes("강서구")) continue;
            // 경기도 광주와 광주광역시 구분
            if (dist === "광주" && addr.includes("광주광역시")) continue;
            return "2군";
        }
    }

    // ✅ 3. 3군 확인 (경기3군)
    for (let dist of CLASSIFICATION["3군_경기"]) {
        if (addr.includes(dist.toUpperCase())) return "3군";
    }

    // ✅ 4. 3군 확인 (광역시)
    for (let dist of CLASSIFICATION["3군_광역시"]) {
        if (addr.includes(dist.toUpperCase())) return "3군";
    }
    return "미분류";
}

// ========================================================
// 질권 체크 시 지방 물건 경고 함수
// ========================================================
function checkRegionWarningForCollateral(address) {
    // 아이엠 또는 메리츠 질권이 체크되어 있는지 확인
    const hopeCheckbox = document.getElementById('hope-collateral-loan');
    const meritzCheckbox = document.getElementById('meritz-collateral-loan');

    const isHopeChecked = hopeCheckbox && hopeCheckbox.checked;
    const isMeritzChecked = meritzCheckbox && meritzCheckbox.checked;

    // 질권이 체크되어 있지 않으면 경고하지 않음
    if (!isHopeChecked && !isMeritzChecked) {
        return;
    }

    // 주소가 없으면 경고하지 않음
    if (!address || address.trim() === '') {
        return;
    }

    // 서울/경기/인천 지역인지 확인 (군 지역 제외)
    const isSeoul = address.includes('서울');
    const isGyeonggi = address.includes('경기');
    const isIncheon = address.includes('인천');

    // 메리츠 질권 시 허용되는 광역시 (3군으로 취급)
    const meritzMetroCities = ['대전', '세종', '대구', '부산', '광주', '울산'];
    const isMeritzMetroCity = isMeritzChecked && meritzMetroCities.some(city => address.includes(city));

    // 제외할 군 지역 목록
    const excludedGuns = ['가평군', '양평군', '연천군', '강화군', '옹진군'];
    const isExcludedGun = excludedGuns.some(gun => address.includes(gun));

    // 유효한 지역 판단
    // - 아이엠: 서울/경기/인천만
    // - 메리츠: 서울/경기/인천 + 광역시(대전, 세종, 대구, 부산, 광주, 울산)
    const isValidRegion = isSeoul || isGyeonggi || isIncheon || isMeritzMetroCity;

    // 유효하지 않은 지역이거나 군 지역이면 경고 표시
    if (!isValidRegion || isExcludedGun) {
        const pledgeType = isHopeChecked ? '아이엠질권' : '메리츠질권';
        const gunWarning = isExcludedGun ? '\n(군 지역은 취급 불가)' : '';
        const regionInfo = isMeritzChecked ? '서울/경기/인천 및 광역시(대전, 세종, 대구, 부산, 광주, 울산)' : '서울/경기/인천';
        showCustomAlert(`⚠️ ${pledgeType} 취급불가 지역입니다!\n\n${regionInfo}만 취급 가능합니다. (군 지역 제외)${gunWarning}\n현재 주소: ${address}`);
        console.log(`🔴 경고: ${pledgeType} 취급불가 지역 - ${address}${isExcludedGun ? ' (군 지역)' : ''}`);
    }
}
