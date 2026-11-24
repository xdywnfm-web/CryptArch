using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Automation;
using System.Windows.Markup;
using System.Windows.Media;
using Forms = System.Windows.Forms;

sealed class Workspace
{
    enum NoticeTone { Information, Warning, Error }
    readonly Window window;
    readonly JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
    readonly ObservableCollection<string> batch = new ObservableCollection<string>();
    readonly ComboBox quality, codec, device, workers;
    readonly Button start, pause, cancel;
    readonly TextBlock count, eta, status;
    readonly ProgressBar progress;
    Process process;
    string source, output, outputOverride;
    bool paused, cancelling, closing;
    bool english;
    static readonly string[] RussianQuality = { "Высокое качество", "Сбалансированное", "Максимальное сжатие" };
    static readonly string[] EnglishQuality = { "High quality", "Balanced", "Maximum compression" };
    string statusRu = "Выберите видеофайл или папку с видео", statusEn = "Choose a video file or folder";
    int done, total;
    bool preparing;
    string etaValue = "—";

    static readonly string[,] Labels = {
        {"MinimizeLabel", "Свернуть", "Minimize"}, {"MaximizeLabel", "Развернуть", "Maximize"},
        {"RestoreLabel", "Восстановить размер", "Restore down"}, {"CloseLabel", "Закрыть", "Close"},
        {"CompressLabel", "Сжатие видео", "Compress video"}, {"QueueLabel", "Очередь", "Queue"},
        {"SettingsLabel", "Настройки", "Settings"}, {"AboutLabel", "О программе", "About"},
        {"QueueEmpty", "Список файлов появится после запуска сжатия.", "The file list will appear once compression starts."},
        {"AboutBody", "Локальное сжатие видео для Windows.\nДвижок FFmpeg. Оригиналы не изменяются.",
            "Local video compression for Windows.\nPowered by FFmpeg. Originals are not changed."},
        {"SourceLabel", "Источник видео", "Video source"},
        {"SourceHint", "Выберите один файл или папку с видео", "Choose one video file or a folder"},
        {"FileLabel", "Выбрать файл", "Choose file"}, {"FolderLabel", "Выбрать папку", "Choose folder"},
        {"OutputLabel", "Папка результата", "Output folder"},
        {"OutputHint", "Куда сохранять сжатые файлы", "Where to save compressed files"},
        {"BrowseLabel", "Обзор", "Browse"}, {"DefaultOutput", "По умолчанию — папка compressed", "Default folder: compressed"},
        {"ResetOutputLabel", "По умолчанию", "Use default"},
        {"CompressionSettings", "Настройки сжатия", "Compression settings"},
        {"QualityLabel", "Качество", "Quality"}, {"CodecLabel", "Кодек", "Codec"},
        {"DeviceLabel", "Устройство", "Device"}, {"WorkersLabel", "Параллельных видео", "Parallel videos"},
        {"CompressionHint", "GPU ускоряет сжатие при поддержке NVIDIA, AMD или Intel. H.264 совместимее; H.265 обычно сжимает лучше.",
            "Supported NVIDIA, AMD or Intel GPUs speed up compression. H.264 is more compatible; H.265 usually compresses better."},
        {"StartLabel", "Начать сжатие", "Start compression"}, {"CancelLabel", "Отменить", "Cancel"},
        {"ProgressLabel", "Прогресс сжатия", "Compression progress"},
        {"LanguageLabel", "Язык интерфейса", "Interface language"},
        {"LanguageHint", "Изменения применяются сразу и сохраняются для следующих запусков.", "Changes take effect immediately and are saved for next time."}
    };

    [STAThread]
    static void Main()
    {
        Window window = null;
        try
        {
            var app = new Application();
            using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Workspace.xaml"))
            {
                window = (Window)XamlReader.Load(stream);
                new Workspace(window);
                app.Run(window);
            }
        }
        catch (Exception ex)
        {
            ShowNotice(window, "Ошибка запуска", ex.GetBaseException().Message, NoticeTone.Error, "ОК", null);
        }
    }

