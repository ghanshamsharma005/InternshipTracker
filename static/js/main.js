// InternTrack - Global Interactivity JavaScript

document.addEventListener('DOMContentLoaded', () => {
    console.log('⚡ InternTrack Foundation initialized successfully.');
    
    // Navbar background transition on scroll
    const navbar = document.getElementById('mainNavbar');
    
    const handleNavbarScroll = () => {
        if (!navbar) return;
        if (window.scrollY > 40) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    };
    
    // Register scroll event listener
    window.addEventListener('scroll', handleNavbarScroll);
    handleNavbarScroll();
    
    // Password visibility toggle helper
    const toggleButtons = document.querySelectorAll('.btn-password-toggle');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const inputGroup = btn.closest('.input-group');
            if (!inputGroup) return;
            
            const input = inputGroup.querySelector('input');
            const icon = btn.querySelector('i');
            
            if (input && icon) {
                if (input.type === 'password') {
                    input.type = 'text';
                    icon.classList.remove('bi-eye-slash');
                    icon.classList.add('bi-eye');
                } else {
                    input.type = 'password';
                    icon.classList.remove('bi-eye');
                    icon.classList.add('bi-eye-slash');
                }
            }
        });
    });

    // Auto-close mobile navbar when clicking in-page anchor links
    const navLinks = document.querySelectorAll('.navbar-nav a[href*="#"]');
    const navbarCollapse = document.getElementById('navbarContent');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (navbarCollapse && navbarCollapse.classList.contains('show')) {
                if (window.bootstrap && bootstrap.Collapse) {
                    const bsCollapse = bootstrap.Collapse.getInstance(navbarCollapse) || new bootstrap.Collapse(navbarCollapse, { toggle: false });
                    bsCollapse.hide();
                }
            }
        });
    });
});
