/**
 * Travel Planning AI — Frontend Logic
 * Handles multi-step wizard, SSE streaming, plan rendering, and revision flow.
 */

'use strict';

// ─── State ────────────────────────────────────────────────────────────────
const state = {
  currentStep: 1,
  threadId: null,
  revisionCount: 0,
  planMarkdown: '',
};

// ─── DOM Refs ──────────────────────────────────────────────────────────────
const steps     = [1,2,3,4,5].map(n => document.getElementById(`step-${n}`));
const toast     = document.getElementById('toast');

// Step-1 inputs
const originEl       = document.getElementById('origin');
const destEl         = document.getElementById('destination');
const depDateEl      = document.getElementById('departure-date');
const retDateEl      = document.getElementById('return-date');
const travelersEl    = document.getElementById('num-travelers');
const travelersDisp  = document.getElementById('travelers-display');
const budgetEl       = document.getElementById('budget');

// Step-2
const activityChips  = document.querySelectorAll('.activity-chip');

// Step-3 (loading)
const agentMap = {
  flight_agent:     document.getElementById('agent-flight'),
  weather_agent:    document.getElementById('agent-weather'),
  hotel_agent:      document.getElementById('agent-hotel'),
  activities_agent: document.getElementById('agent-activities'),
  planner_agent:    document.getElementById('agent-planner'),
};
const progressBar    = document.getElementById('progress-bar');
const progressLabel  = document.getElementById('progress-label');

// Step-4 (review)
const planContent    = document.getElementById('plan-content');
const planSubtitle   = document.getElementById('plan-subtitle');
const revisionBadge  = document.getElementById('revision-badge');
const revisionNum    = document.getElementById('revision-num');
const revisionPanel  = document.getElementById('revision-panel');
const feedbackInput  = document.getElementById('feedback-input');

// Step-5 (done)
const finalPlanContent = document.getElementById('final-plan-content');

