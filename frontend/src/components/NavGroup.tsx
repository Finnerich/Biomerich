import type { MouseEvent as ReactMouseEvent } from "react";
import type { NavGroupDef } from "../navConfig";
import { useStore } from "../store";
import { isUpdateAvailable } from "../update";

interface Props {
  group: NavGroupDef;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function spotlightMove(e: ReactMouseEvent<HTMLElement>) {
  const element = e.currentTarget;
  const rect = element.getBoundingClientRect();
  element.style.setProperty("--mx", `${e.clientX - rect.left}px`);
  element.style.setProperty("--my", `${e.clientY - rect.top}px`);
}

export function NavGroup({ group, collapsed, onToggleCollapse }: Props) {
  const currentTab = useStore((s) => s.currentTab);
  const setCurrentTab = useStore((s) => s.setCurrentTab);
  const updateAvailable = isUpdateAvailable(useStore((s) => s.releases));

  const activeInGroup = group.items.some((item) => item.tab === currentTab);

  return (
    <div className={`nav-group${collapsed ? " collapsed" : ""}`} data-group={group.id}>
      <button
        className={`nav-group-header${activeInGroup ? " active-group" : ""}`}
        onClick={onToggleCollapse}
      >
        <i className={`fa-solid ${group.icon} group-icon`}></i>
        <span className="group-label">{group.label}</span>
        <i className="fa-solid fa-chevron-down group-chevron"></i>
      </button>
      <div className="nav-group-items">
        {group.items.map((item, i) => (
          <button
            key={item.tab}
            className={`nav-item${currentTab === item.tab ? " active" : ""}`}
            data-tab={item.tab}
            data-rail-tip={item.label}
            style={{ ["--i" as string]: i }}
            onMouseMove={spotlightMove}
            onClick={() => setCurrentTab(item.tab)}
          >
            <i className={`fa-solid ${item.icon}`}></i>
            <span>{item.label}</span>
            {item.tab === "patchlog" && updateAvailable && <span className="nav-pill">New</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
