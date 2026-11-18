using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using System.Windows.Forms;

// 窗口位置记忆。
//
// 只在用户数据目录存一份, 不跟授权配置混在一起 —— 前者是使用习惯,
// 后者是凭据, 两者生命周期和敏感级别都不同。
internal static class WindowPlacement
{
    [StructLayout(LayoutKind.Sequential)]
    public struct Point { public int X, Y; }

    [StructLayout(LayoutKind.Sequential)]
    public struct Rect { public int Left, Top, Right, Bottom; }

    [StructLayout(LayoutKind.Sequential)]
    public struct Placement
    {
        public int Length, Flags, ShowCommand;
        public Point MinimumPosition, MaximumPosition;
        public Rect NormalPosition;
    }

    [DllImport("user32.dll")]
    private static extern bool GetWindowPlacement(IntPtr window, ref Placement placement);

    [DllImport("user32.dll")]
    private static extern bool SetWindowPlacement(IntPtr window, ref Placement placement);

    private static string FileName()
    {
        return Path.Combine(Launcher.Home, "window-main.json");
    }

    internal static void Restore(Form window)
    {
        window.WindowState = FormWindowState.Normal;
        var area = Screen.FromControl(window).WorkingArea;
        double scale = window.DeviceDpi / 96.0;
        // 屏幕不够大时等比缩小, 但保持面板可读的下限
        double fit = Math.Min(1.0, Math.Min(area.Width * .92 / (1440 * scale),
            area.Height * .92 / (900 * scale)));
        int width = (int)Math.Round(1440 * scale * fit);
        int height = (int)Math.Round(900 * scale * fit);
        window.MinimumSize = new System.Drawing.Size(Math.Min((int)(900 * scale), width),
            Math.Min((int)(600 * scale), height));
        window.StartPosition = FormStartPosition.Manual;
        window.Bounds = new System.Drawing.Rectangle(area.Left + (area.Width - width) / 2,
            area.Top + (area.Height - height) / 2, width, height);
        try
        {
            string file = FileName();
            if (!File.Exists(file)) return;
            var placement = new JavaScriptSerializer().Deserialize<Placement>(File.ReadAllText(file));
            var bounds = placement.NormalPosition;
            long savedWidth = (long)bounds.Right - bounds.Left;
            long savedHeight = (long)bounds.Bottom - bounds.Top;
            // 明显不合理的存档直接忽略: 换过显示器或分辨率后旧坐标会跑到屏幕外
            if (savedWidth < 200 || savedHeight < 150 || savedWidth > 32768 || savedHeight > 32768 ||
                (placement.ShowCommand != 1 && placement.ShowCommand != 3)) return;
            placement.Length = Marshal.SizeOf(typeof(Placement));
            placement.Flags = 0;
            window.StartPosition = FormStartPosition.Manual;
            SetWindowPlacement(window.Handle, ref placement);
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        catch (ArgumentException) { }
        catch (InvalidOperationException) { }
    }

    internal static void Save(Form window, FormWindowState visibleState)
    {
        if (!window.IsHandleCreated) return;
        try
        {
            var placement = new Placement { Length = Marshal.SizeOf(typeof(Placement)) };
            if (!GetWindowPlacement(window.Handle, ref placement)) return;
            // 最小化状态下关闭, 下次应回到上次可见的大小, 而不是最小化
            placement.ShowCommand = visibleState == FormWindowState.Maximized ? 3 : 1;
            placement.Flags = 0;
            Directory.CreateDirectory(Launcher.Home);
            string file = FileName(), temporary = file + ".tmp";
            File.WriteAllText(temporary, new JavaScriptSerializer().Serialize(placement));
            if (File.Exists(file)) File.Replace(temporary, file, null);
            else File.Move(temporary, file);
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
