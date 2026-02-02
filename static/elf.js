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
});
