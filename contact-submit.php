<?php
declare(strict_types=1);

/** PHP 8.1+. Cloudways must route PHP mail() through its Elastic Email add-on. */
function jengara_config(): array
{
    $path = getenv('JENGARA_MAIL_CONFIG') ?: dirname(__DIR__) . '/jengara-mail-config.php';
    $config = [];
    if (is_file($path)) {
        $real = realpath($path);
        $root = realpath($_SERVER['DOCUMENT_ROOT'] ?? __DIR__) ?: __DIR__;
        if ($real === false || str_starts_with(str_replace('\\', '/', $real), rtrim(str_replace('\\', '/', $root), '/') . '/')) {
            throw new RuntimeException('Configuration must be outside the web root.');
        }
        $config = require $real;
        if (!is_array($config)) {
            throw new RuntimeException('Invalid configuration.');
        }
    }
    return [
        'rate_dir' => getenv('JENGARA_MAIL_RATE_DIR') ?: ($config['rate_dir'] ?? sys_get_temp_dir() . '/jengara-mail-' . substr(hash('sha256', __DIR__), 0, 16)),
    ];
}

/** Fixed 64 shards, each bounded to 128 active keys; flock makes updates atomic. */
function jengara_rate_limit(string $directory, string $ip, int $now): bool
{
    if (filter_var($ip, FILTER_VALIDATE_IP) === false) {
        throw new RuntimeException('Missing client address.');
    }
    if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
        throw new RuntimeException('Rate limiter unavailable.');
    }
    $root = realpath($_SERVER['DOCUMENT_ROOT'] ?? __DIR__) ?: __DIR__;
    $resolved = realpath($directory);
    if ($resolved === false || $resolved === $root || str_starts_with(str_replace('\\', '/', $resolved), rtrim(str_replace('\\', '/', $root), '/') . '/')) {
        throw new RuntimeException('Rate storage must be outside the web root.');
    }
    $key = hash('sha256', $ip);
    $file = $directory . '/' . (hexdec(substr($key, 0, 2)) % 64) . '.json';
    $handle = @fopen($file, 'c+');
    if ($handle === false) {
        throw new RuntimeException('Rate limiter unavailable.');
    }
    try {
        if (!flock($handle, LOCK_EX)) {
            throw new RuntimeException('Rate limiter unavailable.');
        }
        @chmod($file, 0600);
        $raw = stream_get_contents($handle, 32769);
        if ($raw === false || strlen($raw) > 32768) {
            throw new RuntimeException('Rate limiter storage invalid.');
        }
        $entries = $raw === '' ? [] : json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
        if (!is_array($entries)) {
            throw new RuntimeException('Rate limiter storage invalid.');
        }
        foreach ($entries as $id => $entry) {
            if (!is_array($entry) || !isset($entry['until'], $entry['count']) || $entry['until'] <= $now) {
                unset($entries[$id]);
            }
        }
        if (!isset($entries[$key]) && count($entries) >= 128) {
            return false;
        }
        $entry = $entries[$key] ?? ['until' => $now + 900, 'count' => 0];
        if ($entry['count'] >= 5) {
            return false;
        }
        $entry['count']++;
        $entries[$key] = $entry;
        $data = json_encode($entries, JSON_THROW_ON_ERROR);
        rewind($handle);
        if (!ftruncate($handle, 0) || fwrite($handle, $data) !== strlen($data) || !fflush($handle)) {
            throw new RuntimeException('Rate limiter write failed.');
        }
        return true;
    } finally {
        flock($handle, LOCK_UN);
        fclose($handle);
    }
}

