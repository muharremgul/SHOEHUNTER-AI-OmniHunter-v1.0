import { splitSizes } from "./Profile";


test("keeps a normal and one-size-up preference for one person", () => {
  expect(splitSizes("42, 43, 42")).toEqual(["42", "43"]);
});

test("supports apparel and trouser size notation", () => {
  expect(splitSizes("M, L")).toEqual(["M", "L"]);
  expect(splitSizes("32/32, 34/32")).toEqual(["32/32", "34/32"]);
});
