/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";

// Silence next/navigation in tests
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  redirect: vi.fn(),
}));

// Silence next/image
vi.mock("next/image", () => ({
  default: ({ src, alt }: { src: string; alt: string }) => {
    // eslint-disable-next-line @next/next/no-img-element
    const { createElement } = require("react");
    return createElement("img", { src, alt });
  },
}));
