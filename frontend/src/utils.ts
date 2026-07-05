export function isRobloxLink(link: string): boolean {
  try {
    let u = link.trim();
    if (!u.includes("://")) u = "https://" + u;
    const host = new URL(u).hostname.toLowerCase();
    return host === "roblox.com" || host.endsWith(".roblox.com");
  } catch {
    return false;
  }
}

export function maskWebhook(url: string | undefined): string {
  if (!url || !url.trim()) return "No webhook URL";
  const m = url.match(/discord(?:app)?\.com\/api\/(?:v\d+\/)?webhooks\/(\d+)/i);
  if (m) return `discord.com/api/webhooks/${m[1]}/...`;
  try {
    const u = url.includes("://") ? url : "https://" + url;
    return new URL(u).hostname + "/...";
  } catch {
    return "•••";
  }
}
