

import base64
import os
import subprocess
import sys
import time


IS_WINDOWS = sys.platform == "win32"
READY_EVENT = r"Local\SolRich_RobloxGuard_v4"
STOP_EVENT = r"Local\SolRich_RobloxGuard_Stop_v4"
PRESENCE_EVENT = r"Local\SolRich_RobloxGuard_Presence_v4"
LEGACY_STOP_EVENTS = (r"Local\SolRich_RobloxGuard_Stop_v3",)


def _event_exists(name):
    if not IS_WINDOWS:
        return False
    import ctypes
    from ctypes import wintypes

    synchronize = 0x00100000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenEventW.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenEventW(synchronize, False, name)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def is_ready():
    return _event_exists(READY_EVENT)


def _powershell_script(owner_process_id):


    return rf"""
$ErrorActionPreference = 'SilentlyContinue'
$ownerProcessId = {int(owner_process_id)}
$nativeSource = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class SolRichRobloxWindows
{{
    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumChildWindows(
        IntPtr parent,
        EnumWindowsProc callback,
        IntPtr lParam
    );

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(
        IntPtr hWnd,
        out uint processId
    );

    [DllImport("user32.dll")]
    private static extern bool PostMessage(
        IntPtr hWnd,
        uint message,
        IntPtr wParam,
        IntPtr lParam
    );

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT
    {{
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }}

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr FindWindow(string className, string title);

    [DllImport("user32.dll")]
    private static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(IntPtr hWnd, int command);

    public static bool HasVisibleWindow(uint wantedProcessId)
    {{
        bool found = false;
        EnumWindowsProc callback = delegate(IntPtr hWnd, IntPtr lParam)
        {{
            uint processId;
            GetWindowThreadProcessId(hWnd, out processId);
            if (processId == wantedProcessId && IsWindowVisible(hWnd))
                found = true;
            return !found;
        }};
        EnumWindows(callback, IntPtr.Zero);
        return found;
    }}

    public static int RequestClose(uint wantedProcessId)
    {{
        const uint WM_CLOSE = 0x0010;
        var sent = new HashSet<IntPtr>();
        EnumWindowsProc callback = delegate(IntPtr hWnd, IntPtr lParam)
        {{
            uint processId;
            GetWindowThreadProcessId(hWnd, out processId);
            if (processId == wantedProcessId && sent.Add(hWnd))
                PostMessage(hWnd, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
            return true;
        }};

        EnumWindows(callback, IntPtr.Zero);
        EnumChildWindows(new IntPtr(-3), callback, IntPtr.Zero);
        return sent.Count;
    }}

    public static bool RefreshOverflowTray()
    {{
        IntPtr hWnd = FindWindow("TopLevelWindowForOverflowXamlIsland", null);
        RECT rect;
        if (hWnd == IntPtr.Zero || !GetWindowRect(hWnd, out rect))
            return false;

        if (!IsWindowVisible(hWnd))
        {{
            ShowWindow(hWnd, 4); // SW_SHOWNOACTIVATE
            System.Threading.Thread.Sleep(120);
            GetWindowRect(hWnd, out rect);
        }}

        try
        {{
            const uint WM_MOUSEMOVE = 0x0200;
            int width = Math.Max(0, rect.Right - rect.Left);
            int height = Math.Max(0, rect.Bottom - rect.Top);
            var targets = new List<IntPtr>();
            targets.Add(hWnd);
            EnumWindowsProc childCallback = delegate(IntPtr child, IntPtr lParam)
            {{
                targets.Add(child);
                return true;
            }};
            EnumChildWindows(hWnd, childCallback, IntPtr.Zero);

            foreach (IntPtr target in targets)
            {{
                for (int y = 8; y < height; y += 12)
                {{
                    for (int x = 8; x < width; x += 12)
                    {{
                        int coordinates = (y << 16) | (x & 0xffff);
                        PostMessage(target, WM_MOUSEMOVE, IntPtr.Zero, new IntPtr(coordinates));
                    }}
                }}
                System.Threading.Thread.Sleep(20);
            }}
        }}
        finally
        {{
            ShowWindow(hWnd, 0); // SW_HIDE
        }}
        return true;
    }}
}}
'@
Add-Type -TypeDefinition $nativeSource

function Close-RobloxProcess([int]$processId) {{
    [SolRichRobloxWindows]::RequestClose([uint32]$processId) | Out-Null
    for ($attempt = 0; $attempt -lt 30; $attempt++) {{
        if ($null -eq (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {{
            Start-Sleep -Milliseconds 200
            [SolRichRobloxWindows]::RefreshOverflowTray() | Out-Null
            return
        }}
        Start-Sleep -Milliseconds 100
    }}
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
    [SolRichRobloxWindows]::RefreshOverflowTray() | Out-Null
}}

$mutexName = 'ROBLOX_singletonMutex'
$readyName = '{READY_EVENT}'
$stopName = '{STOP_EVENT}'
$presenceName = '{PRESENCE_EVENT}'
$presenceCreated = $false
$presenceEvent = [System.Threading.EventWaitHandle]::new(
    $true,
    [System.Threading.EventResetMode]::ManualReset,
    $presenceName,
    [ref]$presenceCreated
)
$createdNew = $false
$mutex = [System.Threading.Mutex]::new($true, $mutexName, [ref]$createdNew)
$ownsMutex = $createdNew
$stopCreated = $false
$stopEvent = [System.Threading.EventWaitHandle]::new(
    $false,
    [System.Threading.EventResetMode]::ManualReset,
    $stopName,
    [ref]$stopCreated
)
if ($stopCreated) {{ $stopEvent.Reset() }}

if (-not $ownsMutex) {{
    try {{ $ownsMutex = $mutex.WaitOne(0) }}
    catch [System.Threading.AbandonedMutexException] {{ $ownsMutex = $true }}
}}

while (-not $ownsMutex) {{
    if ($stopEvent.WaitOne(0)) {{
        $stopEvent.Dispose()
        $mutex.Dispose()
        $presenceEvent.Dispose()
        exit 0
    }}
    $owner = Get-Process -Id $ownerProcessId -ErrorAction SilentlyContinue
    $players = @(Get-Process -Name RobloxPlayerBeta -ErrorAction SilentlyContinue)
    $now = [DateTime]::UtcNow
    foreach ($player in $players) {{
        $player.Refresh()
        if (
            $player.MainWindowHandle -eq 0 -and
            ($now - $player.StartTime.ToUniversalTime()).TotalSeconds -ge 45
        ) {{
            Close-RobloxProcess $player.Id
        }}
    }}
    if ($null -eq $owner -and $players.Count -eq 0) {{
        $stopEvent.Dispose()
        $mutex.Dispose()
        $presenceEvent.Dispose()
        exit 0
    }}
    try {{ $ownsMutex = $mutex.WaitOne(500) }}
    catch [System.Threading.AbandonedMutexException] {{ $ownsMutex = $true }}
}}

$readyCreated = $false
$readyEvent = [System.Threading.EventWaitHandle]::new(
    $true,
    [System.Threading.EventResetMode]::ManualReset,
    $readyName,
    [ref]$readyCreated
)
$seenWindow = @{{}}
$hiddenSince = @{{}}
$firstSeen = @{{}}

try {{
    while (-not $stopEvent.WaitOne(0)) {{
        $now = [DateTime]::UtcNow
        $players = @(Get-Process -Name RobloxPlayerBeta -ErrorAction SilentlyContinue)
        $liveIds = @{{}}
        foreach ($player in $players) {{
            $player.Refresh()
            $key = [string]$player.Id
            $liveIds[$key] = $true
            if (-not $firstSeen.ContainsKey($key)) {{ $firstSeen[$key] = $now }}

            if ([SolRichRobloxWindows]::HasVisibleWindow([uint32]$player.Id)) {{
                $seenWindow[$key] = $true
                $hiddenSince.Remove($key)
                continue
            }}

            if ($seenWindow.ContainsKey($key)) {{
                if (-not $hiddenSince.ContainsKey($key)) {{
                    $hiddenSince[$key] = $now
                }} elseif (($now - $hiddenSince[$key]).TotalSeconds -ge 7) {{
                    Close-RobloxProcess $player.Id
                }}
            }} elseif (($now - $firstSeen[$key]).TotalSeconds -ge 45) {{
                # A player that never produced a real window is a failed launch
                # or an already orphaned tray process.
                Close-RobloxProcess $player.Id
            }}
        }}

        foreach ($key in @($firstSeen.Keys)) {{
            if (-not $liveIds.ContainsKey($key)) {{
                $firstSeen.Remove($key)
                $seenWindow.Remove($key)
                $hiddenSince.Remove($key)
            }}
        }}

        $owner = Get-Process -Id $ownerProcessId -ErrorAction SilentlyContinue
        if ($null -eq $owner -and $players.Count -eq 0) {{ break }}
        Start-Sleep -Milliseconds 500
    }}
}} finally {{
    $readyEvent.Reset()
    $readyEvent.Dispose()
    $stopEvent.Dispose()
    $presenceEvent.Dispose()
    if ($ownsMutex) {{ try {{ $mutex.ReleaseMutex() }} catch {{}} }}
    $mutex.Dispose()
}}
"""


