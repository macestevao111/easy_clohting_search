document.addEventListener('DOMContentLoaded', function() {
  // Abre modais com a classe .info-popup
  var infoButtons = document.querySelectorAll('.info-popup');
  infoButtons.forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      var modalId = btn.getAttribute('data-modal');
      var modal = document.getElementById(modalId);
      if (modal) {
        modal.style.display = 'block';
      }
    });
  });

  // Fecha a modal ao clicar no "X"
  var closeButtons = document.querySelectorAll('.close-modal');
  closeButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      btn.parentElement.parentElement.style.display = 'none';
    });
  });

  // Fecha a modal ao clicar fora do conteúdo
  window.addEventListener('click', function(e) {
    var modals = document.querySelectorAll('.modal');
    modals.forEach(function(modal) {
      if (e.target === modal) {
        modal.style.display = 'none';
      }
    });
  });
});
