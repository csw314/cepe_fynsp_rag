(() => {
  'use strict';

  const PAYLOAD_ROOT = '../../../data/curated/dashboard_payloads/dashboard_01_pit_production/';
  const PAYLOAD_FILES = {
    q1: 'q1_funding_by_year_level.json',
    q2: 'q2_funding_by_organization.json',
    q3: 'q3_site_distribution.json',
    q4: 'q4_above_baseline_program_requests.json',
    q5: 'q5_data_quality_findings.json',
    q6: 'q6_crosscuts_site_splits_reconciliation.json',
  };
  const FUNDING_COLORS = { Baseline: '#4b6a88', ROT: '#d17b33', UFR: '#a64d5f' };

  function text(value) {
    return value === null || value === undefined || value === '' ? 'Not available' : String(value);
  }

  function formatDollar(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Not available';
    const amount = Number(value);
    const sign = amount < 0 ? '-' : '';
    const absolute = Math.abs(amount);
    if (absolute >= 1e9) return `${sign}$${(absolute / 1e9).toFixed(1)}B`;
    if (absolute >= 1e6) return `${sign}$${(absolute / 1e6).toFixed(1)}M`;
    if (absolute >= 1e3) return `${sign}$${(absolute / 1e3).toFixed(1)}K`;
    return `${sign}$${absolute.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }

  function formatPercent(value) {
    return value === null || value === undefined ? 'Not available' : `${(Number(value) * 100).toFixed(1)}%`;
  }

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function makeTable(columns, rows) {
    const wrapper = element('div', 'table-wrap');
    const table = element('table', 'data-table');
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    columns.forEach((column) => headerRow.appendChild(element('th', '', column.label)));
    thead.appendChild(headerRow);
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    if (rows.length === 0) {
      const row = document.createElement('tr');
      const cell = element('td', 'empty-cell', 'No matching records were available.');
      cell.colSpan = columns.length;
      row.appendChild(cell);
      tbody.appendChild(row);
    } else {
      rows.forEach((item) => {
        const row = document.createElement('tr');
        columns.forEach((column) => row.appendChild(element('td', '', column.value(item))));
        tbody.appendChild(row);
      });
    }
    table.appendChild(tbody);
    wrapper.appendChild(table);
    return wrapper;
  }

  function renderMetricCards(container, cards) {
    container.replaceChildren();
    cards.forEach((card) => {
      const panel = element('div', 'metric-card');
      panel.appendChild(element('span', 'metric-label', text(card.label)));
      panel.appendChild(element('strong', 'metric-value', text(card.display)));
      container.appendChild(panel);
    });
  }

  function renderRankedBars(container, data, labelKey, amountKey = 'amount') {
    container.replaceChildren();
    const figure = element('figure', 'ranked-chart');
    figure.setAttribute('role', 'img');
    figure.setAttribute('aria-label', 'Ranked funding visualization. The detailed table below provides exact values.');
    const max = Math.max(...data.map((row) => Math.abs(Number(row[amountKey]) || 0)), 0);
    const chartData = data.slice(0, 15);
    chartData.forEach((row) => {
      const chartRow = element('div', 'ranked-row');
      chartRow.appendChild(element('span', 'ranked-label', text(row[labelKey])));
      const track = element('div', 'bar-track');
      const bar = element('div', Number(row[amountKey]) < 0 ? 'bar-fill negative-bar' : 'bar-fill');
      bar.style.width = `${max ? (Math.abs(Number(row[amountKey]) || 0) / max) * 100 : 0}%`;
      bar.setAttribute('aria-hidden', 'true');
      track.appendChild(bar);
      chartRow.appendChild(track);
      chartRow.appendChild(element('span', 'bar-value', row.amount_display || formatDollar(row[amountKey])));
      figure.appendChild(chartRow);
    });
    container.appendChild(figure);
  }

  function renderQ1(container, data) {
    container.replaceChildren();
    const years = [...new Set(data.map((row) => row.fiscal_year))];
    const totals = Object.fromEntries(years.map((year) => [
      year,
      data.filter((row) => row.fiscal_year === year).reduce((sum, row) => sum + Number(row.amount || 0), 0),
    ]));
    const max = Math.max(...Object.values(totals), 0);
    const figure = element('figure', 'stacked-chart');
    figure.setAttribute('role', 'img');
    figure.setAttribute('aria-label', 'Stacked bar chart of funding by fiscal year and funding level. Exact values are available in the table below.');
    years.forEach((year) => {
      const column = element('div', 'stacked-column');
      const stack = element('div', 'stacked-bar');
      stack.style.height = `${max ? Math.max(8, (totals[year] / max) * 180) : 8}px`;
      data.filter((row) => row.fiscal_year === year).forEach((row) => {
        const segment = element('div', 'stack-segment');
        segment.style.height = `${totals[year] ? (Number(row.amount || 0) / totals[year]) * 100 : 0}%`;
        segment.style.backgroundColor = FUNDING_COLORS[row.funding_level] || '#758898';
        segment.title = `${row.funding_level}: ${row.amount_display}`;
        stack.appendChild(segment);
      });
      column.appendChild(stack);
      column.appendChild(element('strong', 'stacked-year', year));
      column.appendChild(element('span', 'stacked-total', formatDollar(totals[year])));
      figure.appendChild(column);
    });
    container.appendChild(figure);
    const legend = element('p', 'chart-legend');
    ['Baseline', 'ROT', 'UFR'].forEach((level) => {
      const item = element('span', 'legend-item');
      const swatch = element('span', 'legend-swatch');
      swatch.style.backgroundColor = FUNDING_COLORS[level];
      item.appendChild(swatch);
      item.appendChild(document.createTextNode(level));
      legend.appendChild(item);
    });
    container.appendChild(legend);
    container.appendChild(makeTable([
      { label: 'Fiscal year', value: (row) => row.fiscal_year },
      { label: 'Funding level', value: (row) => row.funding_level },
      { label: 'Programmed amount', value: (row) => row.amount_display },
    ], data));
  }

  function renderQ2(container, data) {
    renderRankedBars(container, data, 'organization');
    container.appendChild(makeTable([
      { label: 'Rank', value: (row) => row.rank },
      { label: 'Organization / Sub Office', value: (row) => row.organization },
      { label: 'Funding', value: (row) => row.amount_display },
      { label: 'Share', value: (row) => formatPercent(row.share_of_total) },
    ], data));
  }

  function renderQ3(container, data) {
    renderRankedBars(container, data, 'site');
    container.appendChild(makeTable([
      { label: 'Rank', value: (row) => row.rank },
      { label: 'Site', value: (row) => row.site },
      { label: 'Funding', value: (row) => row.amount_display },
      { label: 'Share', value: (row) => formatPercent(row.share_of_total) },
    ], data));
  }

  function renderQ4(container, data) {
    renderRankedBars(container, data, 'program_request');
    container.appendChild(makeTable([
      { label: 'Rank', value: (row) => row.rank },
      { label: 'Program request', value: (row) => row.program_request },
      { label: 'ROT/UFR funding', value: (row) => row.amount_display },
      { label: 'Cumulative share', value: (row) => formatPercent(row.cumulative_share) },
    ], data));
  }

  function renderQ5(container, data) {
    container.replaceChildren();
    const scorecard = element('div', 'finding-scorecard');
    const reviewed = data.filter((row) => row.status === 'evaluated' && Number(row.row_count) > 0);
    const high = reviewed.filter((row) => row.severity === 'high' || row.severity === 'critical');
    scorecard.appendChild(element('div', 'finding-stat', `${reviewed.length} finding categories with affected rows`));
    scorecard.appendChild(element('div', 'finding-stat high-finding', `${high.length} high-severity review triggers`));
    container.appendChild(scorecard);
    const table = makeTable([
      { label: 'Rule', value: (row) => row.rule_id },
      { label: 'Severity', value: (row) => row.severity },
      { label: 'Status', value: (row) => row.status },
      { label: 'Finding', value: (row) => row.title },
      { label: 'Rows', value: (row) => row.row_count },
      { label: 'Affected dollars', value: (row) => row.affected_dollars_display },
      { label: 'Source layer', value: (row) => row.source_submission_type },
      { label: 'Review detail', value: (row) => row.details },
    ], data);
    container.appendChild(table);
  }

  function renderQ6(container, data) {
    container.replaceChildren();
    container.appendChild(makeTable([
      { label: 'Funding level', value: (row) => row.funding_level },
      { label: 'Federal Crosscuts', value: (row) => row.federal_crosscuts_display },
      { label: 'Federal Site Splits', value: (row) => row.federal_site_splits_display },
      { label: 'Variance (Site Splits − Crosscuts)', value: (row) => row.variance_display },
      { label: 'Variance %', value: (row) => formatPercent(row.variance_percent) },
    ], data));
  }

  function renderChart(container, payload) {
    if (payload.question_id === 'q1') return renderQ1(container, payload.data);
    if (payload.question_id === 'q2') return renderQ2(container, payload.data);
    if (payload.question_id === 'q3') return renderQ3(container, payload.data);
    if (payload.question_id === 'q4') return renderQ4(container, payload.data);
    if (payload.question_id === 'q5') return renderQ5(container, payload.data);
    return renderQ6(container, payload.data);
  }

  function renderAiSummary(container, payload) {
    container.replaceChildren();
    container.appendChild(element('h3', 'panel-heading', 'AI Summary'));
    container.appendChild(element('p', '', payload.plain_language_summary));
    const button = element('button', 'ask-button', 'Ask about this visualization');
    button.type = 'button';
    button.disabled = true;
    button.title = 'Live AskSage Q&A requires a configured backend endpoint and approved credentials.';
    container.appendChild(button);
    container.appendChild(element('p', 'panel-note', 'Live AskSage Q&A is disabled until a backend endpoint and approved AskSage credentials are configured.'));
  }

  function renderTraceability(container, payload) {
    container.replaceChildren();
    const traceability = payload.traceability;
    const details = document.createElement('details');
    const summary = element('summary', '', 'Traceability and source details');
    details.appendChild(summary);
    const list = element('dl', 'traceability-list');
    const fields = [
      ['Chart ID', traceability.chart_id],
      ['Source file', traceability.source_file],
      ['Submission layer', traceability.source_submission_type],
      ['Metric', traceability.metric_definition],
      ['Grouping', (traceability.grouping_columns || []).join(', ')],
      ['Value column', traceability.value_column],
      ['Source records', traceability.record_count],
      ['Row filter', JSON.stringify(traceability.row_filter)],
    ];
    fields.forEach(([label, value]) => {
      list.appendChild(element('dt', '', label));
      list.appendChild(element('dd', '', text(value)));
    });
    details.appendChild(list);
    const limitsHeading = element('h3', 'panel-heading', 'Data limitations');
    details.appendChild(limitsHeading);
    const limits = element('ul', 'limitations-list');
    (traceability.limitations || []).forEach((limit) => limits.appendChild(element('li', '', limit)));
    details.appendChild(limits);
    const lineage = traceability.lineage || {};
    const lineageNote = Array.isArray(lineage.source_row_id_sample)
      ? `${lineage.source_row_id_count || lineage.source_row_id_sample.length} source-row identifiers are retained for lineage${lineage.lineage_truncated ? '; the displayed sample is bounded' : ''}.`
      : 'Lineage identifiers are retained separately for each source submission layer.';
    details.appendChild(element('p', 'panel-note', lineageNote));
    container.appendChild(details);
  }

  async function getJson(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Unable to load ${path} (${response.status})`);
    return response.json();
  }

  function showUnavailable(message) {
    document.querySelectorAll('.chart-placeholder').forEach((container) => {
      container.replaceChildren(element('p', 'load-error', message));
    });
  }

  async function renderDashboard() {
    try {
      const manifest = await getJson(`${PAYLOAD_ROOT}manifest.json`);
      const payloadEntries = await Promise.all(Object.entries(PAYLOAD_FILES).map(async ([questionId, file]) => [
        questionId,
        await getJson(`${PAYLOAD_ROOT}${file}`),
      ]));
      document.getElementById('dashboard-generation').textContent = `Last generated: ${new Date(manifest.generated_at).toLocaleString()}.`;
      payloadEntries.forEach(([questionId, payload]) => {
        const section = document.querySelector(`[data-question-id="${questionId}"]`);
        if (!section) return;
        renderMetricCards(section.querySelector('.metric-summary'), payload.metric_cards || []);
        renderChart(section.querySelector('.chart-placeholder'), payload);
        renderAiSummary(section.querySelector('.ai-summary'), payload);
        renderTraceability(section.querySelector('.traceability'), payload);
      });
    } catch (error) {
      showUnavailable('Generated dashboard data is unavailable. Run the Dashboard 1 payload build, then serve the project root over HTTP.');
      document.getElementById('dashboard-generation').textContent = 'Generated data could not be loaded. See the chart messages for the required build and serving steps.';
      console.error(error);
    }
  }

  document.addEventListener('DOMContentLoaded', renderDashboard);
})();
