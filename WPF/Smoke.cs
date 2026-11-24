using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Markup;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;

// Compile beside the portable executable; pass input, output directory and settings screenshot.
static class Smoke
{
    [STAThread]
    static int Main(string[] args)
    {
        var app = new Application();
        var exe = Assembly.LoadFrom(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "CryptArch V2 Beta.exe"));
        Window window;
        using (var stream = exe.GetManifestResourceStream("Workspace.xaml"))
            window = (Window)XamlReader.Load(stream);
        var type = exe.GetType("Workspace", true);
        var flags = BindingFlags.Instance | BindingFlags.NonPublic;
        var languageFile = Path.Combine(args[1], "test-language.txt");
        var controller = Activator.CreateInstance(type, flags, null, new object[] { window, languageFile }, null);
        bool timedOut = false;
        window.ContentRendered += (s, e) =>
        {
            var quality = (ComboBox)window.FindName("Quality");
            var outputPicker = (Button)window.FindName("ChooseOutput");
            var pause = (Button)window.FindName("Pause");
            var cancel = (Button)window.FindName("Cancel");
            if (quality.IsVisible || outputPicker.IsVisible || pause.ActualWidth != pause.ActualHeight ||
                cancel.ActualWidth != cancel.ActualHeight || !pause.IsVisible || !cancel.IsVisible)
                throw new InvalidOperationException("Home layout contains settings or non-square action buttons.");
            var home = (FrameworkElement)window.FindName("HomeContent");
            var workspace = (ScrollViewer)window.FindName("Workspace");
            var center = home.TranslatePoint(new Point(home.ActualWidth / 2, home.ActualHeight / 2), workspace);
            if (home.ActualWidth > 860 || Math.Abs(center.Y - workspace.ViewportHeight / 2) > 4)
                throw new InvalidOperationException("Home is not centered in the workspace.");
            SavePreview(window, Path.ChangeExtension(args[2], ".home.png"));
            ((Button)window.FindName("NavQueue")).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.UpdateLayout();
            if (!((ScrollViewer)window.FindName("QueuePane")).IsVisible ||
                !((TextBlock)window.FindName("QueueEmptyText")).IsVisible || window.OwnedWindows.Count != 0)
                throw new InvalidOperationException("Queue is not an inline empty state.");
            type.GetMethod("Handle", flags).Invoke(controller, new object[] { "started", new object[] { args[0] } });
            window.UpdateLayout();
            var queue = (ListBox)window.FindName("QueueFiles");
            if (!queue.IsVisible || queue.Items.Count != 1 || ((TextBlock)window.FindName("QueueEmptyText")).IsVisible)
                throw new InvalidOperationException("The queue page did not show the current file.");
            ((Button)window.FindName("NavAbout")).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            if (!((ScrollViewer)window.FindName("AboutPane")).IsVisible || window.OwnedWindows.Count != 0)
                throw new InvalidOperationException("About opened outside the workspace.");
            window.Dispatcher.BeginInvoke(DispatcherPriority.ApplicationIdle, new Action(() =>
            {
                var notice = window.OwnedWindows.Cast<Window>().Single();
                var keep = (Button)notice.FindName("NoticeBack");
                if (notice.Owner != window || notice.ShowInTaskbar || notice.WindowStyle != WindowStyle.None ||
                    !keep.IsVisible || !keep.IsDefault)
                    throw new InvalidOperationException("The themed confirmation is not owned with a safe default.");
                SavePreview(notice, Path.ChangeExtension(args[2], ".notice.png"));
                keep.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            }));
            if ((bool)type.GetMethod("ConfirmStop", flags).Invoke(controller, null))
                throw new InvalidOperationException("The safe confirmation action stopped compression.");
            type.GetMethod("SetPaths", flags).Invoke(controller, new object[] { args[0], args[1] });
            quality.SelectedIndex = 2;
            ((Button)window.FindName("NavSettings")).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            if (((ScrollViewer)window.FindName("SettingsPane")).Visibility != Visibility.Visible)
                throw new InvalidOperationException("Settings did not open.");
            ((ComboBox)window.FindName("Language")).SelectedIndex = 1;
            window.UpdateLayout();
            if (File.ReadAllText(languageFile) != "en" || (string)quality.SelectedItem != "Maximum compression")
                throw new InvalidOperationException("Language change did not preserve the selected quality or save the setting.");
            if (!quality.IsVisible || !outputPicker.IsVisible)
                throw new InvalidOperationException("Compression and output controls missing from Settings.");
            ((ComboBox)window.FindName("Workers")).SelectedIndex = 1;
            type.GetMethod("SetOutputFolder", flags).Invoke(controller, new object[] { args[1] });
            type.GetMethod("ChooseSource", flags).Invoke(controller, new object[] { args[0] });
            if (((TextBlock)window.FindName("OutputPath")).Text != args[1])
                throw new InvalidOperationException("Choosing a source reset the custom output folder.");
            ((Button)window.FindName("ResetOutput")).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            if (((TextBlock)window.FindName("OutputPath")).Text != Path.Combine(Path.GetDirectoryName(args[0]), "compressed"))
                throw new InvalidOperationException("Reset did not restore the default output.");
            type.GetMethod("SetOutputFolder", flags).Invoke(controller, new object[] { args[1] });
            SavePreview(window, args[2]);
            Window next;
            using (var stream = exe.GetManifestResourceStream("Workspace.xaml"))
                next = (Window)XamlReader.Load(stream);
            Activator.CreateInstance(type, flags, null, new object[] { next, languageFile }, null);
            if (((ComboBox)next.FindName("Language")).SelectedIndex != 1)
                throw new InvalidOperationException("Saved language was not restored.");
            next.Close();
            ((Button)window.FindName("NavCompress")).RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            if (((ScrollViewer)window.FindName("Workspace")).Visibility != Visibility.Visible ||
                ((TextBlock)window.FindName("SourcePath")).Text != args[0] ||
                !((TextBlock)window.FindName("SettingsSummary")).Text.Contains("Maximum compression") ||
                !((TextBlock)window.FindName("SettingsSummary")).Text.Contains("parallel: 4"))
                throw new InvalidOperationException("Home did not preserve the input or reflect the active settings.");
            type.GetMethod("SetPaths", flags).Invoke(controller, new object[] { null, null });
            type.GetMethod("SetStatus", flags).Invoke(controller,
                new object[] { "Выберите видеофайл или папку с видео", "Choose a video file or folder" });
            window.UpdateLayout();
            SavePreview(window, Path.ChangeExtension(args[2], ".en.png"));
            type.GetMethod("SetPaths", flags).Invoke(controller, new object[] { args[0], args[1] });
            var maximize = (Button)window.FindName("Maximize");
            var normalIcon = maximize.Content as Geometry;
            maximize.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.Dispatcher.Invoke(new Action(() => { }), DispatcherPriority.ApplicationIdle);
            if (normalIcon == null || window.WindowState != WindowState.Maximized ||
                !(maximize.Content is Geometry) || ReferenceEquals(maximize.Content, normalIcon))
                throw new InvalidOperationException("Caption did not switch to the restore icon.");
            maximize.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            window.Dispatcher.Invoke(new Action(() => { }), DispatcherPriority.ApplicationIdle);
            if (window.WindowState != WindowState.Normal || !ReferenceEquals(maximize.Content, normalIcon))
                throw new InvalidOperationException("Caption did not return to the maximize icon.");
            type.GetMethod("Start", flags).Invoke(controller, null);
            type.GetField("closing", flags).SetValue(controller, true);
            var timeout = new DispatcherTimer { Interval = TimeSpan.FromSeconds(30) };
            timeout.Tick += (sender, tick) =>
            {
                timeout.Stop();
                timedOut = true;
                type.GetMethod("Cancel", flags).Invoke(controller, null);
                app.Shutdown(1);
            };
            timeout.Start();
        };
        app.Run(window);
        var output = Path.Combine(args[1], Path.GetFileName(args[0]));
        if (timedOut || !File.Exists(output) || new FileInfo(output).Length == 0)
            throw new Exception("WPF did not produce the expected output.");
        Console.WriteLine("WPF passed page navigation, owned confirmation, settings and compression checks.");
        return 0;
    }

    static void SavePreview(Window window, string path)
    {
        var content = (FrameworkElement)window.Content;
        var bitmap = new RenderTargetBitmap((int)content.ActualWidth, (int)content.ActualHeight, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(content);
        var png = new PngBitmapEncoder();
        png.Frames.Add(BitmapFrame.Create(bitmap));
        using (var file = File.Create(path)) png.Save(file);
    }
}
