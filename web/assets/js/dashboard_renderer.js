/* Shared static renderer for Dashboards 2-5. Generated JSON remains the source of all values. */
(function () {
  'use strict';

  function text(value) {
    if (value === null || value === undefined || value === '') return 'Not available';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function makeTable(rows) {
    const wrap = element('div', 'table-wrap');
    const table = element('table', 'data-table');
    const allKeys = [];
    rows.forEach((row) => Object.keys(row || {}).forEach((key) => {
      if (!allKeys.includes(key) && key !== 'source_row_id_sample') allKeys.push(key);
    }));
    const keys = allKeys.slice(0, 10);
    const head = document.createElement('thead');
    const headRow = document.createElement('tr');
    keys.forEach((key) => headRow.appendChild(element('th', '', key.replaceAll('_', ' '))));
    head.appendChild(headRow);
    table.appendChild(head);
    const body = document.createElement('tbody');
    rows.slice(0, 100).forEach((row) => {
      const tr = document.createElement('tr');
      keys.forEach((key) => tr.appendChild(element('td', '', text(row[key]))));
      body.appendChild(tr);
    });
    if (!rows.length) {
      const tr = document.createElement('tr');
      const cell = element('td', 'empty-cell', 'No generated rows are available for this question.');
      cell.colSpan = Math.max(keys.length, 1);
      tr.appendChild(cell);
      body.appendChild(tr);
    }
    table.appendChild(body);
    wrap.appendChild(table);
    return wrap;
  }

  function renderMetrics(container, metrics) {
    container.replaceChildren();
    (metrics || []).forEach((metric) => {
      const card = element('div', 'metric-card');
      card.appendChild(element('span', 'metric-label', metric.label));
      card.appendChild(element('strong', 'metric-value', metric.display || text(metric.value)));
      container.appendChild(card);
    });
  }

  function renderChart(container, payload) {
    container.replaceChildren();
    container.appendChild(element('h3', 'panel-heading', payload.chart_title));
    container.appendChild(makeTable(payload.data || []));
  }

  function renderAiSummary(container, payload) {
    container.replaceChildren();
    container.appendChild(element('h3', 'panel-heading', 'AI Summary'));
    container.appendChild(element('p', '', payload.plain_language_summary || payload.summary));
    const button = element('button', 'ask-button', 'Ask about this visualization');
    button.type = 'button';
    button.disabled = true;
    button.title = 'Live AskSage Q&A requires a configured backend endpoint and approved credentials.';
    container.appendChild(button);
    container.appendChild(element('p', 'panel-note', 'Live AskSage Q&A is disabled until a protected backend endpoint and approved credentials are configured.'));
  }

  function renderTraceability(container, payload) {
    container.replaceChildren();
    const traceability = payload.traceability || {};
    const details = document.createElement('details');
    details.appendChild(element('summary', '', 'Traceability and source details'));
    const list = element('dl', 'traceability-list');
    [
      ['Chart ID', payload.chart_id || traceability.chart_id],
      ['Source file', payload.source_file || traceability.source_file],
      ['Submission layer', payload.source_submission_type || traceability.source_submission_type],
      ['Metric', payload.metric_definition || traceability.metric_definition],
      ['Grouping', (payload.grouping_columns || traceability.grouping_columns || []).join(', ')],
      ['Value column', payload.value_column || traceability.value_column],
      ['Source records', payload.record_count || traceability.record_count],
      ['Row filter', JSON.stringify(payload.row_filter || traceability.row_filter || {})],
    ].forEach(([label, value]) => {
      list.appendChild(element('dt', '', label));
      list.appendChild(element('dd', '', text(value)));
    });
    details.appendChild(list);
    details.appendChild(element('h3', 'panel-heading', 'Data limitations'));
    const limitations = element('ul', 'limitations-list');
    (payload.limitations || traceability.limitations || []).forEach((limit) => limitations.appendChild(element('li', '', limit)));
    details.appendChild(limitations);
    const lineage = traceability.lineage || {};
    details.appendChild(element('p', 'panel-note', lineage.source_row_id_count === null
      ? 'This derived finding links to upstream aggregate dashboard evidence; inspect its cited payloads for bounded source-row lineage identifiers.'
      : `${lineage.source_row_id_count || 0} source-row identifiers are retained for lineage${lineage.lineage_truncated ? '; displayed samples are bounded' : ''}.`));
    container.appendChild(details);
  }

  function showUnavailable(message) {
    document.querySelectorAll('.chart-placeholder').forEach((container) => {
      container.replaceChildren(element('p', 'load-error', message));
    });
  }

  async function render(config) {
    try {
      const manifest = await loadDashboardPayload(`${config.payloadRoot}manifest.json`);
      const entries = await Promise.all(Object.entries(config.payloadFiles).map(async ([questionId, file]) => [
        questionId,
        await loadDashboardPayload(`${config.payloadRoot}${file}`),
      ]));
      const status = document.getElementById('dashboard-generation');
      if (status) status.textContent = `Last generated: ${new Date(manifest.generated_at).toLocaleString()}.`;
      entries.forEach(([questionId, payload]) => {
        const section = document.querySelector(`[data-question-id="${questionId}"]`);
        if (!section) return;
        renderMetrics(section.querySelector('.metric-summary'), payload.metric_cards);
        renderChart(section.querySelector('.chart-placeholder'), payload);
        renderAiSummary(section.querySelector('.ai-summary'), payload);
        renderTraceability(section.querySelector('.traceability'), payload);
      });
    } catch (error) {
      showUnavailable('Generated dashboard data is unavailable. Run the dashboard payload build, then serve the repository root over HTTP.');
      const status = document.getElementById('dashboard-generation');
      if (status) status.textContent = 'Generated data could not be loaded. See the chart messages for required build and serving steps.';
      console.error(error);
    }
  }

  window.CepeDashboardRenderer = { render };
})();
