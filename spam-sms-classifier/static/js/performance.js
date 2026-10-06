async function loadPerformance() {
  try {
    const response = await fetch('/api/model-performance');
    const data = await response.json();
    if (!response.ok || !data) throw new Error('Unable to load model performance');

    const rows = Array.isArray(data) ? data : (Array.isArray(data.results) ? data.results : []);
    const tbody = document.getElementById('performance-body');
    if (tbody) {
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="5">No model performance data available.</td></tr>';
        return;
      }

      tbody.innerHTML = rows.map((item) => `
        <tr>
          <td>${item.model_name || item.model || 'Model'}</td>
          <td>${Number(item.accuracy || 0).toFixed(3)}</td>
          <td>${Number(item.precision || 0).toFixed(3)}</td>
          <td>${Number(item.recall || 0).toFixed(3)}</td>
          <td>${Number(item.f1_score || 0).toFixed(3)}</td>
        </tr>
      `).join('');
    }

    if (window.Chart) {
      const chartCanvas = document.getElementById('performance-chart');
      if (chartCanvas) {
        const models = rows.map((item) => item.model_name || item.model || 'Model');
        const accuracy = rows.map((item) => Number(item.accuracy || 0) * 100);
        new Chart(chartCanvas, {
          type: 'bar',
          data: {
            labels: models,
            datasets: [{
              label: 'Accuracy (%)',
              data: accuracy,
              backgroundColor: ['#5b8cff', '#ff5b77', '#1ec98b', '#ffb84d'],
              borderRadius: 10
            }]
          },
          options: {
            responsive: true,
            plugins: {
              legend: { display: false }
            },
            scales: {
              y: {
                beginAtZero: true,
                max: 100
              }
            }
          }
        });
      }
    }
  } catch (error) {
    console.error('Performance error:', error);
    const tbody = document.getElementById('performance-body');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="5">Unable to load model metrics.</td></tr>';
    }
  }
}

loadPerformance();
