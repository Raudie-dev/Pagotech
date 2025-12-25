/* ===========================================
   PagoTech - Usuarios JavaScript
   =========================================== */

document.addEventListener("DOMContentLoaded", function () {
  // ============================================
  // Seleccionar todos los usuarios
  // ============================================
  const selectAll = document.getElementById("selectAll");
  const userCheckboxes = document.querySelectorAll(".user-checkbox");

  if (selectAll) {
    selectAll.addEventListener("change", function () {
      userCheckboxes.forEach((checkbox) => {
        checkbox.checked = this.checked;
      });
    });

    // Actualizar estado de "select all" cuando se cambian checkboxes individuales
    userCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", function () {
        const allChecked = Array.from(userCheckboxes).every((cb) => cb.checked);
        const someChecked = Array.from(userCheckboxes).some((cb) => cb.checked);
        selectAll.checked = allChecked;
        selectAll.indeterminate = someChecked && !allChecked;
      });
    });
  }

  // ============================================
  // Modal de edición - cargar datos
  // ============================================
  const editUserModal = document.getElementById("editUserModal");
  if (editUserModal) {
    editUserModal.addEventListener("show.bs.modal", function (event) {
      const button = event.relatedTarget;

      // Obtener datos del botón data-*
      const id = button.getAttribute("data-id");
      const nombre = button.getAttribute("data-nombre");
      const email = button.getAttribute("data-email");
      const telefono = button.getAttribute("data-telefono");
      const aprobado = button.getAttribute("data-aprobado"); // "1" o "0"
      const bloqueado = button.getAttribute("data-bloqueado"); // "1" o "0"

      // Asignar valores a los inputs
      document.getElementById("edit_id").value = id || "";
      document.getElementById("edit_nombre").value = nombre || "";
      document.getElementById("edit_email").value = email || "";
      document.getElementById("edit_telefono").value = telefono || "";

      // Marcar switches correctamente (comparando con "1")
      document.getElementById("edit_aprobado").checked = aprobado === "1";
      document.getElementById("edit_bloqueado").checked = bloqueado === "1";
    });
  }

  // ============================================
  // Animación hover en filas
  // ============================================
  const userRows = document.querySelectorAll(".user-row");
  userRows.forEach((row) => {
    row.addEventListener("mouseenter", function () {
      this.style.backgroundColor = "rgba(230, 57, 70, 0.05)";
    });
    row.addEventListener("mouseleave", function () {
      this.style.backgroundColor = "";
    });
  });

  // ============================================
  // Confirmación para acciones críticas
  // ============================================
  const deleteLinks = document.querySelectorAll(
    'a[href="#"][class*="text-danger"]'
  );
  deleteLinks.forEach((link) => {
    link.addEventListener("click", function (e) {
      if (this.textContent.includes("Eliminar")) {
        if (
          !confirm(
            "¿Estás seguro de que deseas eliminar este usuario? Esta acción no se puede deshacer."
          )
        ) {
          e.preventDefault();
        }
      }
    });
  });

  // ============================================
  // Confirmación para bloquear/desbloquear
  // ============================================
  const blockForms = document.querySelectorAll('form[method="post"]');
  blockForms.forEach((form) => {
    form.addEventListener("submit", function (e) {
      const blockInput = this.querySelector('input[name="bloquear_id"]');
      const unblockInput = this.querySelector('input[name="desbloquear_id"]');

      if (blockInput) {
        if (!confirm("¿Estás seguro de que deseas bloquear este usuario?")) {
          e.preventDefault();
        }
      } else if (unblockInput) {
        if (
          !confirm(
            "¿Deseas desbloquear este usuario para que pueda acceder nuevamente?"
          )
        ) {
          e.preventDefault();
        }
      }
    });
  });

  // ============================================
  // Auto-dismiss para alerts después de 5 segundos
  // ============================================
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach((alert) => {
    setTimeout(() => {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000);
  });

  // ============================================
  // Mejorar la búsqueda - limpiar espacios
  // ============================================
  const searchForm = document.querySelector('form[method="get"]');
  if (searchForm) {
    searchForm.addEventListener("submit", function (e) {
      const searchInput = this.querySelector('input[name="q"]');
      if (searchInput) {
        searchInput.value = searchInput.value.trim();
      }
    });
  }

  // ============================================
  // Feedback visual al copiar ID
  // ============================================
  /* const userIdElements = document.querySelectorAll('small:contains("ID:")');
    userIdElements.forEach(el => {
        el.style.cursor = 'pointer';
        el.title = 'Click para copiar ID';
        
        el.addEventListener('click', function() {
            const id = this.textContent.replace('ID:', '').trim();
            navigator.clipboard.writeText(id).then(() => {
                // Mostrar feedback
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check text-success me-1"></i>Copiado!';
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                }, 2000);
            });
        });
    }); 
    */

  // ============================================
  // Lazy loading para modales
  // ============================================
  const viewUserModal = document.getElementById("viewUserModal");

  if (viewUserModal) {
    // 1. EVENTO AL ABRIR: Reiniciamos al spinner inmediatamente
    viewUserModal.addEventListener("show.bs.modal", function (event) {
      const loading = document.getElementById("userLoading");

      // Inyectamos el spinner de nuevo apenas se abre para que el usuario no vea datos viejos
      loading.innerHTML = `
      <div class="spinner-border text-danger" role="status">
          <span class="visually-hidden">Cargando...</span>
      </div>`;

      const button = event.relatedTarget;
      const userId = button.getAttribute("data-id");
      const nombre = button.getAttribute("data-nombre");
      const email = button.getAttribute("data-email");
      const telefono = button.getAttribute("data-telefono");
      const aprobado = button.getAttribute("data-aprobado") === "1";
      const bloqueado = button.getAttribute("data-bloqueado") === "1";

      // 2. EFECTO DE CARGA: Después del tiempo definido, mostramos la info
      setTimeout(() => {
        // Verificamos que el contenedor aún exista (por seguridad)
        if (loading) {
          loading.innerHTML = `
          <div class="text-start p-2 animate-fade-in">
              <div class="d-flex align-items-center mb-4 p-3 rounded-3" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05);">
                  <div class="user-avatar me-3" style="width: 55px; height: 55px; font-size: 22px;">
                      ${nombre.charAt(0).toUpperCase()}
                  </div>
                  <div>
                      <h5 class="text-white mb-0 fw-bold">${nombre}</h5>
                      <span class="user-sub-text">ID: #${userId.padStart(
                        6,
                        "0"
                      )}</span>
                  </div>
              </div>
              
              <div class="row g-4">
                  <div class="col-md-6">
                      <label class="form-label-custom mb-2">Información de Contacto</label>
                      <div class="text-white mb-2 small"><i class="fas fa-envelope text-danger me-2"></i>${email}</div>
                      <div class="text-white small"><i class="fas fa-phone text-danger me-2"></i>${telefono}</div>
                  </div>
                  <div class="col-md-6">
                      <label class="form-label-custom mb-2">Estado del Sistema</label>
                      <div class="mb-2">
                          <span class="badge-status ${
                            aprobado ? "status-approved" : "status-pending"
                          }">
                              <div class="status-dot" style="background: ${
                                aprobado ? "#10b981" : "#f59e0b"
                              };"></div>
                              ${aprobado ? "Cuenta Verificada" : "Pendiente"}
                          </span>
                      </div>
                      <div>
                          <span class="badge-status ${
                            bloqueado ? "status-blocked" : "status-approved"
                          }">
                              <div class="status-dot" style="background: ${
                                bloqueado ? "#e63946" : "#10b981"
                              };"></div>
                              ${
                                bloqueado
                                  ? "Acceso Bloqueado"
                                  : "Acceso Habilitado"
                              }
                          </span>
                      </div>
                  </div>
              </div>
          </div>
        `;
        }
      }, 400);
    });

    // 3. EVENTO AL CERRAR: Limpiamos todo para que la próxima apertura esté limpia
    viewUserModal.addEventListener("hidden.bs.modal", function () {
      const loading = document.getElementById("userLoading");
      loading.innerHTML = `
      <div class="spinner-border text-danger" role="status">
          <span class="visually-hidden">Cargando...</span>
      </div>`;
    });
  }

  // ============================================
  // Contador de usuarios seleccionados
  // ============================================
  function updateSelectedCount() {
    const checkedBoxes = document.querySelectorAll(".user-checkbox:checked");
    const count = checkedBoxes.length;

    // Aquí podrías mostrar un badge o mensaje con el conteo
    if (count > 0) {
      console.log(`${count} usuario(s) seleccionado(s)`);
    }
  }

  userCheckboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", updateSelectedCount);
  });
});

