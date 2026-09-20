using System.Net;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Authentication;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

var settings = ProxySettings.Parse(args);
Directory.CreateDirectory(settings.RuntimeDir);
Directory.CreateDirectory(settings.LogDir);
Directory.CreateDirectory(settings.CertDir);

var serverCertificate = CertificateManager.EnsureServerCertificate(settings.CertDir, settings.TargetHost);

Console.WriteLine($"[proxy] target host : {settings.TargetHost}");
Console.WriteLine($"[proxy] listen port : {settings.ListenPort}");
Console.WriteLine($"[proxy] cert path   : {Path.Combine(settings.CertDir, "newbest_capture_proxy.cer")}");

if (settings.PrepareOnly)
{
    Console.WriteLine("[proxy] prepare-only complete");
    return;
}

using var logger = new CaptureLogger(settings.LogDir);
using var proxy = new HttpsCaptureProxy(settings, serverCertificate, logger);
using var cts = new CancellationTokenSource();

Console.CancelKeyPress += (_, eventArgs) =>
{
    eventArgs.Cancel = true;
    cts.Cancel();
};

await proxy.RunAsync(cts.Token);

sealed record ProxySettings(
    string TargetHost,
    int ListenPort,
    bool PrepareOnly,
    string RuntimeDir,
    string LogDir,
    string CertDir)
{
    private const string DefaultHost = "newbest.lge.com";
    private const int DefaultPort = 8877;

    public static ProxySettings Parse(string[] args)
    {
        var targetHost = DefaultHost;
        var listenPort = DefaultPort;
        var prepareOnly = false;
        var runtimeDir = Path.Combine(AppContext.BaseDirectory, "runtime_data");

        foreach (var arg in args)
        {
            if (arg.StartsWith("--host=", StringComparison.OrdinalIgnoreCase))
            {
                targetHost = arg.Split('=', 2)[1].Trim();
            }
            else if (arg.StartsWith("--port=", StringComparison.OrdinalIgnoreCase) &&
                     int.TryParse(arg.Split('=', 2)[1], out var parsedPort))
            {
                listenPort = parsedPort;
            }
            else if (arg.Equals("--prepare-only", StringComparison.OrdinalIgnoreCase))
            {
                prepareOnly = true;
            }
            else if (arg.StartsWith("--runtime-dir=", StringComparison.OrdinalIgnoreCase))
            {
                runtimeDir = arg.Split('=', 2)[1].Trim();
            }
        }

        var logDir = Path.Combine(runtimeDir, "logs");
        var certDir = Path.Combine(runtimeDir, "certs");
        return new ProxySettings(targetHost, listenPort, prepareOnly, runtimeDir, logDir, certDir);
    }
}

static class CertificateManager
{
    public static X509Certificate2 EnsureServerCertificate(string certDir, string hostName)
    {
        var cerPath = Path.Combine(certDir, "newbest_capture_proxy.cer");
        var friendlyName = $"LgCaptureProxy:{hostName}";

        using (var store = new X509Store(StoreName.My, StoreLocation.CurrentUser))
        {
            store.Open(OpenFlags.ReadWrite);
            foreach (var cert in store.Certificates)
            {
                if (cert.HasPrivateKey && string.Equals(cert.FriendlyName, friendlyName, StringComparison.OrdinalIgnoreCase))
                {
                    if (!File.Exists(cerPath))
                    {
                        File.WriteAllBytes(cerPath, cert.Export(X509ContentType.Cert));
                    }
                    return cert;
                }
            }

            using var rsa = RSA.Create(2048);
            var req = new CertificateRequest(
                $"CN={hostName}",
                rsa,
                HashAlgorithmName.SHA256,
                RSASignaturePadding.Pkcs1);

            var san = new SubjectAlternativeNameBuilder();
            san.AddDnsName(hostName);

            req.CertificateExtensions.Add(san.Build());
            req.CertificateExtensions.Add(new X509BasicConstraintsExtension(false, false, 0, false));
            req.CertificateExtensions.Add(
                new X509KeyUsageExtension(
                    X509KeyUsageFlags.DigitalSignature | X509KeyUsageFlags.KeyEncipherment,
                    false));
            req.CertificateExtensions.Add(
                new X509EnhancedKeyUsageExtension(
                    new OidCollection { new("1.3.6.1.5.5.7.3.1") },
                    false));
            req.CertificateExtensions.Add(new X509SubjectKeyIdentifierExtension(req.PublicKey, false));

            using var generated = req.CreateSelfSigned(
                DateTimeOffset.UtcNow.AddDays(-1),
                DateTimeOffset.UtcNow.AddYears(3));

            var persisted = new X509Certificate2(
                generated.Export(X509ContentType.Pfx),
                string.Empty,
                X509KeyStorageFlags.Exportable | X509KeyStorageFlags.PersistKeySet);
            persisted.FriendlyName = friendlyName;
            store.Add(persisted);

            File.WriteAllBytes(cerPath, persisted.Export(X509ContentType.Cert));
            return persisted;
        }
    }
}