    Workspace(Window window) : this(window, Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "CryptArch V2 Beta", "language.txt")) { }

    Workspace(Window window, string languageFile)
    {
        this.window = window;
        try { english = File.ReadAllText(languageFile).Trim() == "en"; }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        quality = Choices("Quality", 1, english ? EnglishQuality : RussianQuality);
        codec = Choices("Codec", 1, "H.264", "H.265");
        device = Choices("Device", 0, "CPU", "GPU");
        workers = Choices("Workers", 0, "2", "4", "8");
        start = Get<Button>("Start");
        pause = Get<Button>("Pause");
        cancel = Get<Button>("Cancel");
        count = Get<TextBlock>("Count");
        eta = Get<TextBlock>("Eta");
        status = Get<TextBlock>("Status");
        progress = Get<ProgressBar>("Progress");
        var language = Choices("Language", english ? 1 : 0, "Русский", "English");
        ApplyLanguage();
        Get<ListBox>("QueueFiles").ItemsSource = batch;
        ShowPage("NavCompress", false);
        language.SelectionChanged += (s, e) => {
            english = language.SelectedIndex == 1;
            ApplyLanguage();
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(languageFile));
                File.WriteAllText(languageFile, english ? "en" : "ru");
            }
            catch (IOException) { LanguageSaveWarning(); }
            catch (UnauthorizedAccessException) { LanguageSaveWarning(); }
        };
        Click("ChooseFile", ChooseFile);
        Click("ChooseFolder", () => ChooseDirectory(false));
        Click("ChooseOutput", () => ChooseDirectory(true));
        Click("ResetOutput", () => SetOutputFolder(null));
        Click("Start", Start);
        Click("Pause", TogglePause);
        Click("Cancel", () => { if (ConfirmStop()) Cancel(); });
        foreach (var nav in new[] { "NavCompress", "NavSettings", "NavQueue", "NavAbout" })
            Click(nav, () => ShowPage(nav));
        Click("Minimize", () => SystemCommands.MinimizeWindow(window));
        Click("Maximize", () => {
            if (window.WindowState == WindowState.Maximized) SystemCommands.RestoreWindow(window);
            else SystemCommands.MaximizeWindow(window);
        });
        Click("CloseWindow", window.Close);
        workers.SelectionChanged += (s, e) => {
            if (Selected(workers) == "8")
                Tell(L("Высокая нагрузка", "High system load"), L(
                    "Восемь параллельных задач сильно нагружают ПК. На слабых системах возможны зависания и сбои.",
                    "Eight parallel jobs can put a heavy load on your PC and may cause freezes or crashes on slower systems."), NoticeTone.Warning);
        };
        foreach (var selector in new[] { quality, codec, device, workers })
            selector.SelectionChanged += (s, e) => RefreshSummary();
        window.Closing += (s, e) => {
            if (process == null) return;
            e.Cancel = true;
            if (closing || (!cancelling && !ConfirmStop())) return;
            if (process == null) { e.Cancel = false; return; }
            closing = true;
            Cancel();
        };
    }

    T Get<T>(string name) where T : class { return (T)window.FindName(name); }
    string L(string ru, string en) { return english ? en : ru; }

    void ShowPage(string activeNav, bool focus = true)
    {
        var navigation = new[] { "NavCompress", "NavSettings", "NavQueue", "NavAbout" };
        var pages = new[] { "Workspace", "SettingsPane", "QueuePane", "AboutPane" };
        for (int i = 0; i < navigation.Length; i++)
        {
            var nav = Get<Button>(navigation[i]);
            var active = navigation[i] == activeNav;
            Get<ScrollViewer>(pages[i]).Visibility = active ? Visibility.Visible : Visibility.Collapsed;
            nav.Background = active ? new SolidColorBrush(Color.FromRgb(39, 38, 79)) : Brushes.Transparent;
            nav.BorderBrush = active ? new SolidColorBrush(Color.FromRgb(65, 65, 122)) : Brushes.Transparent;
        }
        if (focus) (activeNav == "NavSettings" ? (Control)Get<ComboBox>("Language") : Get<Button>(activeNav)).Focus();
    }

    void ApplyLanguage()
    {
        for (int i = 0; i < Labels.GetLength(0); i++)
            window.Resources[Labels[i, 0]] = Labels[i, english ? 2 : 1];
        var selected = quality.SelectedIndex;
        quality.ItemsSource = english ? EnglishQuality : RussianQuality;
        quality.SelectedIndex = selected;
        SetPaths(source, output);
        RefreshSummary();
        RenderProgress();
        RefreshPause();
        status.Text = L(statusRu, statusEn);
    }

    void LanguageSaveWarning()
    {
        Tell(L("Настройки", "Settings"), L("Язык изменён, но сохранить его не удалось.",
            "The language changed, but it could not be saved."), NoticeTone.Warning);
    }

    void SetStatus(string ru, string en)
    {
        statusRu = ru;
        statusEn = en;
        status.Text = L(ru, en);
    }

    void RenderProgress()
    {
        count.Text = preparing ? L("0%   •   Подготовка", "0%   •   Preparing") :
            String.Format(L("{0:0}%   •   {1} из {2}", "{0:0}%   •   {1} of {2}"), progress.Value, done, total);
        eta.Text = L("Оставшееся время: ", "Time remaining: ") + etaValue;
    }

    void RefreshPause()
    {
        Get<System.Windows.Shapes.Path>("PauseIcon").Data =
            (Geometry)window.Resources[paused ? "ActionResumeIcon" : "ActionPauseIcon"];
        var label = paused ? L("Продолжить", "Resume") : L("Пауза", "Pause");
        pause.ToolTip = label;
        AutomationProperties.SetName(pause, label);
    }

    void RefreshSummary()
    {
        Get<TextBlock>("SettingsSummary").Text = String.Format(
            L("Параметры: {0}  •  {1}  •  {2}  •  параллельно: {3}", "Settings: {0}  •  {1}  •  {2}  •  parallel: {3}"),
            Selected(quality), Selected(codec), Selected(device), Selected(workers));
    }

    void Click(string name, Action action) { Get<Button>(name).Click += (s, e) => action(); }
    ComboBox Choices(string name, int index, params string[] items)
    {
        var box = Get<ComboBox>(name);
        box.ItemsSource = items;
        box.SelectedIndex = index;
        return box;
    }
    static string Selected(ComboBox box) { return (string)box.SelectedItem; }
    void Tell(string title, string message, NoticeTone tone)
    {
        ShowNotice(window, title, message, tone, "OK", null);
    }

    bool ConfirmStop()
    {
        return ShowNotice(window, L("Остановить сжатие?", "Stop compression?"),
            L("Готовые файлы сохранятся.", "Completed files will be kept."), NoticeTone.Warning,
            L("Остановить", "Stop"), L("Продолжить сжатие", "Keep compressing"));
    }

    static bool ShowNotice(Window owner, string title, string message, NoticeTone tone, string acceptLabel, string backLabel)
    {
        Window dialog;
        using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Notice.xaml"))
            dialog = (Window)XamlReader.Load(stream);
        if (owner != null && owner.IsVisible) dialog.Owner = owner;
        else dialog.WindowStartupLocation = WindowStartupLocation.CenterScreen;
        dialog.Title = "CryptArch — " + title;
        ((TextBlock)dialog.FindName("NoticeHeading")).Text = title;
        ((TextBlock)dialog.FindName("NoticeBody")).Text = message;
        var glyph = (System.Windows.Shapes.Path)dialog.FindName("NoticeGlyph");
        var badge = (Border)dialog.FindName("NoticeBadge");
        if (tone == NoticeTone.Error)
        {
            glyph.Data = Geometry.Parse("M3,3 L13,13 M13,3 L3,13");
            glyph.Stroke = new SolidColorBrush(Color.FromRgb(255, 160, 183));
            badge.Background = new SolidColorBrush(Color.FromRgb(85, 37, 56));
        }
        else if (tone == NoticeTone.Warning)
        {
            glyph.Data = Geometry.Parse("M8,1 L15,14 H1 Z M8,5 V9 M8,11 V11.6");
            glyph.Stroke = new SolidColorBrush(Color.FromRgb(255, 209, 150));
            badge.Background = new SolidColorBrush(Color.FromRgb(74, 49, 40));
        }
        else glyph.Data = Geometry.Parse("M8,1 A7,7 0 1 1 7.99,1 Z M8,7 V12 M8,4 V4.7");
        var accept = (Button)dialog.FindName("NoticeAccept");
        var back = (Button)dialog.FindName("NoticeBack");
        accept.Content = acceptLabel;
        accept.Click += (s, e) => { dialog.DialogResult = true; };
        accept.IsDefault = backLabel == null;
        if (backLabel != null)
        {
            back.Content = backLabel;
            back.Visibility = Visibility.Visible;
            back.IsDefault = true;
            back.Click += (s, e) => { dialog.DialogResult = false; };
        }
        dialog.Loaded += (s, e) => (backLabel == null ? accept : back).Focus();
        dialog.PreviewKeyDown += (s, e) => {
            if (e.Key != System.Windows.Input.Key.Escape) return;
            e.Handled = true;
            dialog.DialogResult = false;
        };
        return dialog.ShowDialog() == true;
    }

    void ChooseFile()
    {
        var dialog = new Microsoft.Win32.OpenFileDialog {
            Title = L("Выберите видео", "Choose a video"), CheckFileExists = true,
            Filter = L("Видеофайлы", "Video files") + "|*.mp4;*.mov;*.mkv;*.avi;*.webm;*.m4v;*.mpeg;*.mpg;*.wmv;*.ts;*.mts|" + L("Все файлы", "All files") + "|*.*"
        };
        if (dialog.ShowDialog(window) == true)
            ChooseSource(dialog.FileName);
    }

    void ChooseDirectory(bool isOutput)
    {
        using (var dialog = new Forms.FolderBrowserDialog {
            Description = isOutput ? L("Куда сохранить сжатые файлы?", "Where should compressed files be saved?") :
                L("Выберите папку с видео", "Choose a folder with videos"),
            ShowNewFolderButton = isOutput
        })
        {
            var owner = new DialogOwner(new System.Windows.Interop.WindowInteropHelper(window).Handle);
            if (dialog.ShowDialog(owner) != Forms.DialogResult.OK) return;
            if (isOutput) SetOutputFolder(dialog.SelectedPath);
            else ChooseSource(dialog.SelectedPath);
        }
    }

    sealed class DialogOwner : Forms.IWin32Window
    {
        public IntPtr Handle { get; private set; }
        public DialogOwner(IntPtr handle) { Handle = handle; }
    }

    void ChooseSource(string input)
    {
        var defaultFolder = input == null ? null :
            Path.Combine(Directory.Exists(input) ? input : Path.GetDirectoryName(input), "compressed");
        SetPaths(input, outputOverride ?? defaultFolder);
    }

    void SetOutputFolder(string folder)
    {
        outputOverride = folder;
        ChooseSource(source);
    }

    void SetPaths(string input, string destination)
    {
        source = input; output = destination;
        var selected = Get<TextBlock>("SourcePath");
        selected.Text = input ?? L("Не выбрано", "Not selected"); selected.ToolTip = input;
        selected = Get<TextBlock>("OutputPath");
        selected.Text = destination ?? L("Не выбрано", "Not selected"); selected.ToolTip = destination;
        Get<Button>("ResetOutput").IsEnabled = process == null && outputOverride != null;
    }

    void SetRunning(bool running)
    {
        foreach (var selector in new[] { quality, codec, device, workers }) selector.IsEnabled = !running;
        foreach (var name in new[] { "ChooseFile", "ChooseFolder", "ChooseOutput", "Start" })
            Get<Button>(name).IsEnabled = !running;
        Get<Button>("ResetOutput").IsEnabled = !running && outputOverride != null;
        pause.IsEnabled = cancel.IsEnabled = running;
        RefreshPause();
    }

    void Start()
    {
        if (process != null) return;
        if (String.IsNullOrEmpty(source) || String.IsNullOrEmpty(output))
        {
            Tell(L("Нет источника или результата", "Source or output missing"),
                L("Выберите видео или папку и укажите, куда сохранить результат.",
                    "Choose a video or folder and specify where to save the result."), NoticeTone.Warning);
            return;
        }
        var info = new ProcessStartInfo(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "engine", "CryptArchEngine.exe")) {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardInput = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        Process child;
        try { child = Process.Start(info); }
        catch (Exception ex) { Tell(L("Не удалось запустить движок", "Could not start the engine"), ex.Message, NoticeTone.Error); return; }
        process = child;
        paused = cancelling = false;
        progress.Value = 0;
        preparing = true;
        done = total = 0;
        etaValue = "—";
        RenderProgress();
        SetStatus("Поиск видео…", "Finding videos…");
        batch.Clear();
        SetRunning(true);
        var errors = child.StandardError.ReadToEndAsync();
        Task.Run(() => ReadWorker(child, errors));
        try
        {
            var request = json.Serialize(new { source = source, output = output,
                quality = RussianQuality[quality.SelectedIndex], codec = Selected(codec), device = Selected(device),
                workers = Int32.Parse(Selected(workers)) });
            // The .NET Framework stdin writer uses the Windows console code page.
            child.StandardInput.WriteLine(Regex.Replace(request, @"[^\x00-\x7F]",
                match => "\\u" + ((int)match.Value[0]).ToString("x4")));
        }
        catch (IOException) { SetStatus("Не удалось передать параметры движку.", "Could not send settings to the engine."); }
    }

    void ReadWorker(Process child, Task<string> errors)
    {
        bool terminal = false;
        string failure = null;
        try
        {
            string line;
            while ((line = child.StandardOutput.ReadLine()) != null)
            {
                var message = (Dictionary<string, object>)new JavaScriptSerializer { MaxJsonLength = int.MaxValue }.DeserializeObject(line);
                var kind = (string)message["kind"];
                terminal = kind == "finished" || kind == "fatal";
                window.Dispatcher.InvokeAsync(() => Handle(kind, message["data"]));
                if (terminal) break;
            }
        }
        catch (Exception ex) { failure = ex.Message; }
        finally
        {
            try { child.StandardInput.Close(); } catch (IOException) { }
            child.WaitForExit();
            var error = errors.GetAwaiter().GetResult();
            child.Dispose();
            if (!terminal)
                window.Dispatcher.InvokeAsync(() => Handle("fatal", failure ?? (String.IsNullOrWhiteSpace(error) ?
                    L("Движок неожиданно завершился.", "The engine exited unexpectedly.") : error.Trim())));
        }
    }

    bool Send(string command)
    {
        if (process == null) return false;
        try { process.StandardInput.WriteLine(command); return true; }
        catch (IOException) { return false; }
        catch (InvalidOperationException) { return false; }
    }

    void TogglePause()
    {
        if (!Send(paused ? "resume" : "pause")) return;
        paused = !paused;
        RefreshPause();
        if (paused) SetStatus("Пауза", "Paused");
        else SetStatus("Сжатие видео…", "Compressing videos…");
    }

    void Cancel()
    {
        if (process == null || cancelling) return;
        cancelling = true;
        Send("cancel");
        SetStatus("Останавливаем задачи…", "Stopping jobs…");
        pause.IsEnabled = cancel.IsEnabled = false;
    }

    void Handle(string kind, object data)
    {
        if (kind == "status")
        {
            if (paused || cancelling) return;
            var message = (string)data;
            var translated = message == "Поиск видео…" ? "Finding videos…" :
                message == "Проверка видеокарты…" ? "Checking the GPU…" :
                message.StartsWith("Используется ", StringComparison.Ordinal) ?
                    "Using " + message.Substring("Используется ".Length) : message;
            SetStatus(message, translated);
            return;
        }
        if (kind == "started")
        {
            foreach (var file in (object[])data) batch.Add((string)file);
            if (!paused && !cancelling) SetStatus("Сжатие видео…", "Compressing videos…");
            return;
        }
        if (kind == "progress")
        {
            if (paused || cancelling) return;
            var d = (Dictionary<string, object>)data;
            progress.Value = Convert.ToDouble(d["fraction"]) * 100;
            preparing = false;
            done = Convert.ToInt32(d["done"]);
            total = Convert.ToInt32(d["total"]);
            var time = d["eta"] == null ? "—" : "≈ " + TimeSpan.FromSeconds(Math.Max(0, Convert.ToDouble(d["eta"]))).ToString(@"hh\:mm\:ss");
            var speed = Convert.ToDouble(d["speed"]);
            etaValue = time + (speed > 0 ? String.Format("   •   {0:0.0}×", speed) : "");
            RenderProgress();
            return;
        }
        process = null;
        paused = preparing = false;
        etaValue = "—";
        RenderProgress();
        SetRunning(false);
        if (closing) { window.Close(); return; }
        if (kind == "fatal")
        {
            SetStatus("Не удалось выполнить сжатие.", "Compression failed.");
            Tell(L("Ошибка", "Error"), (string)data, NoticeTone.Error);
        }
        else if (kind == "finished") Report((Dictionary<string, object>)data);
    }

    void Report(Dictionary<string, object> data)
    {
        var results = ((object[])data["results"]).Cast<Dictionary<string, object>>().ToArray();
        var successful = results.Where(r => (string)r["status"] == "ok").ToArray();
        var errors = results.Where(r => (string)r["status"] == "error" || (string)r["status"] == "skipped").ToArray();
        var larger = successful.Where(r => Convert.ToInt64(r["compressed"]) > Convert.ToInt64(r["original"])).ToArray();
        double original = Convert.ToDouble(data["original"]);
        double change = original == 0 ? 0 : 100 * (1 - Convert.ToDouble(data["compressed"]) / original);
        var comparisonRu = original == 0 ? "Нет завершённых файлов для сравнения." :
            String.Format("Результат на {0:0.0}% {1} оригиналов.", Math.Abs(change), change >= 0 ? "меньше" : "больше");
        var comparisonEn = original == 0 ? "No completed files to compare." :
            String.Format("Output is {0:0.0}% {1} than the originals.", Math.Abs(change), change >= 0 ? "smaller" : "larger");
        var stopped = (bool)data["cancelled"];
        var titleRu = stopped ? "Остановлено" : "Готово";
        var titleEn = stopped ? "Stopped" : "Done";
        SetStatus(String.Format("{0}: обработано {1} из {2}. {3}", titleRu, successful.Length, data["total"], comparisonRu),
            String.Format("{0}: processed {1} of {2}. {3}", titleEn, successful.Length, data["total"], comparisonEn));
        var lines = new List<string> { status.Text, L("Оригиналы не изменены.", "Originals have not been changed.") };
        lines.AddRange(errors.Select(r => L("Ошибка или пропуск: ", "Error or skipped: ") + r["source"] + "\n" + r["message"]));
        lines.AddRange(larger.Select(r => L("Больше оригинала: ", "Larger than the original: ") + r["source"]));
        for (int i = 0; i < lines.Count; i += 5)
        {
            var page = String.Join("\n\n", lines.Skip(i).Take(5));
            for (int offset = 0; offset < page.Length; offset += 1300)
                Tell(L(titleRu, titleEn), page.Substring(offset, Math.Min(1300, page.Length - offset)),
                     lines.Count > 2 ? NoticeTone.Warning : NoticeTone.Information);
        }
    }
}
