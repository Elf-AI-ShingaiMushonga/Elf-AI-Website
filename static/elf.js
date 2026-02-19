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
  const trigger = document.getElementById("menuToggle");
  if (!menu) return;

  const willOpen = menu.classList.contains("hidden");
  menu.classList.toggle("hidden");

  if (trigger) {
    trigger.classList.toggle("is-open", willOpen);
    trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
    const icon = trigger.querySelector("i");
    if (icon) {
      icon.classList.toggle("fa-bars", !willOpen);
      icon.classList.toggle("fa-xmark", willOpen);
    }
  }
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

function isoDateFromTodayOffset(days) {
  const safeOffset = Number.isFinite(days) ? days : 30;
  const targetDate = new Date();
  targetDate.setHours(12, 0, 0, 0);
  targetDate.setDate(targetDate.getDate() + safeOffset);

  const year = targetDate.getFullYear();
  const month = String(targetDate.getMonth() + 1).padStart(2, "0");
  const day = String(targetDate.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function initProjectFormEnhancements() {
  const projectForms = document.querySelectorAll("[data-project-form]");
  if (!projectForms.length) return;

  projectForms.forEach((form) => {
    const clientModeSelect = form.querySelector("[data-client-mode]");
    const existingClientField = form.querySelector("[data-existing-client-field]");
    const existingClientSelect = form.querySelector("select[name='client_id']");
    const newClientFields = form.querySelector("[data-new-client-fields]");
    const newClientRequiredInputs = form.querySelectorAll("[data-new-client-required]");

    const applyClientMode = () => {
      const mode = (clientModeSelect?.value || "existing").toLowerCase();
      const useNewClient = mode === "new";

      existingClientField?.classList.toggle("hidden", useNewClient);
      newClientFields?.classList.toggle("hidden", !useNewClient);

      if (existingClientSelect) {
        existingClientSelect.required = !useNewClient;
      }
      newClientRequiredInputs.forEach((input) => {
        input.required = useNewClient;
      });
    };

    clientModeSelect?.addEventListener("change", applyClientMode);
    applyClientMode();

    const timelineSelect = form.querySelector("[data-timeline-days]");
    const dueDateInput = form.querySelector("[data-due-date]");
    const resetDueDateButton = form.querySelector("[data-reset-timeline-due-date]");

    const syncDueDateToTimeline = (force = false) => {
      if (!timelineSelect || !dueDateInput) return;
      if (!force && dueDateInput.dataset.manualDueDate === "true") return;

      const timelineDays = Number(timelineSelect.value);
      const safeDays = Number.isFinite(timelineDays) ? timelineDays : 30;
      dueDateInput.value = isoDateFromTodayOffset(safeDays);
    };

    if (dueDateInput) {
      dueDateInput.dataset.manualDueDate = "false";
      dueDateInput.addEventListener("input", () => {
        dueDateInput.dataset.manualDueDate = "true";
      });
    }

    timelineSelect?.addEventListener("change", () => syncDueDateToTimeline());
    resetDueDateButton?.addEventListener("click", () => {
      if (dueDateInput) {
        dueDateInput.dataset.manualDueDate = "false";
      }
      syncDueDateToTimeline(true);
      dueDateInput?.focus();
    });
  });
}

function initTaskFormEnhancements() {
  const taskForms = document.querySelectorAll("[data-task-form]");
  if (!taskForms.length) return;

  taskForms.forEach((form) => {
    const dueDateInput = form.querySelector("[data-task-due-date]");
    const presetButtons = form.querySelectorAll("[data-due-offset]");

    if (!dueDateInput || !presetButtons.length) return;

    const setDueDateFromOffset = (offsetDays) => {
      const offset = Number(offsetDays);
      if (!Number.isFinite(offset)) return;
      dueDateInput.value = isoDateFromTodayOffset(offset);
      dueDateInput.focus();
    };

    presetButtons.forEach((button) => {
      button.addEventListener("click", () => {
        setDueDateFromOffset(button.dataset.dueOffset);
      });
    });
  });
}

function initOptionSearchFilters() {
  const searchInputs = document.querySelectorAll("[data-option-filter-input]");
  if (!searchInputs.length) return;

  searchInputs.forEach((input) => {
    const targetId = input.getAttribute("data-option-filter-target");
    if (!targetId) return;

    const targetSelect = document.getElementById(targetId);
    if (!(targetSelect instanceof HTMLSelectElement)) return;

    const filterOptions = () => {
      const term = (input.value || "").trim().toLowerCase();
      Array.from(targetSelect.options).forEach((option) => {
        if (!option.value) {
          option.hidden = false;
          return;
        }

        const label = (option.textContent || "").toLowerCase();
        const isVisible = !term || label.includes(term) || option.selected;
        option.hidden = !isVisible;
      });
    };

    input.addEventListener("input", filterOptions);
    filterOptions();
  });
}

function initMessageEnhancements() {
  const messageThreads = document.querySelectorAll("[data-message-thread]");
  messageThreads.forEach((thread) => {
    thread.scrollTop = thread.scrollHeight;
  });

  const snippetButtons = document.querySelectorAll("[data-message-snippet]");
  snippetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-message-target");
      const snippetText = (button.getAttribute("data-message-snippet") || "").trim();
      if (!targetId || !snippetText) return;

      const textarea = document.getElementById(targetId);
      if (!(textarea instanceof HTMLTextAreaElement)) return;

      const currentValue = (textarea.value || "").trimEnd();
      textarea.value = currentValue ? `${currentValue}\n${snippetText}` : snippetText;
      textarea.focus();
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
  });

  const countableTextareas = document.querySelectorAll("[data-char-count-target]");
  countableTextareas.forEach((textarea) => {
    const counterId = textarea.getAttribute("data-char-count-target");
    if (!counterId) return;

    const counter = document.getElementById(counterId);
    if (!counter) return;

    const updateCounter = () => {
      const length = (textarea.value || "").length;
      const maxLength = Number(textarea.getAttribute("maxlength"));
      if (Number.isFinite(maxLength) && maxLength > 0) {
        counter.textContent = `${length}/${maxLength}`;
      } else {
        counter.textContent = String(length);
      }
    };

    textarea.addEventListener("input", updateCounter);
    updateCounter();
  });
}