function jengara_contact(array $server, string $raw, array $config, ?callable $testTransport = null): array
{
    if ($testTransport !== null && PHP_SAPI !== 'cli') {
        throw new LogicException('Test transport is CLI only.');
    }
    if (($server['REQUEST_METHOD'] ?? '') !== 'POST') {
        return [405, ['ok' => false, 'message' => 'Use POST.']];
    }
    if (($server['HTTP_SEC_FETCH_SITE'] ?? '') === 'cross-site') {
        return [403, ['ok' => false, 'message' => 'Cross-site requests are not accepted.']];
    }
    if (strlen($raw) > 16384 || (int)($server['CONTENT_LENGTH'] ?? 0) > 16384) {
        return [413, ['ok' => false, 'message' => 'Request is too large.']];
    }
    $type = strtolower(trim(explode(';', $server['CONTENT_TYPE'] ?? '')[0]));
    if (!in_array($type, ['application/json'], true)) {
        return [415, ['ok' => false, 'message' => 'Send JSON data.']];
    }
    try {
        if (!jengara_rate_limit($config['rate_dir'], $server['REMOTE_ADDR'] ?? '', time())) {
            return [429, ['ok' => false, 'message' => 'Too many requests. Please try again in 15 minutes.']];
        }
    } catch (Throwable $error) {
        return [503, ['ok' => false, 'message' => 'Contact service is temporarily unavailable. Please email hello@jengara.ai.']];
    }
    try {
        $fields = json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
    } catch (Throwable $error) {
        return [400, ['ok' => false, 'message' => 'Invalid request.']];
    }
    $allowed = ['name', 'email', 'company', 'interest', 'message', 'website'];
    if (!is_array($fields) || array_diff(array_keys($fields), $allowed)) {
        return [422, ['ok' => false, 'message' => 'Invalid form fields.']];
    }
    foreach ($fields as $value) {
        if (!is_string($value) || preg_match('//u', $value) !== 1 || preg_match('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/', $value)) {
            return [422, ['ok' => false, 'message' => 'Invalid form fields.']];
        }
    }
    $fields = array_map('trim', $fields);
    if (($fields['website'] ?? '') !== '') {
        return [422, ['ok' => false, 'message' => 'Unable to accept this request.']];
    }
    foreach (['name' => [1, 100], 'email' => [3, 200], 'company' => [1, 200], 'message' => [20, 2000]] as $key => [$minimum, $maximum]) {
        $value = $fields[$key] ?? '';
        if (preg_match_all('/./us', $value) < $minimum || preg_match_all('/./us', $value) > $maximum || ($key !== 'message' && preg_match('/[\r\n]/', $value))) {
            return [422, ['ok' => false, 'message' => 'Please check your name, email, company and message.']];
        }
    }
    $services = ['AI strategy', 'AI transformation', 'Performance & governance', 'Private capital', 'Labs collaboration', 'Help me scope the engagement'];
    if (!in_array($fields['interest'] ?? '', $services, true) || !filter_var($fields['email'], FILTER_VALIDATE_EMAIL)) {
        return [422, ['ok' => false, 'message' => 'Please choose an engagement and enter a valid email address.']];
    }
    $body = "New Jengara website enquiry\n\nName: {$fields['name']}\nEmail: {$fields['email']}\nCompany: " . ($fields['company'] ?? '') . "\nEngagement: {$fields['interest']}\n\n{$fields['message']}\n";
    $headers = ['From' => 'Jengara <hello@jengara.ai>', 'Reply-To' => $fields['email'], 'MIME-Version' => '1.0', 'Content-Type' => 'text/plain; charset=UTF-8'];
    try {
        $accepted = $testTransport !== null
            ? $testTransport('hello@jengara.ai', 'Jengara website enquiry', $body, $headers)
            : @mail('hello@jengara.ai', 'Jengara website enquiry', $body, $headers);
    } catch (Throwable $error) {
        $accepted = false;
    }
    return $accepted === true
        ? [202, ['ok' => true, 'status' => 'accepted', 'message' => 'Your enquiry has been accepted for sending. Delivery is not yet confirmed.']]
        : [503, ['ok' => false, 'message' => 'Your enquiry could not be queued. Please try again later or email hello@jengara.ai.']];
}

if (PHP_SAPI !== 'cli') {
    header('Content-Type: application/json; charset=UTF-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    try {
        $raw = file_get_contents('php://input', false, null, 0, 16385);
        [$status, $payload] = jengara_contact($_SERVER, $raw === false ? '' : $raw, jengara_config());
    } catch (Throwable $error) {
        [$status, $payload] = [503, ['ok' => false, 'message' => 'Contact service is temporarily unavailable. Please email hello@jengara.ai.']];
    }
    http_response_code($status);
    if ($status === 405) { header('Allow: POST'); }
    if ($status === 429) { header('Retry-After: 900'); }
    echo json_encode($payload, JSON_UNESCAPED_SLASHES);
}


