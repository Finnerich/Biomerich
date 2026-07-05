import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { RangeSetting } from "./RangeSetting";

function setup(props: Partial<Parameters<typeof RangeSetting>[0]> = {}) {
  const onCommit = vi.fn();
  const utils = render(
    <RangeSetting
      name="Interval" desc="desc" min={0} max={100} step={5} value={20}
      onCommit={onCommit} {...props}
    />,
  );
  const input = utils.container.querySelector("input[type=range]") as HTMLInputElement;
  return { onCommit, input, ...utils };
}

describe("RangeSetting", () => {
  it("renders with the initial (clamped) value", () => {
    const { input } = setup();
    expect(input.value).toBe("20");
  });

  it("commits on release (pointer up), not on every change", () => {
    const { input, onCommit } = setup();
    fireEvent.change(input, { target: { value: "50" } });
    expect(onCommit).not.toHaveBeenCalled();
    fireEvent.pointerUp(input);
    expect(onCommit).toHaveBeenCalledWith(50);
  });

  it("clamps the committed value into [min,max] on the step grid", () => {
    const { input, onCommit } = setup({ min: 0, max: 100, step: 10 });
    fireEvent.change(input, { target: { value: "999" } });
    fireEvent.pointerUp(input);
    expect(onCommit).toHaveBeenCalledWith(100);
  });

  it("shows the formatted value when fmt is given", () => {
    const { getByText } = setup({ value: 90, fmt: (v) => `${v}%` });
    expect(getByText("90%")).toBeTruthy();
  });
});