// ============================================
// Utilidades globales
// ============================================

// Función para formatear fechas
function formatDate(dateString) {
  if (!dateString || dateString === "Sin registro") return "Sin registro";

  const date = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now - date);
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Hoy";
  if (diffDays === 1) return "Ayer";
  if (diffDays < 7) return `Hace ${diffDays} días`;

  return date.toLocaleDateString("es-ES");
}

// Función para validar email
function isValidEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

// Función para validar teléfono
function isValidPhone(phone) {
  const re =
    /^[+]?[(]?[0-9]{1,4}[)]?[-\s.]?[(]?[0-9]{1,4}[)]?[-\s.]?[0-9]{1,9}$/;
  return re.test(phone);
}

// ============================================
// Modal de Eliminación - Cargar datos
// ============================================
const deleteUserModal = document.getElementById("deleteUserModal");
if (deleteUserModal) {
  deleteUserModal.addEventListener("show.bs.modal", function (event) {
    const button = event.relatedTarget; // Botón que activó el modal

    // Extraer info de los atributos data-*
    const id = button.getAttribute("data-id");
    const nombre = button.getAttribute("data-nombre");

    // Actualizar el contenido del modal
    document.getElementById("delete_id_input").value = id;
    document.getElementById("deleteUserName").textContent = nombre;
  });
}
