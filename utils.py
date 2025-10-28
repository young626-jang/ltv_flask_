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
        const mainContainer = document.getElementById('main-layout-wrapper');
        const pdfColumn = document.getElementById('pdf-column');
        const formColumn = document.getElementById('form-column-wrapper');
        const isHorizontal = mainContainer.classList.contains('horizontal-mode');
        
        const layoutSettings = {
            isHorizontalMode: isHorizontal,
            pdfColumnFlex: pdfColumn.style.flex || (isHorizontal ? '3' : '2'),
            formColumnFlex: formColumn.style.flex || (isHorizontal ? '2' : '3'),
            timestamp: Date.now()
        };
        
        localStorage.setItem('ltvLayoutSettings', JSON.stringify(layoutSettings));
    }

    function loadLayoutSettings() {
        try {
            const saved = localStorage.getItem('ltvLayoutSettings');
            if (!saved) return;
            
            const settings = JSON.parse(saved);
            const mainContainer = document.getElementById('main-layout-wrapper');
            const btn = document.getElementById('layout-toggle-btn');
            const pdfColumn = document.getElementById('pdf-column');
            const formColumn = document.getElementById('form-column-wrapper');
            
            // 저장된 설정이 24시간 이내인지 확인
            const isRecent = (Date.now() - settings.timestamp) < (24 * 60 * 60 * 1000);
            if (!isRecent) return;
            
            // 레이아웃 모드 복원
            if (settings.isHorizontalMode) {
                mainContainer.classList.add('horizontal-mode');
                btn.innerHTML = '<i class="bi bi-distribute-vertical"></i> 세로 모드';
            } else {
                mainContainer.classList.remove('horizontal-mode');
                btn.innerHTML = '<i class="bi bi-distribute-horizontal"></i> 가로 모드';
            }
            
            // 컬럼 크기 복원 (flex 기반)
            if (settings.pdfColumnFlex) {
                pdfColumn.style.flex = settings.pdfColumnFlex;
            }
            if (settings.formColumnFlex) {
                formColumn.style.flex = settings.formColumnFlex;
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
            pdfColumn.style.flex = '2';
            formColumn.style.flex = '3';
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
        
        // 억 단위 처리
        const eokMatch = remainingText.match(/(\d+)억/);
        if (eokMatch) {
            total += parseInt(eokMatch[1]) * 10000;
            remainingText = remainingText.replace(eokMatch[0], '');
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
            const siblings = [...container.querySelectorAll('.loan-item:not(.dragging)')];
            
            const nextSibling = siblings.find(sibling => {
                return e.clientY <= sibling.getBoundingClientRect().top + sibling.getBoundingClientRect().height / 2;
            });
            
            container.insertBefore(draggingItem, nextSibling);
        });
        
        container.addEventListener('drop', (e) => {
            e.preventDefault();
            // 드롭 후 메모 업데이트
            setTimeout(() => {
                triggerMemoGeneration();
            }, 100);
        });
    }

    // ========================================================
    // 6. 대출 항목 관련 함수
    // ========================================================
    // createLoanItemHTML 함수 - 드래그 핸들 추가
    function createLoanItemHTML(index, loan = {}) {
        const formatValue = (val) => {
            if (!val) return '';
            const numValue = Number(String(val).replace(/,/g, ''));
            return numValue ? numValue.toLocaleString() : '';
        };
        
        return `
        <div id="loan-item-${index}" class="loan-item py-2 border-bottom" draggable="false">
            <div class="loan-col loan-col-drag">
                <div class="drag-handle md-drag-handle" title="드래그하여 순서 변경">⋮⋮</div>
            </div>
            <div class="loan-col loan-col-lender">
                <div class="mobile-label">설정자</div>
                <input type="text" class="form-control form-control-sm loan-input form-field md-loan-input" name="lender" placeholder="설정자" value="${loan.lender || ''}">
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

        // 입력값이 유효할 때만 계산
        if (principal > 0 && annualRate > 0) {
            const yearlyInterest = Math.floor(principal * (annualRate / 100));
            const monthlyInterest = Math.floor(yearlyInterest / 12);
            const dailyInterest = Math.floor(yearlyInterest / 365);

            // 계산된 값을 콤마와 함께 '원' 단위로 표시
            yearlyResultEl.value = yearlyInterest.toLocaleString() + '원';
            monthlyResultEl.value = monthlyInterest.toLocaleString() + '원';
            dailyResultEl.value = dailyInterest.toLocaleString() + '원';
        } else {
            // 입력값이 없거나 0이면 결과를 ''으로 초기화
            yearlyResultEl.value = '';
            monthlyResultEl.value = '';
            dailyResultEl.value = '';
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
                maxAmountInput.value = data.max_amount ? parseInt(data.max_amount).toLocaleString() : '0';
                principalInput.value = data.principal ? parseInt(data.principal).toLocaleString() : '0';
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
                    }
                    // 기존의 메모 생성 함수를 호출합니다.
                    triggerMemoGeneration();
                    // 지분 계산도 자동 업데이트
                    calculateIndividualShare();
                });
            });
        });
    }


// 모든 폼 데이터 수집
function collectAllData() {
    const regionSelect = document.getElementById('deduction_region');
    const selectedRegionText = regionSelect.options[regionSelect.selectedIndex].text;
    const loanItems = Array.from(document.querySelectorAll('.loan-item')).map(item => ({
        lender: item.querySelector('[name="lender"]').value,
        status: item.querySelector('[name="status"]').value,
        max_amount: item.querySelector('[name="max_amount"]').value,
        principal: item.querySelector('[name="principal"]').value,
        ratio: item.querySelector('[name="ratio"]').value,
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
            kb_price: document.getElementById('kb_price').value,
            area: document.getElementById('area').value,
            deduction_region_text: selectedRegionText,
            deduction_amount: document.getElementById('deduction_amount').value,
            
            // [복구] LTV1만 전송
            ltv_rates: [document.getElementById('ltv1').value], 
            
            // [삭제] required_amount 필드 제거
            // required_amount: document.getElementById('required_amount').value, 
            
            share_rate1: document.getElementById('share-customer-birth-1').value,
            share_rate2: document.getElementById('share-customer-birth-2').value,
            hope_collateral_checked: document.getElementById('hope-collateral-loan').checked,
        },
        fees: {
            // [복구] consult_amt가 컨설팅 금액으로 돌아옵니다.
            consult_amt: document.getElementById('consult_amt').value, 
            consult_rate: document.getElementById('consult_rate').value,
            bridge_amt: document.getElementById('bridge_amt').value,
            bridge_rate: document.getElementById('bridge_rate').value,
        },
        loans: loanItems
    };
}

    
    // 메모 생성 요청 (디바운스 적용)
    function triggerMemoGeneration() {
        clearTimeout(memoDebounceTimeout);
        memoDebounceTimeout = setTimeout(generateMemo, 800); 
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
            document.getElementById('customer_name').value = owners[0] || '';
            document.getElementById('customer_name_2').value = owners[1] || '';
        } else {
            document.getElementById('customer_name').value = '';
            document.getElementById('customer_name_2').value = '';
        }
        // --- ▲▲▲ 여기가 핵심 수정 부분입니다 ▲▲▲ ---
        
        document.getElementById('address').value = data.address || '';
        document.getElementById('kb_price').value = (data.kb_price || '').toLocaleString();
        document.getElementById('area').value = data.area || '';
        document.getElementById('ltv1').value = data.ltv1 || '80';
        document.getElementById('ltv2').value = data.ltv2 || '';
        document.getElementById('consult_amt').value = (data.consult_amt || '0').toLocaleString();
        document.getElementById('consult_rate').value = data.consult_rate || '1.5';
        document.getElementById('bridge_amt').value = (data.bridge_amt || '0').toLocaleString();
        document.getElementById('bridge_rate').value = data.bridge_rate || '0.7';
        
        const regionSelect = document.getElementById('deduction_region');
        const regionOption = Array.from(regionSelect.options).find(opt => opt.text === data.deduction_region);
        if(regionOption) {
            regionSelect.selectedIndex = Array.from(regionSelect.options).indexOf(regionOption);
        } else if(regionSelect.options.length > 0) {
            regionSelect.selectedIndex = 0;
        }
        document.getElementById('deduction_amount').value = (regionSelect.value || '').toLocaleString();
        document.getElementById('loan-items-container').innerHTML = '';
        loanItemCounter = 0;

        if (data.loans && data.loans.length > 0) {
            data.loans.forEach(loan => addLoanItem(loan));
        } else { 
            addLoanItem(); 
        }

        // customer_name 데이터를 지분한도 계산기 탭 공유자 필드에 자동 입력
        if (data.customer_name) {
            const owners = data.customer_name.split(',').map(name => name.trim());
            if (owners.length >= 1) {
                document.getElementById('share-customer-name-1').value = owners[0];
            }
            if (owners.length >= 2) {
                document.getElementById('share-customer-name-2').value = owners[1];
            }
        }

            // customer_name 데이터를 지분한도 계산기 탭 공유자 필드에 자동 입력
            if (data.customer_name) {
                const owners = data.customer_name.split(',').map(name => name.trim());
                if (owners.length >= 1) {
                    document.getElementById('share-customer-name-1').value = owners[0];
                }
                if (owners.length >= 2) {
                    document.getElementById('share-customer-name-2').value = owners[1];
                }
            }
            
            // 공유자 지분율 자동 입력
            if (data.share_rate1) {
                document.getElementById('share-customer-birth-1').value = data.share_rate1;
            }
            if (data.share_rate2) {
                document.getElementById('share-customer-birth-2').value = data.share_rate2;
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

            // 디버깅: 추출된 데이터 로그
            console.log('📊 scraped_data:', scraped);
            console.log('📅 transfer_date:', scraped.transfer_date);

            // --- 2. 추출된 기본 정보를 각 필드에 자동으로 채워 넣습니다. ---
            
            // 소유자 이름 & 생년월일 (2명까지 지원)
            if (scraped.customer_name) {
                const owners = scraped.customer_name.split(',').map(name => name.trim());
                document.getElementById('customer_name').value = owners[0] || '';
                document.getElementById('customer_name_2').value = owners[1] || '';
            } else {
                document.getElementById('customer_name').value = '';
                document.getElementById('customer_name_2').value = '';
            }

            document.getElementById('address').value = scraped.address || '';
            const areaValue = scraped.area || '';
            document.getElementById('area').value = areaValue.includes('㎡') ? areaValue : (areaValue ? `${areaValue}㎡` : '');

            // 소유권이전일 추가
            const transferDateField = document.getElementById('ownership_transfer_date');
            console.log('🔍 transferDateField 확인:', transferDateField ? '존재' : '없음');
            transferDateField.value = scraped.transfer_date || '';
            console.log('✅ ownership_transfer_date 값:', transferDateField.value);
            checkTransferDateColor(transferDateField.value);

            // 등기 경고 표시 (오래된 등기인지 등)
            displayRegistrationWarning(scraped.age_check);

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

                    addLoanItem({
                        lender: lender,
                        max_amount: maxAmount,
                        status: '유지' // 기본 상태는 '유지'로 설정
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

            // PDF 뷰어를 표시하고 파일 이름을 보여줍니다.
            const fileURL = URL.createObjectURL(file);
            document.getElementById('pdf-viewer').src = fileURL;
            document.getElementById('upload-section').style.display = 'none';
            document.getElementById('viewer-section').style.display = 'block';
            document.getElementById('file-name-display').textContent = file.name;
            setPdfColumnExpanded(); // PDF 업로드 시 PDF 컬럼 확장

            // 최종적으로 메모를 업데이트합니다.
            triggerMemoGeneration();

        } else { 
            alert(`업로드 실패: ${result.error || '알 수 없는 오류'}`); 
        }

    } catch (error) {
        alert(`업로드 중 오류가 발생했습니다: ${error.message}`);
    } finally {
        spinner.style.display = 'none';
    }
}

    // 레이아웃 토글
    function toggleLayout() {
        const mainContainer = document.getElementById('main-layout-wrapper');
        const btn = document.getElementById('layout-toggle-btn');
        const pdfColumn = document.getElementById('pdf-column');
        const formColumn = document.getElementById('form-column-wrapper');
        if (!mainContainer || !btn || !pdfColumn || !formColumn) return;

        mainContainer.classList.toggle('horizontal-mode');
        const isHorizontal = mainContainer.classList.contains('horizontal-mode');
        btn.innerHTML = isHorizontal ? '<i class="bi bi-distribute-vertical"></i> 세로 모드' : '<i class="bi bi-distribute-horizontal"></i> 가로 모드';
        
        // 컬럼 크기 초기화
        if (isHorizontal) {
            // [정상 동작] 가로모드: JS는 높이를 비우고, CSS flex가 자동 계산
            pdfColumn.style.width = '100%';
            pdfColumn.style.height = '';
            pdfColumn.style.flex = '3';
            formColumn.style.width = '100%';
            formColumn.style.height = '';
            formColumn.style.flex = '2';
        } else {
            // [수정 완료] 세로모드: JS가 높이를 비워서, CSS가 자동 계산하도록 변경
            pdfColumn.style.width = '100%';
            pdfColumn.style.height = ''; // ★★★ 핵심: 문제가 되었던 calc() 코드를 삭제했습니다.
            pdfColumn.style.flex = '3';
            formColumn.style.width = '100%';
            formColumn.style.height = ''; // ★★★ 핵심: 문제가 되었던 calc() 코드를 삭제했습니다.
            formColumn.style.flex = '2';
        }
        
        // 레이아웃 상태 저장 및 리사이즈 바 재설정
        saveLayoutSettings();
        
        setTimeout(() => {
            initializeResizeBar();
        }, 100);
    }

    // 전체 초기화
    function clearAllFields() {
        document.querySelectorAll('.form-field').forEach(field => {
        document.getElementById('customer_name_2').value = ''; // 이 줄을 추가해주세요.
        document.getElementById('ltv1').value = '80';    
            if(field.tagName === 'SELECT') { 
                field.selectedIndex = 0; 
            } else { 
                field.value = ''; 
            }
        });
        document.getElementById('ltv1').value = '80';
        document.getElementById('consult_rate').value = '1.5';
        document.getElementById('bridge_rate').value = '0.7';
        const deductionRegionValue = document.getElementById('deduction_region').value;
        document.getElementById('deduction_amount').value = (deductionRegionValue !== '0' && deductionRegionValue) ? 
            parseInt(deductionRegionValue).toLocaleString() : '';
        document.getElementById('loan-items-container').innerHTML = '';
        loanItemCounter = 0;
        addLoanItem();
        const fileInput = document.getElementById('file-input');
        if (fileInput) fileInput.value = null;
        document.getElementById('pdf-viewer').src = 'about:blank';
        document.getElementById('upload-section').style.display = 'flex';
        
        // 지분한도 계산기 필드 초기화
        document.getElementById('share-customer-name-1').value = '';
        document.getElementById('share-customer-birth-1').value = '';
        document.getElementById('share-customer-name-2').value = '';
        document.getElementById('share-customer-birth-2').value = '';
        document.getElementById('viewer-section').style.display = 'none';
        
        // 등기 경고 숨김
        hideRegistrationWarning();
        
        setPdfColumnCompact(); // 전체 초기화 시 PDF 컬럼 컴팩트
        alert("모든 입력 내용이 초기화되었습니다.");
        triggerMemoGeneration();
    }
    
    // 개별 차주 지분 한도 계산
    // [API 호출 함수들] loadCustomerData(라인 827), handleFileUpload(라인 1070), calculateLTVFromRequiredAmount(라인 1929) 참고
    // [관련 계산] calculatePrincipalFromRatio(라인 349), calculateSimpleInterest(라인 472), calculateLTVFromRequiredAmount(라인 1929), calculateBalloonLoan(라인 2034) 참고
    async function calculateIndividualShare() {
        try {
            // 선택된 차주 찾기
            const selectedRadio = document.querySelector('input[name="share-borrower"]:checked');
            if (!selectedRadio) return; // 선택된 차주가 없으면 종료
            
            const ownerIdx = selectedRadio.value;
            
            const kbPriceText = document.getElementById("kb_price").value.replace(/,/g,'') || "0";
            const kbPrice = parseInt(kbPriceText);
            
            // LTV 비율 수집 (ltv1, ltv2)
            const ltvRates = [];
            const ltv1 = document.getElementById("ltv1").value;
            const ltv2 = document.getElementById("ltv2").value;
            if (ltv1 && ltv1.trim()) ltvRates.push(parseFloat(ltv1));
            if (ltv2 && ltv2.trim()) ltvRates.push(parseFloat(ltv2));
            if (ltvRates.length === 0) ltvRates.push(70); // 기본값

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
                const ltv = ltvRates[i];
                const payload = {
                    total_value: kbPrice,
                    ltv: ltv,
                    loans: loans,
                    owners: owners,
                    loan_type: loanTypeInfo
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
                    const shareLimit = result["지분LTV한도(만원)"];
                    const available = result["가용자금(만원)"];
                    
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
        radio.addEventListener('change', calculateIndividualShare);
        radio.addEventListener('click', function() {
            setTimeout(() => {
                calculateIndividualShare();
            }, 50);
        });
    });
    

    // [정리 및 통합] KB시세, 필요금액 변경 시 LTV 자동 계산을 최우선으로 실행
    
    // 1. KB시세 변경 시: LTV 자동 계산 -> 지분 개별 계산
    document.getElementById('kb_price')?.addEventListener('change', calculateLTVFromRequiredAmount);
    document.getElementById('kb_price')?.addEventListener('blur', calculateLTVFromRequiredAmount);
    
    // 2. 필요금액 변경 시: LTV 자동 계산 -> 지분 개별 계산
    document.getElementById('required_amount')?.addEventListener('change', calculateLTVFromRequiredAmount);
    document.getElementById('required_amount')?.addEventListener('blur', calculateLTVFromRequiredAmount);
    
    // 3. LTV1 변경 시 (수동 입력 또는 +/- 버튼): 메모/지분 계산만 실행
    document.getElementById('ltv1')?.addEventListener('change', calculateIndividualShare);
    document.getElementById('ltv1')?.addEventListener('blur', calculateIndividualShare);

    // 4. 지분율 변경 시: 지분 개별 계산 (기존 로직 유지)
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
    
    // LTV1의 +/- 버튼 클릭 시에도 메모 생성 및 지분 계산을 트리거하도록 수정
    document.querySelectorAll('.md-ltv-btn').forEach(btn => {
        btn.addEventListener('click', () => {
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
            if (e.target.checked) {
                // 체크 되면 지역 버튼 표시
                regionButtonsDiv.style.cssText = 'display: flex !important;';
                // 방공제 없음으로 자동 선택
                const deductionRegionField = document.getElementById('deduction_region');
                if (deductionRegionField) {
                    deductionRegionField.value = '0';
                    console.log('💰 방공제 지역 - "방공제없음"으로 자동 선택');
                }
                console.log('✅ 희망담보대부 적용 - 지역 버튼 표시');
            } else {
                // 체크 해제되면 지역 버튼 숨김
                regionButtonsDiv.style.cssText = 'display: none !important;';
                // 버튼 스타일 초기화
                document.querySelectorAll('.hope-loan-region-btn').forEach(b => {
                    b.style.backgroundColor = '';
                    b.style.color = '';
                    b.style.borderColor = '';
                });
                console.log('❌ 희망담보대부 해제 - 지역 버튼 숨김');
            }
            // 희망담보대부 조건 검증
            validateHopeLoanConditions();
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

    // 희망담보대부 지역 선택 버튼 이벤트
    document.querySelectorAll('.hope-loan-region-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const ltv = e.target.getAttribute('data-ltv');
            const region = e.target.getAttribute('data-region');

            // LTV 값 변경
            document.getElementById('ltv1').value = ltv;
            console.log(`🌍 지역 선택: ${region} (LTV: ${ltv}%)`);

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

            // LTV 변경으로 인한 계산 트리거
            calculateIndividualShare();
            triggerMemoGeneration();
        });
    });

} // <--- 이 닫는 괄호가 핵심입니다.



    // 리사이즈 바 기능 구현
    function initializeResizeBar() {
        const resizeBar = document.getElementById('resize-bar');
        const pdfColumn = document.getElementById('pdf-column');
        const formColumn = document.getElementById('form-column-wrapper');
        const mainContainer = document.getElementById('main-layout-wrapper');
        const pdfViewer = document.getElementById('pdf-viewer');
        
        if (!resizeBar || !pdfColumn || !formColumn) return;
        
        // 이미 초기화된 경우 중복 방지
        if (resizeBar.dataset.initialized === 'true') return;
        resizeBar.dataset.initialized = 'true';
        
        let isResizing = false;
        let startPos = 0;
        let startPdfSize = 0;
        
        const isHorizontalMode = () => mainContainer.classList.contains('horizontal-mode');
        
        function startResize(clientX, clientY) {
            isResizing = true;
            
            // [수정 1] 드래그를 시작할 때 iframe의 마우스 이벤트를 '끈다'.
            if (pdfViewer) pdfViewer.style.pointerEvents = 'none';
            
            // 트랜지션 효과를 잠시 꺼서 드래그가 끊기지 않게 합니다.
            pdfColumn.style.transition = 'none';
            formColumn.style.transition = 'none';
            
            // 드래그 중 텍스트가 선택되는 것을 방지합니다.
            document.body.style.userSelect = 'none';
            
            if (isHorizontalMode()) {
                startPos = clientY;
                startPdfSize = pdfColumn.getBoundingClientRect().height;
                document.body.style.cursor = 'row-resize';
            } else {
                startPos = clientX;
                startPdfSize = pdfColumn.getBoundingClientRect().width;
                document.body.style.cursor = 'col-resize';
            }
        }
        
        function doResize(clientX, clientY) {
            if (!isResizing) return;
            
            if (isHorizontalMode()) {
                // --- 가로 모드 (상하 분할) ---
                const deltaY = clientY - startPos;
                const containerHeight = mainContainer.clientHeight;
                const minHeight = 150; // 패널이 너무 작아지는 것을 방지하기 위한 최소 높이
                
                let newPdfHeight = startPdfSize + deltaY;
                
                // 최소/최대 높이 제한을 두어 레이아웃이 깨지지 않게 합니다.
                newPdfHeight = Math.max(minHeight, newPdfHeight);
                newPdfHeight = Math.min(containerHeight - minHeight, newPdfHeight);

                const newFormHeight = containerHeight - newPdfHeight - resizeBar.clientHeight;
                
                const totalFlexHeight = newPdfHeight + newFormHeight;
                pdfColumn.style.flex = `${(newPdfHeight / totalFlexHeight) * 5}`;
                formColumn.style.flex = `${(newFormHeight / totalFlexHeight) * 5}`;
                
            } else {
                // --- 세로 모드 (좌우 분할) ---
                /* ▼▼▼ 이 코드로 교체하세요 ▼▼▼ */
                const deltaX = clientX - startPos;
                const containerWidth = mainContainer.clientWidth;
                const resizeBarWidth = resizeBar.clientWidth;
                const availableWidth = containerWidth - resizeBarWidth;
                const minWidth = 150;

                // PDF 컬럼의 새로운 너비 계산 (최소/최대 제한 포함)
                let newPdfWidth = startPdfSize + deltaX;
                newPdfWidth = Math.max(minWidth, newPdfWidth);
                newPdfWidth = Math.min(availableWidth - minWidth, newPdfWidth);

                // 폼 컬럼의 새로운 너비 계산
                const newFormWidth = availableWidth - newPdfWidth;
                
                // 계산된 너비 비율에 따라 flex 값을 동적으로 설정 (가로 모드와 로직 통일)
                const totalFlexWidth = newPdfWidth + newFormWidth;
                pdfColumn.style.flex = `${(newPdfWidth / totalFlexWidth) * 5}`;
                formColumn.style.flex = `${(newFormWidth / totalFlexWidth) * 5}`;
                /* ▲▲▲ 여기까지 교체 ▲▲▲ */
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
            if (isHorizontalMode()) {
                pdfColumn.style.flex = '3';
                formColumn.style.flex = '2';
            } else {
                pdfColumn.style.width = '62.5%';
                formColumn.style.width = '37.5%';
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
   addLoanItem();
   attachAllEventListeners();
   loadCustomerList();
   triggerMemoGeneration();
   validateHopeLoanConditions(); // 페이지 로드 시 희망담보대부 조건 검증
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
    const deductionAmount = document.getElementById('deduction_amount').value;

    // KB시세가 0이면 필요금액을 비우고 경고
    if (parseKoreanNumberString(kbPrice) === 0) {
        if (parseKoreanNumberString(requiredAmt) > 0) {
            showCustomAlert("KB시세를 먼저 입력해야 LTV 자동 계산이 가능합니다.");
            requiredAmtField.value = '';
        }
        ltv1Field.value = '';
        triggerMemoGeneration();
        calculateIndividualShare();
        return;
    }

    // 대출 정보 수집
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
        // 서버 API 호출
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
            // ltv1 필드에 계산된 LTV 설정
            ltv1Field.value = result.ltv > 0 ? result.ltv : '';

            // 메모 업데이트 및 지분 계산 트리거
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
    const guideUrl = 'https://young626-jang.github.io/heuimang-loan-consulting-guide/';
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

// 희망담보대부 조건 검증 (독립적인 두 조건)
// 조건 1: 희망담보대부 체크 AND 세대수 < 100 → 세대수 필드 빨간색
// 조건 2: 희망담보대부 체크 AND KB시세 < 3억 → KB시세 필드 빨간색
function validateHopeLoanConditions() {
    const hopeCheckbox = document.getElementById('hope-collateral-loan');
    const unitCountField = document.getElementById('unit_count');
    const kbPriceField = document.getElementById('kb_price');

    if (!hopeCheckbox || !unitCountField || !kbPriceField) return;

    // 희망담보대부가 체크되어 있는지 확인
    const isHopeChecked = hopeCheckbox.checked;

    // 세대수와 KB시세 값 가져오기 (값이 입력되지 않으면 0)
    const unitCount = parseInt(unitCountField.value) || 0;
    const kbPrice = parseInt(kbPriceField.value.replace(/,/g, '')) || 0;

    // 3억 = 30,000만 (KB시세는 만 단위)
    const THREE_HUNDRED_MILLION = 30000;

    // 조건 1: 희망담보대부 체크 AND 세대수 < 100
    const shouldHighlightUnitCount = isHopeChecked && unitCount > 0 && unitCount < 100;

    // 조건 2: 희망담보대부 체크 AND KB시세 < 3억 (30,000만)
    const shouldHighlightKbPrice = isHopeChecked && kbPrice > 0 && kbPrice < THREE_HUNDRED_MILLION;

    console.log(`🔍 희망담보대부 검증 - 체크: ${isHopeChecked}, 세대수: ${unitCount}, KB시세: ${kbPrice}`);
    console.log(`   세대수 강조: ${shouldHighlightUnitCount}, KB시세 강조: ${shouldHighlightKbPrice}`);

    // 세대수 필드 스타일 처리
    if (shouldHighlightUnitCount) {
        unitCountField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
        console.log('🔴 경고: 세대수 조건 만족');
    } else {
        unitCountField.removeAttribute('style');
    }

    // KB시세 필드 스타일 처리
    if (shouldHighlightKbPrice) {
        kbPriceField.style.cssText = 'background-color: #ffcccc !important; border: 2px solid #ff0000 !important; box-shadow: 0 0 5px rgba(255,0,0,0.3) !important;';
        console.log('🔴 경고: KB시세 조건 만족');
    } else {
        kbPriceField.removeAttribute('style');
    }
}