sealed class CaptureLogger : IDisposable
{
    private readonly object _gate = new();
    private readonly StreamWriter _writer;

    public string LogPath { get; }

    public CaptureLogger(string logDir)
    {
        LogPath = Path.Combine(logDir, $"capture-{DateTime.Now:yyyyMMdd-HHmmss}.jsonl");
        _writer = new StreamWriter(
            new FileStream(LogPath, FileMode.Create, FileAccess.Write, FileShare.Read))
        {
            AutoFlush = true
        };
    }

    public void Log(CaptureRecord record)
    {
        lock (_gate)
        {
            _writer.WriteLine(JsonSerializer.Serialize(record));
        }
    }

    public void Dispose() => _writer.Dispose();
}

sealed record CaptureRecord(
    string TimestampUtc,
    string ConnectionId,
    string TargetHost,
    string Direction,
    string StartLine,
    Dictionary<string, string> Headers,
    int BodyLength,
    string? BodyText,
    string? BodyBase64,
    string? Note)
{
    public static CaptureRecord FromMessage(
        string connectionId,
        string targetHost,
        string direction,
        ParsedHttpMessage message,
        string? note = null)
    {
        var preview = BodyPreview.Create(message.BodyBytes, message.Headers);
        return new CaptureRecord(
            DateTime.UtcNow.ToString("O"),
            connectionId,
            targetHost,
            direction,
            message.StartLine,
            new Dictionary<string, string>(message.Headers, StringComparer.OrdinalIgnoreCase),
            message.BodyBytes.Length,
            preview.Text,
            preview.Base64,
            note);
    }
}

sealed record BodyPreview(string? Text, string? Base64)
{
    private const int PreviewLimit = 64 * 1024;

    public static BodyPreview Create(byte[] bodyBytes, IReadOnlyDictionary<string, string> headers)
    {
        if (bodyBytes.Length == 0)
        {
            return new BodyPreview(null, null);
        }

        var previewBytes = bodyBytes.Length <= PreviewLimit
            ? bodyBytes
            : bodyBytes[..PreviewLimit];

        var contentType = headers.TryGetValue("Content-Type", out var value) ? value : string.Empty;
        if (LooksTextual(contentType, previewBytes))
        {
            var text = DecodeText(previewBytes, contentType);
            if (bodyBytes.Length > PreviewLimit)
            {
                text += "\n... [truncated]";
            }
            return new BodyPreview(text, null);
        }

        var base64 = Convert.ToBase64String(previewBytes);
        if (bodyBytes.Length > PreviewLimit)
        {
            base64 += "...";
        }
        return new BodyPreview(null, base64);
    }

    private static bool LooksTextual(string? contentType, byte[] bytes)
    {
        var normalized = (contentType ?? string.Empty).ToLowerInvariant();
        if (normalized.Contains("json") ||
            normalized.Contains("xml") ||
            normalized.Contains("text") ||
            normalized.Contains("javascript") ||
            normalized.Contains("html") ||
            normalized.Contains("x-www-form-urlencoded") ||
            normalized.Contains("nexacro") ||
            normalized.Contains("ssv"))
        {
            return true;
        }

        var printable = 0;
        foreach (var b in bytes)
        {
            if (b == 9 || b == 10 || b == 13 || (b >= 32 && b <= 126))
            {
                printable++;
            }
        }

        return printable >= Math.Max(1, bytes.Length * 8 / 10);
    }

