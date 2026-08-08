const PALETTE = [
  "var(--cat-1)",
  "var(--cat-2)",
  "var(--cat-3)",
  "var(--cat-4)",
  "var(--cat-5)",
  "var(--cat-6)",
  "var(--cat-7)",
];

const cache = new Map();

export function colorForCategory(category) {
  if (cache.has(category)) return cache.get(category);
  const color = PALETTE[cache.size % PALETTE.length];
  cache.set(category, color);
  return color;
}
