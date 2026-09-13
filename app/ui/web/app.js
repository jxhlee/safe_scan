// Defensive guard: on rare occasions (e.g. a window left idle in the
// background for a long time gets its renderer reloaded by the OS/WebView2)
// `pywebviewready` can fire before window.pywebview.api is fully populated.
// Poll briefly for the specific method rather than trusting the flag alone.
function waitForApiMethod(name, timeoutMs = 4000) {
  return new Promise((resolve) => {
    const start = performance.now();
    (function poll() {
      if (typeof window.pywebview?.api?.[name] === 'function') {
        resolve(true);
        return;
      }
      if (performance.now() - start > timeoutMs) {
        resolve(false);
        return;
      }
      setTimeout(poll, 150);
    })();
  });
}

// This same frontend runs two ways: inside the pywebview desktop app (talks
// to Python via window.pywebview.api) and as a plain website (talks to the
// FastAPI server via fetch). `window.pywebview` only exists in the desktop
// case, and by the time a human has typed/pasted text and clicked a button
// it has always finished injecting - checked fresh per call, not cached, so
// there's no startup race to worry about.
function isDesktopApp() {
  return typeof window.pywebview !== 'undefined';
}

async function apiAnalyze(text, summaryLen, riskRatio) {
  if (isDesktopApp()) {
    const ready = await waitForApiMethod('analyze_text');
    if (!ready) throw new Error('앱과 연결이 끊긴 것 같습니다. 창을 닫고 다시 실행해주세요.');
    return window.pywebview.api.analyze_text(text, summaryLen, riskRatio);
  }
  const res = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, summary_length: summaryLen, risk_weight_ratio: riskRatio }),
  });
  return res.json();
}

function apiOpenFile() {
  if (isDesktopApp()) {
    return (async () => {
      const ready = await waitForApiMethod('open_file');
      if (!ready) return { error: '앱과 연결이 끊긴 것 같습니다. 창을 닫고 다시 실행해주세요.' };
      return window.pywebview.api.open_file();
    })();
  }
  // Browsers can't show a native "open file" dialog from script - trigger
  // the hidden <input type="file"> instead, then upload whatever was picked.
  return new Promise((resolve) => {
    const fileInput = document.getElementById('file-input');
    fileInput.onchange = async () => {
      const file = fileInput.files[0];
      fileInput.value = '';
      if (!file) {
        resolve({ text: null });
        return;
      }
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        resolve(await res.json());
      } catch (err) {
        resolve({ error: '파일을 업로드하는 중 오류가 발생했습니다: ' + err });
      }
    };
    fileInput.click();
  });
}

const els = {
  input: document.getElementById('input-text'),
  openFile: document.getElementById('btn-open-file'),
  filenameLabel: document.getElementById('filename-label'),
  summaryLengthValue: document.getElementById('summary-length-value'),
  summaryLengthDec: document.getElementById('summary-length-dec'),
  summaryLengthInc: document.getElementById('summary-length-inc'),
  riskRatio: document.getElementById('risk-ratio'),
  riskRatioLabel: document.getElementById('risk-ratio-label'),
  analyze: document.getElementById('btn-analyze'),
  status: document.getElementById('status-message'),
  statsBar: document.getElementById('stats-bar'),
  statsSummaryText: document.getElementById('stats-summary-text'),
  statsMetaText: document.getElementById('stats-meta-text'),
  statChipHigh: document.getElementById('stat-chip-high'),
  statChipMid: document.getElementById('stat-chip-mid'),
  statHighCount: document.getElementById('stat-high-count'),
  statMidCount: document.getElementById('stat-mid-count'),
  checklist: document.getElementById('checklist-container'),
  summary: document.getElementById('summary-container'),
  riskList: document.getElementById('risk-list-container'),
  riskFilterBanner: document.getElementById('risk-filter-banner'),
  riskFilterText: document.getElementById('risk-filter-text'),
  riskFilterClear: document.getElementById('risk-filter-clear'),
  originalView: document.getElementById('original-view'),
  countChecklist: document.getElementById('count-checklist'),
  countSummary: document.getElementById('count-summary'),
  countRisklist: document.getElementById('count-risklist'),
  themeToggle: document.getElementById('theme-toggle'),
  sampleSelect: document.getElementById('sample-select'),
  easyModeToggle: document.getElementById('easy-mode-toggle'),
};

