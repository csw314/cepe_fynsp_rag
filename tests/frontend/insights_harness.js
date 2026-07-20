(async function () {
  'use strict';

  const results = {};
  const output = document.getElementById('results');
  const harness = document.getElementById('harness');
  const helpers = window.CepeDashboardRenderer.__test__;
  const payload = {
    dashboard_id: 'dashboard_01_pit_production', question_id: 'q1', chart_id: 'dashboard_01_pit_production_q1',
    chart_title: 'Funding by fiscal year and funding level',
    insights: { enabled: true, suggested_question: 'Which fiscal year drives the largest change?', context_version: '1.0' },
    filter_options: { fiscal_year: ['FY2028', 'FY2029'], funding_level: ['Baseline'] },
  };
  const activeFilters = { fiscal_year: 'FY2029', unknown_client_field: 'ignored' };
  const target = document.createElement('div');
  target.className = 'visualization-capture';
  target.style.width = '640px';
  target.style.height = '220px';
  target.style.background = 'white';
  target.textContent = 'Synthetic aggregate chart · FY2029 · Baseline';
  const cssBar = document.createElement('div');
  cssBar.style.cssText = 'width:180px;height:18px;background:#27648c;margin:8px';
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '100'); svg.setAttribute('height', '24');
  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  rect.setAttribute('width', '90'); rect.setAttribute('height', '18'); rect.setAttribute('fill', '#246443');
  svg.appendChild(rect);
  const canvas = document.createElement('canvas');
  canvas.width = 100; canvas.height = 20;
  canvas.getContext('2d').fillRect(0, 0, 80, 16);
  const table = document.createElement('table');
  const row = table.insertRow(); row.insertCell().textContent = 'Table value';
  target.append(cssBar, svg, canvas, table);
  harness.appendChild(target);

  let responseMode = 'answered';
  const postedRequests = [];
  const responsePayload = (status = 'answered') => ({
    schema_version: '1.0', status,
    answer: status === 'answered' ? '<img src=x onerror=alert(1)> Grounded answer.' : '',
    key_observations: status === 'answered' ? ['Observed fact'] : [],
    review_triggers: ['Review trigger'],
    limitations: status === 'answered' ? ['Human review required'] : ['The evidence is insufficient.'],
    citations: status === 'answered' ? [{ type: 'dashboard_payload', id: 'dashboard_01_pit_production_q1', label: 'Synthetic payload', source_file_id: null, page: null, section: null }] : [],
    context_used: {
      dashboard_id: 'dashboard_01_pit_production', question_id: 'q1', chart_id: 'dashboard_01_pit_production_q1',
      payload_ids: ['dashboard_01_pit_production_q1'], active_filter_state: { fiscal_year: ['FY2029'] },
      ontology_node_ids: ['node:1'], ontology_edge_ids: ['edge:1'], ontology_path_ids: [],
      guidance_chunk_ids: ['guidance:1'], source_file_ids: ['source:1'], image_used: false,
      image_sha256: null, context_truncated: false,
    },
    ai_metadata: { model: 'mock-model', prompt_version: 'test', request_id: 'mock-request', review_status: 'unreviewed_ai_output' },
  });
  window.fetch = async (url, options = {}) => {
    if (String(url).endsWith('/health')) {
      return new Response(JSON.stringify({
        schema_version: '1.0', service_available: true, asksage_configured: true,
        image_input_supported: true, document_context_available: true,
        ontology_context_available: true,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    postedRequests.push(JSON.parse(options.body));
    if (responseMode === 'failure') throw new TypeError('synthetic network failure');
    if (responseMode === 'pending') {
      return new Promise((resolve, reject) => {
        options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
      });
    }
    return new Response(JSON.stringify(responsePayload(responseMode)), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  const waitForStatus = async (state, expected, attempts = 100) => {
    for (let index = 0; index < attempts && state.status !== expected; index += 1) {
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
    return state.status === expected;
  };

  const state = helpers.createInsightsState(payload, activeFilters, target);
  harness.appendChild(state.slot);
  state.toggle.click();
  await new Promise((resolve) => setTimeout(resolve, 25));
  results.open_and_aria = state.open && state.toggle.getAttribute('aria-expanded') === 'true' && !state.card.hidden;
  results.prepared_question_visible = state.suggestedButton.textContent === payload.insights.suggested_question;
  results.focus_on_open = document.activeElement === state.heading;
  state.customButton.click();
  results.blank_query_rejected = state.status === 'error' && document.activeElement === state.textarea;
  state.captureTarget = null;
  state.textarea.value = 'Line one\nLine two';
  const beforeBareEnter = postedRequests.length;
  state.textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 25));
  results.bare_enter_does_not_submit = postedRequests.length === beforeBareEnter;
  state.textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }));
  results.ctrl_enter_and_answer = await waitForStatus(state, 'answered');
  const customRequest = postedRequests.at(-1);
  results.filter_state_sent = JSON.stringify(customRequest?.active_filter_state) === JSON.stringify({ fiscal_year: ['FY2029'] });
  results.multiline_preserved = customRequest?.query === 'Line one\nLine two';
  results.image_failure_fallback = customRequest?.chart_image === null && customRequest?.client_metadata?.image_capture_status === 'unavailable';
  results.safe_text_rendering = state.response.textContent.includes('<img src=x onerror=alert(1)>') && !state.response.querySelector('img');
  results.citation_rendering = state.response.textContent.includes('Dashboard Payload') && state.response.textContent.includes('Synthetic payload');
  results.focus_on_response = document.activeElement?.classList.contains('insights-response-heading');

  const second = helpers.createInsightsState({ ...payload, question_id: 'q2', chart_id: 'dashboard_01_pit_production_q2' }, {}, target);
  harness.appendChild(second.slot);
  second.toggle.click();
  await new Promise((resolve) => setTimeout(resolve, 25));
  results.independent_cards = state.open && second.open;

  responseMode = 'insufficient_evidence';
  second.suggestedButton.click();
  results.insufficient_evidence = await waitForStatus(second, 'insufficient_evidence') && second.response.textContent.includes('The evidence is insufficient.');
  const preparedRequest = postedRequests.at(-1);
  results.prepared_action_and_image = preparedRequest?.action === 'suggested_question'
    && preparedRequest?.chart_image?.mime_type === 'image/png'
    && preparedRequest?.client_metadata?.image_capture_status === 'captured';

  responseMode = 'pending';
  state.summarizeButton.click();
  results.loading_state = await waitForStatus(state, 'loading');
  state.cancelButton.click();
  results.cancel_behavior = state.status === 'cancelled' && !state.summarizeButton.disabled;

  const originalSetTimeout = window.setTimeout;
  window.setTimeout = (callback, delay, ...args) => originalSetTimeout(callback, delay === 70000 ? 10 : delay, ...args);
  state.summarizeButton.click();
  results.timeout_rendering = await waitForStatus(state, 'error') && state.statusRegion.textContent.includes('timed out');
  window.setTimeout = originalSetTimeout;

  responseMode = 'failure';
  second.summarizeButton.click();
  const panelFailed = await waitForStatus(second, 'unavailable');
  responseMode = 'answered';
  state.suggestedButton.click();
  const otherRecovered = await waitForStatus(state, 'answered');
  results.failed_panel_isolation = panelFailed && otherRecovered;

  state.closeButton.click();
  results.close_and_focus_restore = !state.open && document.activeElement === state.toggle;

  helpers.resetInsightsHealth();
  window.fetch = async () => { throw new TypeError('offline'); };
  const offline = helpers.createInsightsState({ ...payload, question_id: 'q3', chart_id: 'dashboard_01_pit_production_q3' }, {}, target);
  harness.appendChild(offline.slot);
  offline.toggle.click();
  await new Promise((resolve) => setTimeout(resolve, 40));
  results.static_unavailable = offline.status === 'unavailable' && offline.statusRegion.textContent.includes('deterministic analysis remain available');

  try {
    const capture = await helpers.captureVisualization(target);
    results.native_capture = capture.mime_type === 'image/png' && capture.width > 0 && capture.height > 0 && capture.sha256.length === 64;
  } catch (error) {
    results.native_capture = false;
    results.native_capture_error = String(error?.message || error);
  }
  results.capture_excludes_card = !target.querySelector('.insights-card');
  results.capture_component_coverage = Boolean(target.querySelector('svg') && target.querySelector('canvas') && target.querySelector('table'));
  results.responsive_wrapping = window.innerWidth > 800 || getComputedStyle(state.slot.querySelector('.insights-actions')).gridTemplateColumns.split(' ').length === 1;
  output.dataset.complete = 'true';
  output.textContent = JSON.stringify(results);
}());
