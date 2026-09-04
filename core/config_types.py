
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AutobuyItem(TypedDict, total=False):
    name: str
    amount: int
    all: bool


class ScheduleEntry(TypedDict, total=False):
    accId: Optional[int]
    minutes: int


class FishingAccCfg(TypedDict, total=False):
    autoSell: bool
    sellAfter: int
    sellCycle: int
    route: str
    primeRoute: bool
    sellOnStart: bool


class CalibGroup(TypedDict, total=False):
    pixels: Dict[str, Any]
    regions: Dict[str, Any]


class CycleStep(TypedDict, total=False):
    type: str
    accId: int
    minutes: int
    afk: bool


class LimboAccountEntry(TypedDict, total=False):
    path: str
    edenWatch: bool
    edenInterval: int


class AutopopBiomeEntry(TypedDict, total=False):
    enabled: bool
    items: List[AutobuyItem]


class AutopopAccountEntry(TypedDict, total=False):
    enabled: bool
    biomes: Dict[str, AutopopBiomeEntry]


class FishingConfig(TypedDict, total=False):
    enabled: bool
    preset: str
    account: Optional[int]
    schedule: List[ScheduleEntry]
    webhookEnabled: bool
    accounts: Dict[str, FishingAccCfg]
    pixels: Dict[str, Any]


class CycleConfig(TypedDict, total=False):
    enabled: bool
    steps: List[CycleStep]
    limbo: Dict[str, Any]


class AutopopConfig(TypedDict, total=False):
    biomes: Dict[str, Any]
    accounts: Dict[str, AutopopAccountEntry]
    ocrFailsafe: bool
    amountRegion: Optional[List[int]]
    notifyUse: bool
    notifyFail: bool
    presets: Dict[str, Any]
    activePreset: str
    leaveLimboOnRareBiome: bool


class MerchantsConfig(TypedDict, total=False):
    calib: Dict[str, CalibGroup]
    autobuy: Dict[str, Any]
    buyLog: List[Any]
    preset: str


class EdenConfig(TypedDict, total=False):
    account: Optional[int]
    edenWatch: bool
    edenInterval: int


class Automation(TypedDict, total=False):
    mode: str
    biomeRandomizer: bool
    strangeController: bool
    merchantTeleporter: bool
    preset: str
    amount: str
    ocrFailsafe: Dict[str, bool]
    notifications: Dict[str, bool]
    pixels: Dict[str, Any]
    firstItemRegion: Optional[List[int]]
    biomePings: Dict[str, Any]
    autopop: AutopopConfig
    intervals: Dict[str, int]
    searchTerms: Dict[str, str]
    eden: EdenConfig
    fishing: FishingConfig
    cycle: CycleConfig
    merchants: MerchantsConfig
    calib: Dict[str, CalibGroup]


class AppSettings(TypedDict, total=False):
    hotkey: str
    modeHotkey: str
    antiAfkEnabled: bool
    antiAfkAction: str
    antiAfkInterval: int
    antiAfkStandalone: bool
    ramTrimEnabled: bool
    ramTrimInterval: int
    perfMode: str
    slowReset: bool
    fakePingGuard: bool
    fakePingPrompt: bool
    tesseractPromptDismissed: bool


class AccountModules(TypedDict, total=False):
    strangeController: bool
    biomeRandomizer: bool
    merchantTeleporter: bool
    auraDetection: bool


class Account(TypedDict, total=False):
    id: int
    name: str
    link: str
    avatar: str
    enabled: bool
    modules: AccountModules
    hasToken: bool
    tokenUser: str
    tokenValid: bool


class Webhook(TypedDict, total=False):
    id: int
    name: str
    url: str
    active: bool
    routedAccounts: List[int]


class EdenStats(TypedDict, total=False):
    count: int
    lastFound: str
    log: List[str]
    accountSeconds: Dict[str, float]


class ModuleUseCounts(TypedDict, total=False):
    strangeController: int
    biomeRandomizer: int
    combined: int


class CyberspaceAccountProgress(TypedDict, total=False):
    id: int
    name: str
    avatar: str
    enabled: bool
    active: bool
    modules: Dict[str, bool]
    lifetime: ModuleUseCounts
    session: ModuleUseCounts
    combinedLifetime: int
    combinedSession: int
    usesPerHour: float


class CyberspaceProgress(TypedDict, total=False):
    odds: int
    cyberspaceCount: int
    lifetime: ModuleUseCounts
    unattributed: ModuleUseCounts
    session: ModuleUseCounts
    sinceLast: ModuleUseCounts
    estimatedRemaining: int
    averageCycleOverdue: int
    progressPercent: float
    chanceSinceLastPercent: float
    etaSeconds: Optional[int]
    etaMode: str
    usesPerHour: float
    activeAccounts: int
    activeSources: int
    intervals: Dict[str, int]
    accounts: List[CyberspaceAccountProgress]
    lastCyberspace: str
    lastCyberspaceAccount: Optional[int]
    trackingSince: str
    anchorReason: str
    sessionCyberspaces: int
    accurateSinceLastCyberspace: bool


class ConfigRecovery(TypedDict, total=False):
    status: str
    preservedFile: Optional[str]


class BackendState(TypedDict, total=False):
    running: bool
    uptime: float
    version: str
    settings: AppSettings
    automation: Automation
    accounts: List[Account]
    webhooks: List[Webhook]
    biomeCounts: Dict[str, int]
    moduleCounts: Dict[str, int]
    cyberspaceProgress: CyberspaceProgress
    unknownBiomes: Dict[str, int]
    merchantCounts: Dict[str, int]
    edenStats: EdenStats
    configRecovery: Optional[ConfigRecovery]