// --- Theme ---
function currentTheme() {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}
function applyThemeIcon() {
  els.themeToggle.textContent = currentTheme() === 'dark' ? '🌙' : '☀️';
}
applyThemeIcon();
els.themeToggle.addEventListener('click', () => {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('tos-checker-theme', next); } catch (e) { /* ignore */ }
  applyThemeIcon();
});

// --- Easy mode (kids / seniors / anyone unfamiliar with legal jargon) ---
const EASY_GRADE_LABEL = { 높음: '위험해요', 중간: '확인해보세요', 낮음: '가벼운 주의' };
const EASY_CATEGORY_LABEL = { 개인정보: '내 정보', 금전: '돈', 책임: '문제생겼을 때' };

const EASY_TEXT_TARGETS = [
  { sel: '.brand-badge', easy: '위험한 부분 확인하기' },
  { sel: 'header .disclaimer', easy: '약관에서 위험할 수 있는 부분을 컴퓨터가 찾아주는 도구예요. 중요한 약속을 하기 전에는 원문도 꼭 읽어보세요.' },
  { sel: '.input-panel-title', easy: '📄 여기에 약관을 넣어주세요' },
  { sel: '.input-panel-hint', easy: '글자를 붙여넣거나 파일을 올려주세요' },
  { sel: '#btn-open-file', easy: '📁 파일 불러오기' },
  { sel: '#btn-analyze', easy: '🔍 확인하기' },
  { sel: '.tabs-hint', easy: '🔗 눌러보면 더 자세히 볼 수 있어요' },
  { sel: '.tab-btn[data-tab="checklist"] .tab-label-text', easy: '체크리스트' },
  { sel: '.tab-btn[data-tab="summary"] .tab-label-text', easy: '요약' },
  { sel: '.tab-btn[data-tab="risklist"] .tab-label-text', easy: '위험 목록' },
  { sel: '.tab-btn[data-tab="original"] .tab-label-text', easy: '원문 보기' },
  { sel: '#stat-chip-high .stat-chip-label', easy: '🔴 위험해요' },
  { sel: '#stat-chip-mid .stat-chip-label', easy: '🟠 확인해보세요' },
  { sel: '#risk-filter-clear', easy: '다 보기' },
  { sel: '#original-legend-note', easy: '— 색칠된 부분이 위험할 수 있는 문장이에요' },
  { sel: '.footer-disclaimer', easy: '※ 이 결과는 컴퓨터가 도와주는 것이에요. 진짜 중요한 결정은 어른이나 전문가와 다시 확인하세요.' },
];

const NORMAL_PLACEHOLDER = els.input.placeholder;
const EASY_PLACEHOLDER = '여기에 약관 내용을 넣어주세요.';
const NORMAL_SUMMARY_NOTE_HTML = document.getElementById('summary-tab-note').innerHTML;
const EASY_SUMMARY_NOTE_HTML = '중요한 문장만 모아놨어요. 전체 내용은 <strong>위험 목록</strong>에서 다 볼 수 있어요.';

let easyMode = false;
let lastResult = null;
let lastStatsArgs = null;
const normalTextCache = new Map();

function applyEasyMode(on) {
  easyMode = on;
  document.documentElement.dataset.easyMode = on ? 'on' : 'off';
  els.easyModeToggle.classList.toggle('active', on);
  els.easyModeToggle.textContent = on ? '👵🧒 쉬운 모드 끄기' : '👵🧒 쉬운 모드';

  EASY_TEXT_TARGETS.forEach(({ sel, easy }) => {
    const el = document.querySelector(sel);
    if (!el) return;
    if (!normalTextCache.has(sel)) normalTextCache.set(sel, el.textContent);
    el.textContent = on ? easy : normalTextCache.get(sel);
  });
  els.input.placeholder = on ? EASY_PLACEHOLDER : NORMAL_PLACEHOLDER;
  document.getElementById('summary-tab-note').innerHTML = on ? EASY_SUMMARY_NOTE_HTML : NORMAL_SUMMARY_NOTE_HTML;

  try { localStorage.setItem('tos-checker-easy-mode', on ? '1' : '0'); } catch (e) { /* ignore */ }

  if (lastResult) {
    render(lastResult);
    if (lastStatsArgs) showStats(...lastStatsArgs);
  }
}

els.easyModeToggle.addEventListener('click', () => applyEasyMode(!easyMode));

let savedEasyMode = false;
try { savedEasyMode = localStorage.getItem('tos-checker-easy-mode') === '1'; } catch (e) { /* ignore */ }
applyEasyMode(savedEasyMode);

