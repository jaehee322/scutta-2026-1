// static/js/settings.js 파일의 기존 내용을 모두 지우고 아래 코드로 교체해주세요.

document.addEventListener('DOMContentLoaded', () => {
    // --- 새 회원 일괄 등록 관련 로직 ---
    const registrationQueue = [];
    const addToQueueBtn = document.getElementById('add-to-queue-btn');
    const queueBody = document.getElementById('registration-queue-body');
    const batchRegisterBtn = document.getElementById('batch-register-btn');

    function renderQueue() {
        queueBody.innerHTML = '';
        registrationQueue.forEach((user, index) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${user.name}</td>
                <td>${user.gender === 'M' ? '남자' : '여자'}</td>
                <td>${user.freshman === 'Y' ? '신입' : '기존'}</td>
                <td>${user.is_admin ? '✔️' : '❌'}</td>
                <td><button class="text-red-500 font-bold" onclick="removeFromQueue(${index})">X</button></td>
            `;
            queueBody.appendChild(tr);
        });
    }

    window.removeFromQueue = (index) => {
        registrationQueue.splice(index, 1);
        renderQueue();
    };

    addToQueueBtn.addEventListener('click', () => {
        const name = document.getElementById('name').value.trim();
        const password = document.getElementById('password').value.trim();
        const gender = document.getElementById('gender').value;
        const freshman = document.getElementById('freshman').value;
        const isAdmin = document.getElementById('is_admin').checked;

        if (!name || !password || !gender || !freshman) {
            alert('모든 필드를 입력해주세요.');
            return;
        }

        registrationQueue.push({ name, password, gender, freshman, is_admin: isAdmin });
        renderQueue();

        // 입력 필드 초기화
        document.getElementById('name').value = '';
        document.getElementById('password').value = '';
        document.getElementById('gender').value = '';
        document.getElementById('freshman').value = '';
        document.getElementById('is_admin').checked = false;
    });

    batchRegisterBtn.addEventListener('click', () => {
        if (registrationQueue.length === 0) {
            alert('등록할 사용자가 대기열에 없습니다.');
            return;
        }
        
        fetch('/admin/batch_add_users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ users: registrationQueue })
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            if (data.success) {
                window.location.reload();
            }
        });
    });

    // --- 선수 삭제 관련 로직 ---
    const deletePlayersBtn = document.getElementById('delete-players-btn');
    const selectAllCheckbox = document.getElementById('select-all-players');
    const playerCheckboxes = document.querySelectorAll('.player-checkbox');

    selectAllCheckbox.addEventListener('change', (e) => {
        playerCheckboxes.forEach(checkbox => {
            checkbox.checked = e.target.checked;
        });
    });

    deletePlayersBtn.addEventListener('click', () => {
        const selectedIds = Array.from(playerCheckboxes)
            .filter(checkbox => checkbox.checked)
            .map(checkbox => checkbox.value);

        if (selectedIds.length === 0) {
            alert('삭제할 선수를 선택해주세요.');
            return;
        }

        if (confirm(`선택된 ${selectedIds.length}명의 선수를 정말로 삭제하시겠습니까?\n이 작업은 되돌릴 수 없으며, 관련된 모든 경기, 베팅, 로그 기록이 영구적으로 삭제됩니다.`)) {
            fetch('/admin/delete_players', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ player_ids: selectedIds })
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                if (data.success && data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else if (data.success) {
                    window.location.reload();
                }
            });
        }
    });

    // --- 오늘의 상대 관련 로직 ---
    const resetPartnerBtn = document.getElementById('reset-partner-button');
    const registerPartnerBtn1 = document.getElementById('register-partner-button-1');
    const registerPartnerBtn2 = document.getElementById('register-partner-button-2');
    const partnerTable = document.getElementById('setting-partner-table');
    const partnerBody = document.getElementById('setting-partner-body');
    let generatedPairs = [];

    resetPartnerBtn.addEventListener('click', () => {
        if (confirm('오늘의 상대 목록을 정말로 초기화하시겠습니까?')) {
            fetch('/reset_partner', { method: 'POST' })
            .then(response => {
                if (response.ok) {
                    alert('초기화되었습니다.');
                    location.reload();
                } else {
                    alert('초기화에 실패했습니다.');
                }
            });
        }
    });

    // ▼▼▼ 이 부분이 빠져있었습니다! ▼▼▼
    registerPartnerBtn1.addEventListener('click', () => {
        const oldPlayers = document.getElementById('old-player-input').value.trim().split(/\s+/);
        const newPlayers = document.getElementById('new-player-input').value.trim().split(/\s+/);

        if (oldPlayers.length === 0 || newPlayers.length === 0 || oldPlayers[0] === '' || newPlayers[0] === '') {
            alert('기존 부원과 신입 부원 이름을 모두 입력해주세요.');
            return;
        }

        fetch('/register_partner', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_players: oldPlayers, new_players: newPlayers })
        })
        .then(response => response.json())
        .then(data => {
            if(data.error) {
                alert('오류: ' + data.error);
                return;
            }
            generatedPairs = data;
            partnerBody.innerHTML = '';
            data.forEach(pair => {
                const row = `<tr><td>${pair.p1_name}</td><td>${pair.p2_name}</td></tr>`;
                partnerBody.innerHTML += row;
            });
            partnerTable.classList.remove('hidden');
            registerPartnerBtn2.classList.remove('hidden');
        });
    });

    registerPartnerBtn2.addEventListener('click', () => {
        if (generatedPairs.length === 0) {
            alert('먼저 매칭을 진행해주세요.');
            return;
        }

        fetch('/submit_partner', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pairs: generatedPairs })
        })
        .then(response => {
             if (response.ok) {
                alert('오늘의 상대가 확정되었습니다.');
                window.location.href = '/partner.html';
            } else {
                response.json().then(data => alert('확정 실패: ' + data.error));
            }
        });
    });
});