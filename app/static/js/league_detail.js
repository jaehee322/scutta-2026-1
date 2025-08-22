document.addEventListener('input', function (event) {
    if (event.target.matches('.league-input')) {
        const input = event.target;
        const value = input.value;

        if (!/^\d*$/.test(value)) {
            input.value = value.replace(/\D/g, '');
        }

        const numericValue = parseInt(input.value, 10);
        if (numericValue > 3) {
            input.value = '';
        } else if (numericValue < 0) {
            input.value = '';
        }
    }
});

function saveLeague(leagueId) {
    const inputs = document.querySelectorAll('.league-input');
    const scores = {};

    inputs.forEach(input => {
        const row = parseInt(input.getAttribute('data-row'), 10);
        const col = parseInt(input.getAttribute('data-col'), 10);
        const key = `p${row + 1}p${col + 1}`;
        const value = input.value.trim();

        scores[key] = value === '' ? null : parseInt(value, 10);
    });

    for (let i = 0; i < 4; i++) {
        for (let j = 0; j < 4 - i; j++) {
            const key1 = `p${i + 1}p${i + j + 2}`;
            const key2 = `p${i + j + 2}p${i + 1}`;

            const value1 = scores[key1];
            const value2 = scores[key2];

            if (value1 !== null && value2 !== null && value1 + value2 !== 3) {
                alert(
                    `세트 스코어는 3:0 또는 2:1 이어야 합니다.\n` +
                    `선수 ${i + 1} vs 선수 ${i + j + 2} 의 경기 결과를 수정해 주세요.`
                );
                return;
            }

            if (value1 === null && value2 !== null) {
                scores[key1] = 3 - value2;
            } else if (value1 !== null && value2 === null) {
                scores[key2] = 3 - value1;
            }
        }
    }

    fetch(`/save_league/${leagueId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scores }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                location.reload();
            } else {
                alert(data.error || '저장에 실패했습니다.');
            }
        })
        .catch(error => console.error('Error saving league:', error));
}

function requestPassword() {
    return new Promise((resolve) => {
        const modal = document.createElement('div');
        modal.style.position = 'fixed';
        modal.style.top = '0';
        modal.style.left = '0';
        modal.style.width = '100vw';
        modal.style.height = '100vh';
        modal.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        modal.style.display = 'flex';
        modal.style.justifyContent = 'center';
        modal.style.alignItems = 'center';
        modal.style.zIndex = '1000';

        const form = document.createElement('div');
        form.style.backgroundColor = 'white';
        form.style.padding = '20px';
        form.style.borderRadius = '10px';
        form.style.textAlign = 'center';
        form.innerHTML = `
            <p>리그전을 제출하려면 비밀번호를 입력하세요.</p><br>
            <input type="password" id="passwordInput" style="padding: 5px; width: 80%; border: 1px solid #ccc; border-radius: 5px;"><br><br>
            <button id="cancelButton" style="padding: 5px 10px; border-radius: 5px;">취소</button>
            <button id="confirmButton" style="margin-left: 20px; padding: 5px 10px; border-radius: 5px; background-color: #374151; color: white;">확인</button>
        `;

        modal.appendChild(form);
        document.body.appendChild(modal);

        document.getElementById('confirmButton').addEventListener('click', () => {
            const password = document.getElementById('passwordInput').value;
            document.body.removeChild(modal);
            resolve(password);
        });

        document.getElementById('cancelButton').addEventListener('click', () => {
            document.body.removeChild(modal);
            resolve(null);
        });
    });
}

async function submitLeague(leagueId) {
    const password = await requestPassword();
    if (!password) {
        return; // 사용자가 취소했거나 비밀번호를 입력하지 않음
    }

    if (password !== 'yeong6701') {
        alert('비밀번호가 올바르지 않습니다.');
        return;
    }

    const inputs = document.querySelectorAll('.league-input');
    const scores = {};
    let playerNames = [];

    document.querySelectorAll('.player-name a').forEach(element => {
        playerNames.push(element.textContent.trim());
    });

    inputs.forEach(input => {
        const row = parseInt(input.getAttribute('data-row'), 10);
        const col = parseInt(input.getAttribute('data-col'), 10);
        const key = `p${row + 1}p${col + 1}`;
        const value = input.value.trim();
        scores[key] = value === '' ? null : parseInt(value, 10);
    });

    const matches = [];
    for (let i = 0; i < 4; i++) {
        for (let j = 0; j < 4 - i; j++) {
            const key1 = `p${i + 1}p${i + j + 2}`;
            const key2 = `p${i + j + 2}p${i + 1}`;
            let value1 = scores[key1];
            let value2 = scores[key2];

            if (value1 === null && value2 !== null) {
                value1 = 3 - value2;
            } else if (value1 !== null && value2 === null) {
                value2 = 3 - value1;
            } else if (value1 === null && value2 === null) {
                continue
            }

            const winner = value1 > value2 ? playerNames[i] : playerNames[j + i + 1];
            const loser = value1 > value2 ? playerNames[j + i + 1] : playerNames[i];
            const setScore = value1 > value2 ? `${value1}:${value2}` : `${value2}:${value1}`;
            matches.push({ winner: winner, loser: loser, score: setScore, league: true });
        }
    }

    if (matches.length === 0) {
        alert("제출할 경기 결과가 없습니다. 리그전을 삭제합니다.");
        deleteLeague(leagueId);
        return;
    }
    fetch('/submit_matches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(matches),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // ▼▼▼ 경기 제출 성공 후, 리그를 삭제하지 않고 메시지만 띄웁니다. ▼▼▼
            alert(data.message + '\n경기 결과가 제출되었습니다. 이제 이 리그는 수동으로 삭제할 수 있습니다.');
            location.reload(); // 페이지 새로고침
        } else {
            alert('제출 실패: ' + (data.error || '알 수 없는 오류'));
        }
    })
    .catch(error => console.error('Error submitting league:', error));
}


// 2. deleteLeague 함수 수정 (비밀번호 확인 로직 추가)
async function deleteLeague(leagueId) {
    const password = await requestPassword(); // 비밀번호를 먼저 묻습니다.
    if (password === null) return; // 사용자가 취소한 경우

    if (password !== 'yeong6701') { // 비밀번호가 틀리면 여기서 중단
        alert('비밀번호가 올바르지 않습니다.');
        return;
    }

    // 비밀번호가 맞으면 삭제를 진행합니다.
    if (!confirm('정말로 이 리그를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.')) {
        return;
    }

    fetch(`/delete_league/${leagueId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            window.location.href = '/league.html'; // 삭제 후 리그 목록으로 이동
        } else {
            alert('오류: ' + data.error);
        }
    });
}