// --- Summary length stepper ---
const SUMMARY_LENGTH_MIN = 3;
const SUMMARY_LENGTH_MAX = 15;
let summaryLength = 5;

function renderStepper() {
  els.summaryLengthValue.textContent = summaryLength;
  els.summaryLengthDec.disabled = summaryLength <= SUMMARY_LENGTH_MIN;
  els.summaryLengthInc.disabled = summaryLength >= SUMMARY_LENGTH_MAX;
}
els.summaryLengthDec.addEventListener('click', () => {
  summaryLength = Math.max(SUMMARY_LENGTH_MIN, summaryLength - 1);
  renderStepper();
});
els.summaryLengthInc.addEventListener('click', () => {
  summaryLength = Math.min(SUMMARY_LENGTH_MAX, summaryLength + 1);
  renderStepper();
});
renderStepper();

// --- Sample loader ---
const SAMPLES = {
  delivery: `제1조(목적) 본 약관은 회사가 제공하는 배달 플랫폼 서비스의 이용조건 및 절차를 규정함을 목적으로 합니다.

제2조(개인정보 수집 및 제공) 회사는 서비스 제공을 위해 이용자의 정밀 위치정보를 수집합니다. 회원가입 시 광고 식별자를 수집하며, 마케팅 목적으로 제3자에게 제공됩니다. 별도의 동의 없이 마케팅 목적으로 활용할 수 있습니다.

제3조(보유기간) 회사는 회원 탈퇴 후에도 별도로 보관할 수 있습니다.

제4조(자동결제) 무료 체험 종료 후 자동으로 유료로 전환되며, 별도의 해지 신청이 없는 한 자동으로 갱신됩니다.

제5조(환불) 결제 완료 후 취소 및 환불이 불가합니다.

제6조(회사의 책임) 회사는 어떠한 경우에도 책임을 지지 않습니다.

제7조(약관의 변경) 회사는 언제든지 약관을 변경할 수 있습니다.

제8조(게시물의 저작권) 게시물에 대한 저작권은 회사에 귀속됩니다.

제9조(분쟁해결) 본사 소재지를 관할하는 법원을 전속 관할로 합니다.`,
};

els.sampleSelect.addEventListener('change', () => {
  const key = els.sampleSelect.value;
  if (!key || !SAMPLES[key]) return;
  els.input.value = SAMPLES[key];
  els.filenameLabel.textContent = '';
  els.sampleSelect.value = '';
});

// --- Tabs ---
document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});

function activateTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === tabName));
  document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === `tab-${tabName}`));
}

// --- Input controls ---
els.riskRatio.addEventListener('input', () => {
  els.riskRatioLabel.textContent = els.riskRatio.value;
});

els.openFile.addEventListener('click', async () => {
  const result = await apiOpenFile();
  if (result.error) {
    setStatus(result.error, true);
    return;
  }
  if (result.text === null || result.text === undefined) return;
  els.input.value = result.text;
  els.filenameLabel.textContent = result.filename || '';
});

els.analyze.addEventListener('click', async () => {
  const text = els.input.value.trim();
  if (!text) {
    setStatus(easyMode ? '먼저 약관 내용을 넣어주세요.' : '분석할 텍스트를 입력하거나 파일을 열어주세요.', true);
    return;
  }
  setStatus(easyMode ? '읽어보고 있어요...' : '분석 중입니다...');
  els.statsBar.hidden = true;
  els.analyze.disabled = true;
  const startedAt = performance.now();
  try {
    const result = await apiAnalyze(text, summaryLength, Number(els.riskRatio.value));
    const elapsedMs = performance.now() - startedAt;
    if (result.error) {
      setStatus(result.error, true);
      return;
    }
    lastResult = result;
    lastStatsArgs = [result, text.length, elapsedMs];
    render(result);
    setStatus('');
    showStats(result, text.length, elapsedMs);
    activateTab('checklist');
  } catch (err) {
    setStatus('분석 중 오류가 발생했습니다: ' + err, true);
  } finally {
    els.analyze.disabled = false;
  }
});

function setStatus(message, isError) {
  els.status.textContent = message;
  els.status.style.color = isError ? 'var(--grade-high)' : '';
}

