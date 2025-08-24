// static/js/submit_match.js 파일의 전체 내용입니다.

let matchCounter = 0;

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('match-list')) {
        addMatchRow();
    }
});

function addMatchRow() {
    matchCounter++;
    const matchList = document.getElementById('match-list');
    
    const newRow = document.createElement('div');
    newRow.id = `match-${matchCounter}`;
    newRow.className = 'match-row grid grid-cols-11 gap-2 items-center';
    
    newRow.innerHTML = `
        <input type="text" placeholder="승리자" class="winner-input col-span-4">
        <div class="col-span-3 flex justify-center gap-1">
            <button type="button" class="score-btn w-1/2" data-score="3:0" onclick="selectScore(this)">3:0</button>
            <button type="button" class="score-btn w-1/2" data-score="2:1" onclick="selectScore(this)">2:1</button>
            <input type="hidden" class="score-input">
        </div>
        <input type="text" placeholder="패배자" class="loser-input col-span-4">
    `;
    
    matchList.appendChild(newRow);
}

function selectScore(button) {
    const parentRow = button.closest('.match-row');
    parentRow.querySelectorAll('.score-btn').forEach(btn => btn.classList.remove('selected'));
    button.classList.add('selected');
    parentRow.querySelector('.score-input').value = button.dataset.score;
}

async function submitMatches() {
    // 이 함수는 이전의 '타이핑' + '선수 유효성 검사' 버전과 동일합니다.
    // ... (이전의 올바른 submitMatches 함수 코드를 여기에 그대로 사용합니다)
}
async function submitMatches() {
    const matches = [];
    const matchRows = document.querySelectorAll('.match-row');
    let validationError = false;

    matchRows.forEach(row => {
        const winner = row.querySelector('.winner-input').value;
        const loser = row.querySelector('.loser-input').value;
        const score = row.querySelector('.score-input').value;

        if (winner && loser && score) {
            if (winner === loser) {
                alert('승리자와 패배자는 다른 사람이어야 합니다.');
                validationError = true;
                return;
            }
            matches.push({ winner, loser, score, league: false });
        } else if (winner || loser || score) {
            alert('한 경기의 승리자, 패배자, 스코어는 모두 입력하거나 모두 비워주세요.');
            validationError = true;
        }
    });

    if (validationError) return;
    if (matches.length === 0) {
        alert('제출할 경기 결과가 없습니다.');
        return;
    }
    
    if (!confirm(`${matches.length}개의 경기 결과를 제출하시겠습니까?`)) {
        return;
    }

    try {
        // 일괄 제출은 선수 이름이 유효하다고 가정하고 바로 제출합니다.
        const submitResponse = await fetch('/submit_matches', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(matches)
        });
        const submitData = await submitResponse.json();
        
        if (submitData.success) {
            alert(submitData.message);
            window.location.reload();
        } else {
            alert('오류: ' + (submitData.error || submitData.message));
        }

    } catch (error) {
        console.error("Submit error:", error);
        alert('제출 중 오류가 발생했습니다. 콘솔을 확인해주세요.');
    }
}