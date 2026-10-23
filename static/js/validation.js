// Client-side validation that mirrors the backend rules in app/schemas.py.
// Pure functions only (no DOM), so it can be unit-tested with Node.
// Messages are kept identical to the API's so users see the same wording either way.

export const CATEGORIES = ["food", "travel", "bills", "other"];

export const TITLE_MAX_LENGTH = 100;
export const MAX_AMOUNT = 99999999.99;

// A plain decimal number, optionally with an exponent: "12", "12.50", ".5", "1e3".
const NUMBER_PATTERN = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function validateTitle(title) {
  const trimmed = String(title ?? "").trim();
  if (trimmed === "") return "title is required";
  if (trimmed.length > TITLE_MAX_LENGTH) {
    return `title must be at most ${TITLE_MAX_LENGTH} characters`;
  }
  return null;
}

// Counts decimal places on the string itself (float math would turn 1.005 into 1.00499...).
// Trailing zeros don't count, matching the backend ("1.500" equals 1.50).
function decimalPlaces(text) {
  const mantissa = text.split(/[eE]/)[0];
  const fraction = mantissa.includes(".") ? mantissa.split(".")[1] : "";
  return fraction.replace(/0+$/, "").length;
}

function validateAmount(amount) {
  const text = String(amount ?? "").trim();
  if (text === "") return "amount is required";
  if (!NUMBER_PATTERN.test(text)) return "amount must be a number";
  const value = Number(text);
  if (!Number.isFinite(value)) return "amount must be a number";
  if (value <= 0) return "amount must be greater than 0";
  if (decimalPlaces(text) > 2) return "amount must have at most 2 decimal places";
  if (value > MAX_AMOUNT) return `amount must be at most ${MAX_AMOUNT}`;
  return null;
}

function validateCategory(category) {
  if (!category) return "category is required";
  if (!CATEGORIES.includes(category)) {
    return `category must be one of: ${CATEGORIES.join(", ")}`;
  }
  return null;
}

// True when "YYYY-MM-DD" names a real day (rejects 2026-02-30, month 13, year 0000).
export function isRealDate(text) {
  const [year, month, day] = text.split("-").map(Number);
  if (year < 1) return false;
  const date = new Date(year, month - 1, day);
  date.setFullYear(year); // Date() maps years 0-99 to 1900-1999; undo that.
  return (
    date.getFullYear() === year &&
    date.getMonth() === month - 1 &&
    date.getDate() === day
  );
}

// `today` is a "YYYY-MM-DD" string; same-format strings compare correctly as text.
function validateDate(date, today) {
  if (!date) return null; // optional: the server uses today's date
  if (!DATE_PATTERN.test(date)) return "date must be in YYYY-MM-DD format";
  if (!isRealDate(date)) return "date must be a valid calendar date";
  if (date > today) return "date cannot be in the future";
  return null;
}

// Returns {} when valid, otherwise { field: message } for each invalid field.
export function validateExpense({ title, amount, category, date }, today) {
  const errors = {};
  const checks = {
    title: validateTitle(title),
    amount: validateAmount(amount),
    category: validateCategory(category),
    date: validateDate(date, today),
  };
  for (const [field, message] of Object.entries(checks)) {
    if (message) errors[field] = message;
  }
  return errors;
}