function showStats(result, charCount, elapsedMs) {
  const high = result.risk_list.filter((r) => r.grade === '높음').length;
  const mid = result.risk_list.filter((r) => r.grade === '중간').length;
  els.statsSummaryText.textContent = easyMode
    ? `다 봤어요! 위험할 수 있는 부분 ${result.risk_list.length}개를 찾았어요`
    : `분석 완료 · 위험 조항 ${result.risk_list.length}건 식별됨`;
  const seconds = (elapsedMs / 1000).toFixed(2);
  els.statsMetaText.textContent = `총 ${charCount.toLocaleString()}자 분석 · 소요시간 ${seconds}초`;

  els.statHighCount.textContent = high;
  els.statMidCount.textContent = mid;
  els.statChipHigh.hidden = high === 0;
  els.statChipMid.hidden = mid === 0;

  els.statsBar.hidden = false;
}

els.statChipHigh.addEventListener('click', () => applyRiskFilter('높음'));
els.statChipMid.addEventListener('click', () => applyRiskFilter('중간'));
els.riskFilterClear.addEventListener('click', () => applyRiskFilter(null));

function applyRiskFilter(grade) {
  riskListFilterGrade = grade;
  renderRiskList(allRiskItems);
  activateTab('risklist');
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

const GRADE_ICON = { 높음: '🔴', 중간: '🟠', 낮음: '🔵' };

// --- Render ---
let allRiskItems = [];
let riskListFilterGrade = null;

function render(result) {
  allRiskItems = result.risk_list;
  riskListFilterGrade = null;

  renderChecklist(result.checklist);
  renderSummary(result.summary);
  renderRiskList(allRiskItems);
  renderOriginal(result.full_text, result.highlight_spans);

  const riskCount = result.checklist.filter((c) => c.status === '위험 발견').length;
  els.countChecklist.textContent = `${riskCount}/${result.checklist.length}`;
  els.countSummary.textContent = result.summary.length;
  els.countRisklist.textContent = result.risk_list.length;
}

const CHECKLIST_GROUP_DEFS = [
  { key: 'high', title: '높음', easyTitle: '위험해요', dotClass: '높음', match: (i) => i.status === '위험 발견' && i.grade === '높음' },
  { key: 'mid', title: '중간', easyTitle: '확인해보세요', dotClass: '중간', match: (i) => i.status === '위험 발견' && i.grade === '중간' },
  { key: 'low', title: '낮음', easyTitle: '가벼운 주의', dotClass: '낮음', match: (i) => i.status === '위험 발견' && i.grade === '낮음' },
  { key: 'none', title: '미기재', easyTitle: '안 나와있어요', dotClass: 'none', match: (i) => i.status === '언급 없음' },
  { key: 'safe', title: '정상', easyTitle: '괜찮아요', dotClass: 'safe', match: (i) => i.status === '정상 고지 확인' },
];

function checklistCardHtml(item) {
  const finding = easyMode ? item.simple_finding : item.finding;
  const question = easyMode ? item.simple_question : item.question;
  const hasClauses = item.linked_clause_ids.length > 0;
  const goBtn = hasClauses
    ? `<button class="go-to-clause" data-clause="${item.linked_clause_ids[0]}">원문에서 보기</button>`
    : '';
  return `<details class="checklist-card">
    <summary>
      <span class="checklist-label">${escapeHtml(item.label)}</span>
      <span class="card-finding">${escapeHtml(finding)}</span>
    </summary>
    <div class="checklist-detail">
      <div class="checklist-question">${escapeHtml(question)}</div>
      ${goBtn}
    </div>
  </details>`;
}

function renderChecklist(items) {
  if (!items.length) {
    els.checklist.innerHTML = '<p class="empty-hint">체크리스트 항목이 없습니다.</p>';
    return;
  }
  const groups = CHECKLIST_GROUP_DEFS.map((def) => ({ ...def, items: items.filter(def.match) })).filter(
    (g) => g.items.length > 0
  );
  els.checklist.innerHTML = groups
    .map(
      (group) => `<section class="checklist-group" data-key="${group.key}">
        <h3 class="checklist-group-heading">
          <span class="legend-dot ${group.dotClass}"></span>${easyMode ? group.easyTitle : group.title}
          <span class="group-count">${group.items.length}건</span>
        </h3>
        <div class="group-cards">${group.items.map(checklistCardHtml).join('')}</div>
      </section>`
    )
    .join('');
  els.checklist.querySelectorAll('button.go-to-clause').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      goToClause(btn.dataset.clause);
    });
  });
}

