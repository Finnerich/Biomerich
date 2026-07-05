import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { CustomSelect } from "./CustomSelect";

const OPTS = [
  { value: "a", label: "Alpha" },
  { value: "b", label: "Beta" },
  { value: "c", label: "Gamma" },
];

function setup(props: Partial<Parameters<typeof CustomSelect>[0]> = {}) {
  const onChange = vi.fn();
  const utils = render(
    <CustomSelect options={OPTS} value="a" onChange={onChange} aria-label="Pick" {...props} />,
  );
  const trigger = utils.container.querySelector(".cs-trigger") as HTMLElement;
  return { onChange, trigger, ...utils };
}

describe("CustomSelect (a11y)", () => {
  it("exposes the ARIA combobox/listbox pattern", () => {
    const { trigger, container } = setup();
    expect(trigger.getAttribute("role")).toBe("combobox");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(trigger.getAttribute("aria-haspopup")).toBe("listbox");
    expect(container.querySelector('[role="listbox"]')).toBeTruthy();
    const opts = container.querySelectorAll('[role="option"]');
    expect(opts.length).toBe(3);
    expect(container.querySelector('[role="option"][aria-selected="true"]')?.textContent).toBe("Alpha");
  });

  it("opens on ArrowDown and highlights the selected option", () => {
    const { trigger } = setup({ value: "b" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const activeId = trigger.getAttribute("aria-activedescendant");
    expect(activeId).toBeTruthy();
    expect(document.getElementById(activeId!)?.textContent).toBe("Beta");
  });

  it("navigates with arrows and chooses with Enter", () => {
    const { trigger, onChange } = setup({ value: "a" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("b");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });

  it("Home/End jump to first/last option", () => {
    const { trigger, onChange } = setup({ value: "b" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "End" });
    fireEvent.keyDown(trigger, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("c");
  });

  it("Escape closes without choosing", () => {
    const { trigger, onChange } = setup();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("does not open when disabled", () => {
    const { trigger } = setup({ disabled: true });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(trigger.getAttribute("tabIndex")).toBe("-1");
  });
});
