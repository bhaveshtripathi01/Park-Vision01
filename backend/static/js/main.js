(function () {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

  function showToast(message, type = "success") {
    const stack = document.getElementById("toast-stack");
    if (!stack) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.setAttribute("data-testid", `toast-${type}`);
    toast.textContent = message;
    stack.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 3200);
  }

  async function fetchJSON(url, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      headers["X-CSRF-Token"] = csrfToken;
    }

    const response = await fetch(url, {
      credentials: "include",
      ...options,
      method,
      headers,
    });

    const isJSON = response.headers.get("content-type")?.includes("application/json");
    const data = isJSON ? await response.json() : null;

    if (!response.ok) {
      const message = data?.detail || data?.message || "Request failed";
      throw new Error(message);
    }

    return data;
  }

  function animateCounters() {
    const counters = document.querySelectorAll("[data-counter-target]");
    if (!counters.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const el = entry.target;
          const target = Number(el.getAttribute("data-counter-target"));
          const duration = 1200;
          const start = performance.now();

          const tick = (time) => {
            const progress = Math.min((time - start) / duration, 1);
            el.textContent = Math.round(progress * target).toLocaleString();
            if (progress < 1) {
              requestAnimationFrame(tick);
            }
          };
          requestAnimationFrame(tick);
          observer.unobserve(el);
        });
      },
      { threshold: 0.35 },
    );

    counters.forEach((counter) => observer.observe(counter));
  }

  function setupTypewriter() {
    const el = document.querySelector("[data-typewriter]");
    if (!el) return;
    const text = el.getAttribute("data-typewriter") || "";
    let i = 0;
    const timer = setInterval(() => {
      el.textContent = text.slice(0, i);
      i += 1;
      if (i > text.length) clearInterval(timer);
    }, 36);
  }

  function setupNavbar() {
    const nav = document.getElementById("top-nav");
    if (!nav) return;
    const update = () => {
      if (window.scrollY > 16) nav.classList.add("scrolled");
      else nav.classList.remove("scrolled");
    };
    update();
    window.addEventListener("scroll", update, { passive: true });

    const menuBtn = document.getElementById("user-menu-button");
    const menu = document.getElementById("user-menu");
    if (menuBtn && menu) {
      menuBtn.addEventListener("click", () => {
        menu.hidden = !menu.hidden;
      });
      window.addEventListener("click", (e) => {
        if (!menu.contains(e.target) && !menuBtn.contains(e.target)) {
          menu.hidden = true;
        }
      });
    }

    const logoutButton = document.getElementById("logout-button");
    if (logoutButton) {
      logoutButton.addEventListener("click", async () => {
        try {
          await fetchJSON("/api/auth/logout", { method: "POST" });
          window.location.href = "/api/login";
        } catch (error) {
          showToast(error.message, "error");
        }
      });
    }
  }

  function setupMiniGrid() {
    const cells = document.querySelectorAll(".mini-cell");
    if (!cells.length) return;
    setInterval(() => {
      cells.forEach((cell) => {
        const status = Math.random() > 0.5 ? "available" : "occupied";
        cell.style.borderColor = status === "available" ? "rgba(0,255,136,.55)" : "rgba(255,59,92,.55)";
        cell.style.boxShadow =
          status === "available" ? "0 0 12px rgba(0,255,136,.2)" : "0 0 12px rgba(255,59,92,.2)";
      });
    }, 1200);
  }

  document.body.classList.add("page-enter");
  setupNavbar();
  animateCounters();
  setupTypewriter();
  setupMiniGrid();

  window.ParkVision = {
    csrfToken,
    showToast,
    fetchJSON,
    formatRupee(amount) {
      return `₹${Number(amount || 0).toFixed(2)}`;
    },
  };
})();
