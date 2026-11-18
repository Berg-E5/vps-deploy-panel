using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

// 主窗口: WebView2 装面板页面。
//
// 安全约束 (和网页版一致, 不放宽):
//   * 页面只能留在本机面板地址上, 任何外链交给默认浏览器
//   * WebMessage 关闭 —— 页面 JS 碰不到宿主
//   * HostObjects 关闭
//   * 面板地址只从后端读, 页面自己不能改
internal sealed partial class ClientWindow : Form
{
    private readonly WebView2 view = new WebView2();
    private readonly Label message = new Label();
    private readonly string portFile;
    private Uri panel;

    internal ClientWindow(string portFilePath)
    {
        portFile = portFilePath;
        AutoScaleDimensions = new SizeF(96, 96);
        AutoScaleMode = AutoScaleMode.Dpi;
        Text = "VPS Deploy Panel";
        Icon = LoadIcon();
        Size = new Size(1440, 900);
        MinimumSize = new Size(900, 600);
        StartPosition = FormStartPosition.CenterScreen;
        WindowState = FormWindowState.Normal;
        view.Dock = DockStyle.Fill;
        message.Dock = DockStyle.Fill;
        message.TextAlign = ContentAlignment.MiddleCenter;
        message.Font = new Font("Microsoft YaHei UI", 12);
        message.Text = "正在启动 VPS Deploy Panel…";
        Controls.Add(view);
        Controls.Add(message);
        // 等 WinForms 应用完显示器的初始 DPI 缩放之后再恢复窗口大小,
        // 否则会按缩放后的尺寸再缩放一次
        Shown += delegate { WindowPlacement.Restore(this); };
        Resize += delegate { };
        FormClosing += delegate { WindowPlacement.Save(this, WindowState); };
        Shown += async delegate { await Start(); };
        FormClosed += delegate { view.Dispose(); };
    }

    private static Icon LoadIcon()
    {
        try
        {
            string path = Path.Combine(Launcher.Root, "vpsdeploy.ico");
            if (File.Exists(path)) return new Icon(path);
        }
        catch (Exception) { }
        return SystemIcons.Application;
    }

    internal void OnUi(Action action)
    {
        try { if (!IsDisposed && IsHandleCreated) BeginInvoke(action); }
        catch (InvalidOperationException) { }
    }

    internal void FocusWindow()
    {
        Show();
        if (WindowState == FormWindowState.Minimized) WindowState = FormWindowState.Normal;
        Activate();
    }

    // 后端会挑空闲端口 (8787 被占就往后找), 外壳必须等它把端口写出来
    private async Task<Uri> WaitForPanel()
    {
        using (var client = new HttpClient(new HttpClientHandler { UseProxy = false }))
        {
            client.Timeout = TimeSpan.FromSeconds(2);
            for (int attempt = 0; attempt < 80 && !IsDisposed; attempt++)
            {
                Uri candidate = ReadPort();
                if (candidate != null)
                {
                    try
                    {
                        var health = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(
                            await client.GetStringAsync(new Uri(candidate, "api/health")));
                        if (health.ContainsKey("security") && (string)health["security"] == "local-only")
                            return candidate;
                    }
                    catch (HttpRequestException) { }
                    catch (TaskCanceledException) { }
                    catch (InvalidOperationException) { }
                }
                await Task.Delay(250);
            }
        }
        return null;
    }

    private Uri ReadPort()
    {
        try
        {
            if (!File.Exists(portFile)) return null;
            string value = File.ReadAllText(portFile).Trim();
            if (!value.All(char.IsDigit) || value.Length == 0) return null;
            return new Uri("http://127.0.0.1:" + value + "/");
        }
        catch (IOException) { return null; }
        catch (UnauthorizedAccessException) { return null; }
    }

    private async Task Start()
    {
        try
        {
            var target = await WaitForPanel();
            if (target == null)
            {
                Fail("面板启动未完成，请稍后重新打开客户端。");
                return;
            }
            if (IsDisposed) return;
            panel = target;
            Launcher.Panel = target;
            var environment = await CoreWebView2Environment.CreateAsync(null,
                Path.Combine(Launcher.Home, "webview"));
            await Initialize(environment);
            view.CoreWebView2.Navigate(target.AbsoluteUri);
        }
        catch (Exception error)
        {
            Fail(error.Message);
        }
    }

    private async Task Initialize(CoreWebView2Environment env)
    {
        await view.EnsureCoreWebView2Async(env);
        // 页面 JS 不许和宿主对话
        view.CoreWebView2.Settings.AreHostObjectsAllowed = false;
        view.CoreWebView2.Settings.IsWebMessageEnabled = false;
        view.CoreWebView2.Settings.IsScriptEnabled = true;
        view.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
        view.CoreWebView2.Settings.IsStatusBarEnabled = false;

        // 外部链接一律交给默认浏览器, 不在窗口里开
        view.CoreWebView2.NewWindowRequested += delegate(object sender, CoreWebView2NewWindowRequestedEventArgs args)
        {
            args.Handled = true;
            try
            {
                Uri destination;
                if (Uri.TryCreate(args.Uri, UriKind.Absolute, out destination) && !Launcher.Local(destination))
                    Launcher.External(destination);
            }
            catch (Exception) { }
        };

        // 导航白名单: 离开本机面板地址就交给浏览器
        view.CoreWebView2.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs args)
        {
            Uri destination;
            if (!Uri.TryCreate(args.Uri, UriKind.Absolute, out destination))
            {
                args.Cancel = true;
                return;
            }
            if (Launcher.Local(destination)) return;
            args.Cancel = true;
            try { Launcher.External(destination); } catch (Exception) { }
        };

        view.CoreWebView2.NavigationCompleted += delegate(object sender, CoreWebView2NavigationCompletedEventArgs args)
        {
            if (!args.IsSuccess && args.WebErrorStatus != CoreWebView2WebErrorStatus.OperationCanceled)
                Fail("面板页面加载失败，请重新打开客户端。");
            else
                message.Visible = false;
        };
    }

    private void Fail(string text)
    {
        message.Text = text;
        message.Visible = true;
        view.Visible = false;
    }
}
