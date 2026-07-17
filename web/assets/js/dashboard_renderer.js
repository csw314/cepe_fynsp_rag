/* CEPE dependency-free renderer for validated, aggregate-only dashboard payloads. */
(function () {
  'use strict';

  const PAGE_SIZE = 25;
  const CHART_LIMIT = 15;
  const MONEY = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
  const NUMBER = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
  const REQUIRED_PAYLOAD_FIELDS = [
    'schema_version', 'dashboard_id', 'question_id', 'question_text', 'data', 'columns',
    'visualization', 'filter_options', 'active_filter_state', 'quality_summary', 'traceability',
    'source_metadata', 'narrative', 'ontology_references', 'generated_metadata',
  ];

  function el(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function asText(value) {
    if (value === null || value === undefined || value === '') return 'Not available';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function titleCase(value) {
    return String(value).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function formatValue(value, format) {
    if (value === null || value === undefined || value === '') return 'Not available';
    const number = Number(value);
    if (format === 'currency' && Number.isFinite(number)) return MONEY.format(number);
    if (format === 'percentage' && Number.isFinite(number)) {
      const normalized = Math.abs(number) <= 1 ? number * 100 : number;
      return `${NUMBER.format(normalized)}%`;
    }
    if ((format === 'number' || typeof value === 'number') && Number.isFinite(number)) return NUMBER.format(number);
    return asText(value);
  }

  function validatePayload(payload) {
    if (!payload || typeof payload !== 'object') throw new Error('Payload is not a JSON object.');
    const missing = REQUIRED_PAYLOAD_FIELDS.filter((field) => !(field in payload));
    if (missing.length) throw new Error(`Payload is missing required fields: ${missing.join(', ')}.`);
    if (payload.schema_version !== '2.0') throw new Error(`Unsupported payload schema ${asText(payload.schema_version)}; expected 2.0.`);
    if (!Array.isArray(payload.data) || !Array.isArray(payload.columns)) throw new Error('Payload data and columns must be arrays.');
    if (!payload.visualization.type) throw new Error('Payload visualization type is missing.');
    return payload;
  }

  function safeCsvCell(value) {
    let rendered = value === null || value === undefined ? '' : (typeof value === 'object' ? JSON.stringify(value) : String(value));
    if (/^[=+\-@]/.test(rendered)) rendered = `'${rendered}`;
    return `"${rendered.replaceAll('"', '""')}"`;
  }

  function downloadCsv(payload, rows, columns, activeFilters) {
    const metadata = [
      ['payload_id', payload.chart_id],
      ['question', payload.question_text],
      ['active_filters', JSON.stringify({ ...payload.active_filter_state, ...activeFilters })],
      ['aggregate_only', 'true'],
    ];
    const lines = metadata.map(([key, value]) => `${safeCsvCell(key)},${safeCsvCell(value)}`);
    lines.push('');
    lines.push(columns.map((column) => safeCsvCell(column.label)).join(','));
    rows.forEach((row) => lines.push(columns.map((column) => safeCsvCell(row[column.key])).join(',')));
    const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${payload.chart_id}_filtered_aggregate.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function compareValues(left, right, direction) {
    const a = left === null || left === undefined ? '' : left;
    const b = right === null || right === undefined ? '' : right;
    const aNumber = Number(a);
    const bNumber = Number(b);
    const result = Number.isFinite(aNumber) && Number.isFinite(bNumber)
      ? aNumber - bNumber
      : String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
    return direction === 'asc' ? result : -result;
  }

  function makeDataTable(payload, rows, activeFilters) {
    const section = el('section', 'evidence-table');
    const allColumns = payload.columns.map((column) => ({ ...column }));
    const state = { search: '', sortKey: null, sortDirection: 'asc', page: 1, visible: new Set(allColumns.filter((c) => c.visible !== false).map((c) => c.key)) };
    const controls = el('div', 'table-controls');
    const searchLabel = el('label', 'table-search');
    searchLabel.appendChild(el('span', '', 'Search aggregate records'));
    const search = document.createElement('input');
    search.type = 'search';
    search.setAttribute('aria-label', `Search ${payload.question_id} aggregate records`);
    searchLabel.appendChild(search);
    controls.appendChild(searchLabel);

    const columnsControl = document.createElement('details');
    columnsControl.className = 'column-control';
    columnsControl.appendChild(el('summary', '', 'Visible columns'));
    const columnChoices = el('div', 'column-choices');
    allColumns.forEach((column) => {
      const label = el('label', 'checkbox-label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = state.visible.has(column.key);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) state.visible.add(column.key); else state.visible.delete(column.key);
        state.page = 1;
        draw();
      });
      label.append(checkbox, document.createTextNode(column.label));
      columnChoices.appendChild(label);
    });
    columnsControl.appendChild(columnChoices);
    controls.appendChild(columnsControl);

    const exportButton = el('button', 'secondary-button', 'Export filtered aggregate CSV');
    exportButton.type = 'button';
    controls.appendChild(exportButton);
    section.appendChild(controls);

    const count = el('p', 'table-count');
    section.appendChild(count);
    const wrap = el('div', 'table-wrap');
    section.appendChild(wrap);
    const pager = el('div', 'pager');
    section.appendChild(pager);

    function filteredRows() {
      const query = state.search.trim().toLocaleLowerCase();
      let result = rows.filter((row) => !query || allColumns.some((column) => asText(row[column.key]).toLocaleLowerCase().includes(query)));
      if (state.sortKey) result = result.slice().sort((a, b) => compareValues(a[state.sortKey], b[state.sortKey], state.sortDirection));
      return result;
    }

    function draw() {
      const result = filteredRows();
      const visibleColumns = allColumns.filter((column) => state.visible.has(column.key));
      const pageCount = Math.max(1, Math.ceil(result.length / PAGE_SIZE));
      state.page = Math.min(state.page, pageCount);
      const start = (state.page - 1) * PAGE_SIZE;
      const displayed = result.slice(start, start + PAGE_SIZE);
      count.textContent = `${NUMBER.format(result.length)} of ${NUMBER.format(rows.length)} aggregate records match. Showing ${result.length ? start + 1 : 0}–${Math.min(start + PAGE_SIZE, result.length)}. No records are silently discarded.`;
      wrap.replaceChildren();
      const table = el('table', 'data-table');
      const caption = el('caption', 'sr-only', `Aggregate evidence for ${payload.question_text}`);
      table.appendChild(caption);
      const head = document.createElement('thead');
      const headRow = document.createElement('tr');
      visibleColumns.forEach((column) => {
        const th = el('th');
        th.scope = 'col';
        const button = el('button', 'sort-button', column.label);
        button.type = 'button';
        if (state.sortKey === column.key) {
          th.setAttribute('aria-sort', state.sortDirection === 'asc' ? 'ascending' : 'descending');
          button.appendChild(document.createTextNode(state.sortDirection === 'asc' ? ' ▲' : ' ▼'));
        }
        button.addEventListener('click', () => {
          if (state.sortKey === column.key) state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
          else { state.sortKey = column.key; state.sortDirection = 'asc'; }
          draw();
        });
        th.appendChild(button);
        headRow.appendChild(th);
      });
      head.appendChild(headRow);
      table.appendChild(head);
      const body = document.createElement('tbody');
      displayed.forEach((row) => {
        const tr = document.createElement('tr');
        visibleColumns.forEach((column) => {
          const td = el('td', column.format === 'currency' || column.format === 'number' ? 'numeric' : '', formatValue(row[column.key], column.format));
          if (column.format === 'status' || column.key === 'severity') td.dataset.status = String(row[column.key] || 'unknown').toLowerCase();
          tr.appendChild(td);
        });
        body.appendChild(tr);
      });
      if (!displayed.length) {
        const tr = document.createElement('tr');
        const td = el('td', 'empty-cell', 'No aggregate records match the current filters and search.');
        td.colSpan = Math.max(1, visibleColumns.length);
        tr.appendChild(td);
        body.appendChild(tr);
      }
      table.appendChild(body);
      wrap.appendChild(table);
      pager.replaceChildren();
      const previous = el('button', 'secondary-button', 'Previous');
      previous.type = 'button'; previous.disabled = state.page <= 1;
      previous.addEventListener('click', () => { state.page -= 1; draw(); });
      const page = el('span', 'page-status', `Page ${state.page} of ${pageCount}`);
      const next = el('button', 'secondary-button', 'Next');
      next.type = 'button'; next.disabled = state.page >= pageCount;
      next.addEventListener('click', () => { state.page += 1; draw(); });
      pager.append(previous, page, next);
      exportButton.onclick = () => downloadCsv(payload, result, visibleColumns, activeFilters);
    }

    search.addEventListener('input', () => { state.search = search.value; state.page = 1; draw(); });
    draw();
    return section;
  }

  function crossFilterButton(label, field, value, applyFilter, className = 'chart-filter-button') {
    const button = el('button', className, label);
    button.type = 'button';
    button.title = `Filter dashboard to ${titleCase(field)}: ${value}`;
    button.addEventListener('click', () => applyFilter(field, String(value)));
    return button;
  }

  function numericRows(payload, rows) {
    const y = payload.visualization.y;
    return rows.filter((row) => Number.isFinite(Number(row[y])));
  }

  function renderRankedChart(payload, rows, applyFilter) {
    const x = payload.visualization.x;
    const y = payload.visualization.y;
    const ranked = numericRows(payload, rows).slice().sort((a, b) => Math.abs(Number(b[y])) - Math.abs(Number(a[y])));
    const displayed = ranked.slice(0, CHART_LIMIT);
    const max = Math.max(0, ...displayed.map((row) => Math.abs(Number(row[y]))));
    const figure = el('figure', 'ranked-chart');
    figure.setAttribute('aria-label', payload.visualization.accessible_description);
    displayed.forEach((row) => {
      const line = el('div', 'ranked-row');
      line.appendChild(crossFilterButton(asText(row[x]), x, row[x], applyFilter, 'chart-label-button'));
      const track = el('div', 'bar-track');
      const bar = el('span', Number(row[y]) < 0 ? 'bar-fill negative' : 'bar-fill');
      bar.style.width = `${max ? Math.max(1, Math.abs(Number(row[y])) / max * 100) : 0}%`;
      bar.setAttribute('aria-hidden', 'true');
      track.appendChild(bar);
      line.append(track, el('span', 'bar-value numeric', formatValue(row[y], payload.visualization.format.y)));
      figure.appendChild(line);
    });
    if (!displayed.length) figure.appendChild(el('p', 'empty-cell', 'No numeric aggregate records match the active filters.'));
    figure.appendChild(el('figcaption', 'chart-caption', `${displayed.length} of ${ranked.length} ranked aggregate categories shown in the chart; the searchable table and CSV contain the entire filtered view.`));
    return figure;
  }

  function renderStackedChart(payload, rows, applyFilter) {
    const { x, y, series } = payload.visualization;
    const groups = new Map();
    numericRows(payload, rows).forEach((row) => {
      const key = asText(row[x]);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    });
    const totals = [...groups.values()].map((items) => items.reduce((sum, row) => sum + Math.abs(Number(row[y])), 0));
    const max = Math.max(0, ...totals);
    const figure = el('figure', 'stacked-chart');
    figure.setAttribute('aria-label', payload.visualization.accessible_description);
    [...groups.entries()].slice(0, CHART_LIMIT).forEach(([key, items], index) => {
      const total = totals[index];
      const column = el('div', 'stacked-column');
      const stack = el('div', 'stacked-bar');
      stack.style.height = `${max ? Math.max(12, total / max * 210) : 12}px`;
      items.forEach((row, itemIndex) => {
        const segment = crossFilterButton('', series, row[series], applyFilter, `stack-segment series-${itemIndex % 6}`);
        segment.style.height = `${total ? Math.abs(Number(row[y])) / total * 100 : 0}%`;
        segment.setAttribute('aria-label', `${asText(row[series])}: ${formatValue(row[y], payload.visualization.format.y)}`);
        stack.appendChild(segment);
      });
      column.append(stack, crossFilterButton(key, x, key, applyFilter, 'chart-label-button'), el('span', 'stacked-total numeric', formatValue(total, payload.visualization.format.y)));
      figure.appendChild(column);
    });
    figure.appendChild(el('figcaption', 'chart-caption', 'Select a labeled category or segment to apply an aggregate cross-filter. Exact values are in the accessible table.'));
    return figure;
  }

  function renderHeatmap(payload, rows, applyFilter) {
    const { x, y, series } = payload.visualization;
    const xValues = [...new Set(rows.map((row) => asText(row[x])))];
    const seriesValues = [...new Set(rows.map((row) => asText(row[series])))];
    const values = numericRows(payload, rows).map((row) => Math.abs(Number(row[y])));
    const max = Math.max(0, ...values);
    const grid = el('div', 'heatmap-wrap');
    const table = el('table', 'heatmap');
    const caption = el('caption', 'sr-only', payload.visualization.accessible_description);
    table.appendChild(caption);
    const thead = document.createElement('thead');
    const header = document.createElement('tr');
    const corner = el('th', '', titleCase(series)); corner.scope = 'col'; header.appendChild(corner);
    xValues.forEach((value) => { const th = el('th'); th.scope = 'col'; th.appendChild(crossFilterButton(value, x, value, applyFilter, 'heatmap-filter')); header.appendChild(th); });
    thead.appendChild(header); table.appendChild(thead);
    const tbody = document.createElement('tbody');
    seriesValues.slice(0, CHART_LIMIT).forEach((seriesValue) => {
      const tr = document.createElement('tr');
      const th = document.createElement('th'); th.scope = 'row'; th.appendChild(crossFilterButton(seriesValue, series, seriesValue, applyFilter, 'heatmap-filter')); tr.appendChild(th);
      xValues.forEach((xValue) => {
        const row = rows.find((item) => asText(item[x]) === xValue && asText(item[series]) === seriesValue);
        const value = row && Number.isFinite(Number(row[y])) ? Number(row[y]) : null;
        const td = el('td', 'heat-cell', formatValue(value, payload.visualization.format.y));
        td.style.setProperty('--intensity', max && value !== null ? String(Math.min(1, Math.abs(value) / max)) : '0');
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody); grid.appendChild(table);
    grid.appendChild(el('p', 'chart-caption', `${Math.min(seriesValues.length, CHART_LIMIT)} of ${seriesValues.length} row categories shown; darker cells indicate greater magnitude and every cell retains its numeric label.`));
    return grid;
  }

  function renderReconciliation(payload, rows, applyFilter) {
    const figure = el('figure', 'variance-chart');
    figure.setAttribute('aria-label', payload.visualization.accessible_description);
    const values = rows.map((row) => Math.abs(Number(row.variance_amount) || 0));
    const max = Math.max(0, ...values);
    rows.forEach((row) => {
      const line = el('div', 'variance-row');
      line.appendChild(crossFilterButton(asText(row.funding_level), 'funding_level', row.funding_level, applyFilter, 'chart-label-button'));
      const track = el('div', 'variance-track');
      const marker = el('span', Number(row.variance_amount) < 0 ? 'variance-bar negative' : 'variance-bar positive');
      marker.style.width = `${max ? Math.abs(Number(row.variance_amount)) / max * 50 : 0}%`;
      marker.style.left = Number(row.variance_amount) < 0 ? `${50 - (max ? Math.abs(Number(row.variance_amount)) / max * 50 : 0)}%` : '50%';
      track.appendChild(marker);
      line.append(track, el('span', 'numeric', formatValue(row.variance_amount, 'currency')));
      figure.appendChild(line);
    });
    figure.appendChild(el('figcaption', 'chart-caption', 'Bars left of center are negative; bars right of center are positive. Text labels preserve direction without relying on color.'));
    return figure;
  }

  function renderDiverging(payload, rows, applyFilter) {
    const { x, y, series } = payload.visualization;
    const valid = numericRows(payload, rows);
    const max = Math.max(0, ...valid.map((row) => Math.abs(Number(row[y]))));
    const figure = el('figure', 'variance-chart');
    figure.setAttribute('aria-label', payload.visualization.accessible_description);
    valid.slice(0, CHART_LIMIT).forEach((row) => {
      const label = series ? `${asText(row[series])} · ${asText(row[x])}` : asText(row[x]);
      const value = Number(row[y]);
      const line = el('div', 'variance-row');
      line.appendChild(crossFilterButton(label, x, row[x], applyFilter, 'chart-label-button'));
      const track = el('div', 'variance-track');
      const bar = el('span', value < 0 ? 'variance-bar negative' : 'variance-bar positive');
      const width = max ? Math.abs(value) / max * 50 : 0;
      bar.style.width = `${width}%`;
      bar.style.left = value < 0 ? `${50 - width}%` : '50%';
      track.appendChild(bar);
      line.append(track, el('span', 'numeric', formatValue(value, payload.visualization.format.y)));
      figure.appendChild(line);
    });
    figure.appendChild(el('figcaption', 'chart-caption', `${Math.min(valid.length, CHART_LIMIT)} of ${valid.length} signed aggregate changes shown. Negative values extend left of center; positive values extend right.`));
    return figure;
  }

  function renderTimeline(payload, rows, applyFilter) {
    const scheduled = rows.filter((row) => row.start_date && row.end_date && !Number.isNaN(Date.parse(row.start_date)) && !Number.isNaN(Date.parse(row.end_date)));
    const years = scheduled.flatMap((row) => [new Date(row.start_date).getUTCFullYear(), new Date(row.end_date).getUTCFullYear()]);
    const minimum = Math.min(...years, 2028);
    const maximum = Math.max(...years, 2032);
    const span = Math.max(1, maximum - minimum);
    const figure = el('figure', 'timeline-chart');
    figure.setAttribute('aria-label', payload.visualization.accessible_description);
    scheduled.slice(0, CHART_LIMIT).forEach((row) => {
      const start = new Date(row.start_date).getUTCFullYear();
      const end = new Date(row.end_date).getUTCFullYear();
      const line = el('div', 'timeline-row');
      line.appendChild(crossFilterButton(asText(row.acquisition_name || row.acquisition_id), 'acquisition_type', row.acquisition_type, applyFilter, 'chart-label-button'));
      const track = el('div', 'timeline-track');
      const range = el('span', row.schedule_status === 'within_schedule' ? 'timeline-range' : 'timeline-range review');
      range.style.left = `${(start - minimum) / span * 100}%`;
      range.style.width = `${Math.max(1, (end - start) / span * 100)}%`;
      range.setAttribute('aria-label', `${start} through ${end}; ${asText(row.schedule_status)}`);
      track.appendChild(range);
      line.append(track, el('span', 'numeric', `${start}–${end}`));
      figure.appendChild(line);
    });
    if (!scheduled.length) figure.appendChild(el('p', 'empty-cell', 'No valid start/end date ranges match the active filters.'));
    figure.appendChild(el('figcaption', 'chart-caption', `Timeline scale FY${minimum}–FY${maximum}. ${scheduled.length} valid ranges are available; invalid or missing dates remain visible in the complete evidence table.`));
    return figure;
  }

  function renderBubble(payload, rows, applyFilter) {
    const { x, y, series } = payload.visualization;
    const valid = numericRows(payload, rows).filter((row) => Number.isFinite(Number(row[x])));
    const xValues = valid.map((row) => Number(row[x]));
    const yValues = valid.map((row) => Number(row[y]));
    const minX = Math.min(...xValues, 0);
    const maxX = Math.max(...xValues, 1);
    const minY = Math.min(...yValues, 0);
    const maxY = Math.max(...yValues, 1);
    const plot = el('figure', 'bubble-chart');
    plot.setAttribute('aria-label', payload.visualization.accessible_description);
    valid.slice(0, 30).forEach((row, index) => {
      const xPosition = (Number(row[x]) - minX) / Math.max(1, maxX - minX) * 90 + 5;
      const yPosition = 92 - (Number(row[y]) - minY) / Math.max(1, maxY - minY) * 82;
      const diameter = Math.max(18, Math.min(62, 18 + Math.sqrt(Math.abs(Number(row[y])) / Math.max(1, maxY)) * 44));
      const bubble = crossFilterButton('', series || x, row[series] || row[x], applyFilter, `bubble series-${index % 6}`);
      bubble.style.left = `calc(${xPosition}% - ${diameter / 2}px)`;
      bubble.style.top = `calc(${yPosition}% - ${diameter / 2}px)`;
      bubble.style.width = `${diameter}px`;
      bubble.style.height = `${diameter}px`;
      bubble.setAttribute('aria-label', `${asText(row.program_request || row[x])}; ${titleCase(x)} ${asText(row[x])}; ${formatValue(row[y], payload.visualization.format.y)}; ${asText(row[series])}`);
      plot.appendChild(bubble);
    });
    plot.append(el('span', 'bubble-y-label', titleCase(y)), el('span', 'bubble-x-label', `${titleCase(x)} ${minX}–${maxX}`));
    plot.appendChild(el('figcaption', 'chart-caption', `${Math.min(valid.length, 30)} of ${valid.length} requests shown. Bubble size and vertical position encode aggregate dollars; horizontal position encodes priority tier. Exact values are in the table.`));
    return plot;
  }

  function renderFindingCards(payload, rows, applyFilter) {
    const grid = el('div', 'finding-grid');
    rows.slice(0, CHART_LIMIT).forEach((row) => {
      const severity = String(row.severity || row.overall_status || 'not_evaluated').toLowerCase();
      const card = el('article', 'finding-card'); card.dataset.status = severity;
      card.append(el('span', 'status-label', titleCase(severity)), el('h4', '', asText(row.title || row.theme || row.rule_id || row.section)));
      const amount = row.affected_dollars ?? row.materiality ?? row.row_count;
      card.appendChild(el('p', 'numeric', formatValue(amount, row.affected_dollars !== undefined || row.materiality !== undefined ? 'currency' : 'number')));
      const button = crossFilterButton(`Filter to ${titleCase(severity)}`, 'severity', severity, applyFilter, 'text-button');
      card.appendChild(button); grid.appendChild(card);
    });
    if (!rows.length) grid.appendChild(el('p', 'empty-cell', 'No findings match the active filters.'));
    return grid;
  }

  function renderChart(payload, rows, applyFilter) {
    const type = payload.visualization.type;
    if (type.includes('reconciliation') || type.includes('variance')) return renderReconciliation(payload, rows, applyFilter);
    if (type.includes('yoy_change') || type.includes('classified')) return renderDiverging(payload, rows, applyFilter);
    if (type.includes('schedule')) return renderTimeline(payload, rows, applyFilter);
    if (type.includes('bubble')) return renderBubble(payload, rows, applyFilter);
    if ((type.includes('heatmap') || type.includes('matrix')) && payload.visualization.series) return renderHeatmap(payload, rows, applyFilter);
    if (type === 'stacked_bar' || type === 'stacked_column') return renderStackedChart(payload, rows, applyFilter);
    if (type.includes('finding') || type.includes('scorecard') || type.includes('status')) return renderFindingCards(payload, rows, applyFilter);
    if (payload.visualization.x && payload.visualization.y) return renderRankedChart(payload, rows, applyFilter);
    return renderFindingCards(payload, rows, applyFilter);
  }

  function renderMetrics(container, metrics, payload, rows, activeFilters) {
    container.replaceChildren();
    const availableFields = new Set(payload.data.flatMap((row) => Object.keys(row)));
    const hasInteractiveFilters = Object.keys(activeFilters).some((field) => availableFields.has(field));
    const y = payload.visualization.y;
    const filteredValues = y ? rows.map((row) => Number(row[y])).filter(Number.isFinite) : [];
    if (hasInteractiveFilters) {
      const card = el('div', 'metric-card');
      const value = filteredValues.length ? filteredValues.reduce((sum, item) => sum + item, 0) : null;
      card.append(
        el('span', 'metric-label', filteredValues.length ? 'Filtered aggregate view' : 'Filtered aggregate records'),
        el('strong', 'metric-value numeric', filteredValues.length ? formatValue(value, payload.visualization.format.y) : NUMBER.format(rows.length)),
      );
      container.appendChild(card);
    }
    (metrics || []).forEach((metric) => {
      const card = el('div', 'metric-card');
      const label = hasInteractiveFilters ? `${metric.label} (build scope)` : metric.label;
      card.append(el('span', 'metric-label', label), el('strong', 'metric-value numeric', metric.display || formatValue(metric.value, metric.format)));
      container.appendChild(card);
    });
  }

  function renderNarrative(container, payload) {
    container.replaceChildren();
    (payload.narrative || []).forEach((record) => {
      const item = el('article', 'narrative-record');
      item.append(el('h3', 'panel-heading', titleCase(record.origin)), el('p', '', record.text));
      if (record.citations && record.citations.length) item.appendChild(el('p', 'citation-line', `Evidence: ${record.citations.join(', ')}`));
      container.appendChild(item);
    });
  }

  function renderTraceability(container, payload, activeFilters) {
    container.replaceChildren();
    const details = document.createElement('details');
    details.appendChild(el('summary', '', 'Traceability, metric, and lineage'));
    const trace = payload.traceability || {};
    const list = el('dl', 'traceability-list');
    const sources = (payload.source_metadata || []).map((source) => `${source.dataset}: ${source.source_file} (${source.submission_type || 'layer not specified'})`).join('; ');
    [
      ['Payload / chart ID', payload.chart_id],
      ['Metric definition', payload.metric_definition || trace.metric_definition],
      ['Source', sources],
      ['Grouping', (payload.grouping_columns || trace.grouping_columns || []).join(', ')],
      ['Value column', payload.value_column || trace.value_column],
      ['Aggregate record count', payload.data.length],
      ['Build filters', JSON.stringify(payload.active_filter_state)],
      ['Interactive filters', JSON.stringify(activeFilters)],
      ['Ontology references', (payload.ontology_references || []).join(', ')],
      ['Lineage', JSON.stringify(payload.lineage || trace.lineage || {})],
    ].forEach(([label, value]) => { list.append(el('dt', '', label), el('dd', '', asText(value))); });
    details.appendChild(list); container.appendChild(details);
  }

  function rowMatchesFilters(row, activeFilters) {
    return Object.entries(activeFilters).every(([field, selected]) => {
      if (!(field in row)) return true;
      return String(row[field]).toLocaleLowerCase() === String(selected).toLocaleLowerCase();
    });
  }

  function renderQuestion(section, payload, activeFilters, applyFilter) {
    const rows = payload.data.filter((row) => rowMatchesFilters(row, activeFilters));
    const chartContainer = section.querySelector('.chart-placeholder');
    const metrics = section.querySelector('.metric-summary');
    const narrative = section.querySelector('.narrative-summary, .ai-summary');
    const traceability = section.querySelector('.traceability');
    renderMetrics(metrics, payload.metrics || payload.metric_cards, payload, rows, activeFilters);
    chartContainer.replaceChildren();
    chartContainer.appendChild(el('h3', 'chart-title', payload.chart_title));
    const sourceLabel = (payload.source_metadata || []).map((source) => `${source.dataset}: ${source.source_file}`).join('; ');
    chartContainer.appendChild(el('p', 'chart-definition', `Metric: ${payload.metric_definition}`));
    chartContainer.appendChild(el('p', 'chart-source', `Source: ${sourceLabel || 'Not available'}`));
    const meta = el('div', 'chart-meta');
    meta.append(
      el('span', '', `Units: ${payload.visualization.format.y || 'as labeled'}`),
      el('span', '', `Build filters: ${JSON.stringify(payload.active_filter_state)}`),
      el('span', '', `Interactive filters: ${JSON.stringify(activeFilters)}`),
      el('span', '', `Completeness: ${asText(payload.quality_summary.financial_completeness?.aggregate_status || payload.quality_summary.overall_status)}`),
    );
    chartContainer.appendChild(meta);
    const warnings = payload.warnings || [];
    if (warnings.length) {
      const warning = el('aside', 'material-warning');
      warning.appendChild(el('strong', '', 'Material limitations'));
      const list = el('ul'); warnings.forEach((message) => list.appendChild(el('li', '', message))); warning.appendChild(list);
      chartContainer.appendChild(warning);
    }
    chartContainer.appendChild(renderChart(payload, rows, applyFilter));
    chartContainer.appendChild(makeDataTable(payload, rows, activeFilters));
    renderNarrative(narrative, payload);
    renderTraceability(traceability, payload, activeFilters);
    section.dataset.renderState = rows.length ? 'ready' : 'empty';
  }

  function renderPanelError(section, error) {
    if (!section) return;
    const chart = section.querySelector('.chart-placeholder');
    chart.replaceChildren(el('div', 'panel-error', `This question could not be rendered: ${error.message}`));
    section.dataset.renderState = 'invalid';
  }

  function renderHealth(manifest) {
    const container = document.getElementById('data-health');
    if (!container) return;
    const health = manifest.data_health || {};
    container.replaceChildren();
    const heading = el('div', 'health-heading');
    const status = el('strong', 'health-status', asText(health.overall_status));
    status.dataset.status = String(health.overall_status || 'not_evaluated').toLowerCase().replace(' ', '_');
    heading.append(el('h2', '', 'Dashboard data health'), status);
    container.appendChild(heading);
    const grid = el('dl', 'health-grid');
    [
      ['Dataset', health.source_dataset_identity], ['Source date', health.source_file_date],
      ['Generated', health.dashboard_generation_date], ['Scenario', health.scenario],
      ['Submission layer', health.submission_layer], ['Fiscal years', health.fiscal_year_scope],
      ['Source rows considered', health.source_rows_considered], ['Rows included', health.rows_included],
      ['Rows excluded', health.rows_excluded], ['Blank amounts', health.blank_monetary_values],
      ['Invalid amounts', health.invalid_monetary_values], ['Reconciliation', health.reconciliation_status],
    ].forEach(([label, value]) => grid.append(el('dt', '', label), el('dd', 'numeric', asText(value))));
    container.append(grid, el('p', 'health-rule', `${asText(health.quality_check_summary)} Status rule: ${asText(health.status_rule)}`));
  }

  function buildFilterBar(payloads, activeFilters, onChange) {
    const container = document.getElementById('dashboard-filters');
    if (!container) return;
    const options = new Map();
    payloads.forEach((payload) => Object.entries(payload.filter_options || {}).forEach(([field, values]) => {
      if (!options.has(field)) options.set(field, new Set());
      values.forEach((value) => options.get(field).add(String(value)));
    }));
    container.replaceChildren();
    const heading = el('div', 'filter-heading');
    heading.append(el('h2', '', 'Aggregate filters'), el('p', '', 'Filters apply only where the payload contains the selected aggregate dimension; overlapping submission layers are never added together.'));
    container.appendChild(heading);
    const controls = el('div', 'filter-controls');
    const selects = new Map();
    options.forEach((values, field) => {
      const label = el('label', 'filter-control'); label.appendChild(el('span', '', titleCase(field)));
      const select = document.createElement('select'); select.dataset.field = field;
      select.appendChild(new Option('All supported values', ''));
      [...values].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).forEach((value) => select.appendChild(new Option(value, value)));
      select.addEventListener('change', () => { if (select.value) activeFilters[field] = select.value; else delete activeFilters[field]; renderChips(); onChange(); });
      label.appendChild(select); controls.appendChild(label); selects.set(field, select);
    });
    const reset = el('button', 'secondary-button', 'Reset filters'); reset.type = 'button';
    reset.addEventListener('click', () => { Object.keys(activeFilters).forEach((key) => delete activeFilters[key]); selects.forEach((select) => { select.value = ''; }); renderChips(); onChange(); });
    controls.appendChild(reset); container.appendChild(controls);
    const chips = el('div', 'filter-chips'); chips.setAttribute('aria-label', 'Active filters'); container.appendChild(chips);
    const announcer = document.getElementById('filter-announcer');

    function renderChips() {
      chips.replaceChildren();
      Object.entries(activeFilters).forEach(([field, value]) => {
        const chip = el('button', 'filter-chip', `${titleCase(field)}: ${value} ×`); chip.type = 'button';
        chip.addEventListener('click', () => { delete activeFilters[field]; if (selects.has(field)) selects.get(field).value = ''; renderChips(); onChange(); });
        chips.appendChild(chip);
      });
      if (!Object.keys(activeFilters).length) chips.appendChild(el('span', 'no-filters', 'No interactive filters applied.'));
      if (announcer) announcer.textContent = Object.keys(activeFilters).length ? `Active filters changed: ${JSON.stringify(activeFilters)}` : 'All interactive filters cleared.';
    }

    renderChips();
    return function applyFilter(field, value) {
      if (!options.has(field) || !options.get(field).has(String(value))) return;
      activeFilters[field] = String(value);
      if (selects.has(field)) selects.get(field).value = String(value);
      renderChips(); onChange();
      container.scrollIntoView({ block: 'nearest' });
    };
  }

  async function render(config) {
    const status = document.getElementById('dashboard-generation');
    const manifestResult = await Promise.allSettled([loadDashboardPayload(`${config.payloadRoot}manifest.json`)]);
    if (manifestResult[0].status === 'rejected') {
      if (status) status.textContent = `Manifest unavailable: ${manifestResult[0].reason.message}`;
      document.querySelectorAll('[data-question-id]').forEach((section) => renderPanelError(section, manifestResult[0].reason));
      return;
    }
    const manifest = manifestResult[0].value;
    if (!manifest || manifest.schema_version !== '2.0' || !Array.isArray(manifest.payloads)) {
      const error = new Error(`Unsupported or incomplete dashboard manifest schema: ${asText(manifest?.schema_version)}.`);
      if (status) status.textContent = error.message;
      document.querySelectorAll('[data-question-id]').forEach((section) => renderPanelError(section, error));
      return;
    }
    renderHealth(manifest);
    if (status) status.textContent = `Generated ${new Date(manifest.generated_at).toLocaleString()} · Schema ${manifest.schema_version} · Contract ${manifest.contract_validation_status}.`;
    const entries = Object.entries(config.payloadFiles);
    const results = await Promise.allSettled(entries.map(([, file]) => loadDashboardPayload(`${config.payloadRoot}${file}`)));
    const payloads = [];
    results.forEach((result, index) => {
      const [questionId] = entries[index];
      const section = document.querySelector(`[data-question-id="${questionId}"]`);
      if (result.status === 'rejected') { renderPanelError(section, result.reason); return; }
      try { payloads.push(validatePayload(result.value)); } catch (error) { renderPanelError(section, error); }
    });
    const activeFilters = {};
    let applyFilter = () => {};
    const redraw = () => payloads.forEach((payload) => {
      const section = document.querySelector(`[data-question-id="${payload.question_id}"]`);
      try { renderQuestion(section, payload, activeFilters, applyFilter); } catch (error) { renderPanelError(section, error); }
    });
    applyFilter = buildFilterBar(payloads, activeFilters, redraw) || applyFilter;
    redraw();
  }

  window.CepeDashboardRenderer = { render, validatePayload };
})();
