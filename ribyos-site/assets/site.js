(() => {
  "use strict";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const menu = document.querySelector(".r-menu");
  const navigation = document.querySelector("#r-navigation");
  const closeMenu = () => {
    menu.setAttribute("aria-expanded", "false");
    navigation.classList.remove("open");
  };
  menu.addEventListener("click", () => {
    const open = menu.getAttribute("aria-expanded") === "true";
    menu.setAttribute("aria-expanded", String(!open));
    navigation.classList.toggle("open", !open);
  });
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) closeMenu();
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".r-header")) closeMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      menu.getAttribute("aria-expanded") === "true"
    ) {
      closeMenu();
      menu.focus();
    }
  });

  if ("IntersectionObserver" in window && !reduceMotion.matches) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08 },
    );
    document
      .querySelectorAll("[data-reveal]")
      .forEach((target) => observer.observe(target));
    document.documentElement.classList.add("motion-ready");
  }

  const tabs = Array.from(document.querySelectorAll("[data-surface]"));
  const panels = Array.from(document.querySelectorAll(".r-app-panel"));
  const walkthrough = document.querySelector("#walkthrough");
  const conceptStatus = document.querySelector("#concept-status");
  const nodes = Array.from(document.querySelectorAll("[data-step]"));
  let timers = [];
  function resetWalkthrough() {
    timers.forEach(clearTimeout);
    timers = [];
    walkthrough.disabled = false;
    walkthrough.textContent = "Walk through →";
    conceptStatus.textContent = "A workflow concept. No live execution.";
    nodes.forEach((node) => node.classList.remove("is-active"));
  }
  function selectSurface(surface, focus = false) {
    resetWalkthrough();
    tabs.forEach((tab) => {
      const selected = tab.dataset.surface === surface;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && focus) tab.focus({ preventScroll: true });
    });
    panels.forEach((panel) => {
      panel.hidden = panel.id !== `panel-${surface}`;
    });
    document.querySelector("#preview-title").textContent =
      `Ribyos ${surface[0].toUpperCase()}${surface.slice(1)}`;
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectSurface(tab.dataset.surface));
    tab.addEventListener("keydown", (event) => {
      let next;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      if (event.key === "ArrowLeft")
        next = (index + tabs.length - 1) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        selectSurface(tabs[next].dataset.surface, true);
      }
    });
  });
  document.querySelectorAll("[data-open-surface]").forEach((button) => {
    button.addEventListener("click", () => {
      selectSurface(button.dataset.openSurface, true);
      document
        .querySelector(".r-preview-wrap")
        .scrollIntoView({
          behavior: reduceMotion.matches ? "instant" : "smooth",
          block: "start",
        });
    });
  });

  const stages = [
    "Concept step 1/4 · Scope the approved knowledge.",
    "Concept step 2/4 · Research relevant evidence.",
    "Concept step 3/4 · Check sources and gaps.",
    "Concept step 4/4 · Prepare a draft for human review.",
  ];
  walkthrough.addEventListener("click", () => {
    resetWalkthrough();
    walkthrough.disabled = true;
    walkthrough.textContent = "Walking through…";
    const complete = () => {
      conceptStatus.textContent =
        "Concept complete · Draft awaits human review.";
      walkthrough.disabled = false;
      walkthrough.textContent = "Replay concept →";
    };
    if (reduceMotion.matches) {
      nodes.forEach((node) => node.classList.add("is-active"));
      complete();
      return;
    }
    nodes.forEach((node, index) => {
      timers.push(
        setTimeout(() => {
          nodes.forEach((item) => item.classList.remove("is-active"));
          node.classList.add("is-active");
          conceptStatus.textContent = stages[index];
        }, index * 950),
      );
    });
    timers.push(setTimeout(complete, 3800));
  });

  const filterButtons = document.querySelectorAll("[data-filter]");
  const packs = Array.from(document.querySelectorAll(".r-pack"));
  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      filterButtons.forEach((item) =>
        item.setAttribute("aria-pressed", String(item === button)),
      );
      packs.forEach((pack) => {
        pack.hidden =
          button.dataset.filter !== "all" &&
          pack.dataset.category !== button.dataset.filter;
      });
      const count = packs.filter((pack) => !pack.hidden).length;
      document.querySelector("#pack-count").textContent =
        `${count} planned packs`;
    });
  });

  const dialog = document.querySelector("#workflow-dialog");
  const workflowURL = new URL("workflows.json", document.currentScript.src);
  const data = fetch(workflowURL)
    .then((response) => {
      if (!response.ok) throw new Error("Workflow descriptions unavailable");
      return response.json();
    })
    .catch(() => null);
  let returnFocus;
  const detailContainer = document.querySelector("#workflow-details");
  function addSection(title, content) {
    const section = document.createElement("section");
    section.className = "r-dialog-section";
    const heading = document.createElement("h3");
    heading.textContent = title;
    section.append(heading);
    if (Array.isArray(content)) {
      const list = document.createElement("ul");
      content.forEach((text) => {
        const item = document.createElement("li");
        item.textContent = text;
        list.append(item);
      });
      section.append(list);
    } else {
      const paragraph = document.createElement("p");
      paragraph.textContent = content;
      section.append(paragraph);
    }
    detailContainer.append(section);
  }
  document.querySelectorAll("[data-workflow]").forEach((button) => {
    button.addEventListener("click", async () => {
      const descriptions = await data;
      const pack = descriptions?.find(
        (item) => item.id === button.dataset.workflow,
      );
      returnFocus = button;
      detailContainer.replaceChildren();
      document.querySelector("#workflow-title").textContent =
        pack?.title || "Workflow details";
      document.querySelector("#workflow-category").textContent =
        pack?.label || "PLANNED WORKFLOW";
      if (pack) {
        addSection("The business problem", pack.problem);
        addSection("Inputs and data scope", pack.inputs);
        addSection("Agent roles", pack.roles);
        addSection("Evidence and output", pack.output);
        addSection("Human approval boundary", pack.approval);
        addSection("Requested permissions", pack.permissions);
        addSection("Proposed success criterion", pack.success);
      } else {
        addSection(
          "Details temporarily unavailable",
          "Please try again later or contact Jengara Labs to discuss this planned workflow.",
        );
      }
      dialog.showModal();
      document.documentElement.classList.add("has-dialog");
    });
  });
  document
    .querySelector(".r-dialog-close")
    .addEventListener("click", () => dialog.close());
  document
    .querySelector(".r-dialog-done")
    .addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    const bounds = dialog.getBoundingClientRect();
    if (
      event.target === dialog &&
      (event.clientX < bounds.left ||
        event.clientX > bounds.right ||
        event.clientY < bounds.top ||
        event.clientY > bounds.bottom)
    )
      dialog.close();
  });
  dialog.addEventListener("close", () => {
    document.documentElement.classList.remove("has-dialog");
    returnFocus?.focus({ preventScroll: true });
  });
})();
