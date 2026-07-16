async function loadDashboardPayload(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Unable to load payload: ${path}`);
  }
  return response.json();
}

function renderUnavailableState() {
  document.querySelectorAll('.chart-placeholder').forEach((el) => {
    el.textContent = `${el.dataset.chartId}: run the Python payload export pipeline to render this chart.`;
  });
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.querySelector('[data-question-id]')) {
    return;
  }
  renderUnavailableState();
});
