// static/js/betting_detail.js 파일의 전체 내용입니다.

// ===================================
// 베팅 저장 (참가자용)
// ===================================
function saveBetting(bettingId) {
    const participantsData = [];
    const participantRows = document.querySelectorAll('#participants-table [data-participant-id]');

    participantRows.forEach(row => {
        const participantId = row.dataset.participantId;
        const choiceInput = row.querySelector(`input[name="choice-${participantId}"]:checked`);
        
        participantsData.push({
            id: parseInt(participantId),
            winner: choiceInput ? parseInt(choiceInput.value) : null
        });
    });

    fetch(`/betting/${bettingId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ participants: participantsData })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('베팅 정보가 저장되었습니다.');
            location.reload();
        } else {
            alert('오류: ' + data.error);
        }
    });
}

// ===================================
// 결과 제출 (관리자용)
// ===================================
function submitBettingResult(bettingId, p1Name, p2Name) {
    const winnerName = document.getElementById('winner-select').value;
    const score = document.getElementById('score-select').value;

    if (!winnerName) {
        alert('승자를 선택해주세요.');
        return;
    }

    const data = { bettingId, p1Name, p2Name, winnerName, score };

    if (!confirm(`${winnerName} 선수의 승리로 결과를 제출하시겠습니까?\n이 작업은 되돌릴 수 없으며, 베팅이 즉시 마감됩니다.`)) {
        return;
    }

    fetch('/submit_betting_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.results) {
            const results = data.results;
            const winNames = results.winParticipants.join(', ') || '없음';
            const loseNames = results.loseParticipants.join(', ') || '없음';
            
            alert(
                `결과가 제출되었습니다!\n\n` +
                `승자: ${results.winnerName}\n` +
                `패자: ${results.loserName}\n\n` +
                `베팅 성공자 (${results.winParticipants.length}명): ${winNames}\n` +
                `베팅 실패자 (${results.loseParticipants.length}명): ${loseNames}\n\n` +
                `1인당 예상 분배 포인트: ${results.distributedPoints} pt`
            );
            location.reload();
        } else {
            alert('오류: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('서버와 통신 중 오류가 발생했습니다.');
    });
}

// ===================================
// 베팅 삭제 (관리자용)
// ===================================
async function deleteBetting(bettingId) {
    const password = await requestPasswordModal("삭제하려면 비밀번호를 입력하세요."); 
    if (password === null) return;

    fetch(`/betting/${bettingId}/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: password })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            window.location.href = '/betting';
        } else {
            alert('오류: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('베팅 삭제 중 오류가 발생했습니다.');
    });
}

// ===================================
// 참가자 추가/삭제 (관리자용)
// ===================================
async function addParticipants(bettingId) {
    const namesString = prompt("추가할 참가자들의 이름을 띄어쓰기로 구분하여 입력하세요:");
    if (!namesString || namesString.trim() === '') return;

    const names = namesString.trim().split(/\s+/).filter(name => name);
    if (names.length === 0) return;

    try {
        const idResponse = await fetch('/get_player_ids', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ names: names })
        });
        const idData = await idResponse.json();

        if (!idData.success) {
            throw new Error(idData.error || "선수 ID를 가져오지 못했습니다.");
        }

        const addResponse = await fetch('/add_participants', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bettingId: bettingId, playerIds: idData.player_ids })
        });
        const addData = await addResponse.json();

        alert(addData.message || addData.error);
        if (addData.success) {
            location.reload();
        }
    } catch (error) {
        alert("오류 발생: " + error.message);
    }
}

async function removeParticipants(bettingId) {
    const namesString = prompt("삭제할 참가자들의 이름을 띄어쓰기로 구분하여 입력하세요:");
    if (!namesString || namesString.trim() === '') return;

    const names = namesString.trim().split(/\s+/).filter(name => name);
    if (names.length === 0) return;
    
    try {
        const idResponse = await fetch('/get_player_ids', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ names: names })
        });
        const idData = await idResponse.json();
    
        if (!idData.success) {
            throw new Error(idData.error || "선수 ID를 가져오지 못했습니다.");
        }
    
        const removeResponse = await fetch('/remove_participants', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bettingId: bettingId, playerIds: idData.player_ids })
        });
        const removeData = await removeResponse.json();
    
        alert(removeData.message || removeData.error);
        if (removeData.success) {
            location.reload();
        }
    } catch(error) {
        alert("오류 발생: " + error.message);
    }
}

// ===================================
// 비밀번호 입력 모달 (공용 헬퍼 함수)
// ===================================
function requestPasswordModal(promptMessage = "비밀번호를 입력하세요.") {
    return new Promise((resolve) => {
        const existingModal = document.getElementById('password-modal');
        if (existingModal) existingModal.remove();

        const modal = document.createElement('div');
        modal.id = 'password-modal';
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-[2000]';
        
        modal.innerHTML = `
            <div class="bg-white p-6 rounded-lg shadow-xl text-center w-11/12 max-w-xs">
                <p class="mb-4 font-bold">${promptMessage}</p>
                <input type="password" id="passwordInput" class="w-full mb-4">
                <div class="flex justify-end gap-2">
                    <button id="cancelButton" class="bg-gray-200 button text-sm">취소</button>
                    <button id="confirmButton" class="bg-main button text-sm">확인</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const passwordInput = document.getElementById('passwordInput');
        passwordInput.focus();

        const closeModal = (value) => {
            document.body.removeChild(modal);
            resolve(value);
        };

        document.getElementById('confirmButton').onclick = () => closeModal(passwordInput.value);
        document.getElementById('cancelButton').onclick = () => closeModal(null);
        modal.onclick = (e) => { if (e.target === modal) closeModal(null); };
        passwordInput.onkeydown = (e) => { if (e.key === 'Enter') closeModal(passwordInput.value); };
    });
}