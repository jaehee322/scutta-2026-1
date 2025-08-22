// static/js/approval.js

let currentOffset = 0;
const limit = 30;
let currentTab = 'all';
let startDate = null;
let endDate = null;

document.addEventListener('DOMContentLoaded', function() {
    loadMatches();

    const calendar = flatpickr("#calendar", {
        mode: "range",
        dateFormat: "Y-m-d",
        onChange: function(selectedDates) {
            if (selectedDates.length === 2) {
                startDate = selectedDates[0];
                endDate = selectedDates[1];
            }
        }
    });

    document.getElementById('open-calendar').addEventListener('click', () => {
        document.getElementById('calendar-modal').classList.remove('hidden');
    });
    document.getElementById('close-calendar').addEventListener('click', () => {
        document.getElementById('calendar-modal').classList.add('hidden');
    });
    document.getElementById('search-dates').addEventListener('click', () => {
        currentOffset = 0;
        loadMatches(false);
        document.getElementById('calendar-modal').classList.add('hidden');
    });
    document.getElementById('clear-dates').addEventListener('click', () => {
        startDate = null;
        endDate = null;
        calendar.clear();
        currentOffset = 0;
        loadMatches(false);
    });
});

function selectTab(tabElement, tabName) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    tabElement.classList.add('active');
    currentTab = tabName;
    currentOffset = 0;
    loadMatches(false);
}

function loadMatches(append = false) {
    let url = `/get_matches?offset=${currentOffset}&limit=${limit}&tab=${currentTab}`;
    if (startDate && endDate) {
        url += `&start_date=${startDate.toISOString().split('T')[0]}&end_date=${endDate.toISOString().split('T')[0]}`;
    }

    fetch(url)
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById('match-table-body');
            if (!append) {
                tableBody.innerHTML = '';
            }
            data.forEach(match => {
                const row = document.createElement('tr');
                const approvedText = match.approved ? '✔️' : '❌';
                row.innerHTML = `
                    <td><input type="checkbox" class="match-checkbox" value="${match.id}"></td>
                    <td>${approvedText}</td>
                    <td>${match.winner_name}</td>
                    <td>${match.score}</td>
                    <td>${match.loser_name}</td>
                    <td>${formatTimestamp(match.timestamp)}</td>
                `;
                tableBody.appendChild(row);
            });
            currentOffset += data.length;
        });
}

document.getElementById('load-more').addEventListener('click', () => loadMatches(true));

function approveMatches() {
    const selectedIds = Array.from(document.querySelectorAll('.match-checkbox:checked')).map(cb => cb.value);
    if (selectedIds.length === 0) {
        alert('승인할 경기를 선택하세요.');
        return;
    }
    fetch('/approve_matches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedIds })
    }).then(() => location.reload());
}

function deleteMatches() {
    const selectedIds = Array.from(document.querySelectorAll('.match-checkbox:checked')).map(cb => cb.value);
    if (selectedIds.length === 0) {
        alert('삭제할 경기를 선택하세요.');
        return;
    }
    fetch('/delete_matches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedIds })
    }).then(() => location.reload());
}

function approveAllMatches() {
    fetch('/select_all_matches')
        .then(response => response.json())
        .then(data => {
            if (data.ids.length === 0) {
                alert('승인 대기 중인 경기가 없습니다.');
                return;
            }
            fetch('/approve_matches', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: data.ids })
            }).then(() => location.reload());
        });
}

function toggleSelectAll(source) {
    document.querySelectorAll('.match-checkbox').forEach(checkbox => {
        checkbox.checked = source.checked;
    });
}

function formatTimestamp(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const year = date.getFullYear().toString().slice(-2);
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}