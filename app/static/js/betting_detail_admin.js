// static/js/betting_detail_admin.js (새 파일 또는 전체 교체)

function submitBettingResult(bettingId, p1Name, p2Name) {
    const winnerSelect = document.getElementById('winner-select');
    const scoreSelect = document.getElementById('score-select');

    const winnerName = winnerSelect.value;
    const score = scoreSelect.value;

    if (!winnerName) {
        alert('승자를 선택해주세요.');
        return;
    }

    if (!confirm(`${winnerName}의 승리(${score})로 결과를 제출하시겠습니까?`)) {
        return;
    }

    fetch('/submit_betting_result', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            bettingId: bettingId,
            winnerName: winnerName,
            score: score
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const results = data.results;
                const winParticipantsText = results.winParticipants.length > 0 ? results.winParticipants.join(', ') : '없음';
                const loseParticipantsText = results.loseParticipants.length > 0 ? results.loseParticipants.join(', ') : '없음';

                const alertMessage = `
            베팅 결과가 제출되었습니다!
            ----------------------------------------
            - 승리: ${results.winnerName}
            - 패배: ${results.loserName}
            ----------------------------------------
            - 베팅 성공 (${results.winParticipants.length}명):
            ${winParticipantsText}
            - 베팅 실패 (${results.loseParticipants.length}명):
            ${loseParticipantsText}
            ----------------------------------------
            - 예상 분배 포인트: ${results.distributedPoints} pt
            `;
                alert(alertMessage);
                window.location.href = '/betting'
            } else {
                alert('오류: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('결과 제출 중 오류가 발생했습니다.');
        });
}

function addParticipantsModal(bettingId) {
    const namesString = prompt("추가할 참가자의 이름을 쉼표(,)로 구분하여 모두 입력하세요:", "");
    if (namesString) {
        const names = namesString.split(',').map(name => name.trim()).filter(name => name);
        if (names.length > 0) {
            const playerIds = names.map(name => {
                const player = ALL_PLAYERS.find(p => p.name === name);
                return player ? player.id : null;
            }).filter(id => id !== null);

            if (playerIds.length !== names.length) {
                alert("일부 선수를 찾을 수 없습니다. 이름을 다시 확인해주세요.");
                return;
            }

            sendParticipantUpdate(bettingId, playerIds, '/add_participants');
        }
    }
}

function removeParticipantsModal(bettingId) {
    const namesString = prompt("삭제할 참가자의 이름을 쉼표(,)로 구분하여 모두 입력하세요:", "");
    if (namesString) {
        const names = namesString.split(',').map(name => name.trim()).filter(name => name);
        if (names.length > 0) {
            const playerIds = names.map(name => {
                const player = ALL_PLAYERS.find(p => p.name === name);
                return player ? player.id : null;
            }).filter(id => id !== null);

            if (playerIds.length !== names.length) {
                alert("일부 선수를 찾을 수 없습니다. 이름을 다시 확인해주세요.");
                return;
            }

            sendParticipantUpdate(bettingId, playerIds, '/remove_participants');
        }
    }
}

function sendParticipantUpdate(bettingId, playerIds, url) {
    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bettingId: bettingId, playerIds: playerIds })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                window.location.reload();
            } else {
                alert('오류: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('처리 중 오류가 발생했습니다.');
        });
}