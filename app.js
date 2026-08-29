const repoGrid = document.querySelector("#repoGrid");
const searchInput = document.querySelector("#searchInput");
const categoryFilters = document.querySelector("#categoryFilters");
const sortSelect = document.querySelector("#sortSelect");
const emptyState = document.querySelector("#emptyState");

const repoCount = document.querySelector("#repoCount");
const developerCount = document.querySelector("#developerCount");
const categoryCount = document.querySelector("#categoryCount");

let repos = [];
let currentCategory = "All";

function escapeHTML(value = "") {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(dateValue) {
  const date = new Date(dateValue);

  if (Number.isNaN(date.getTime())) {
    return "unknown";
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(date);
}

function repoCard(repo) {
  const topics = (repo.topics || [])
    .slice(0, 4)
    .map(topic => `<span class="tag">${escapeHTML(topic)}</span>`)
    .join("");

  return `
    <article class="repo-card">
      <div class="repo-top">
        <div class="developer">
          <img
            class="avatar"
            src="${escapeHTML(repo.avatar)}"
            alt="${escapeHTML(repo.developer)} avatar"
            loading="lazy"
          >

          <div class="developer-text">
            <span class="developer-name">${escapeHTML(repo.developer)}</span>
            <span class="developer-handle">@${escapeHTML(repo.username)}</span>
          </div>
        </div>

        <span class="star-count">★ ${Number(repo.stars || 0)}</span>
      </div>

      <h3 class="repo-name">${escapeHTML(repo.name)}</h3>

      <p class="repo-description">
        ${escapeHTML(repo.description || "No description provided.")}
      </p>

      <div class="tags">
        ${topics}
      </div>

      <div class="repo-footer">
        <span class="repo-meta">
          ${escapeHTML(repo.language || "Unknown")} · updated ${formatDate(repo.updated)}
        </span>

        <div class="repo-links">
          <a href="${escapeHTML(repo.profile_url)}" target="_blank" rel="noreferrer">
            Profile
          </a>

          <a href="${escapeHTML(repo.repo_url)}" target="_blank" rel="noreferrer">
            Repository ↗
          </a>
        </div>
      </div>
    </article>
  `;
}

function renderCategories() {
  const categories = [
    "All",
    ...new Set(repos.map(repo => repo.category).filter(Boolean))
  ];

  categoryFilters.innerHTML = categories
    .map(category => `
      <button
        class="filter ${category === currentCategory ? "active" : ""}"
        data-category="${escapeHTML(category)}"
        type="button"
      >
        ${escapeHTML(category)}
      </button>
    `)
    .join("");

  categoryCount.textContent = Math.max(categories.length - 1, 0);
}

function getFilteredRepos() {
  const query = searchInput.value.trim().toLowerCase();

  let filtered = repos.filter(repo => {
    const matchesCategory =
      currentCategory === "All" || repo.category === currentCategory;

    const searchable = [
      repo.developer,
      repo.username,
      repo.name,
      repo.description,
      repo.language,
      repo.category,
      ...(repo.topics || [])
    ]
      .join(" ")
      .toLowerCase();

    return matchesCategory && searchable.includes(query);
  });

  switch (sortSelect.value) {
    case "stars-low":
      filtered.sort((a, b) => a.stars - b.stars);
      break;

    case "stars-high":
      filtered.sort((a, b) => b.stars - a.stars);
      break;

    case "updated":
      filtered.sort((a, b) => new Date(b.updated) - new Date(a.updated));
      break;

    default:
      filtered.sort((a, b) => {
        if (Boolean(a.featured) !== Boolean(b.featured)) {
          return Number(b.featured) - Number(a.featured);
        }

        return new Date(b.updated) - new Date(a.updated);
      });
      break;
  }

  return filtered;
}

function renderRepos() {
  const filtered = getFilteredRepos();

  repoGrid.innerHTML = filtered.map(repoCard).join("");
  emptyState.hidden = filtered.length !== 0;
}

function updateStats() {
  repoCount.textContent = repos.length;

  const developers = new Set(
    repos.map(repo => repo.username).filter(Boolean)
  );

  developerCount.textContent = developers.size;
}

categoryFilters.addEventListener("click", event => {
  const button = event.target.closest("[data-category]");

  if (!button) {
    return;
  }

  currentCategory = button.dataset.category;
  renderCategories();
  renderRepos();
});

searchInput.addEventListener("input", renderRepos);
sortSelect.addEventListener("change", renderRepos);

async function loadRepos() {
  try {
    const response = await fetch("data/developers.json");

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    repos = await response.json();

    updateStats();
    renderCategories();
    renderRepos();
  } catch (error) {
    console.error("Could not load repository data:", error);

    emptyState.hidden = false;
    emptyState.querySelector("h3").textContent = "Could not load repo data";
    emptyState.querySelector("p").textContent =
      "Check data/developers.json and try again.";
  }
}

loadRepos();
