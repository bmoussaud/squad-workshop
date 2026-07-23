const form = document.querySelector("#generation-form");
const statusRegion = document.querySelector("#generation-status");
const resultRegion = document.querySelector("#result-region");

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = value;
  return element.innerHTML;
}

function showResult(payload, title) {
  const safeTitle = escapeHtml(title);
  const safeUrl = escapeHtml(payload.artifact.url);
  resultRegion.innerHTML = `
    <div class="result-heading">
      <p class="eyebrow">Latest creation</p>
      <h2 id="result-heading">${safeTitle}</h2>
    </div>
    <figure class="card-result">
      <img src="${safeUrl}" alt="Generated fantasy card for ${safeTitle}">
      <figcaption><span class="success-mark" aria-hidden="true">&#10003;</span><span>Generation succeeded</span></figcaption>
    </figure>
    <a class="secondary-action" href="/">Generate another card</a>`;
}

if (form && statusRegion && resultRegion) {
  form.addEventListener("submit", async (event) => {
    if (!form.reportValidity()) return;
    event.preventDefault();

    const button = form.querySelector("button[type='submit']");
    const title = form.elements.title.value.trim();
    const description = form.elements.description.value.trim();
    button.disabled = true;
    button.classList.add("is-busy");
    statusRegion.textContent = "Generating your card. This may take a moment.";

    try {
      const response = await fetch("/api/generations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, description }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error?.message || "The card could not be generated.");
      }
      showResult(payload, title);
      statusRegion.textContent = "Card generated successfully.";
      resultRegion.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      statusRegion.textContent = error instanceof Error ? error.message : "The card could not be generated.";
    } finally {
      button.disabled = false;
      button.classList.remove("is-busy");
    }
  });
}
