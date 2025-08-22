// static/js/betting_approval.js

let currentOffset = 0;
const limit = 30;
let currentTab = 'all';

document.addEventListener('DOMContentLoaded', function() {
    loadBettings();
});

function selectTab(tabElement, tabName) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    tabElement.classList.add('active');
    currentTab = tabName;
    currentOffset = 0;
    loadBettings(false);
}

function loadBettings(append = false) {
    fetch(`/get_bettings?offset=${currentOffset}&limit=${limit}&tab=${currentTab}`)
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById('betting-table-body');
            if (!append) {
                tableBody.innerHTML = '';
            }
            data.forEach(betting => {
                const row = document.createElement('tr');
                const approvedText = betting.approved ? '✔️' : '❌';
                row.innerHTML = `
                    <td><input type="checkbox" class="betting-checkbox" value="${betting.id}"></td>
                    <td>${approvedText}</td>
                    <td>${betting.match.winner_name}</td>
                    <td>${betting.match.score}</td>
                    <td>${betting.match.loser_name}</td>
                    <td>${betting.win_participants.join(', ') || '없음'}</td>
                    <td>${betting.lose_participants.join(', ') || '없음'}</td>
                    <td>${betting.point}</td>
                `;
                tableBody.appendChild(row);
            });
            currentOffset += data.length;
        });
}

document.getElementById('load-more').addEventListener('click', () => loadBettings(true));

function approveBettings() {
    const selectedIds = Array.from(document.querySelectorAll('.betting-checkbox:checked')).map(cb => cb.value);
    if (selectedIds.length === 0) {
        alert('승인할 베팅을 선택하세요.');
        return;
    }
    fetch('/approve_bettings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedIds })
    }).then(() => location.reload());
}

function deleteBettings() {
    const selectedIds = Array.from(document.querySelectorAll('.betting-checkbox:checked')).map(cb => cb.value);
    if (selectedIds.length === 0) {
        alert('삭제할 베팅을 선택하세요.');
        return;
    }
    fetch('/delete_bettings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedIds })
    }).then(() => location.reload());
}

function approveAllBettings() {
    fetch('/select_all_bettings')
        .then(response => response.json())
        .then(data => {
            if (data.ids.length === 0) {
                alert('승인 대기 중인 베팅이 없습니다.');
                return;
            }
            fetch('/approve_bettings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: data.ids })
            }).then(() => location.reload());
        });
}

function toggleSelectAll(source) {
    document.querySelectorAll('.betting-checkbox').forEach(checkbox => {
        checkbox.checked = source.checked;
    });
}