using CASCLib;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

// A deliberately narrow JSON request/response adapter for exact local CASC names.
// No arbitrary executable, download, map write, or shell operation exists here.
try
{
    if (args.Length != 1) throw new ArgumentException("Expected one request.json argument.");
    using var json = JsonDocument.Parse(File.ReadAllText(args[0]));
    var request = json.RootElement;
    var installation = Path.GetFullPath(request.GetProperty("installation").GetString()!);
    var destination = Path.GetFullPath(request.GetProperty("destination").GetString()!);
    var key = request.GetProperty("build_key").GetString()!;
    var product = request.GetProperty("product").GetString()!;
    if (!Regex.IsMatch(key, "^[a-f0-9]{32}$") || product is not ("s2" or "s2_cn"))
        throw new ArgumentException("Invalid build/product.");
    if (Directory.Exists(destination) || File.Exists(destination) ||
        destination.StartsWith(installation.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) ||
        destination.Equals(installation, StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Destination must be new and outside installation.");
    var buildInfo = Path.Combine(installation, ".build.info");
    var expectedHash = request.GetProperty("build_info_sha256").GetString();
    if (Hex(SHA256.HashData(File.ReadAllBytes(buildInfo))) != expectedHash)
        throw new InvalidOperationException("Installation build info changed before extraction.");
    var names = request.GetProperty("paths").EnumerateArray().Select(p => SafePath(p.GetString()!)).ToArray();
    if (names.Length is < 1 or > 5000 || names.Distinct(StringComparer.OrdinalIgnoreCase).Count() != names.Length)
        throw new ArgumentException("Duplicate or invalid path count.");

    var all = VerBarConfig.ReadVerBarConfig(File.OpenRead(buildInfo));
    Dictionary<string, string>? selected = null;
    for (var i = 0; i < all.Count; i++)
    {
        if (all[i].GetValueOrDefault("BuildKey") == key && all[i].GetValueOrDefault("Active") == "1")
        {
            if (selected != null) throw new InvalidOperationException("Ambiguous build key.");
            selected = new Dictionary<string, string>(all[i]);
        }
    }
    if (selected == null) throw new InvalidOperationException("Selected active build no longer exists.");
    var selectedProduct = selected.GetValueOrDefault("Product");
    if (string.IsNullOrEmpty(selectedProduct)) selectedProduct = selected.GetValueOrDefault("Branch") == "cn" ? "s2_cn" : "s2";
    if (selectedProduct != product) throw new InvalidOperationException("Requested product and selected row differ.");
    // Upstream 1.0.23 matches Product, but current multi-region SC2 rows leave it
    // blank. Build the equivalent local config from the explicitly selected row.
    // Invalid IPv6 host intentionally makes any upstream HTTP fallback fail URI
    // construction before network I/O; normal local reads do not consult it.
    const string blockedHost = "[offline-disabled]";
    try { _ = new Uri("http://" + blockedHost + "/"); throw new InvalidOperationException("Offline host guard failed."); }
    catch (UriFormatException) { }
    selected["Product"] = product;
    selected["CDNHosts"] = blockedHost;
    selected["CDNServers"] = "";
    var normalized = string.Join('|', selected.Keys) + "\n" + string.Join('|', selected.Values) + "\n";
    var oneRow = VerBarConfig.ReadVerBarConfig(new StringReader(normalized));
    var config = (CASCConfig)(Activator.CreateInstance(typeof(CASCConfig), nonPublic: true) ?? throw new InvalidOperationException("Cannot construct pinned CASCConfig."));
    SetProperty(config, "BasePath", installation);
    SetProperty(config, "OnlineMode", false);
    SetProperty(config, "Product", product);
    SetProperty(config, "Region", selected.GetValueOrDefault("Branch") ?? "");
    SetProperty(config, "GameType", CASCGameType.S2);
    config.ActiveBuild = 0;
    SetField(config, "_BuildInfo", oneRow);
    var build = ReadConfig(installation, key);
    SetField(config, "_Builds", new List<KeyValueConfig> { build });
    SetField(config, "_CDNConfig", ReadConfig(installation, selected["CDNKey"]));
    Logger.Init(new LocalLog());
    CASCConfig.LoadFlags = LoadFlags.None;
    CASCConfig.ValidateData = true;
    CASCConfig.ThrowOnFileNotFound = true;
    CASCConfig.ThrowOnMissingDecryptionKey = true;
    CDNCache.Enabled = false;
    CDNCache.Init(config);
    var handler = CASCHandler.OpenStorage(config, new BackgroundWorkerEx());
    handler.Root.LoadListFile("");
    handler.Root.SetFlags(LocaleFlags.All, false, false);
    Directory.CreateDirectory(destination);
    var files = new List<object>();
    var missing = new List<object>();
    foreach (var name in names)
    {
        var output = Path.Combine(destination, name.Replace('/', Path.DirectorySeparatorChar));
        try
        {
            using var source = handler.OpenFile(name) ?? throw new IOException("No local data stream.");
            Directory.CreateDirectory(Path.GetDirectoryName(output)!);
            using (var target = new FileStream(output, FileMode.CreateNew, FileAccess.Write)) source.CopyTo(target);
            using var verify = File.OpenRead(output);
            using var sha = SHA256.Create();
            files.Add(new { path = name, bytes = verify.Length, sha256 = Hex(sha.ComputeHash(verify)) });
        }
        catch (Exception ex) { missing.Add(new { path = name, error = ex.Message }); }
    }
    var result = new { files, missing, product, branch = selected.GetValueOrDefault("Branch"), build_key = key, build_uid = config.BuildUID, local_only = true };
    File.WriteAllText("result.json", JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }), new UTF8Encoding(false));
    Console.WriteLine(JsonSerializer.Serialize(new { extracted = files.Count, missing = missing.Count, local_only = true }));
    return missing.Count == 0 ? 0 : 2;
}
catch (Exception ex)
{
    Console.Error.WriteLine(ex.GetType().Name + ": " + ex.Message);
    return 1;
}

static string Hex(byte[] hash) => Convert.ToHexString(hash).ToLowerInvariant();
static void SetProperty(object target, string name, object value) =>
    (target.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.Instance) ?? throw new MissingMemberException(name)).SetValue(target, value);
static void SetField(object target, string name, object value) =>
    (target.GetType().GetField(name, BindingFlags.NonPublic | BindingFlags.Instance) ?? throw new MissingMemberException(name)).SetValue(target, value);
static KeyValueConfig ReadConfig(string root, string key)
{
    if (!Regex.IsMatch(key, "^[a-fA-F0-9]{32}$")) throw new ArgumentException("Invalid config key.");
    return KeyValueConfig.ReadKeyValueConfig(File.OpenRead(Path.Combine(root, "SC2Data", "config", key[..2], key.Substring(2, 2), key)));
}
static string SafePath(string raw)
{
    var name = raw.Replace('\\', '/');
    if (name.StartsWith('/') || name.Split('/').Any(p => p.Length == 0 || p is "." or ".." ||
        p.EndsWith('.') || p.EndsWith(' ') || p.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 ||
        Regex.IsMatch(p.Split('.')[0], "^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", RegexOptions.IgnoreCase)))
        throw new ArgumentException("Unsafe virtual path.");
    return name;
}
sealed class LocalLog : ILoggerOptions
{
    public string LogFileName => "casc.log";
    public bool TimeStamp => true;
}