    private static string DecodeText(byte[] bytes, string? contentType)
    {
        var charsetMatch = Regex.Match(contentType ?? string.Empty, @"charset=([\w-]+)", RegexOptions.IgnoreCase);
        if (charsetMatch.Success)
        {
            try
            {
                return Encoding.GetEncoding(charsetMatch.Groups[1].Value).GetString(bytes);
            }
            catch
            {
            }
        }

        return Encoding.UTF8.GetString(bytes);
    }
}

sealed class HttpsCaptureProxy : IDisposable
{
    private readonly ProxySettings _settings;
    private readonly X509Certificate2 _serverCertificate;
    private readonly CaptureLogger _logger;
    private readonly TcpListener _listener;

    public HttpsCaptureProxy(ProxySettings settings, X509Certificate2 serverCertificate, CaptureLogger logger)
    {
        _settings = settings;
        _serverCertificate = serverCertificate;
        _logger = logger;
        _listener = new TcpListener(IPAddress.Loopback, settings.ListenPort);
    }

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        _listener.Start();
        Console.WriteLine($"[proxy] listening on 127.0.0.1:{_settings.ListenPort}");
        Console.WriteLine($"[proxy] writing logs to {_logger.LogPath}");

        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                TcpClient client;
                try
                {
                    client = await _listener.AcceptTcpClientAsync(cancellationToken);
                }
                catch (OperationCanceledException)
                {
                    break;
                }