def _start_helper():
    script = _powershell_script(os.getpid())
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    powershell = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )
    creation_flags = 0x08000000 | 0x00000200
    subprocess.Popen(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-EncodedCommand",
            encoded,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creation_flags,
    )


def ensure(timeout=2.5):
    if not IS_WINDOWS:
        return False
    if is_ready():
        return True
    _stop_legacy_helpers()
    if not _event_exists(PRESENCE_EVENT):
        try:
            _start_helper()
        except OSError as error:
            print(f"[Roblox] Could not start detached guard: {error}")
            return False

    deadline = time.monotonic() + max(0.0, float(timeout))
    while time.monotonic() < deadline:
        if is_ready():
            return True
        time.sleep(0.05)
    return is_ready()


def _signal_stop_event(name):
    
    if not IS_WINDOWS:
        return False
    import ctypes
    from ctypes import wintypes

    event_modify_state = 0x0002
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenEventW.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.SetEvent.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenEventW(event_modify_state, False, name)
    if not handle:
        return False
    try:
        return bool(kernel32.SetEvent(handle))
    finally:
        kernel32.CloseHandle(handle)


def _stop_legacy_helpers():
    for event_name in LEGACY_STOP_EVENTS:
        _signal_stop_event(event_name)


def request_stop(timeout=2.0):
    
    if not IS_WINDOWS:
        return False
    if not _signal_stop_event(STOP_EVENT):
        return False

    deadline = time.monotonic() + max(0.0, float(timeout))
    while time.monotonic() < deadline:
        if not _event_exists(PRESENCE_EVENT):
            return True
        time.sleep(0.05)
    return not _event_exists(PRESENCE_EVENT)
