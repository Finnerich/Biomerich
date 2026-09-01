import type { Slot } from "./slots";

export interface CalibSubgroup {
  key: string;
  label: string;
  points: Slot[];
  regions: Slot[];
}
export interface CalibGroup {
  key: string;
  label: string;
  scope?: string;
  icon?: string;
  color?: string;
  points: Slot[];
  regions: Slot[];
  subgroups?: CalibSubgroup[];
}

export const MERCHANT_CALIB_GROUPS: CalibGroup[] = [
  { key: "general", label: "Merchant General", scope: "Shared by every merchant", points: [["dialogue_skip", "Dialogue Skip"]], regions: [["merchant_name", "Merchant Name"]] },
  {
    key: "shop", label: "Merchant Shop", scope: "Shared buy panel",
    points: [["buy_button", "Buy Button"], ["amount_box", "Amount Box"], ["set_max_button", "Set To Max Button"], ["close_button", "Close Button"]],
    regions: [["item_slot_1", "Item Slot 1"], ["item_slot_2", "Item Slot 2"], ["item_slot_3", "Item Slot 3"], ["item_slot_4", "Item Slot 4"], ["item_slot_5", "Item Slot 5"], ["amount_label", "Amount Label"], ["item_name", "Item Name (optional)"]],
  },
  { key: "mari", label: "Mari Dialogue", scope: "Mari only", points: [["open_button", "Open Button"], ["leave_button", "Leave Button"]], regions: [] },
  { key: "jester", label: "Jester Dialogue", scope: "Jester only", points: [["open_button", "Open Button"], ["exchange_button", "Exchange Button"], ["leave_button", "Leave Button"]], regions: [] },
  { key: "rin", label: "Rin Dialogue", scope: "Rin only", points: [["leave_button", "Leave Button"]], regions: [] },
];

export const EXTRA_CALIB_GROUPS: CalibGroup[] = [
  {
    key: "eden", label: "Eden Calibrations", icon: "fa-solid fa-circle-dot", color: "#a78bfa",
    points: [["eden_click", "Eden Click Point"]],
    regions: [],
  },
];
