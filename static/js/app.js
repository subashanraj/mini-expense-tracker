// UI logic: holds a small state object, talks to the API and renders the page.
// All user data is inserted with textContent (never innerHTML) to prevent XSS.
import { listExpenses, createExpense, deleteExpense, getSummary } from "./api.js";
import { validateExpense, CATEGORIES } from "./validation.js";

const PAGE_LIMIT = 10;
const FIELDS = ["title", "amount", "category", "date"];
const CATEGORY_LABELS = { food: "Food", travel: "Travel", bills: "Bills", other: "Other" };

const state = {
  page: 1,
  category: "",       // "" means all categories
  totalPages: 1,
  listRequestId: 0,   // lets us ignore responses from outdated list requests
  isSubmitting: false,
  isDeleting: false,
  pendingDelete: null, // { expense, row } while the dialog is open
  newExpenseId: null,  // highlighted with an animation on the next render
};

// Shortcut for document.getElementById.
const $ = (id) => document.getElementById(id);

// ---------- Formatting helpers ----------

const moneyFormat = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });
const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });

function formatMoney(value) {
  return moneyFormat.format(Number(value));
}

// Parse "YYYY-MM-DD" as a *local* date; new Date("YYYY-MM-DD") would be UTC midnight.
function formatDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return dateFormat.format(new Date(year, month - 1, day));
}

function pad(number) {
  return String(number).padStart(2, "0");
}

