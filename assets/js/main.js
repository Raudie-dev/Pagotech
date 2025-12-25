function showToast(message, type = 'success') {
  const container = document.querySelector('.toast-container');
  if (!container) return; // Seguridad por si no existe el contenedor

  const toastHtml = `
      <div class="toast align-items-center text-white bg-${type} border-0 shadow-lg" role="alert" aria-live="assertive" aria-atomic="true">
          <div class="d-flex">
              <div class="toast-body">
                  <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'} me-2"></i> ${message}
              </div>
              <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
          </div>
      </div>`;
  
  container.insertAdjacentHTML('beforeend', toastHtml);
  const toastEl = container.lastElementChild;
  const bsToast = new bootstrap.Toast(toastEl, { delay: 5000 });
  bsToast.show();
}

document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('registered') === '1') {
    // 1. Mostrar la notificación
    showToast('Usuario creado con éxito. Esperando aprobación del administrador.', 'success');
    
    // 2. Limpiar la URL para que no vuelva a salir al recargar
    const newUrl = window.location.pathname;
    window.history.replaceState({}, document.title, newUrl);
  }

  // --- AUTO-MOSTRAR MENSAJES DE DJANGO ---
  const existingToasts = document.querySelectorAll('.toast-container .toast');
  existingToasts.forEach(toastEl => {
    const bsToast = new bootstrap.Toast(toastEl);
    bsToast.show();
  });

  const menuToggle = document.querySelector(".menu-toggle")
  const mobileNav = document.querySelector(".mobile-nav")

  if (menuToggle && mobileNav) {
    menuToggle.addEventListener("click", function () {
      this.classList.toggle("active")
      mobileNav.classList.toggle("active")
      document.body.classList.toggle("nav-open")
    })

    // Close menu when clicking on a nav link
    const mobileNavLinks = mobileNav.querySelectorAll("a")
    mobileNavLinks.forEach((link) => {
      link.addEventListener("click", () => {
        menuToggle.classList.remove("active")
        mobileNav.classList.remove("active")
        document.body.classList.remove("nav-open")
      })
    })
  }

  // Header scroll effect
  const header = document.querySelector(".header")
  let lastScroll = 0

  window.addEventListener("scroll", () => {
    const currentScroll = window.scrollY

    if (currentScroll > 50) {
      header.classList.add("scrolled")
    } else {
      header.classList.remove("scrolled")
    }

    lastScroll = currentScroll
  })

  // Smooth scrolling for anchor links
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault()

      const targetId = this.getAttribute("href")
      if (targetId === "#") return

      const targetElement = document.querySelector(targetId)

      if (targetElement) {
        const headerHeight = document.querySelector(".header").offsetHeight
        const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset - headerHeight

        window.scrollTo({
          top: targetPosition,
          behavior: "smooth",
        })
      }
    })
  })

  // Active menu item based on scroll position
  const sections = document.querySelectorAll("section[id]")
  const navLinks = document.querySelectorAll(".nav-list a")

  const observerOptions = {
    root: null,
    rootMargin: "-20% 0px -80% 0px",
    threshold: 0,
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const id = entry.target.getAttribute("id")
        navLinks.forEach((link) => {
          link.classList.remove("active")
          if (link.getAttribute("href") === `#${id}`) {
            link.classList.add("active")
          }
        })
      }
    })
  }, observerOptions)

  sections.forEach((section) => {
    observer.observe(section)
  })

  // Animate elements on scroll
  const animateOnScroll = () => {
    const elements = document.querySelectorAll(".feature-card, .step-card, .step-connector,.pricing-card")

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.style.opacity = "1"
            entry.target.style.transform = "translateY(0)"
          }
        })
      },
      {
        threshold: 0.1,
        rootMargin: "0px 0px -50px 0px",
      },
    )

    elements.forEach((el, index) => {
      el.style.opacity = "0"
      el.style.transform = "translateY(30px)"
      el.style.transition = `opacity 0.6s ease ${index * 0.1}s, transform 0.3s ease ${index * 0.1}s`
      observer.observe(el)
    })
  }

  animateOnScroll()

  // Stats counter animation
  const animateStats = () => {
    const statValues = document.querySelectorAll(".stat-value")

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const el = entry.target
            el.style.opacity = "1"
            el.style.transform = "translateY(0)"
            observer.unobserve(el)
          }
        })
      },
      { threshold: 0.5 },
    )

    statValues.forEach((stat, index) => {
      stat.style.opacity = "0"
      stat.style.transform = "translateY(20px)"
      stat.style.transition = `all 0.3s ease ${index * 0.2}s`
      observer.observe(stat)
    })
  }

  animateStats()
})
