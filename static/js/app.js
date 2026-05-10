/**
 * Chess Game Review – Frontend Application
 * Handles board interaction, eval bar, charts, and move navigation.
 */

// ── State ──────────────────────────────────────────────────────────────────
let currentMoveIndex = 0;  // 0 = start position, 1 = after first move
let board = null;
let boardFlipped = false;
let evalChart = null;
const moves = ANALYSIS_DATA.moves || [];
const fens = ANALYSIS_DATA.fens || [];
const totalMoves = moves.length;

// ── Init ───────────────────────────────────────────────────────────────────
$(document).ready(function () {
  initBoard();
  initEvalChart();
  bindKeyboard();
  goToMove(0);
});

// ── Board initialization ───────────────────────────────────────────────────
function initBoard() {
  const config = {
    draggable: false,
    position: fens[0] || 'start',
    orientation: 'white',
    pieceTheme: 'https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/img/chesspieces/wikipedia/{piece}.png',
  };
  board = Chessboard('board', config);
  $(window).resize(board.resize);
}

// ── Move navigation ────────────────────────────────────────────────────────
function goToMove(index) {
  index = Math.max(0, Math.min(index, totalMoves));
  currentMoveIndex = index;

  // Update board position
  const fen = fens[index] || fens[fens.length - 1];
  if (board && fen) {
    board.position(fen, false);
  }

  // Update eval bar
  updateEvalBar(index);

  // Update move list highlighting
  updateMoveListHighlight(index);

  // Update move detail panel
  if (index > 0) {
    showMoveDetail(index - 1);
  } else {
    hideMoveDetail();
  }

  // Scroll move into view
  if (index > 0) {
    const moveEl = document.getElementById(`move-${index - 1}`);
    if (moveEl) {
      moveEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }
}

function nextMove() {
  goToMove(currentMoveIndex + 1);
}

function prevMove() {
  goToMove(currentMoveIndex - 1);
}

function toggleFlip() {
  boardFlipped = !boardFlipped;
  if (board) {
    board.flip();
  }
}

// ── Eval bar ───────────────────────────────────────────────────────────────
function updateEvalBar(moveIndex) {
  const whiteBar = document.getElementById('eval-bar-white');
  const blackBar = document.getElementById('eval-bar-black');
  const evalText = document.getElementById('eval-text');

  if (!whiteBar || !blackBar) return;

  let winProb = 0.5;
  let cpDisplay = '0.0';

  if (moveIndex === 0) {
    winProb = 0.5;
    cpDisplay = '0.0';
  } else {
    const move = moves[moveIndex - 1];
    if (move) {
      // win_prob_after is from the perspective of the side that just moved
      // We need it from White's perspective
      const wp = move.win_prob_after;
      if (move.color === 'white') {
        winProb = wp;
      } else {
        winProb = 1 - wp;
      }

      // Display CP value
      const cp = move.cp_after;
      if (cp !== null && cp !== undefined) {
        if (move.color === 'white') {
          // cp_after is from Black's perspective after white moved, negate for display
          const cpWhite = -cp;
          cpDisplay = formatCp(cpWhite);
        } else {
          const cpWhite = cp;
          cpDisplay = formatCp(cpWhite);
        }
      }
    }
  }

  const whitePercent = Math.round(winProb * 100);
  const blackPercent = 100 - whitePercent;

  whiteBar.style.height = `${blackPercent}%`;  // white at bottom
  blackBar.style.height = `${whitePercent}%`;  // inverted because bar is top-to-bottom

  // Actually: bar shows black at top, white at bottom
  // whiteBar fills from bottom upward
  whiteBar.style.height = `${whitePercent}%`;
  blackBar.style.height = `${blackPercent}%`;

  if (evalText) {
    evalText.textContent = cpDisplay;
  }
}

function formatCp(cp) {
  if (cp === null || cp === undefined) return '0.0';
  if (Math.abs(cp) >= 1000) {
    return cp > 0 ? '+M' : '-M';
  }
  const pawns = cp / 100;
  return (pawns >= 0 ? '+' : '') + pawns.toFixed(1);
}

// ── Move list highlighting ─────────────────────────────────────────────────
function updateMoveListHighlight(moveIndex) {
  document.querySelectorAll('.move-item').forEach(el => {
    el.classList.remove('active');
  });

  if (moveIndex > 0) {
    const activeEl = document.getElementById(`move-${moveIndex - 1}`);
    if (activeEl) {
      activeEl.classList.add('active');
    }
  }
}

// ── Move detail panel ──────────────────────────────────────────────────────
function showMoveDetail(moveIndex) {
  const move = moves[moveIndex];
  if (!move) return;

  const panel = document.getElementById('move-detail');
  if (!panel) return;

  panel.classList.remove('hidden');

  // Title
  const title = document.getElementById('detail-title');
  if (title) {
    title.textContent = `Move ${move.move_number}${move.color === 'black' ? '...' : '.'} ${move.san}`;
  }

  // Played move + classification
  const played = document.getElementById('detail-played');
  if (played) {
    played.textContent = move.san + (move.symbol || '');
    played.className = `font-mono font-bold text-lg ${move.color_class || ''}`;
  }

  const cls = document.getElementById('detail-classification');
  if (cls) {
    cls.textContent = move.label || '';
    cls.className = `text-sm font-medium mt-1 ${move.color_class || ''}`;
  }

  // Best move
  const best = document.getElementById('detail-best');
  if (best) {
    best.textContent = move.engine_top_move || '–';
  }

  // Eval change
  const evalChange = document.getElementById('detail-eval-change');
  if (evalChange && move.cp_before !== null && move.cp_after !== null) {
    const before = formatCp(move.cp_before);
    const after = formatCp(-move.cp_after);
    const cpLoss = move.cp_loss ? ` (${move.cp_loss.toFixed(0)} cp loss)` : '';
    evalChange.textContent = `Eval: ${before} → ${after}${cpLoss}`;
  } else if (evalChange) {
    evalChange.textContent = '';
  }

  // Tactics
  const tactics = document.getElementById('detail-tactics');
  if (tactics) {
    if (move.tactics && move.tactics.length > 0) {
      tactics.innerHTML = move.tactics.slice(0, 3).map(t =>
        `<div class="mb-1 px-2 py-1 rounded text-xs
          ${t.severity === 'high' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' :
            t.severity === 'medium' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' :
            'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'}">${t.description}</div>`
      ).join('');
    } else {
      tactics.textContent = 'No tactical patterns.';
    }
  }

  // Alternatives
  const alts = document.getElementById('detail-alternatives');
  if (alts && move.alternatives && move.alternatives.length > 0) {
    alts.innerHTML = '<div class="font-medium text-gray-600 dark:text-gray-400 mb-1">Alternatives:</div>' +
      move.alternatives.map(a => {
        const cp = a.score_cp !== null ? formatCp(a.score_cp) : '';
        return `<span class="inline-block mr-3 font-mono">${a.move_uci || ''} <span class="text-green-500">${cp}</span></span>`;
      }).join('');
  } else if (alts) {
    alts.innerHTML = '';
  }
}

function hideMoveDetail() {
  const panel = document.getElementById('move-detail');
  if (panel) {
    panel.classList.add('hidden');
  }
}

// ── Eval chart ─────────────────────────────────────────────────────────────
function initEvalChart() {
  const canvas = document.getElementById('eval-chart');
  if (!canvas || !moves.length) return;

  // Build data: win probability for white across all moves
  const labels = [];
  const winProbData = [];
  const pointColors = [];

  // Start position
  labels.push('Start');
  winProbData.push(50);
  pointColors.push('rgba(156, 163, 175, 0.8)');

  moves.forEach((move, i) => {
    labels.push(`${move.move_number}${move.color === 'white' ? '.' : '...'} ${move.san}`);

    let wp = move.win_prob_after;
    if (move.color === 'black') {
      wp = 1 - wp;
    }
    winProbData.push(Math.round(wp * 100));

    // Color by classification
    const colorMap = {
      blunder: 'rgba(239, 68, 68, 0.8)',
      mistake: 'rgba(251, 146, 60, 0.8)',
      inaccuracy: 'rgba(250, 204, 21, 0.8)',
      good: 'rgba(156, 163, 175, 0.8)',
      excellent: 'rgba(134, 239, 172, 0.8)',
      best: 'rgba(34, 197, 94, 0.9)',
      brilliant: 'rgba(34, 211, 238, 0.9)',
      book: 'rgba(96, 165, 250, 0.8)',
      missed_win: 'rgba(168, 85, 247, 0.8)',
    };
    pointColors.push(colorMap[move.classification] || 'rgba(156, 163, 175, 0.8)');
  });

  const isDark = document.documentElement.classList.contains('dark');
  const gridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
  const textColor = isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.7)';

  evalChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: winProbData,
        borderColor: 'rgba(34, 197, 94, 0.8)',
        borderWidth: 1.5,
        pointBackgroundColor: pointColors,
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.2,
        fill: {
          target: { value: 50 },
          above: 'rgba(34, 197, 94, 0.15)',
          below: 'rgba(239, 68, 68, 0.15)',
        },
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 200 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => items[0].label,
            label: (item) => `White: ${item.raw}%`,
          },
        },
      },
      scales: {
        x: {
          display: false,
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            callback: (v) => v + '%',
            stepSize: 25,
          },
        },
      },
      onClick: (evt, elements) => {
        if (elements.length > 0) {
          const idx = elements[0].index;
          goToMove(idx);
        }
      },
    },
  });
}

