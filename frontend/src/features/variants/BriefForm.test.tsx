import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BriefForm } from "./BriefForm";
import * as variantsApiModule from "@/api/variants";

// Suppress toast (sonner) side effects in tests
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

// Mock the API so no real network calls happen
vi.mock("@/api/variants", () => ({
  variantsApi: {
    generate: vi.fn(),
  },
}));

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderForm(onSuccess = vi.fn()) {
  const client = makeClient();
  return render(
    <QueryClientProvider client={client}>
      <BriefForm onSuccess={onSuccess} />
    </QueryClientProvider>
  );
}

// Helper: get the `n` input by name attribute (shadcn Form wraps in div, label points to div)
function getNInput(): HTMLInputElement {
  return document.querySelector('input[name="n"]') as HTMLInputElement;
}

describe("BriefForm — n field NaN / zero guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("defaults to 5", () => {
    renderForm();
    expect(getNInput().value).toBe("5");
  });

  it("accepts a valid integer between 1 and 5", () => {
    renderForm();
    fireEvent.change(getNInput(), { target: { value: "3" } });
    expect(getNInput().value).toBe("3");
  });

  it("clamps to 1 when 0 is entered (prevents zero submit)", () => {
    renderForm();
    fireEvent.change(getNInput(), { target: { value: "0" } });
    // Math.max(1, Math.min(5, 0)) = 1 → button label should show 1
    expect(screen.getByRole("button", { name: /1개 변주 생성/ })).toBeInTheDocument();
  });

  it("falls back to 5 when the field is cleared (empty string)", () => {
    renderForm();
    fireEvent.change(getNInput(), { target: { value: "" } });
    // parseInt("", 10) === NaN → fallback to 5
    expect(screen.getByRole("button", { name: /5개 변주 생성/ })).toBeInTheDocument();
  });

  it("clamps to 5 when value exceeds max", () => {
    renderForm();
    fireEvent.change(getNInput(), { target: { value: "9" } });
    // Math.max(1, Math.min(5, 9)) = 5
    expect(screen.getByRole("button", { name: /5개 변주 생성/ })).toBeInTheDocument();
  });

  it("calls mutate with n=5 fallback when field was cleared before submit", async () => {
    const mockGenerate = vi.fn().mockResolvedValue([]);
    vi.mocked(variantsApiModule.variantsApi).generate = mockGenerate;

    renderForm();

    // Fill required fields using name attribute selectors
    const conceptInput = document.querySelector('input[name="concept"]') as HTMLInputElement;
    const verticalInput = document.querySelector('input[name="vertical"]') as HTMLInputElement;
    const toneInput = document.querySelector('input[name="tone"]') as HTMLInputElement;
    fireEvent.change(conceptInput, { target: { value: "테스트 컨셉" } });
    fireEvent.change(verticalInput, { target: { value: "portrait" } });
    fireEvent.change(toneInput, { target: { value: "따뜻한" } });

    // Select at least one step — checkboxes are sr-only inside styled labels
    const checkboxes = screen.getAllByRole("checkbox", { hidden: true });
    // Directly update the value and dispatch change event (sr-only checkboxes)
    fireEvent.click(checkboxes[0]);

    // Clear the n field — should fall back to 5
    fireEvent.change(getNInput(), { target: { value: "" } });

    // Submit the form
    fireEvent.click(screen.getByRole("button", { name: /변주 생성/ }));

    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalled();
      const firstArg = mockGenerate.mock.calls[0][0] as { n: number };
      expect(firstArg.n).toBe(5);
    });
  });
});
