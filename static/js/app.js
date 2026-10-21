// FixFlow — client-side JS utilities

// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('flash-container');
  if (container) {
    setTimeout(() => {
      container.style.transition = 'opacity 0.5s';
      container.style.opacity = '0';
      setTimeout(() => container.remove(), 500);
    }, 5000);
  }
});