                _ = Task.Run(() => HandleClientAsync(client, cancellationToken), cancellationToken);
            }
        }
        finally
        {
            _listener.Stop();
        }
    }

    public void Dispose() => _listener.Stop();

    private async Task HandleClientAsync(TcpClient client, CancellationToken cancellationToken)
    {
        var connectionId = Guid.NewGuid().ToString("N")[..8];
        using (client)
        using (var clientStream = client.GetStream())
        {
            ParsedHttpMessage? firstMessage;
            try
            {
                firstMessage = await HttpWire.ReadMessageAsync(clientStream, cancellationToken);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[proxy] {connectionId} failed to read first message: {ex.Message}");
                return;
            }

            if (firstMessage is null)
            {
                return;
            }

            if (firstMessage.StartLine.StartsWith("CONNECT ", StringComparison.OrdinalIgnoreCase))
            {
                var target = HttpWire.ParseConnectTarget(firstMessage.StartLine);
                if (target is null)
                {
                    await HttpWire.WriteAsciiAsync(clientStream, "HTTP/1.1 400 Bad Request\r\n\r\n", cancellationToken);
                    return;
                }

                if (target.Value.Host.Equals(_settings.TargetHost, StringComparison.OrdinalIgnoreCase))
                {
                    Console.WriteLine($"[proxy] {connectionId} intercept {target.Value.Host}:{target.Value.Port}");
                    _logger.Log(new CaptureRecord(
                        DateTime.UtcNow.ToString("O"),
                        connectionId,
                        target.Value.Host,
                        "connect",
                        firstMessage.StartLine,
                        new Dictionary<string, string>(firstMessage.Headers, StringComparer.OrdinalIgnoreCase),
                        0,
                        null,
                        null,
                        "HTTPS CONNECT intercepted"));

                    await HttpWire.WriteAsciiAsync(
                        clientStream,
                        "HTTP/1.1 200 Connection Established\r\nProxy-Agent: LgCaptureProxy\r\n\r\n",
                        cancellationToken);

                    using var clientTls = new SslStream(clientStream, leaveInnerStreamOpen: false);
                    await clientTls.AuthenticateAsServerAsync(new SslServerAuthenticationOptions
                    {
                        ServerCertificate = _serverCertificate,
                        EnabledSslProtocols = SslProtocols.Tls12 | SslProtocols.Tls13,
                        ClientCertificateRequired = false
                    }, cancellationToken);

                    using var remote = new TcpClient();
                    await remote.ConnectAsync(target.Value.Host, target.Value.Port, cancellationToken);
                    using var remoteStream = remote.GetStream();
                    using var remoteTls = new SslStream(
                        remoteStream,
                        leaveInnerStreamOpen: false,
                        (_, _, _, _) => true);

                    await remoteTls.AuthenticateAsClientAsync(new SslClientAuthenticationOptions
                    {
                        TargetHost = target.Value.Host,
                        EnabledSslProtocols = SslProtocols.Tls12 | SslProtocols.Tls13,
                        CertificateRevocationCheckMode = X509RevocationMode.NoCheck
                    }, cancellationToken);

                    await HandleMitmLoopAsync(connectionId, target.Value.Host, clientTls, remoteTls, cancellationToken);
                    return;
                }

                await HandleBlindTunnelAsync(connectionId, target.Value.Host, target.Value.Port, clientStream, cancellationToken);
                return;
            }

            await HandleDirectHttpAsync(connectionId, firstMessage, clientStream, cancellationToken);
        }
    }

    private async Task HandleBlindTunnelAsync(
        string connectionId,
        string host,
        int port,
        NetworkStream clientStream,
        CancellationToken cancellationToken)
    {
        Console.WriteLine($"[proxy] {connectionId} tunnel {host}:{port}");
        _logger.Log(new CaptureRecord(
            DateTime.UtcNow.ToString("O"),
            connectionId,
            host,
            "connect",
            $"CONNECT {host}:{port}",
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase),
            0,
            null,
            null,
            "Blind tunnel"));

        using var remote = new TcpClient();
        await remote.ConnectAsync(host, port, cancellationToken);
        using var remoteStream = remote.GetStream();

        await HttpWire.WriteAsciiAsync(
            clientStream,
            "HTTP/1.1 200 Connection Established\r\nProxy-Agent: LgCaptureProxy\r\n\r\n",
            cancellationToken);

        var toRemote = clientStream.CopyToAsync(remoteStream, cancellationToken);
        var toClient = remoteStream.CopyToAsync(clientStream, cancellationToken);
        await Task.WhenAny(toRemote, toClient);
    }

    private async Task HandleMitmLoopAsync(
        string connectionId,
        string host,
        SslStream clientTls,
        SslStream remoteTls,
        CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            ParsedHttpMessage? request;
            try
            {
                request = await HttpWire.ReadMessageAsync(clientTls, cancellationToken);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[proxy] {connectionId} request read failed: {ex.Message}");
                return;
            }

            if (request is null)
            {
                return;
            }

            _logger.Log(CaptureRecord.FromMessage(connectionId, host, "request", request));
            await remoteTls.WriteAsync(request.RawBytes, cancellationToken);
            await remoteTls.FlushAsync(cancellationToken);

            ParsedHttpMessage? response;
            try
            {
                response = await HttpWire.ReadMessageAsync(remoteTls, cancellationToken);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[proxy] {connectionId} response read failed: {ex.Message}");
                return;
            }

            if (response is null)
            {
                return;
            }

            _logger.Log(CaptureRecord.FromMessage(connectionId, host, "response", response));
            await clientTls.WriteAsync(response.RawBytes, cancellationToken);
            await clientTls.FlushAsync(cancellationToken);

            if (HttpWire.ShouldClose(request, response))
            {
                return;
            }
        }
    }

    private async Task HandleDirectHttpAsync(
        string connectionId,
        ParsedHttpMessage firstMessage,
        NetworkStream clientStream,
        CancellationToken cancellationToken)
    {
        var target = HttpWire.ResolveTarget(firstMessage);
        if (target is null)
        {
            await HttpWire.WriteAsciiAsync(clientStream, "HTTP/1.1 400 Bad Request\r\n\r\n", cancellationToken);
            return;
        }

        using var remote = new TcpClient();
        await remote.ConnectAsync(target.Value.Host, target.Value.Port, cancellationToken);
        using var remoteStream = remote.GetStream();

        _logger.Log(CaptureRecord.FromMessage(connectionId, target.Value.Host, "request", firstMessage));
        await remoteStream.WriteAsync(firstMessage.RawBytes, cancellationToken);
        await remoteStream.FlushAsync(cancellationToken);

        var response = await HttpWire.ReadMessageAsync(remoteStream, cancellationToken);
        if (response is null)
        {
            return;
        }

        _logger.Log(CaptureRecord.FromMessage(connectionId, target.Value.Host, "response", response));
        await clientStream.WriteAsync(response.RawBytes, cancellationToken);
        await clientStream.FlushAsync(cancellationToken);
    }
}

