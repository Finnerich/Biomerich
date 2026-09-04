@echo off
setlocal
cd /d "%~dp0"

REM ============================================================================
REM  build.bat  --  STABLE / RELEASE build  ->  dist\SolRich-<version>.exe
REM  Windowed (no console). Uses %LOCALAPPDATA%\SolRich as config folder.
REM  For debugging a crash, use dev-build.bat instead (it keeps a console open).
REM ============================================================================

REM Pull APP_VERSION out of core\config.py (read-only, no imports) for the exe name.
set "VERSION="
for /f "usebackq delims=" %%v in (`python -c "import re,io;print(re.search('APP_VERSION[ ]*=[ ]*[\x27\x22]([^\x27\x22]+)', io.open('core/config.py',encoding='utf-8').read()).group(1))"`) do set "VERSION=%%v"
if not defined VERSION set "VERSION=unknown"
echo Building SolRich version %VERSION%

REM Keep the reviewed PyInstaller bootloader reproducible. Run
REM "python -m pip install -r requirements-dev.txt" if this check fails.
python -c "import importlib.metadata as m, sys; v=m.version('pyinstaller'); print('PyInstaller', v); sys.exit(0 if v == '6.22.2' else 1)"
if errorlevel 1 (
    echo ERROR: This release requires PyInstaller 6.22.2.
    echo Run: python -m pip install -r requirements-dev.txt
    exit /b 1
)

REM RELEASE build: strip dev-only features (Remote, Plugins, Link Extractor, Cycle
REM Builder, Limbo & Eden). Vite reads SOLRICH_RELEASE -> __RELEASE__ (tree-shakes the
REM frontend); the PyInstaller --runtime-hook below sets the same var for the exe so
REM core/buildflag.py resolves RELEASE=True. setlocal (top) scopes it to this build.
set "SOLRICH_RELEASE=1"

echo [1/2] Building React frontend (frontend\ -^> web-react-dist\)...
if not exist "frontend\node_modules" (
    echo   node_modules missing -- running npm install...
    pushd frontend
    call npm install
    if errorlevel 1 ( echo ERROR: npm install failed & popd & exit /b 1 )
    popd
)
pushd frontend
call npm run build
if errorlevel 1 ( echo ERROR: React build failed & popd & exit /b 1 )
popd
if not exist "web-react-dist\index.html" (
    echo ERROR: web-react-dist\index.html not found after build
    exit /b 1
)

echo.
echo [2/2] Packaging SolRich-%VERSION%.exe (stable, windowed)...
REM Write the Windows version resource so the exe has real file properties (helps AV on an
REM unsigned build). Regenerated from APP_VERSION each build.
python gen_version_info.py
if errorlevel 1 ( echo ERROR: version info generation failed & exit /b 1 )
python -m PyInstaller ^
    --noconsole ^
    --onefile ^
    --clean ^
    --noconfirm ^
    --noupx ^
    --name="SolRich-%VERSION%" ^
    --icon="frontend/public/assets/icon.ico" ^
    --version-file=version_info.txt ^
    --add-data="web-react-dist;web-react-dist" ^
    --add-data="core\aura_catalog.json;core" ^
    --collect-submodules uvicorn ^
    --collect-submodules websockets ^
    --exclude-module numpy ^
    --exclude-module eel ^
    --exclude-module gevent ^
    --runtime-hook=release_hook.py ^
    --exclude-module core.limbo ^
    --exclude-module core.limbo_paths ^
    --collect-all webview ^
    main.py
if errorlevel 1 ( echo ERROR: stable build failed & exit /b 1 )

echo.
echo Done.  dist\SolRich-%VERSION%.exe   (uses %%LOCALAPPDATA%%\SolRich)
endlocal
