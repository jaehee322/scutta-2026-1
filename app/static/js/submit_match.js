// static/js/submit_match.js

let matchCounter = 1;

function toggleScore(button, matchId) {
    const buttons = document.querySelectorAll(`#${matchId} .score-input`);
    buttons.forEach(btn => btn.classList.remove('selected'));
    button.classList.add('selected');
}

function addMatch() {
    matchCounter++;
    const matchList = document.getElementById('match-list');
    const newMatch = document.createElement('div');
    newMatch.id = `match-${matchCounter}`;
    newMatch.className = 'match-row flex items-center justify-between mb-2';
    newMatch.innerHTML = `
        <input type="text" placeholder="승리" class="winner-input border rounded w-1/3 p-1 text-center mr-2">
        <div class="flex gap-2">
            <button class="score-input px-4 py-1 border rounded" onclick="toggleScore(this, 'match-${matchCounter}')">3:0</button>
            <button class="score-input px-4 py-1 border rounded" onclick="toggleScore(this, 'match-${matchCounter}')">2:1</button>
        </div>
        <input type="text" placeholder="패배" class="loser-input border rounded w-1/3 p-1 text-center ml-2">
    `;
    matchList.appendChild(newMatch);
}

function submitMatches() {
    const matches = [];
    const rows = document.querySelectorAll('.match-row');

    rows.forEach(row => {
        const winner = row.querySelector('.winner-input')?.value.trim() || '';
        const loser = row.querySelector('.loser-input')?.value.trim() || '';
        const score = row.querySelector('.score-input.selected')?.textContent || '';

        if (winner && loser && score) {
            matches.push({ winner, loser, score, league: false });
        }
    });

    if (matches.length === 0) {
        alert("모두 입력해 주세요.");
        return;
    }

    fetch('/check_players', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ matches })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`서버 응답 오류: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.unknownPlayers.length > 0) {
            alert(`${data.unknownPlayers.join(', ')}이(가) 없습니다.`);
        }

        const validMatches = matches.filter(match =>
            !data.unknownPlayers.includes(match.winner) &&
            !data.unknownPlayers.includes(match.loser)
        );

        if (validMatches.length > 0) {
            return fetch('/submit_matches', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(validMatches)
            });
        } else {
            return Promise.reject('유효한 경기가 없습니다.');
        }
    })
    .then(response => {
        if (!response) return;
        if (!response.ok) {
            throw new Error(`서버 응답 오류: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (!data) return;
        if (data.success) {
            alert(data.message);
            location.reload();
        } else {
            alert(data.error);
        }
    })
    .catch(error => {
        console.error("오류 발생!", error);
        alert('오류가 발생했습니다. 개발자 도구 콘솔을 확인해주세요.');
    });
}