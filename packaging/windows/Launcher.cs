using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

// 桌面外壳的入口。
//
// 职责边界:
//   * 这个 exe 只管"窗口"和"进程编排"
//   * 真正的面板逻辑仍在 app/desktop.py 起的 uvicorn 里 (仍然只监听 127.0.0.1)
//
// 单实例: 用命名互斥体 + 命名事件, 第二次双击只把已有窗口叫到前台,
// 不会起第二个面板、也不会抢端口。
[assembly: AssemblyTitle("VPS Deploy Panel")]
[assembly: AssemblyDescription("VPS Deploy Panel desktop client")]
[assembly: AssemblyCompany("VPS Deploy Panel")]
[assembly: AssemblyProduct("VPS Deploy Panel")]
[assembly: System.Runtime.Versioning.TargetFramework(".NETFramework,Version=v4.8")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

internal static class Launcher
{
    internal static string Root = AppDomain.CurrentDomain.BaseDirectory;
    internal static string Home;
    internal static Uri Panel;

    // 按 Windows 的命令行转义规则加引号, 路径里有空格或尾随反斜杠也不会出错
    internal static string Quote(string value)
    {
        var text = new StringBuilder("\"");
        int slashes = 0;
        foreach (char character in value)
        {
            if (character == '\\') { slashes++; continue; }
            if (character == '"')
                text.Append('\\', slashes * 2 + 1);
            else
                text.Append('\\', slashes);
            text.Append(character);
            slashes = 0;
        }
        text.Append('\\', slashes * 2);
        return text.Append('"').ToString();
    }

    private static string Option(string[] args, string key, string fallback)
    {
        int index = Array.IndexOf(args, key);
        return index >= 0 && index + 1 < args.Length ? args[index + 1] : fallback;
    }

    // 只有本机面板地址算"内部", 其它一律交给默认浏览器
    internal static bool Local(Uri uri)
    {
        return uri.Scheme == Panel.Scheme && uri.Host == Panel.Host && uri.Port == Panel.Port;
    }

    internal static void External(Uri uri)
    {
        Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true });
    }

    private static void Signal(string name)
    {
        try { using (var signal = EventWaitHandle.OpenExisting(name)) signal.Set(); }
        catch (WaitHandleCannotBeOpenedException) { }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            // DPI 感知必须在创建任何窗口之前设置
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Home = Path.GetFullPath(Option(args, "--home",
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                             "VPSDeployPanel")));
            int port = int.Parse(Option(args, "--port", "8787"));
            Panel = new Uri("http://127.0.0.1:" + port + "/");

            using (var sha = SHA256.Create())
            {
                // 互斥体名字带上数据目录和端口: 换了安装目录或端口就是另一套实例
                string key = BitConverter.ToString(sha.ComputeHash(
                    Encoding.UTF8.GetBytes(Home.ToUpperInvariant() + port))).Replace("-", "");
                string name = @"Local\VPSDeployPanel.Client." + key;

                // 后端自己会挑空闲端口, 通过这个文件把实际端口告诉外壳
                string portFile = Path.Combine(Home, "desktop.port");
                string command = "-I " + Quote(Path.Combine(Root, "app", "desktop.py")) +
                                 " --quiet --port-file " + Quote(portFile);
                foreach (string argument in args)
                    if (argument != "--ui-smoke") command += " " + Quote(argument);

                ProcessStartInfo start = new ProcessStartInfo(
                    Path.Combine(Root, "runtime", "python", "pythonw.exe"), command);
                start.WorkingDirectory = Root;
                start.UseShellExecute = false;
                start.CreateNoWindow = true;

                using (Process process = Process.Start(start))
                {
                    if (Array.IndexOf(args, "--stop") >= 0)
                    {
                        // --stop: 等后端优雅退出。部署任务在跑时后端会拒绝, 退出码非零。
                        // 窗口也要关掉 —— 只停后端会留下一个空壳窗口。
                        if (!process.WaitForExit(20000)) return 1;
                        int code = process.ExitCode;
                        if (code == 0) Signal(name + ".Exit");
                        return code;
                    }
                }

                bool first;
                using (var mutex = new Mutex(true, name, out first))
                {
                    if (!first)
                    {
                        // 已经有一个窗口了, 把它叫到前台
                        Signal(name + ".Focus");
                        return 0;
                    }
                    using (var focus = new EventWaitHandle(false, EventResetMode.AutoReset, name + ".Focus"))
                    using (var exit = new EventWaitHandle(false, EventResetMode.AutoReset, name + ".Exit"))
                    using (var window = new ClientWindow(portFile))
                    {
                        var focusWait = ThreadPool.RegisterWaitForSingleObject(focus, delegate
                        {
                            window.OnUi(window.FocusWindow);
                        }, null, -1, false);
                        // --stop 成功后退出会发这个事件, 窗口随之关闭
                        var exitWait = ThreadPool.RegisterWaitForSingleObject(exit, delegate
                        {
                            window.OnUi(delegate { window.Close(); });
                        }, null, -1, false);
                        Application.Run(window);
                        focusWait.Unregister(null);
                        exitWait.Unregister(null);
                    }
                    mutex.ReleaseMutex();
                }
                return 0;
            }
        }
        catch (Exception error)
        {
            if (Array.IndexOf(args, "--quiet") < 0)
                MessageBox.Show(error.Message, "VPS Deploy Panel",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
