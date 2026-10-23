// Run with: node --test tests/js/
// Mirrors the backend validation cases so client and server stay in sync.
import { test } from "node:test";
import assert from "node:assert/strict";
import { validateExpense, CATEGORIES } from "../../static/js/validation.js";

const TODAY = "2026-10-15";
const valid = { title: "Lunch", amount: "250.50", category: "food", date: "2026-10-01" };

// Validate `valid` with one field overridden; return that field's message (or undefined).
function errorFor(field, value) {
  return validateExpense({ ...valid, [field]: value }, TODAY)[field];
}

test("a valid expense has no errors", () => {
  assert.deepEqual(validateExpense(valid, TODAY), {});
});

test("exports the four categories", () => {
  assert.deepEqual(CATEGORIES, ["food", "travel", "bills", "other"]);
});

test("title is required (empty, whitespace, missing)", () => {
  for (const value of ["", "   ", undefined, null]) {
    assert.equal(errorFor("title", value), "title is required");
  }
});

test("title length is checked after trimming", () => {
  assert.equal(errorFor("title", "a".repeat(100)), undefined);
  assert.equal(errorFor("title", `  ${"a".repeat(100)}  `), undefined);
  assert.equal(errorFor("title", "a".repeat(101)), "title must be at most 100 characters");
});

test("amount is required", () => {
  for (const value of ["", "  ", undefined, null]) {
    assert.equal(errorFor("amount", value), "amount is required");
  }
});

test("amount must be a number", () => {
  for (const value of ["abc", "NaN", "Infinity", "-Infinity", "12abc", "1,000", "0x10"]) {
    assert.equal(errorFor("amount", value), "amount must be a number", value);
  }
});

test("amount must be greater than 0", () => {
  for (const value of ["0", "0.00", "-5", "-0.01"]) {
    assert.equal(errorFor("amount", value), "amount must be greater than 0", value);
  }
});

test("amount allows at most 2 decimal places", () => {
  for (const value of ["1.005", "10.999", "0.001"]) {
    assert.equal(errorFor("amount", value), "amount must have at most 2 decimal places", value);
  }
  for (const value of ["1.50", "1.5", "10", "0.01", "1.500"]) {
    assert.equal(errorFor("amount", value), undefined, value);
  }
});

test("amount has an upper bound", () => {
  assert.equal(errorFor("amount", "99999999.99"), undefined);
  assert.equal(errorFor("amount", "100000000"), "amount must be at most 99999999.99");
});

test("amount accepts a JS number too", () => {
  assert.equal(errorFor("amount", 12.5), undefined);
});

test("category is required and must be known", () => {
  assert.equal(errorFor("category", ""), "category is required");
  assert.equal(errorFor("category", undefined), "category is required");
  assert.equal(errorFor("category", "shopping"), "category must be one of: food, travel, bills, other");
  assert.equal(errorFor("category", "Food"), "category must be one of: food, travel, bills, other");
  for (const category of CATEGORIES) assert.equal(errorFor("category", category), undefined);
});

test("date is optional", () => {
  assert.equal(errorFor("date", ""), undefined);
  assert.equal(errorFor("date", undefined), undefined);
});

test("date must be YYYY-MM-DD", () => {
  for (const value of ["15-10-2026", "2026/10/15", "2026-1-5", "yesterday", "2026-10-15T00:00"]) {
    assert.equal(errorFor("date", value), "date must be in YYYY-MM-DD format", value);
  }
});

test("date must be a real calendar date", () => {
  for (const value of ["2026-02-30", "2026-13-01", "2026-00-10", "2025-02-29", "0000-01-01"]) {
    assert.equal(errorFor("date", value), "date must be a valid calendar date", value);
  }
  assert.equal(errorFor("date", "2024-02-29"), undefined); // leap year
});

test("date cannot be in the future", () => {
  assert.equal(errorFor("date", TODAY), undefined);
  assert.equal(errorFor("date", "2026-10-16"), "date cannot be in the future");
});

test("reports every invalid field at once", () => {
  const errors = validateExpense({ title: "", amount: "abc", category: "", date: "bad" }, TODAY);
  assert.deepEqual(Object.keys(errors).sort(), ["amount", "category", "date", "title"]);
});
