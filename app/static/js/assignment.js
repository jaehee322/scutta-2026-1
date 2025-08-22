document.addEventListener('DOMContentLoaded', function() {
    loadPlayers();

    document.getElementById('player-search-btn').addEventListener('click', () => {
        const query = document.getElementById('player-search-input').value;
        loadPlayers(query);
    });

    document.getElementById('show-all-players-btn').addEventListener('click', () => {
        document.getElementById('player-search-input').value = '';
        loadPlayers('', true);
    });

    // 저장 버튼에 이벤트 리스너 추가
    document.getElementById('save-all-btn').addEventListener('click', saveAllChanges);
});

function loadPlayers(searchQuery = '', showAll = false) {
    let url = `/get_assignment_players?search=${encodeURIComponent(searchQuery)}&show_all=${showAll}`;
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById('assignment-player-list-body');
            tableBody.innerHTML = '';
            data.forEach(player => {
                const row = document.createElement('tr');
                // 각 행에 player-id를 저장해 둡니다.
                row.dataset.playerId = player.id;
                // 각 input에 원래 값을 data-original-value로 저장해 둡니다.
                row.innerHTML = `
                    <td><a href="/player/${player.id}" class="hover:underline">${player.name}</a></td>
                    <td class="w-24"><input type="number" data-original-value="${player.achieve_count || 0}" value="${player.achieve_count || 0}" class="w-full text-center border rounded py-1 achieve-input"></td>
                    <td class="w-24"><input type="number" data-original-value="${player.betting_count || 0}" value="${player.betting_count || 0}" class="w-full text-center border rounded py-1 betting-input"></td>
                    <td class="w-24"><input type="number" data-original-value="${player.rank || ''}" value="${player.rank || ''}" class="w-full text-center border rounded py-1 rank-input"></td>
                `;
                tableBody.appendChild(row);
            });
        });
}

// 새로운 일괄 저장 함수
function saveAllChanges() {
    const changes = [];
    const rows = document.querySelectorAll('#assignment-player-list-body tr');

    rows.forEach(row => {
        const playerId = row.dataset.playerId;
        const playerChange = { id: playerId };
        let hasChanged = false;

        const rankInput = row.querySelector('.rank-input');
        const achieveInput = row.querySelector('.achieve-input');
        const bettingInput = row.querySelector('.betting-input');

        // 원래 값과 현재 값을 비교해서 변경된 경우에만 추가
        if (rankInput.value !== rankInput.dataset.originalValue) {
            playerChange.rank = rankInput.value;
            hasChanged = true;
        }
        if (achieveInput.value !== achieveInput.dataset.originalValue) {
            playerChange.achieve_count = achieveInput.value;
            hasChanged = true;
        }
        if (bettingInput.value !== bettingInput.dataset.originalValue) {
            playerChange.betting_count = bettingInput.value;
            hasChanged = true;
        }

        if (hasChanged) {
            changes.push(playerChange);
        }
    });

    if (changes.length === 0) {
        alert('변경사항이 없습니다.');
        return;
    }

    if (!confirm(`${changes.length}명의 선수 정보에 변경사항이 있습니다. 저장하시겠습니까?`)) {
        return;
    }

    fetch('/save_all_assignment_changes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(changes)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            // 저장 후 목록을 새로고침하여 원래 값을 갱신합니다.
            loadPlayers(document.getElementById('player-search-input').value);
        } else {
            alert('오류: ' + data.error);
        }
    });
}