// ── Keyboard navigation ────────────────────────────────────────────────────
function bindKeyboard() {
  document.addEventListener('keydown', function (e) {
    // Don't intercept when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextMove();
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      prevMove();
    } else if (e.key === 'Home') {
      e.preventDefault();
      goToMove(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      goToMove(totalMoves);
    }
  });
}

// ── Tab switching ──────────────────────────────────────────────────────────
function switchTab(tabId) {
  // Hide all panels
  document.querySelectorAll('.tab-panel').forEach(el => {
    el.classList.add('hidden');
  });

  // Deactivate all tab buttons
  document.querySelectorAll('.tab-btn').forEach(el => {
    el.classList.remove('border-green-500', 'text-green-600', 'dark:text-green-400');
    el.classList.add('border-transparent', 'text-gray-500', 'dark:text-gray-400');
  });

  // Show selected panel
  const panel = document.getElementById(`panel-${tabId}`);
  if (panel) {
    panel.classList.remove('hidden');
  }

  // Activate selected tab button
  const btn = document.getElementById(`tab-${tabId}`);
  if (btn) {
    btn.classList.remove('border-transparent', 'text-gray-500', 'dark:text-gray-400');
    btn.classList.add('border-green-500', 'text-green-600', 'dark:text-green-400');
  }
}