sealed record ParsedHttpMessage(
    string StartLine,
    Dictionary<string, string> Headers,
    byte[] BodyBytes,
    byte[] RawBytes);

static class HttpWire
{
    private static readonly byte[] HeaderTerminator = Encoding.ASCII.GetBytes("\r\n\r\n");

    public static async Task<ParsedHttpMessage?> ReadMessageAsync(Stream stream, CancellationToken cancellationToken)
    {
        var headerBytes = await ReadHeadersAsync(stream, cancellationToken);
        if (headerBytes is null)
        {
            return null;
        }

        var headerText = Encoding.ASCII.GetString(headerBytes);
        var headerLines = headerText.Split("\r\n", StringSplitOptions.None);
        if (headerLines.Length == 0 || string.IsNullOrWhiteSpace(headerLines[0]))
        {
            return null;
        }

        var startLine = headerLines[0];
        var headers = ParseHeaders(headerLines.Skip(1));

        byte[] bodyBytes;
        if (headers.TryGetValue("Transfer-Encoding", out var transferEncoding) &&
            transferEncoding.Contains("chunked", StringComparison.OrdinalIgnoreCase))
        {
            bodyBytes = await ReadChunkedBodyAsync(stream, cancellationToken);
        }
        else if (headers.TryGetValue("Content-Length", out var contentLengthValue) &&
                 int.TryParse(contentLengthValue, out var contentLength) &&
                 contentLength > 0)
        {
            bodyBytes = await ReadExactAsync(stream, contentLength, cancellationToken);
        }
        else
        {
            bodyBytes = Array.Empty<byte>();
        }

        var rawBytes = new byte[headerBytes.Length + bodyBytes.Length];
        Buffer.BlockCopy(headerBytes, 0, rawBytes, 0, headerBytes.Length);
        Buffer.BlockCopy(bodyBytes, 0, rawBytes, headerBytes.Length, bodyBytes.Length);
        return new ParsedHttpMessage(startLine, headers, bodyBytes, rawBytes);
    }

    public static (string Host, int Port)? ParseConnectTarget(string startLine)
    {
        var parts = startLine.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length < 2)
        {
            return null;
        }

        var target = parts[1];
        var hostPort = target.Split(':', 2);
        if (hostPort.Length == 1)
        {
            return (hostPort[0], 443);
        }

