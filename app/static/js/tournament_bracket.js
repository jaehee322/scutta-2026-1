/**
 * tournament_bracket.js
 * Renders precise SVG connecting lines between tournament bracket match nodes.
 */

document.addEventListener('DOMContentLoaded', () => {
    drawBracketLines();
    window.addEventListener('resize', drawBracketLines);
});

function drawBracketLines() {
    // 1. Setup SVG Canvas
    const container = document.querySelector('.tournament-container');
    if (!container) return;

    // Remove existing SVG if it exists
    let svg = document.getElementById('bracket-lines-svg');
    if (svg) svg.remove();

    // Create new SVG overlay
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.id = 'bracket-lines-svg';
    svg.style.position = 'absolute';
    svg.style.top = 0;
    svg.style.left = 0;
    svg.style.width = '100%';
    svg.style.height = '100%';
    svg.style.pointerEvents = 'none'; // Click through
    svg.style.zIndex = 0;

    // Make sure container is relative to absolute position SVG
    container.style.position = 'relative';
    container.appendChild(svg);

    // Ensure elements sit on top
    const rounds = document.querySelectorAll('.bracket-round');
    rounds.forEach(r => r.style.zIndex = 1);

    // 2. Calculate Lines
    for (let i = 0; i < rounds.length - 1; i++) {
        const currentRound = rounds[i];
        const nextRound = rounds[i + 1];

        const currentMatches = currentRound.querySelectorAll('.bracket-match');
        const nextMatches = nextRound.querySelectorAll('.bracket-match');

        // Draw line from each pair of matches in current round to their target in next round
        for (let j = 0; j < currentMatches.length; j += 2) {
            const topMatch = currentMatches[j];
            const bottomMatch = currentMatches[j + 1];
            const targetMatch = nextMatches[Math.floor(j / 2)];

            if (!topMatch || !bottomMatch || !targetMatch) continue;

            // Get absolute coordinates relative to the container
            const containerRect = container.getBoundingClientRect();

            const topRect = topMatch.getBoundingClientRect();
            const bottomRect = bottomMatch.getBoundingClientRect();
            const targetRect = targetMatch.getBoundingClientRect();

            // Calculate start and end points
            const startX = topRect.right - containerRect.left;
            const topY = topRect.top + (topRect.height / 2) - containerRect.top;
            const bottomY = bottomRect.top + (bottomRect.height / 2) - containerRect.top;

            const endX = targetRect.left - containerRect.left;
            const targetY = targetRect.top + (targetRect.height / 2) - containerRect.top;

            const midX = startX + (endX - startX) / 2;

            // Draw Top Match -> Target
            drawLine(svg, startX, topY, midX, topY, midX, targetY, endX, targetY);

            // Draw Bottom Match -> Target
            drawLine(svg, startX, bottomY, midX, bottomY, midX, targetY, endX, targetY);
        }
    }
}

function drawLine(svg, x1, y1, x2, y2, x3, y3, x4, y4) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${x1} ${y1} L ${x2} ${y2} L ${x3} ${y3} L ${x4} ${y4}`;
    path.setAttribute('d', d);
    path.setAttribute('stroke', 'var(--color-border-strong, #E5E8EB)');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(path);
}
