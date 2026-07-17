window.CepeDashboardRenderer.render({
  payloadRoot: '../../../data/curated/dashboard_payloads/dashboard_01_pit_production/',
  payloadFiles: {
    q1: 'q1_funding_by_year_level.json', q2: 'q2_funding_by_organization.json',
    q3: 'q3_site_distribution.json', q4: 'q4_above_baseline_program_requests.json',
    q5: 'q5_data_quality_findings.json', q6: 'q6_crosscuts_site_splits_reconciliation.json',
  },
});
