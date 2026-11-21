"""构建 Windows 桌面客户端 (原生窗口 + WebView2)。

与浏览器版 (windows/build-installer.ps1) 的区别只在"外壳":
两边共用同一份 Python 运行时、同一份 app/ 代码、同一个后端。

产出:
  dist/VPSDeployPanel-<版本>-Setup.exe   桌面版安装包
  dist/VPSDeployPanel-<版本>-portable.zip 免安装包

依赖:
  * csc.exe         —— Windows 自带 (.NET Framework 4.8), 不用装 Visual Studio
  * WebView2 SDK    —— 从 nuget 官方源下载, 校验 SHA-256
  * Inno Setup      —— 编译安装包

用法:
  python packaging/windows/build.py
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.0.8"

# GitHub Actions on Windows may default stdout to cp1252. Chinese build
# messages must never turn a successful build into a UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, OSError):
        pass

# 固定版本 + SHA-256: WebView2 SDK 只认这三个文件, 换版本必须同时换哈希。
WEBVIEW_VERSION = "1.0.4314.35"
WEBVIEW_SHA256 = "90778deb1b77e36292828b4b5833c9255c27533f40e0ddd55891ae718944edc4"
WEBVIEW_URL = f"https://www.nuget.org/api/v2/package/Microsoft.Web.WebView2/{WEBVIEW_VERSION}"
WEBVIEW_FILES = {
    "lib/net462/Microsoft.Web.WebView2.Core.dll": "Microsoft.Web.WebView2.Core.dll",
    "lib/net462/Microsoft.Web.WebView2.WinForms.dll": "Microsoft.Web.WebView2.WinForms.dll",
    "build/native/x64/WebView2Loader.dll": "WebView2Loader.dll",
    "LICENSE.txt": "WebView2-LICENSE.txt",
}

# python-build-standalone: 自带运行时, 版本和哈希都钉死。
PYTHON_VERSION = "3.12.16"
PYTHON_BUILD = "20261110"
PYTHON_SHA256 = "e23fe5b16926de1d81661b1a97352e89fb167549c55a6825796ccd0f32ec7f1b"


def say(message: str) -> None:
    print(f"[desktop] {message}", flush=True)


def download(url: str, target: Path, digest: str) -> Path:
    """下载并校验 SHA-256。校验不过就中止, 不用损坏的文件继续。"""
    import urllib.request
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".download")
    say(f"下载 {url}")
    with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as out:
        shutil.copyfileobj(response, out)
    actual = hashlib.sha256(temporary.read_bytes()).hexdigest()
    if actual != digest:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"校验失败: 期望 {digest}, 实际 {actual}")
    temporary.replace(target)
    return target


def find_csc() -> Path:
    """csc.exe 是 Windows 自带的, 不用装 Visual Studio。"""
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework/v4.0.30319/csc.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("找不到 csc.exe。桌面客户端需要 .NET Framework 4.8 编译器 (Windows 自带)。")


def build_bundle(stage: Path) -> Path:
    """组装桌面版目录: 运行时 + 应用代码 + 原生外壳 + WebView2。"""
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    # 1) 运行时: 复用 windows/build-installer.ps1 准备好的那一份
    runtime = ROOT / "windows/build/runtime"
    if not (runtime / "python/pythonw.exe").is_file():
        raise RuntimeError(
            "运行时还没准备好。先跑 windows/build-installer.ps1, 或者用 --stage-runtime 传入目录。"
        )
    say("复制运行时")
    shutil.copytree(runtime, stage / "runtime")

    # 2) 应用代码
    say("复制应用代码")
    shutil.copytree(ROOT / "app", stage / "app",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(ROOT / "requirements-codex-worker.txt",
                    stage / "requirements-codex-worker.txt")

    # 3) WebView2
    downloads = ROOT / ".build/windows-downloads"
    package = download(WEBVIEW_URL, downloads / f"webview2-{WEBVIEW_VERSION}.nupkg", WEBVIEW_SHA256)
    with zipfile.ZipFile(package) as archive:
        for source, name in WEBVIEW_FILES.items():
            (stage / name).write_bytes(archive.read(source))

    # 4) 图标: 与界面里的品牌符号一致 (编译要用, 先拷过来)
    icon = ROOT / "windows/build/icon.ico"
    if not icon.is_file():
        raise RuntimeError("图标还没生成。先跑 windows/make-icon.py。")
    shutil.copyfile(icon, stage / "vpsdeploy.ico")
    # LICENSE
    shutil.copyfile(ROOT / "LICENSE", stage / "LICENSE")

    # 5) 编译原生外壳
    say("编译原生外壳")
    csc = find_csc()
    output = stage / "VPSDeployPanel.exe"
    subprocess.run([
        str(csc), "/nologo", "/target:winexe", "/platform:x64",
        "/reference:System.Windows.Forms.dll",
        "/reference:System.Drawing.dll",
        "/reference:System.Net.Http.dll",
        "/reference:System.Web.Extensions.dll",
        f"/reference:{stage / 'Microsoft.Web.WebView2.Core.dll'}",
        f"/reference:{stage / 'Microsoft.Web.WebView2.WinForms.dll'}",
        f"/win32icon:{stage / 'vpsdeploy.ico'}",
        f"/win32manifest:{ROOT / 'packaging/windows/app.manifest'}",
        f"/out:{output}",
        str(ROOT / "packaging/windows/Launcher.cs"),
        str(ROOT / "packaging/windows/ClientWindow.cs"),
        str(ROOT / "packaging/windows/WindowPlacement.cs"),
    ], check=True, cwd=ROOT / "packaging/windows")
    if not output.is_file():
        raise RuntimeError("原生外壳编译失败")

    # 5) .NET Framework 4.8 运行时配置 (PerMonitorV2 DPI)
    shutil.copyfile(ROOT / "packaging/windows/VPSDeployPanel.exe.config", stage / "VPSDeployPanel.exe.config")

    # 5b) 卸载清理脚本 (装到 scripts\ 下, 卸载时先停进程再删文件)
    (stage / "scripts").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "packaging/windows/Uninstall-Desktop.ps1", stage / "scripts/Uninstall-Desktop.ps1")

    # 5c) LICENSE / README 随包
    shutil.copyfile(ROOT / "LICENSE", stage / "LICENSE")
    shutil.copyfile(ROOT / "README.md", stage / "README.md")

    manifest = {
        "version": VERSION,
        "python": {"version": PYTHON_VERSION, "sha256": PYTHON_SHA256},
        "webview2_sdk": {"version": WEBVIEW_VERSION, "sha256": WEBVIEW_SHA256},
        "signed": False,
    }
    (stage / "BUILD-MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return stage

def main() -> int:
    if sys.platform != "win32":
        raise RuntimeError("桌面客户端只能在 Windows 上构建。")
    stage = ROOT / ".build/windows-desktop"
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)

    bundle = build_bundle(stage)
    say("桌面版目录就绪")

    # Inno Setup
    iscc = None
    for candidate in [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Inno Setup 6/ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]:
        if candidate.is_file():
            iscc = candidate
            break
    if iscc is None:
        raise RuntimeError("找不到 Inno Setup (ISCC.exe)。先装: winget install JRSoftware.InnoSetup")

    say("编译安装包")
    subprocess.run([
        str(iscc), f"/DAppVersion={VERSION}", f"/DBundleDir={stage}", f"/DOutputDir={output}",
        str(ROOT / "packaging/windows/installer.iss"),
    ], check=True)

    setup = output / f"VPSDeployPanel-{VERSION}-Desktop-Setup.exe"
    if not setup.is_file():
        raise RuntimeError("安装包没有生成")
    say(f"完成: {setup} ({setup.stat().st_size // 1024 // 1024} MB)")

    # 免安装包: 只包含 exe + WebView2 + 运行时 + app/ (无安装脚本、无卸载器)
    portable = output / f"VPSDeployPanel-{VERSION}-portable.zip"
    say(f"生成免安装包: {portable}")
    with zipfile.ZipFile(portable, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in sorted(bundle.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts:
                # 安装脚本、配置模板、卸载器不进免安装包
                if file.name not in {"installer.iss", "VPSDeployPanel.exe.config", "Uninstall-Desktop.ps1"}:
                    zf.write(file, file.relative_to(bundle))
        say(f"完成免安装包: {portable} ({portable.stat().st_size // 1024 // 1024} MB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