        return int.TryParse(hostPort[1], out var port) ? (hostPort[0], port) : null;
    }

    public static (string Host, int Port)? ResolveTarget(ParsedHttpMessage message)
    {
        var parts = message.StartLine.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length >= 2 &&
            Uri.TryCreate(parts[1], UriKind.Absolute, out var uri) &&
            (uri.Scheme.Equals("http", StringComparison.OrdinalIgnoreCase) ||
             uri.Scheme.Equals("https", StringComparison.OrdinalIgnoreCase)))
        {
            return (uri.Host, uri.Port);
        }

        if (message.Headers.TryGetValue("Host", out var hostHeader))
        {
            var hostParts = hostHeader.Split(':', 2);
            if (hostParts.Length == 1)
            {
                return (hostParts[0], 80);
            }

            if (int.TryParse(hostParts[1], out var port))
            {
                return (hostParts[0], port);
            }
        }

        return null;
    }

    public static bool ShouldClose(ParsedHttpMessage request, ParsedHttpMessage response)
    {
        return HeaderEquals(request.Headers, "Connection", "close") ||
               HeaderEquals(response.Headers, "Connection", "close") ||
               response.StartLine.Contains(" 101 ");
    }

    public static async Task WriteAsciiAsync(Stream stream, string text, CancellationToken cancellationToken)
    {
        var bytes = Encoding.ASCII.GetBytes(text);
        await stream.WriteAsync(bytes, cancellationToken);
        await stream.FlushAsync(cancellationToken);
    }

    private static bool HeaderEquals(Dictionary<string, string> headers, string key, string expected) =>
        headers.TryGetValue(key, out var value) &&
        value.Contains(expected, StringComparison.OrdinalIgnoreCase);

    private static Dictionary<string, string> ParseHeaders(IEnumerable<string> lines)
    {
        var headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var line in lines)
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var idx = line.IndexOf(':');
            if (idx <= 0)
            {
                continue;
            }

            headers[line[..idx].Trim()] = line[(idx + 1)..].Trim();
        }

        return headers;
    }

    private static async Task<byte[]?> ReadHeadersAsync(Stream stream, CancellationToken cancellationToken)
    {
        using var ms = new MemoryStream();
        var buffer = new byte[1];
        var matched = 0;

        while (true)
        {
            var read = await stream.ReadAsync(buffer.AsMemory(0, 1), cancellationToken);
            if (read == 0)
            {
                return ms.Length == 0 ? null : ms.ToArray();
            }

            ms.WriteByte(buffer[0]);

            if (buffer[0] == HeaderTerminator[matched])
            {
                matched++;
                if (matched == HeaderTerminator.Length)
                {
                    return ms.ToArray();
                }
            }
            else
            {
                matched = buffer[0] == HeaderTerminator[0] ? 1 : 0;
            }

            if (ms.Length > 512 * 1024)
            {
                throw new InvalidOperationException("Header too large");
            }
        }
    }

    private static async Task<byte[]> ReadExactAsync(Stream stream, int length, CancellationToken cancellationToken)
    {
        var buffer = new byte[length];
        var offset = 0;

        while (offset < length)
        {
            var read = await stream.ReadAsync(buffer.AsMemory(offset, length - offset), cancellationToken);
            if (read == 0)
            {
                throw new IOException("Unexpected EOF");
            }
            offset += read;
        }

        return buffer;
    }

    private static async Task<byte[]> ReadChunkedBodyAsync(Stream stream, CancellationToken cancellationToken)
    {
        using var ms = new MemoryStream();

        while (true)
        {
            var sizeLine = await ReadLineBytesAsync(stream, cancellationToken);
            ms.Write(sizeLine, 0, sizeLine.Length);
            var sizeText = Encoding.ASCII.GetString(sizeLine).Trim();
            var semicolon = sizeText.IndexOf(';');
            if (semicolon >= 0)
            {
                sizeText = sizeText[..semicolon];
            }

            var chunkSize = Convert.ToInt32(sizeText, 16);
            if (chunkSize == 0)
            {
                while (true)
                {
                    var trailerLine = await ReadLineBytesAsync(stream, cancellationToken);
                    ms.Write(trailerLine, 0, trailerLine.Length);
                    if (trailerLine.Length == 2 &&
                        trailerLine[0] == (byte)'\r' &&
                        trailerLine[1] == (byte)'\n')
                    {
                        return ms.ToArray();
                    }
                }
            }

            var chunkBytes = await ReadExactAsync(stream, chunkSize + 2, cancellationToken);
            ms.Write(chunkBytes, 0, chunkBytes.Length);
        }
    }

    private static async Task<byte[]> ReadLineBytesAsync(Stream stream, CancellationToken cancellationToken)
    {
        using var ms = new MemoryStream();
        var buffer = new byte[1];
        var previousWasCr = false;

        while (true)
        {
            var read = await stream.ReadAsync(buffer.AsMemory(0, 1), cancellationToken);
            if (read == 0)
            {
                throw new IOException("Unexpected EOF while reading line");
            }

            var b = buffer[0];
            ms.WriteByte(b);

            if (previousWasCr && b == (byte)'\n')
            {
                return ms.ToArray();
            }

            previousWasCr = b == (byte)'\r';
        }
    }
}
