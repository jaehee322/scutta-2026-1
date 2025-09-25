// static/js/index.js 파일 전체를 아래 코드로 교체해주세요.

window.selectCategory = selectCategory;

let offset = 0;
const limit = 30;
let isLoading = false;
let currentCategory = 'win_count';
let searchTimer;

const tableHeader = document.getElementById('table-header');
const tableBody = document.getElementById('table-body');
const loadMoreBtn = document.getElementById('load-more-btn');
const searchInput = document.getElementById('player-search-input');

const columnConfig = {
    win_count: { name: translatedHeaders.win_count, suffix: '' },
    loss_count: { name: translatedHeaders.loss_count, suffix: '' },
    rate_count: { name: translatedHeaders.rate_count, suffix: '%' },
    match_count: { name: translatedHeaders.match_count, suffix: '' },
    opponent_count: { name: translatedHeaders.opponent_count, suffix: '' },
    achieve_count: { name: translatedHeaders.achieve_count, suffix: '' },
    betting_count: { name: translatedHeaders.betting_count, suffix: '' },
};
let dynamicColumns = Object.keys(columnConfig);

function renderHeader() {
    if (!tableHeader) return;
    tableHeader.innerHTML = '';
    const tr = document.createElement('tr');
    
    // ▼▼▼ '순위'와 '이름'을 translatedHeaders 변수로 교체 ▼▼▼
    let headerHTML = `
        <th class="whitespace-nowrap px-4 py-2 text-left">${translatedHeaders.rank}</th>
        <th class="whitespace-nowrap px-4 py-2 text-left">${translatedHeaders.name}</th>
    `;
    // ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

    dynamicColumns.forEach(key => {
        const isCurrent = key === currentCategory;
        headerHTML += `
            <th class="whitespace-nowrap px-4 py-2 text-center cursor-pointer" onclick="selectCategory('${key}')">
                <span class="py-1 px-2 rounded-md ${isCurrent ? 'bg-gray-200 text-gray-900 font-bold' : 'text-gray-600 hover:bg-gray-100'}">
                    ${columnConfig[key].name}
                </span>
            </th>
        `;
    });
    tr.innerHTML = headerHTML;
    tableHeader.appendChild(tr);
}

function createPlayerRow(player, isMyRank = false) {
    const tr = document.createElement('tr');
    if (isMyRank) tr.classList.add('bg-sky-50', 'font-semibold');
    let rowHTML = `
        <td class="px-4 py-2 whitespace-nowrap text-center">${player.current_rank}</td>
        <td class="px-4 py-2 whitespace-nowrap">
            <a href="/player/${player.id}" class="hover:underline">${player.name} (${player.rank})</a>
        </td>
    `;
    dynamicColumns.forEach(key => {
        const value = player.stats[key] + (columnConfig[key].suffix || '');
        const isCurrent = key === currentCategory;
        rowHTML += `<td class="text-center whitespace-nowrap ${isCurrent ? 'font-bold' : ''}">${value}</td>`;
    });
    tr.innerHTML = rowHTML;
    return tr;
}

async function loadRankings(isNew = false) {
    if (isLoading) return;
    isLoading = true;
    if(loadMoreBtn) loadMoreBtn.textContent = '불러오는 중...';
    if (isNew) {
        offset = 0;
        if (tableBody) tableBody.innerHTML = '';
    }

    const query = searchInput && searchInput.value.trim();
    const categoryForURL = currentCategory.replace('_count', '_order');

    try {
        const [myRankRes, rankingsRes] = await Promise.all([
            isNew && currentUserId ? fetch(`/get_my_rank?category=${categoryForURL}`) : Promise.resolve(null),
            query && query.length >= 2
                ? fetch(`/search_players?query=${encodeURIComponent(query)}&category=${categoryForURL}`)
                : fetch(`/rankings?category=${categoryForURL}&offset=${offset}&limit=${limit}`)
        ]);

        if (myRankRes && myRankRes.ok) {
            const myRankPlayer = await myRankRes.json();
            if (myRankPlayer && tableBody) tableBody.prepend(createPlayerRow(myRankPlayer, true));
        }

        if (rankingsRes && rankingsRes.ok) {
            const players = await rankingsRes.json();
            if (players.length === 0 && isNew && tableBody && tableBody.children.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="9" class="text-center py-4">표시할 데이터가 없습니다.</td></tr>`;
            } else if (tableBody) {
                players.forEach(player => {
                    if (player.id !== currentUserId) tableBody.appendChild(createPlayerRow(player, false));
                });
            }
            offset += players.length;
            if(loadMoreBtn) {
                const isSearchMode = query && query.length >= 2;
                loadMoreBtn.style.display = (players.length < limit || isSearchMode) ? 'none' : 'block';
            }
        }
    } catch (error) {
        console.error("Error loading rankings:", error);
    } finally {
        isLoading = false;
        if(loadMoreBtn) loadMoreBtn.textContent = '더보기';
    }
}

function selectCategory(categoryKey) {
    currentCategory = categoryKey;
    dynamicColumns = [categoryKey, ...Object.keys(columnConfig).filter(k => k !== categoryKey)];
    renderHeader();
    loadRankings(true);
}

document.addEventListener('DOMContentLoaded', () => {
    if(loadMoreBtn) loadMoreBtn.addEventListener('click', () => loadRankings(false));
    if(searchInput) searchInput.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => loadRankings(true), 300);
    });
    selectCategory('win_count');
});