function renderSummary(sentences) {
  if (!sentences.length) {
    els.summary.innerHTML = '<p class="empty-hint">요약할 문장이 없습니다.</p>';
    return;
  }
  els.summary.innerHTML = sentences
    .map((s) => {
      const dotClass = s.is_risk_boosted ? 'risk-dot' : 'risk-dot none';
      return `<div class="summary-item">
        <span class="${dotClass}"></span>
        <span class="summary-text" data-clause="${s.clause_id}">${escapeHtml(s.text)}</span>
      </div>`;
    })
    .join('');
  els.summary.querySelectorAll('.summary-text').forEach((el) => {
    el.addEventListener('click', () => goToClause(el.dataset.clause));
  });
}

function renderRiskList(allItems) {
  if (riskListFilterGrade) {
    els.riskFilterBanner.hidden = false;
    const filterLabel = easyMode ? EASY_GRADE_LABEL[riskListFilterGrade] || riskListFilterGrade : riskListFilterGrade;
    els.riskFilterText.textContent = easyMode ? `${filterLabel} 것만 보고 있어요` : `${filterLabel} 등급만 표시 중`;
  } else {
    els.riskFilterBanner.hidden = true;
  }
  const items = riskListFilterGrade ? allItems.filter((r) => r.grade === riskListFilterGrade) : allItems;

  if (!items.length) {
    els.riskList.innerHTML = riskListFilterGrade
      ? '<p class="empty-hint">해당 등급의 위험 조항이 없습니다.</p>'
      : '<p class="empty-hint">탐지된 위험 조항이 없습니다.</p>';
    return;
  }
  els.riskList.innerHTML = items
    .map((item) => {
      const tags = item.tags
        .map((t) => `<span class="tag-pill">${escapeHtml(easyMode ? EASY_CATEGORY_LABEL[t] || t : t)}</span>`)
        .join('');
      const explainList = easyMode ? item.simple_explain : item.explain;
      const explains = explainList.map((e) => `<li>${escapeHtml(e)}</li>`).join('');
      const laws = item.related_law.length
        ? `<div class="risk-law">관련 참고: ${escapeHtml(item.related_law.join(', '))}</div>`
        : '';
      const gradeLabel = easyMode ? EASY_GRADE_LABEL[item.grade] || item.grade : item.grade;
      const headline = easyMode ? item.simple_title : item.title;
      return `<details class="risk-card" data-grade="${item.grade}">
        <summary>
          <span class="grade-pill ${item.grade}">${GRADE_ICON[item.grade] || ''} ${gradeLabel}</span>
          ${tags}
          <span class="risk-headline">${escapeHtml(headline)}</span>
        </summary>
        <div class="risk-detail">
          <div class="risk-excerpt">${escapeHtml(item.excerpt)}</div>
          <ul class="risk-explain-list">${explains}</ul>
          ${laws}
          <button class="go-to-clause" data-clause="${item.clause_id}">원문에서 보기</button>
        </div>
      </details>`;
    })
    .join('');
  els.riskList.querySelectorAll('button.go-to-clause').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      goToClause(btn.dataset.clause);
    });
  });
}

function renderOriginal(fullText, spans) {
  if (!fullText) {
    els.originalView.innerHTML = '<span class="empty-hint">원문이 없습니다.</span>';
    return;
  }
  const sorted = [...spans].sort((a, b) => a.start - b.start);
  let html = '';
  let cursor = 0;
  const seenClause = new Set();
  for (const span of sorted) {
    if (span.start < cursor) continue;
    html += escapeHtml(fullText.slice(cursor, span.start));
    const inner = escapeHtml(fullText.slice(span.start, span.end));
    // Only the first mark for a given clause gets the scroll-target id - a
    // clause can have several matched phrases highlighted independently.
    const idAttr = seenClause.has(span.clause_id) ? '' : ` id="clause-${span.clause_id}"`;
    seenClause.add(span.clause_id);
    html += `<mark class="grade-${span.grade}"${idAttr} data-clause="${span.clause_id}">${inner}</mark>`;
    cursor = span.end;
  }
  html += escapeHtml(fullText.slice(cursor));
  els.originalView.innerHTML = html;
}

function goToClause(clauseId) {
  if (!clauseId) return;
  activateTab('original');
  const mark = document.getElementById(`clause-${clauseId}`);
  if (!mark) return;
  mark.scrollIntoView({ block: 'center', behavior: 'smooth' });
  mark.classList.add('flash');
  setTimeout(() => mark.classList.remove('flash'), 1200);
}