// Today's date in the user's local time zone (toISOString() would use UTC).
function todayLocal() {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function currentMonthLocal() {
  return todayLocal().slice(0, 7);
}

// API messages are lowercase ("title is required"); capitalize them for display.
function displayMessage(message) {
  return message.charAt(0).toUpperCase() + message.slice(1);
}

// Small helper to create an element with a class and text in one line.
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function categoryBadge(category) {
  const badge = el("span", `badge badge-${category}`);
  badge.append(el("span", "dot"), document.createTextNode(CATEGORY_LABELS[category] || category));
  return badge;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------- Toasts ----------

function showToast(message, type = "success") {
  const toast = el("div", `toast toast-${type}`, message);
  $("toasts").append(toast);
  setTimeout(() => {
    toast.classList.add("toast-leaving");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ---------- Expense list ----------

function renderListSkeleton() {
  const list = el("ul", "expense-list");
  list.setAttribute("aria-busy", "true");
  list.setAttribute("aria-label", "Loading expenses");
  for (let i = 0; i < 5; i++) {
    const row = el("li", "expense-row skeleton-row");
    row.append(el("span", "skeleton skeleton-text"), el("span", "skeleton skeleton-amount"));
    list.append(row);
  }
  $("list-body").replaceChildren(list);
}

// A message with an optional button, used for empty and error states.
function renderListMessage(message, { isError = false, onRetry } = {}) {
  const box = el("div", isError ? "state state-error" : "state", message);
  if (isError) box.setAttribute("role", "alert");
  if (onRetry) {
    const retry = el("button", "btn btn-secondary", "Retry");
    retry.type = "button";
    retry.addEventListener("click", onRetry);
    box.append(retry);
  }
  $("list-body").replaceChildren(box);
  $("list-totals").hidden = true;
  $("pagination").hidden = true;
}

function createExpenseRow(expense) {
  const row = el("li", "expense-row");
  if (expense.id === state.newExpenseId) row.classList.add("row-new");

  const info = el("div", "expense-info");
  const meta = el("div", "expense-meta");
  meta.append(categoryBadge(expense.category), el("span", "muted", formatDate(expense.date)));
  info.append(el("span", "expense-title", expense.title), meta);

  const amount = el("span", "expense-amount", formatMoney(expense.amount));

  const deleteButton = el("button", "btn btn-icon", "Delete");
  deleteButton.type = "button";
  deleteButton.setAttribute("aria-label", `Delete ${expense.title}`);
  deleteButton.addEventListener("click", () => openDeleteDialog(expense, row));

  row.append(info, amount, deleteButton);
  return row;
}

function renderList(data) {
  // Totals come from the API and cover every row matching the filter, not just this page.
  $("total-amount").textContent = formatMoney(data.total_amount);
  $("total-count").textContent = `${data.total_count} ${data.total_count === 1 ? "expense" : "expenses"}`;
  $("list-totals").hidden = false;

  const list = el("ul", "expense-list");
  data.items.forEach((expense) => list.append(createExpenseRow(expense)));
  $("list-body").replaceChildren(list);
  state.newExpenseId = null;

  $("page-info").textContent = `Page ${state.page} of ${state.totalPages}`;
  $("prev-page").disabled = state.page <= 1;
  $("next-page").disabled = state.page >= state.totalPages;
  $("pagination").hidden = false;
}

async function loadExpenses() {
  const requestId = ++state.listRequestId;
  renderListSkeleton();
  try {
    const data = await listExpenses({ category: state.category, page: state.page, limit: PAGE_LIMIT });
    if (requestId !== state.listRequestId) return; // a newer request has started

    state.totalPages = Math.max(1, Math.ceil(data.total_count / PAGE_LIMIT));

    // e.g. the last row on the last page was deleted: step back to the new last page.
    if (data.items.length === 0 && state.page > 1 && data.total_count > 0) {
      state.page = state.totalPages;
      return loadExpenses();
    }

    if (data.total_count === 0) {
      renderListMessage(state.category ? "No expenses match this filter." : "No expenses yet. Add your first one!");
      return;
    }
    renderList(data);
  } catch (error) {
    if (requestId !== state.listRequestId) return;
    renderListMessage(error.message, { isError: true, onRetry: loadExpenses });
  }
}

// ---------- Monthly summary ----------

function renderSummaryMessage(message, { isError = false } = {}) {
  const box = el("div", isError ? "state state-error" : "state", message);
  if (isError) {
    box.setAttribute("role", "alert");
    const retry = el("button", "btn btn-secondary", "Retry");
    retry.type = "button";
    retry.addEventListener("click", loadSummary);
    box.append(retry);
  }
  $("summary-body").replaceChildren(box);
}

function renderSummarySkeleton() {
  const grid = el("div", "summary-grid");
  grid.setAttribute("aria-busy", "true");
  grid.append(el("div", "skeleton skeleton-card summary-total"));
  CATEGORIES.forEach(() => grid.append(el("div", "skeleton skeleton-card")));
  $("summary-body").replaceChildren(grid);
}

function renderSummary(data) {
  const grid = el("div", "summary-grid");

  const totalCard = el("div", "summary-card summary-total");
  totalCard.append(el("span", "muted", "Total spent"), el("strong", "summary-amount", formatMoney(data.total)));
  grid.append(totalCard);

  for (const category of CATEGORIES) {
    const amount = Number(data.totals[category]);
    const percent = data.total > 0 ? Math.round((amount / data.total) * 100) : 0;

    const card = el("div", "summary-card");
    const bar = el("div", "bar");
    bar.setAttribute("role", "img");
    bar.setAttribute("aria-label", `${CATEGORY_LABELS[category]}: ${percent}% of the month's spending`);
    const fill = el("div", `bar-fill bar-${category}`);
    fill.style.width = `${percent}%`;
    bar.append(fill);

    card.append(categoryBadge(category), el("strong", "summary-amount", formatMoney(amount)), bar,
      el("span", "muted small", `${percent}%`));
    grid.append(card);
  }
  $("summary-body").replaceChildren(grid);
}

let summaryRequestId = 0;

async function loadSummary() {
  const requestId = ++summaryRequestId;
  const month = $("summary-month").value || currentMonthLocal();
  renderSummarySkeleton();
  try {
    const data = await getSummary(month);
    if (requestId === summaryRequestId) renderSummary(data);
  } catch (error) {
    if (requestId === summaryRequestId) renderSummaryMessage(error.message, { isError: true });
  }
}

// ---------- Add expense form ----------

function setFieldError(field, message) {
  const input = $(field);
  const error = $(`${field}-error`);
  error.textContent = message ? displayMessage(message) : "";
  if (message) input.setAttribute("aria-invalid", "true");
  else input.removeAttribute("aria-invalid");
}

function showFormError(message) {
  const banner = $("form-error");
  banner.textContent = message ? displayMessage(message) : "";
  banner.hidden = !message;
}

function setSubmitting(isSubmitting) {
  state.isSubmitting = isSubmitting;
  const button = $("submit-button");
  button.disabled = isSubmitting;
  button.classList.toggle("is-loading", isSubmitting);
  button.querySelector(".btn-label").textContent = isSubmitting ? "Saving…" : "Add expense";
}

function resetForm() {
  $("expense-form").reset();
  $("date").value = todayLocal();
  FIELDS.forEach((field) => setFieldError(field, null));
}

async function handleSubmit(event) {
  event.preventDefault();
  if (state.isSubmitting) return; // guard against double submit

  const today = todayLocal();
  const values = {
    title: $("title").value,
    amount: $("amount").value.trim(),
    category: $("category").value,
    date: $("date").value,
  };

  showFormError(null);
  const errors = validateExpense(values, today);
  FIELDS.forEach((field) => setFieldError(field, errors[field]));
  if (Object.keys(errors).length > 0) {
    $(FIELDS.find((field) => errors[field])).focus(); // move focus to the first problem
    return;
  }

  setSubmitting(true);
  try {
    const created = await createExpense({
      title: values.title.trim(),
      amount: Number(values.amount),
      category: values.category,
      date: values.date || undefined, // omitted -> server uses today
    });
    resetForm();
    showToast(`Added "${created.title}"`);
    state.newExpenseId = created.id;
    state.page = 1;
    loadExpenses();
    loadSummary();
  } catch (error) {
    showFormError(error.message); // e.g. a 400 from the server, or a network error
  } finally {
    setSubmitting(false);
  }
}

// ---------- Delete ----------

function openDeleteDialog(expense, row) {
  state.pendingDelete = { expense, row };
  $("delete-title").textContent = expense.title;
  $("delete-amount").textContent = formatMoney(expense.amount);
  $("delete-dialog").showModal();
}

function setDeleting(isDeleting) {
  state.isDeleting = isDeleting;
  const button = $("confirm-delete");
  button.disabled = isDeleting;
  button.textContent = isDeleting ? "Deleting…" : "Delete";
}

async function handleConfirmDelete() {
  if (!state.pendingDelete || state.isDeleting) return;
  const { expense, row } = state.pendingDelete;

  setDeleting(true);
  try {
    await deleteExpense(expense.id);
    $("delete-dialog").close();
    row.classList.add("row-removing");
    await wait(250); // let the fade-out play before re-rendering
    showToast(`Deleted "${expense.title}"`);
  } catch (error) {
    $("delete-dialog").close();
    showToast(error.message, "error"); // e.g. 404 "Expense not found" if already deleted
  } finally {
    setDeleting(false);
  }
  // Reload either way so the list reflects the server (loadExpenses handles an emptied page).
  loadExpenses();
  loadSummary();
}

// ---------- Wiring ----------

function init() {
  const today = todayLocal();
  $("date").max = today;
  $("date").value = today;
  $("summary-month").value = currentMonthLocal();
  $("summary-month").max = currentMonthLocal();

  $("expense-form").addEventListener("submit", handleSubmit);
  // Clear a field's error as soon as the user edits it.
  FIELDS.forEach((field) => $(field).addEventListener("input", () => setFieldError(field, null)));

  $("filter-category").addEventListener("change", (event) => {
    state.category = event.target.value;
    state.page = 1;
    loadExpenses();
  });
  $("prev-page").addEventListener("click", () => {
    if (state.page > 1) { state.page -= 1; loadExpenses(); }
  });
  $("next-page").addEventListener("click", () => {
    if (state.page < state.totalPages) { state.page += 1; loadExpenses(); }
  });

  $("summary-month").addEventListener("change", loadSummary);

  $("confirm-delete").addEventListener("click", handleConfirmDelete);
  $("delete-dialog").addEventListener("close", () => { state.pendingDelete = null; });
  // Don't let Escape close the dialog while a delete request is in flight.
  $("delete-dialog").addEventListener("cancel", (event) => {
    if (state.isDeleting) event.preventDefault();
  });

  loadExpenses();
  loadSummary();
}

init();
