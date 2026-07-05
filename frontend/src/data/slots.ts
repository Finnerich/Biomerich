export type Slot = readonly [string, string];

export const PIXEL_SLOTS: Slot[] = [
  ["inventory_button", "Inventory Button"],
  ["item_tab", "Item Tab"],
  ["search_bar", "Search Bar"],
  ["first_item_slot", "First Item Slot"],
  ["amount_box", "Amount Box"],
  ["use_button", "Use Button"],
];

export const FISHING_REGION_SLOTS: Slot[] = [
  ["fishing_failed", "Fishing Failed / Caught Text"],
  ["shop_name", "Shop Name (Captain Flarg)"],
];

export const FISHING_PIXEL_SLOTS: Slot[] = [
  ["cast_point", "Start Fishing Button"],
  ["bite_indicator", "Fish Indicator Pixel"],
  ["bar_sample", "Mid Bar Color Sample"],
  ["zone_left", "Bar Region Left"],
  ["zone_right", "Bar Region Right"],
  ["reel_click", "Reel Click Spot"],
  ["claim_button", "Close / Claim Button"],
  ["collection_button", "Collection Button"],
  ["collection_close_button", "Collection Close Button"],
  ["fish_dialogue", "Shop Dialogue"],
  ["sell_fish_button", "Sell Fish Button"],
  ["first_fish_slot", "First Fish Slot"],
  ["sell_all_button", "Sell All Button"],
  ["sell_confirm_button", "Sell Confirm Button"],
  ["fish_shop_close_button", "Shop Close Button"],
];
