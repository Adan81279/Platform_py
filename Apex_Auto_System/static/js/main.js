// Animaciones y efectos
document.addEventListener('DOMContentLoaded', function() {
    // Smooth scroll para enlaces
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Auto cerrar alertas después de 5 segundos
    setTimeout(function() {
        document.querySelectorAll('.alert').forEach(alert => {
            const closeButton = alert.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            }
        });
    }, 5000);
    
    // Efecto de parallax suave en el hero
    window.addEventListener('scroll', function() {
        const scrolled = window.pageYOffset;
        const hero = document.querySelector('.hero-section');
        if (hero) {
            hero.style.transform = 'translateY(' + scrolled * 0.5 + 'px)';
        }
    });
});