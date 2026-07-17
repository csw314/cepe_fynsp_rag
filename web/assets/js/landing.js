(function () {
  'use strict';
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  async function renderLanding() {
    const status = document.getElementById('landing-generation');
    try {
      const payload = await loadDashboardPayload('../data/curated/dashboard_payloads/landing_summary.json');
      if (payload.schema_version !== '2.0' || !Array.isArray(payload.metrics)) throw new Error('Unsupported or incomplete landing summary schema.');
      const metrics = document.getElementById('landing-metrics');
      metrics.replaceChildren();
      payload.metrics.forEach((metric) => {
        const card = element('article', 'metric-card');
        card.append(element('span', 'metric-label', metric.label), element('strong', 'metric-value numeric', metric.display));
        card.appendChild(element('span', 'citation-line', `Evidence: ${metric.payload_id}`));
        metrics.appendChild(card);
      });
      const actions = document.getElementById('landing-actions');
      actions.replaceChildren();
      payload.highest_priority_actions.forEach((action) => actions.appendChild(element('li', '', action)));
      const sourceHealth = payload.source_health || {};
      document.getElementById('landing-health').textContent = `FORMEX dashboard status: ${payload.data_health.overall_status}. Full-source ingestion status: ${sourceHealth.overall_status || 'NOT EVALUATED'}. Statuses are deterministic and detailed dashboards retain source, filter, metric, warning, and lineage evidence.`;
      status.textContent = `Generated ${new Date(payload.generated_at).toLocaleString()} from ${payload.source_payload_ids.length} validated payloads.`;
    } catch (error) {
      status.textContent = `Generated portfolio data is unavailable: ${error.message}`;
      document.getElementById('landing-metrics').appendChild(element('p', 'panel-error', 'Run the complete dashboard build and serve the repository root over HTTP.'));
    }
  }
  document.addEventListener('DOMContentLoaded', renderLanding);
})();
