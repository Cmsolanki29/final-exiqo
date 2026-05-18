import { act, render, screen } from "@testing-library/react";
import { TypewriterText } from "./TypewriterText";

describe("TypewriterText", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("reveals text character by character while streaming", () => {
    const { getByTestId } = render(
      <TypewriterText text="Hello" isStreaming charDelayMs={12} />
    );
    const root = getByTestId("typewriter-text");

    expect(root.textContent).toBe("");

    act(() => {
      jest.advanceTimersByTime(36);
    });
    expect(root.textContent).toContain("Hel");

    act(() => {
      jest.advanceTimersByTime(24);
    });
    expect(root.textContent).toContain("Hello");
  });

  it("shows blinking cursor while streaming or catching up", () => {
    render(<TypewriterText text="Hi" isStreaming charDelayMs={12} />);
    expect(screen.getByTestId("typewriter-cursor")).toBeInTheDocument();
  });

  it("flushes full text and hides cursor when streaming ends", () => {
    const { getByTestId, rerender } = render(
      <TypewriterText text="Done" isStreaming charDelayMs={12} />
    );
    const root = getByTestId("typewriter-text");

    act(() => {
      jest.advanceTimersByTime(12);
    });
    expect(root.textContent).toContain("D");

    rerender(<TypewriterText text="Done" isStreaming={false} charDelayMs={12} />);

    expect(root.textContent).toContain("Done");
    expect(screen.queryByTestId("typewriter-cursor")).not.toBeInTheDocument();
  });

  it("keeps pace when text grows during stream (delta chunks)", () => {
    const { getByTestId, rerender } = render(
      <TypewriterText text="I have" isStreaming charDelayMs={12} />
    );
    const root = getByTestId("typewriter-text");

    act(() => {
      jest.advanceTimersByTime(72);
    });
    expect(root.textContent).toContain("I have");

    rerender(
      <TypewriterText text="I have implemented typing" isStreaming charDelayMs={12} />
    );

    act(() => {
      jest.advanceTimersByTime(200);
    });
    expect(root.textContent).toContain("implemented");
  });
});