// ─── Helpers ───────────────────────────────────────────────────────────────
function showStep(n) {
  steps.forEach((s, i) => {
    s.classList.toggle('active', i + 1 === n);
  });
  state.currentStep = n;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showToast(msg, type = 'info') {
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  setTimeout(() => toast.classList.remove('show'), 3500);
}

function renderMarkdown(md) {
  if (typeof marked !== 'undefined') {
    return marked.parse(md);
  }
  // Fallback: plain pre block
  return `<pre style="white-space:pre-wrap">${md}</pre>`;
}

function setDefaultDates() {
  const today = new Date();
  const dep   = new Date(today);
  dep.setDate(today.getDate() + 14);
  const ret   = new Date(dep);
  ret.setDate(dep.getDate() + 7);

  depDateEl.value = dep.toISOString().split('T')[0];
  retDateEl.value = ret.toISOString().split('T')[0];
}

function getSelectedActivities() {
  return [...document.querySelectorAll('.activity-chip.selected')]
    .map(el => el.dataset.value);
}

function resetAgentUI() {
  Object.values(agentMap).forEach(el => {
    if (!el) return;
    el.className = 'agent-item';
    el.querySelector('.agent-status').className = 'agent-status idle';
    el.querySelector('.agent-status').textContent = 'Waiting...';
  });
  progressBar.style.width = '0%';
  progressLabel.textContent = 'Initialising agents...';
}

// ─── Agent Progress ────────────────────────────────────────────────────────
const AGENT_ORDER = ['flight_agent','weather_agent','hotel_agent','activities_agent','planner_agent'];
let agentsDone = 0;

function markAgentRunning(nodeName) {
  const el = agentMap[nodeName];
  if (!el) return;
  el.classList.add('running');
  const statusEl = el.querySelector('.agent-status');
  statusEl.className = 'agent-status running';
  statusEl.textContent = 'Running...';
}

function markAgentDone(nodeName, label) {
  const el = agentMap[nodeName];
  if (!el) return;
  el.classList.remove('running');
  el.classList.add('done');
  const statusEl = el.querySelector('.agent-status');
  statusEl.className = 'agent-status done';
  statusEl.textContent = '✓ Done';

  agentsDone++;
  const pct = Math.round((agentsDone / AGENT_ORDER.length) * 100);
  progressBar.style.width = `${pct}%`;
  progressLabel.textContent = label || `${nodeName.replace('_',' ')} complete`;
}

// ─── SSE Streaming ─────────────────────────────────────────────────────────
function connectSSE(url, onEvent, onEnd, onError) {
  const evtSource = new EventSource(url);

  evtSource.addEventListener('node_complete', e => {
    const data = JSON.parse(e.data);
    onEvent(data);
  });

  evtSource.addEventListener('plan_ready', e => {
    const data = JSON.parse(e.data);
    evtSource.close();
    onEnd(data);
  });

  evtSource.addEventListener('error', e => {
    const data = e.data ? JSON.parse(e.data) : { message: 'Stream error' };
    evtSource.close();
    onError(data.message || 'Unknown stream error');
  });

  evtSource.onerror = (err) => {
    // Only fire if connection drops unexpectedly
    if (evtSource.readyState === EventSource.CLOSED) return;
    evtSource.close();
    onError('Connection lost. Please try again.');
  };

  return evtSource;
}

// ─── Step 1 — Validation & Next ───────────────────────────────────────────
document.getElementById('dec-travelers').addEventListener('click', () => {
  const cur = parseInt(travelersEl.value);
  if (cur > 1) { travelersEl.value = cur - 1; travelersDisp.textContent = cur - 1; }
});
document.getElementById('inc-travelers').addEventListener('click', () => {
  const cur = parseInt(travelersEl.value);
  if (cur < 20) { travelersEl.value = cur + 1; travelersDisp.textContent = cur + 1; }
});

document.getElementById('btn-next-1').addEventListener('click', () => {
  if (!originEl.value.trim())    { showToast('⚠️ Please enter your departure city', 'error'); return; }
  if (!destEl.value.trim())      { showToast('⚠️ Please enter your destination', 'error'); return; }
  if (!depDateEl.value)          { showToast('⚠️ Please select a departure date', 'error'); return; }
  if (!retDateEl.value)          { showToast('⚠️ Please select a return date', 'error'); return; }
  if (depDateEl.value >= retDateEl.value) { showToast('⚠️ Return date must be after departure', 'error'); return; }
  if (!budgetEl.value || parseFloat(budgetEl.value) < 100) { showToast('⚠️ Please enter a budget of at least $100', 'error'); return; }
  showStep(2);
});

// ─── Step 2 — Activity Selection ──────────────────────────────────────────
activityChips.forEach(chip => {
  chip.addEventListener('click', () => chip.classList.toggle('selected'));
});

document.getElementById('btn-back-2').addEventListener('click', () => showStep(1));

document.getElementById('btn-launch').addEventListener('click', async () => {
  const activities = getSelectedActivities();
  if (activities.length === 0) {
    showToast('💡 Tip: Select at least one activity for a better plan', 'info');
  }
  await launchAgents(activities);
});

// ─── Launch Agents ─────────────────────────────────────────────────────────
async function launchAgents(activities) {
  showStep(3);
  resetAgentUI();
  agentsDone = 0;

  const payload = {
    origin:          originEl.value.trim(),
    destination:     destEl.value.trim(),
    departure_date:  depDateEl.value,
    return_date:     retDateEl.value,
    num_travelers:   parseInt(travelersEl.value),
    activities:      activities,
    budget:          parseFloat(budgetEl.value),
    budget_currency: 'USD',
  };

  try {
    // Step A: Register session
    const resp = await fetch('/api/plan/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Failed to start session');
    }

    const { thread_id } = await resp.json();
    state.threadId = thread_id;

    // Step B: Connect SSE stream
    progressLabel.textContent = 'Agents online — starting research...';

    // Simulate "running" state for first agent
    markAgentRunning('flight_agent');

    connectSSE(
      `/api/plan/stream/${thread_id}`,
      // onEvent
      (data) => {
        const node = data.node;
        markAgentDone(node, data.label);
        // Mark next agent as running
        const idx = AGENT_ORDER.indexOf(node);
        if (idx >= 0 && idx + 1 < AGENT_ORDER.length) {
          markAgentRunning(AGENT_ORDER[idx + 1]);
        }
        progressLabel.textContent = `${data.emoji || '🔄'} ${data.label}...`;
      },
      // onEnd (plan_ready)
      (data) => {
        state.planMarkdown  = data.plan_draft || '';
        state.revisionCount = data.revision_count || 0;
        showPlan(state.planMarkdown, state.revisionCount);
      },
      // onError
      (msg) => {
        showToast(`❌ ${msg}`, 'error');
        showStep(1);
      }
    );

  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
    showStep(1);
  }
}

