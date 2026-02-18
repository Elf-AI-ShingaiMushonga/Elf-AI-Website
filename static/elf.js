function setTheme(theme) {
  const root = document.documentElement;
  if (theme === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
  localStorage.setItem("elf_theme", theme);
}

function toggleTheme() {
  const root = document.documentElement;
  const isDark = root.classList.contains("dark");
  setTheme(isDark ? "light" : "dark");
}

function toggleMenu() {
  const menu = document.getElementById("mobileMenu");
  if (!menu) return;
  menu.classList.toggle("hidden");
}

function initAutoDismissFlashes() {
  const flashes = document.querySelectorAll("[data-flash]");
  flashes.forEach((flash) => {
    const dismissMs = Number(flash.dataset.dismissMs || 5200);
    const closeButton = flash.querySelector("[data-flash-close]");

    const dismiss = () => {
      if (flash.dataset.dismissed === "true") return;
      flash.dataset.dismissed = "true";
      flash.classList.add("is-dismissing");
      window.setTimeout(() => {
        flash.remove();
      }, 220);
    };

    closeButton?.addEventListener("click", dismiss);
    if (dismissMs > 0) {
      window.setTimeout(dismiss, dismissMs);
    }
  });
}

function initScrollTopButton() {
  const button = document.getElementById("scrollTopButton");
  if (!button) return;

  const toggleVisibility = () => {
    const shouldShow = window.scrollY > 640;
    button.classList.toggle("opacity-0", !shouldShow);
    button.classList.toggle("pointer-events-none", !shouldShow);
  };

  button.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  window.addEventListener("scroll", toggleVisibility, { passive: true });
  toggleVisibility();
}

function initFilterRoots() {
  const roots = document.querySelectorAll("[data-filter-root]");
  if (!roots.length) return;

  roots.forEach((root) => {
    const searchInput = root.querySelector("[data-filter-input]");
    const statusSelect = root.querySelector("[data-filter-status]");
    const stageSelect = root.querySelector("[data-filter-stage]");
    const items = Array.from(root.querySelectorAll("[data-filter-item]"));
    const emptyState = root.querySelector("[data-filter-empty]");
    const countDisplay = root.querySelector("[data-filter-count]");
    const resetButton = root.querySelector("[data-filter-reset]");

    const applyFilters = () => {
      const term = (searchInput?.value || "").trim().toLowerCase();
      const status = (statusSelect?.value || "all").toLowerCase();
      const stage = (stageSelect?.value || "all").toLowerCase();
      let visibleCount = 0;

      items.forEach((item) => {
        const haystack = (item.dataset.filterText || item.textContent || "").toLowerCase();
        const itemStatus = (item.dataset.status || "").toLowerCase();
        const itemStage = (item.dataset.stage || "").toLowerCase();

        const matchesTerm = !term || haystack.includes(term);
        const matchesStatus = status === "all" || itemStatus === status;
        const matchesStage = stage === "all" || itemStage === stage;
        const visible = matchesTerm && matchesStatus && matchesStage;

        item.classList.toggle("hidden", !visible);
        if (visible) visibleCount += 1;
      });

      root.querySelectorAll("[data-filter-group]").forEach((group) => {
        const visibleItemsInGroup = group.querySelectorAll("[data-filter-item]:not(.hidden)").length;
        group.classList.toggle("hidden", visibleItemsInGroup === 0);
      });

      if (countDisplay) {
        countDisplay.textContent = String(visibleCount);
      }
      if (emptyState) {
        emptyState.classList.toggle("hidden", visibleCount > 0);
      }
    };

    searchInput?.addEventListener("input", applyFilters);
    statusSelect?.addEventListener("change", applyFilters);
    stageSelect?.addEventListener("change", applyFilters);
    resetButton?.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      if (statusSelect) statusSelect.value = "all";
      if (stageSelect) stageSelect.value = "all";
      applyFilters();
      searchInput?.focus();
    });
    searchInput?.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      searchInput.value = "";
      applyFilters();
    });
    applyFilters();
  });

  const firstFilterInput = document.querySelector("[data-filter-input]");
  if (!firstFilterInput) return;

  document.addEventListener("keydown", (event) => {
    if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const activeTag = target.tagName.toLowerCase();
    if (activeTag === "input" || activeTag === "textarea" || target.isContentEditable) return;

    event.preventDefault();
    firstFilterInput.focus();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const themeToggle = document.getElementById("themeToggle");
  const themeToggleMobile = document.getElementById("themeToggleMobile");
  const menuToggle = document.getElementById("menuToggle");
  const mobileMenu = document.getElementById("mobileMenu");

  themeToggle?.addEventListener("click", toggleTheme);
  themeToggleMobile?.addEventListener("click", toggleTheme);
  menuToggle?.addEventListener("click", toggleMenu);

  // close menu on link click
  mobileMenu?.querySelectorAll("a[href^='#']").forEach((a) => {
    a.addEventListener("click", () => mobileMenu.classList.add("hidden"));
  });

  initAutoDismissFlashes();
  initScrollTopButton();
  initFilterRoots();
});
