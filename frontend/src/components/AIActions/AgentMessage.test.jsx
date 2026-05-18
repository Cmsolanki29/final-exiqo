import { act, render, screen } from "@testing-library/react";
import AgentMessage from "./AgentMessage";

describe("AgentMessage typing UI", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("shows typing dots when streaming with no content yet", () => {
    render(
      <AgentMessage
        content=""
        steps={[]}
        plan={null}
        streaming
        timestamp={Date.now()}
      />
    );
    expect(screen.getByTestId("agent-typing-indicator")).toBeInTheDocument();
    expect(screen.queryByTestId("typewriter-text")).not.toBeInTheDocument();
  });

  it("uses typewriter effect when streaming with content", () => {
    render(
      <AgentMessage
        content="I have imple"
        steps={[]}
        plan={null}
        streaming
        timestamp={Date.now()}
      />
    );
    const tw = screen.getByTestId("typewriter-text");
    expect(tw.textContent.length).toBeLessThan("I have imple".length + 2);
    expect(screen.getByTestId("typewriter-cursor")).toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(200);
    });
    expect(tw.textContent).toContain("I have imple");
  });

  it("renders full text immediately when not streaming", () => {
    render(
      <AgentMessage
        content="Final answer ready."
        steps={[]}
        plan={null}
        streaming={false}
        timestamp={Date.now()}
      />
    );
    expect(screen.getByText(/Final answer ready/)).toBeInTheDocument();
    expect(screen.queryByTestId("typewriter-text")).not.toBeInTheDocument();
    expect(screen.queryByTestId("typewriter-cursor")).not.toBeInTheDocument();
  });
});