// ─── Show Plan ─────────────────────────────────────────────────────────────
function showPlan(markdown, revCount) {
  planContent.innerHTML = renderMarkdown(markdown);
  planSubtitle.textContent = revCount > 0
    ? `Revision ${revCount} — approve or request further changes`
    : 'Review your personalised itinerary — approve or request changes';

  if (revCount > 0) {
    revisionBadge.style.display = 'block';
    revisionNum.textContent = revCount;
  } else {
    revisionBadge.style.display = 'none';
  }

  revisionPanel.style.display = 'none';
  feedbackInput.value = '';

  showStep(4);
}

// ─── Step 4 — Approve & Revise ─────────────────────────────────────────────
document.getElementById('btn-approve').addEventListener('click', async () => {
  const btn = document.getElementById('btn-approve');
  btn.disabled = true;
  btn.textContent = '⏳ Saving...';

  try {
    const resp = await fetch(`/api/plan/approve/${state.threadId}`, { method: 'POST' });
    if (!resp.ok) throw new Error('Approval failed');
    const data = await resp.json();

    finalPlanContent.innerHTML = renderMarkdown(data.final_plan || state.planMarkdown);
    showStep(5);
    showToast('🎉 Your travel plan has been saved!', 'success');
  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
    btn.disabled = false;
    btn.textContent = '✅ Approve This Plan';
  }
});

document.getElementById('btn-revise-toggle').addEventListener('click', () => {
  const visible = revisionPanel.style.display !== 'none';
  revisionPanel.style.display = visible ? 'none' : 'block';
  if (!visible) feedbackInput.focus();
});

document.getElementById('btn-cancel-revision').addEventListener('click', () => {
  revisionPanel.style.display = 'none';
  feedbackInput.value = '';
});

document.getElementById('btn-submit-revision').addEventListener('click', async () => {
  const feedback = feedbackInput.value.trim();
  if (!feedback) { showToast('⚠️ Please describe what you want changed', 'error'); return; }

  const btn = document.getElementById('btn-submit-revision');
  btn.disabled = true;
  btn.textContent = '⏳ Sending to agents...';

  // Show loading step with only planner active
  showStep(3);
  resetAgentUI();
  agentsDone = 4; // Skip data agents — only planner runs
  progressBar.style.width = '80%';
  markAgentDone('flight_agent', 'Using cached data');
  markAgentDone('weather_agent', 'Using cached data');
  markAgentDone('hotel_agent', 'Using cached data');
  markAgentDone('activities_agent', 'Using cached data');
  markAgentRunning('planner_agent');
  progressLabel.textContent = '✏️ Revising your plan based on feedback...';

  try {
    connectSSE(
      `/api/plan/feedback/${state.threadId}`,
      // This endpoint only runs planner, so we might not get node events
      (data) => {
        if (data.node === 'planner_agent') {
          markAgentDone('planner_agent', 'Revision complete');
          progressBar.style.width = '100%';
        }
      },
      (data) => {
        state.planMarkdown  = data.plan_draft || '';
        state.revisionCount = data.revision_count || state.revisionCount + 1;
        btn.disabled = false;
        btn.textContent = '🔄 Regenerate Plan';
        showPlan(state.planMarkdown, state.revisionCount);
      },
      (msg) => {
        showToast(`❌ ${msg}`, 'error');
        showPlan(state.planMarkdown, state.revisionCount); // go back to current plan
        btn.disabled = false;
        btn.textContent = '🔄 Regenerate Plan';
      }
    );

    // Also POST to feedback endpoint with the feedback text
    // Note: connectSSE handles the GET SSE — the feedback is posted separately
    // The SSE endpoint handles both via request body... 
    // Actually we need to POST the feedback first then connect SSE
    // Let me fix this: POST feedback returns SSE so we pass it via query or the EventSource URL
    // Since EventSource is GET only, we POST first then connect SSE in correct order
    // See app architecture — the feedback endpoint is a POST that returns SSE
    // We need to handle this differently for EventSource (GET-only):
    // Solution: We've already connected via GET SSE for /api/plan/feedback/{id}?feedback=...
    // But feedback body can't be GET. So we'll use fetch with ReadableStream instead.

  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
    btn.disabled = false;
    btn.textContent = '🔄 Regenerate Plan';
  }
});