function initComposePromptButtons() {
  const buttons = document.querySelectorAll("[data-compose-target][data-compose-text]");
  if (!buttons.length) return;

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-compose-target");
      const promptText = (button.getAttribute("data-compose-text") || "").trim();
      if (!targetId || !promptText) return;

      const textarea = document.getElementById(targetId);
      if (!(textarea instanceof HTMLTextAreaElement)) return;

      const hasText = (textarea.value || "").trim().length > 0;
      textarea.value = hasText ? `${textarea.value.trimEnd()}\n${promptText}` : promptText;
      textarea.focus();
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
  });
}

function initInternalOmnibar() {
  const omnibars = Array.from(document.querySelectorAll("[data-internal-omnibar]")).filter(
    (input) => input instanceof HTMLInputElement
  );
  if (!omnibars.length) return;

  const focusOmnibar = () => {
    const visibleOmnibar = omnibars.find((input) => input.offsetParent !== null);
    const target = visibleOmnibar || omnibars[0];
    target.focus();
    target.select();
  };

  document.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase();
    const keyboardShortcut = (event.metaKey || event.ctrlKey) && key === "k";
    if (keyboardShortcut) {
      event.preventDefault();
      focusOmnibar();
      return;
    }

    if (key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const activeTag = target.tagName.toLowerCase();
    if (activeTag === "input" || activeTag === "textarea" || target.isContentEditable) return;

    const hasPageFilter = Boolean(document.querySelector("[data-filter-input]"));
    if (hasPageFilter) return;

    event.preventDefault();
    focusOmnibar();
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
  mobileMenu?.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", () => {
      mobileMenu.classList.add("hidden");
      if (!menuToggle) return;
      menuToggle.classList.remove("is-open");
      menuToggle.setAttribute("aria-expanded", "false");
      const icon = menuToggle.querySelector("i");
      if (!icon) return;
      icon.classList.add("fa-bars");
      icon.classList.remove("fa-xmark");
    });
  });

  initAutoDismissFlashes();
  initScrollTopButton();
  initInternalOmnibar();
  initFilterRoots();
  initProjectFormEnhancements();
  initTaskFormEnhancements();
  initOptionSearchFilters();
  initMessageEnhancements();
  initComposePromptButtons();
});