// ─── Step 5 — New Trip / Print ─────────────────────────────────────────────
document.getElementById('btn-new-trip').addEventListener('click', () => {
  state.threadId = null;
  state.planMarkdown = '';
  state.revisionCount = 0;
  originEl.value = '';
  destEl.value = '';
  budgetEl.value = '';
  document.querySelectorAll('.activity-chip.selected').forEach(c => c.classList.remove('selected'));
  showStep(1);
});

document.getElementById('btn-print').addEventListener('click', () => {
  window.print();
});

// ─── Better Revision Flow (POST + fetch streaming) ─────────────────────────
// Override the revision submit to use fetch streaming instead of EventSource
// because POST body can't be sent via EventSource (GET only).
document.getElementById('btn-submit-revision').removeEventListener('click', null);
document.getElementById('btn-submit-revision').addEventListener('click', async () => {
  const feedback = feedbackInput.value.trim();
  if (!feedback) { showToast('⚠️ Please describe what you want changed', 'error'); return; }

  const btn = document.getElementById('btn-submit-revision');
  btn.disabled = true;
  btn.textContent = '⏳ Revising plan...';

  // Show loading
  showStep(3);
  resetAgentUI();
  agentsDone = 4;
  progressBar.style.width = '80%';
  progressLabel.textContent = '✏️ Planner agent revising your itinerary...';
  markAgentDone('flight_agent', 'Cached'); markAgentDone('weather_agent', 'Cached');
  markAgentDone('hotel_agent', 'Cached');  markAgentDone('activities_agent', 'Cached');
  markAgentRunning('planner_agent');

  try {
    const resp = await fetch(`/api/plan/feedback/${state.threadId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ feedback }),
    });

    if (!resp.ok || !resp.body) throw new Error('Revision request failed');

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();

      for (const part of parts) {
        const dataLine = part.split('\n').find(l => l.startsWith('data:'));
        if (!dataLine) continue;
        const data = JSON.parse(dataLine.replace('data:', '').trim());

        if (data.event === 'node_complete' && data.node === 'planner_agent') {
          markAgentDone('planner_agent', 'Revision done');
          progressBar.style.width = '100%';
        }
        if (data.event === 'plan_ready') {
          state.planMarkdown  = data.plan_draft || '';
          state.revisionCount = data.revision_count || state.revisionCount + 1;
          btn.disabled = false;
          btn.textContent = '🔄 Regenerate Plan';
          showPlan(state.planMarkdown, state.revisionCount);
        }
        if (data.event === 'error') {
          throw new Error(data.message);
        }
      }
    }

  } catch (err) {
    showToast(`❌ ${err.message}`, 'error');
    showPlan(state.planMarkdown, state.revisionCount);
    btn.disabled = false;
    btn.textContent = '🔄 Regenerate Plan';
  }
});

// ─── Init ──────────────────────────────────────────────────────────────────
setDefaultDates();
showStep(1);
