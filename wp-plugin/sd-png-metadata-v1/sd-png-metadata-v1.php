<?php
/**
 * Plugin Name: SD PNG Metadata & Civitai.red Studio (Production V1)
 * Plugin URI: https://github.com/gaijinworld/sd-png-metadata
 * Description: Interactive Automatic1111 / Forge / Civitai.red (R/X/XXX browsingLevel 31) PNG Metadata Verifier & Drag-and-Drop JPG/WEBP-to-PNG Metadata Injector for https://gaijinworld-local.local/png-metadata. Shortcodes: [png_metadata], [png-metadata], [sd_png_metadata].
 * Version: 2026.10.20.02
 * Author: GaijinWorld
 * Author URI: https://github.com/gaijinworld
 * License: BSD-3-Clause
 * Requires PHP: 8.0
 */

if (!defined('ABSPATH')) {
    exit;
}

define('SDPM_PLUGIN_VERSION', '2026.10.20.02');
define('SDPM_PLUGIN_FILE', __FILE__);
define('SDPM_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('SDPM_PLUGIN_URL', plugin_dir_url(__FILE__));
define('SDPM_PAGE_SLUG', 'png-metadata');
define('SDPM_PAGE_TITLE', 'SD PNG Metadata & Civitai.red Studio');
define('SDPM_SHORTCODE', 'png_metadata');
define('SDPM_LOCAL_READY_DIR', 'C:/Users/jgoka/Downloads/__MOVIES/Video/chanyeol/face/civitai_ready_png');

final class SDPM_Plugin {
    private static ?SDPM_Plugin $instance = null;

    public static function instance(): SDPM_Plugin {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        add_shortcode('png_metadata', [$this, 'render_shortcode']);
        add_shortcode('png-metadata', [$this, 'render_shortcode']);
        add_shortcode('sd_png_metadata', [$this, 'render_shortcode']);
        add_shortcode('sd-png-metadata', [$this, 'render_shortcode']);

        add_action('init', [$this, 'maybe_ensure_page'], 20);
        add_action('rest_api_init', [$this, 'register_rest_routes']);
        add_filter('document_title_parts', [$this, 'filter_document_title']);
        add_filter('autoptimize_filter_js_exclude', [$this, 'filter_autoptimize_js_exclude']);
    }

    public function filter_document_title(array $title): array {
        if (is_page(SDPM_PAGE_SLUG)) {
            $title['title'] = 'SD PNG Metadata & Civitai.red Studio v' . SDPM_PLUGIN_VERSION;
        }
        return $title;
    }

    public function filter_autoptimize_js_exclude(string $exclude): string {
        return $exclude . ',SDPM_RUNTIME_CONFIG,CRC_TABLE,injectTextChunksIntoPngBuffer';
    }

    public static function activate(): void {
        self::ensure_page_exists();
        flush_rewrite_rules(false);
    }

    public function maybe_ensure_page(): void {
        if (get_option('sdpm_page_ensured_version') === SDPM_PLUGIN_VERSION) {
            return;
        }
        self::ensure_page_exists();
        update_option('sdpm_page_ensured_version', SDPM_PLUGIN_VERSION, true);
    }

    public static function ensure_page_exists(): void {
        $page = get_page_by_path(SDPM_PAGE_SLUG);
        if ($page instanceof WP_Post) {
            if (
                strpos($page->post_content, '[png_metadata]') === false &&
                strpos($page->post_content, '[png-metadata]') === false &&
                strpos($page->post_content, '[sd_png_metadata]') === false
            ) {
                wp_update_post([
                    'ID' => $page->ID,
                    'post_status' => 'publish',
                    'post_content' => trim($page->post_content . "\n\n[" . SDPM_SHORTCODE . ']'),
                ]);
            } elseif ($page->post_status !== 'publish') {
                wp_update_post([
                    'ID' => $page->ID,
                    'post_status' => 'publish',
                ]);
            }
            return;
        }

        wp_insert_post([
            'post_title' => SDPM_PAGE_TITLE,
            'post_name' => SDPM_PAGE_SLUG,
            'post_status' => 'publish',
            'post_type' => 'page',
            'post_content' => '[' . SDPM_SHORTCODE . ']',
            'comment_status' => 'closed',
            'ping_status' => 'closed',
        ]);
    }

    public function register_rest_routes(): void {
        register_rest_route('sd-png-metadata/v1', '/save-png', [
            'methods' => 'POST',
            'permission_callback' => '__return_true',
            'callback' => [$this, 'handle_save_png'],
        ]);
        register_rest_route('sd-png-metadata/v1', '/gallery-state', [
            'methods' => 'POST',
            'permission_callback' => '__return_true',
            'callback' => [$this, 'handle_gallery_state'],
        ]);
    }

    public function handle_gallery_state(WP_REST_Request $request): WP_REST_Response {
        $params = $request->get_json_params();
        $action = isset($params['action']) ? (string) $params['action'] : '';

        if ($action === 'clear_all') {
            update_option('sdpm_gallery_cleared', '1', true);
            update_option('sdpm_hidden_filenames', [], true);
            return new WP_REST_Response(['ok' => true, 'state' => 'cleared'], 200);
        }
        if ($action === 'restore_all') {
            update_option('sdpm_gallery_cleared', '0', true);
            update_option('sdpm_hidden_filenames', [], true);
            return new WP_REST_Response(['ok' => true, 'state' => 'restored'], 200);
        }
        if ($action === 'hide_one' && !empty($params['filename'])) {
            $hidden = (array) get_option('sdpm_hidden_filenames', []);
            $fname = sanitize_file_name((string) $params['filename']);
            if (!in_array($fname, $hidden, true)) {
                $hidden[] = $fname;
            }
            update_option('sdpm_hidden_filenames', $hidden, true);
            return new WP_REST_Response(['ok' => true, 'hidden' => $hidden], 200);
        }

        return new WP_REST_Response(['ok' => false, 'error' => 'Invalid action'], 400);
    }

    public function handle_save_png(WP_REST_Request $request): WP_REST_Response {
        $params = $request->get_json_params();
        $filename = isset($params['filename']) ? sanitize_file_name((string) $params['filename']) : '';
        $b64 = isset($params['base64_png']) ? (string) $params['base64_png'] : '';

        if ($filename === '' || $b64 === '') {
            return new WP_REST_Response(['ok' => false, 'error' => 'Missing filename or base64_png'], 400);
        }
        if (!str_ends_with(strtolower($filename), '.png')) {
            $filename .= '.png';
        }

        $raw = base64_decode($b64, true);
        if ($raw === false || strlen($raw) < 33 || substr($raw, 0, 8) !== "\x89PNG\r\n\x1a\n") {
            return new WP_REST_Response(['ok' => false, 'error' => 'Invalid PNG binary payload'], 400);
        }

        $saved_paths = [];

        // 1. Save to WordPress uploads directory
        $upload_dir = wp_upload_dir();
        $wp_target_dir = trailingslashit($upload_dir['basedir']) . 'sd-png-metadata/civitai_ready_png';
        if (wp_mkdir_p($wp_target_dir)) {
            $wp_file_path = trailingslashit($wp_target_dir) . $filename;
            if (file_put_contents($wp_file_path, $raw) !== false) {
                $saved_paths[] = $wp_file_path;
            }
        }

        // 2. Also save directly to the local organized folder if accessible on this host
        if (is_dir(dirname(SDPM_LOCAL_READY_DIR)) || wp_mkdir_p(SDPM_LOCAL_READY_DIR)) {
            @wp_mkdir_p(SDPM_LOCAL_READY_DIR);
            $local_path = trailingslashit(SDPM_LOCAL_READY_DIR) . $filename;
            if (@file_put_contents($local_path, $raw) !== false) {
                $saved_paths[] = str_replace('/', '\\', $local_path);
            }
        }

        // 3. Also save into plugin assets/civitai_ready_png
        $plugin_ready_dir = SDPM_PLUGIN_DIR . 'assets/civitai_ready_png';
        if (wp_mkdir_p($plugin_ready_dir)) {
            $plugin_file_path = trailingslashit($plugin_ready_dir) . $filename;
            @file_put_contents($plugin_file_path, $raw);
        }

        return new WP_REST_Response([
            'ok' => true,
            'filename' => $filename,
            'saved_path' => implode(' & ', $saved_paths),
            'download_url' => esc_url_raw(SDPM_PLUGIN_URL . 'assets/civitai_ready_png/' . rawurlencode($filename)),
        ], 200);
    }

    public function render_shortcode($atts = []): string {
        $records_path = SDPM_PLUGIN_DIR . 'assets/civitai_ready_png/metadata-verification.json';
        $records = [];
        if (is_readable($records_path)) {
            $decoded = json_decode((string) file_get_contents($records_path), true);
            if (is_array($decoded)) {
                foreach ($decoded as $rec) {
                    if (($rec['format'] ?? '') === 'PNG') {
                        $rec['web_src'] = esc_url_raw(SDPM_PLUGIN_URL . 'assets/civitai_ready_png/' . rawurlencode((string) $rec['filename']));
                        $records[] = $rec;
                    }
                }
            }
        }

        $initial_cleared = get_option('sdpm_gallery_cleared', '0') === '1';
        $initial_hidden = (array) get_option('sdpm_hidden_filenames', []);

        $rest_save_url = esc_url_raw(rest_url('sd-png-metadata/v1/save-png'));
        $rest_state_url = esc_url_raw(rest_url('sd-png-metadata/v1/gallery-state'));
        $records_json = wp_json_encode($records, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        $hidden_json = wp_json_encode(array_values($initial_hidden), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

        ob_start();
        ?>
<!--noptimize-->
<div id="main" tabindex="-1"></div><div class="ct-inner" style="display:none;" aria-hidden="true"></div>
<div class="sdpm-studio-wrap" id="sdpm-studio-app">
  <style>
    .sdpm-studio-wrap {
      --bg: #0b0f19;
      --panel: #131a2a;
      --panel-alt: #192236;
      --border: #2a3654;
      --text: #e8eefb;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --success: #22c55e;
      --danger: #ef4444;
      --warning: #f59e0b;
      --pink: #f43f5e;
      --purple: #a855f7;
      --mono: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      padding: 28px;
      border-radius: 16px;
      border: 1px solid var(--border);
      margin: 16px auto;
      max-width: 1440px;
      line-height: 1.5;
      box-sizing: border-box;
    }
    .sdpm-studio-wrap * { box-sizing: border-box; }
    .sdpm-studio-wrap code {
      background: #1e293b !important;
      color: #38bdf8 !important;
      padding: 2px 6px !important;
      border-radius: 4px !important;
      font-family: var(--mono) !important;
      font-size: 12px !important;
      border: 1px solid #334155 !important;
    }
    .sdpm-header {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }
    .sdpm-header h1 {
      margin: 0 0 6px 0 !important;
      font-size: 24px !important;
      font-weight: 700 !important;
      color: #fff !important;
    }
    .sdpm-subtitle {
      color: var(--muted);
      font-size: 13px;
      font-family: var(--mono);
    }
    .sdpm-status-pill {
      background: rgba(34, 197, 94, 0.14);
      border: 1px solid var(--success);
      color: #4ade80;
      padding: 8px 16px;
      border-radius: 999px;
      font-weight: 600;
      font-size: 13px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .sdpm-stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .sdpm-stat-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 18px;
    }
    .sdpm-stat-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .sdpm-stat-value {
      font-size: 22px;
      font-weight: 700;
      margin-top: 4px;
      color: #fff;
    }
    .sdpm-stat-sub {
      font-size: 12px;
      color: #4ade80;
      margin-top: 4px;
      word-break: break-all;
    }
    .sdpm-studio-panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      margin-bottom: 28px;
    }
    .sdpm-studio-header {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }
    .sdpm-studio-header h2 {
      margin: 0 !important;
      font-size: 18px !important;
      color: var(--accent) !important;
    }
    .sdpm-form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }
    .sdpm-field {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .sdpm-field.full { grid-column: 1 / -1; }
    .sdpm-field label {
      font-size: 11.5px;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .sdpm-field input, .sdpm-field textarea, .sdpm-field select {
      background: #090d16 !important;
      border: 1px solid var(--border) !important;
      color: var(--text) !important;
      border-radius: 8px !important;
      padding: 8px 10px !important;
      font-family: var(--mono) !important;
      font-size: 12.5px !important;
    }
    .sdpm-field textarea { min-height: 62px; resize: vertical; }
    .sdpm-dropzone-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-top: 14px;
    }
    .sdpm-dropzone {
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.09), rgba(244, 63, 94, 0.09));
      border: 2px dashed var(--accent);
      border-radius: 12px;
      padding: 22px 18px;
      text-align: center;
      transition: all 0.2s ease;
      cursor: pointer;
    }
    .sdpm-dropzone.inspect-only {
      background: linear-gradient(135deg, rgba(168, 85, 247, 0.08), rgba(34, 197, 94, 0.08));
      border-color: var(--purple);
    }
    .sdpm-dropzone.dragover {
      background: rgba(34, 197, 94, 0.2);
      border-color: var(--success);
      transform: scale(1.01);
    }
    .sdpm-dropzone h3 {
      margin: 0 0 6px 0 !important;
      font-size: 15.5px !important;
      color: #fff !important;
    }
    .sdpm-dropzone p {
      margin: 0 !important;
      font-size: 12.5px !important;
      color: var(--muted) !important;
    }
    #sdpm-live-inspect-result {
      margin-top: 14px;
      text-align: left;
      display: none;
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      font-family: var(--mono);
      font-size: 12.5px;
      white-space: pre-wrap;
      color: #a7f3d0;
    }
    #sdpm-injected-gallery {
      margin-top: 18px;
      display: none;
    }
    .sdpm-injected-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .sdpm-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
      background: var(--panel);
      border: 1px solid var(--border);
      padding: 14px 18px;
      border-radius: 12px;
    }
    .sdpm-toolbar-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .sdpm-search-box {
      background: #090d16 !important;
      border: 1px solid var(--border) !important;
      color: var(--text) !important;
      padding: 8px 14px !important;
      border-radius: 8px !important;
      min-width: 260px;
      font-size: 13px !important;
    }
    .sdpm-cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
      gap: 20px;
    }
    .sdpm-empty-state {
      grid-column: 1 / -1;
      background: var(--panel);
      border: 1px dashed var(--border);
      border-radius: 12px;
      padding: 36px 24px;
      text-align: center;
      color: var(--muted);
    }
    .sdpm-image-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .sdpm-card-top {
      display: grid;
      grid-template-columns: 165px 1fr;
      gap: 16px;
      padding: 16px;
      background: var(--panel-alt);
      border-bottom: 1px solid var(--border);
    }
    .sdpm-thumb-wrap {
      width: 165px;
      height: 190px;
      background: #070a12;
      border-radius: 10px;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--border);
    }
    .sdpm-thumb-wrap img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
    .sdpm-meta-head h3 {
      margin: 0 0 6px 0 !important;
      font-size: 15px !important;
      word-break: break-all;
      color: #fff !important;
    }
    .sdpm-badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 10px;
    }
    .sdpm-badge {
      font-size: 11px;
      font-family: var(--mono);
      padding: 3px 8px;
      border-radius: 6px;
      font-weight: 600;
    }
    .sdpm-badge-png { background: rgba(34, 197, 94, 0.18); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4); }
    .sdpm-badge-adult { background: rgba(244, 63, 94, 0.18); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.4); }
    .sdpm-badge-crc { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); }
    .sdpm-kv-mini {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 5px 10px;
      font-size: 12px;
    }
    .sdpm-kv-mini div span.k { color: var(--muted); }
    .sdpm-kv-mini div span.v { color: var(--text); font-family: var(--mono); font-weight: 600; }
    .sdpm-card-body {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .sdpm-section-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin-bottom: 4px;
      font-weight: 700;
    }
    .sdpm-prompt-box {
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 12px;
      color: #dbeafe;
      font-family: var(--mono);
      word-break: break-word;
    }
    .sdpm-prompt-box.neg { color: #fecdd3; }
    .sdpm-raw-details {
      background: #070a12;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 12px;
    }
    .sdpm-raw-details summary {
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
      color: var(--accent);
    }
    .sdpm-raw-pre {
      margin: 8px 0 0 0;
      font-family: var(--mono);
      font-size: 11px;
      color: #a7f3d0;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .sdpm-btn-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }
    .sdpm-btn {
      background: #1e293b;
      border: 1px solid var(--border);
      color: var(--text) !important;
      padding: 7px 13px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none !important;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .sdpm-btn:hover {
      border-color: var(--accent);
      color: var(--accent) !important;
    }
    .sdpm-btn.primary {
      background: var(--success);
      color: #052e16 !important;
      border-color: var(--success);
    }
    .sdpm-btn.danger {
      background: rgba(239, 68, 68, 0.16);
      color: #fca5a5 !important;
      border-color: rgba(239, 68, 68, 0.45);
    }
    .sdpm-btn.danger:hover {
      background: rgba(239, 68, 68, 0.28);
      color: #fff !important;
      border-color: var(--danger);
    }
    .sdpm-btn.warn {
      background: rgba(245, 158, 11, 0.16);
      color: #fcd34d !important;
      border-color: rgba(245, 158, 11, 0.45);
    }
  </style>

  <div class="sdpm-header">
    <div>
      <h1>SD-PNG-Metadata &amp; Civitai.red Studio (LocalWP v<?php echo esc_html(SDPM_PLUGIN_VERSION); ?>)</h1>
      <div class="sdpm-subtitle">Route: https://gaijinworld-local.local/png-metadata/ | Shortcode: [png_metadata] | Output Folder: <?php echo esc_html(SDPM_LOCAL_READY_DIR); ?></div>
    </div>
    <div class="sdpm-status-pill">
      <span>●</span>
      <span id="sdpm-top-status-text">CIVITAI.RED ADULT/XXX STUDIO + DRAG &amp; DROP INJECTOR READY</span>
    </div>
  </div>

  <div class="sdpm-stats-grid">
    <div class="sdpm-stat-card">
      <div class="sdpm-stat-label">Displayed Gallery PNGs</div>
      <div class="sdpm-stat-value" id="sdpm-stat-count"><?php echo count($records); ?> PNGs</div>
      <div class="sdpm-stat-sub">Use "Clear Gallery" below to empty at any time</div>
    </div>
    <div class="sdpm-stat-card">
      <div class="sdpm-stat-label">Binary PNG tEXt["parameters"]</div>
      <div class="sdpm-stat-value">100% CRC32 ✓</div>
      <div class="sdpm-stat-sub">Verified IEEE 802.3 CRC32 &amp; byte offsets</div>
    </div>
    <div class="sdpm-stat-card">
      <div class="sdpm-stat-label">WordPress REST Auto-Save</div>
      <div class="sdpm-stat-value">Active</div>
      <div class="sdpm-stat-sub">Saves dropped images to civitai_ready_png &amp; WP Uploads</div>
    </div>
    <div class="sdpm-stat-card">
      <div class="sdpm-stat-label">Civitai.red Rating Eligibility</div>
      <div class="sdpm-stat-value">R / X / XXX</div>
      <div class="sdpm-stat-sub">browsingLevel: 31 + Civitai resources JSON</div>
    </div>
  </div>

  <div class="sdpm-studio-panel">
    <div class="sdpm-studio-header">
      <h2>1. Drag &amp; Drop Any Future Images (JPG / WEBP / PNG) to Convert to PNG &amp; Add Civitai.red Adult Metadata</h2>
      <div>
        <select id="sdpmPresetSelect" onchange="window.sdpmApplyPreset()" style="background:#090d16;color:#38bdf8;border:1px solid #2a3654;padding:6px 10px;border-radius:6px;font-family:var(--mono);font-size:12px;">
          <option value="photoreal_male">Preset: Civitai.red Adult/XXX Photorealistic Male Portrait (Juggernaut XL + Pony V6)</option>
          <option value="photoreal_female">Preset: Civitai.red Adult/XXX Photorealistic Female Portrait (Juggernaut XL + Pony V6)</option>
          <option value="anime_pony">Preset: Civitai.red Uncensored Anime / 2.5D (Pony Diffusion V6 XL)</option>
        </select>
      </div>
    </div>

    <div class="sdpm-form-grid">
      <div class="sdpm-field full">
        <label>Positive Prompt (Injected into PNG tEXt["parameters"])</label>
        <textarea id="sdpmTplPos">score_9, score_8_up, score_7_up, masterpiece, best quality, ultra-detailed photorealistic portrait of a handsome young East Asian man, expressive eyes, natural skin pores, studio lighting, 85mm f/1.4 lens, raw photo, uncensored, mature aesthetic &lt;lora:add-detail-xl:0.8&gt;</textarea>
      </div>
      <div class="sdpm-field full">
        <label>Negative Prompt</label>
        <textarea id="sdpmTplNeg">score_6, score_5, score_4, blurry, low quality, worst quality, bad anatomy, deformed, disfigured, extra limbs, bad hands, mutated fingers, watermark, text, signature, censored, mosaic censorship, bar censor, jpeg artifacts</textarea>
      </div>
      <div class="sdpm-field">
        <label>Model</label>
        <input type="text" id="sdpmTplModel" value="Juggernaut_XL_v9" />
      </div>
      <div class="sdpm-field">
        <label>Model Hash</label>
        <input type="text" id="sdpmTplHash" value="e4a30e4607" />
      </div>
      <div class="sdpm-field">
        <label>Sampler</label>
        <input type="text" id="sdpmTplSampler" value="DPM++ 2M Karras" />
      </div>
      <div class="sdpm-field">
        <label>Steps / CFG / Clip Skip</label>
        <input type="text" id="sdpmTplStepsCfg" value="30 / 7 / 2" />
      </div>
      <div class="sdpm-field">
        <label>Seed ("auto" = unique per image)</label>
        <input type="text" id="sdpmTplSeed" value="auto" />
      </div>
      <div class="sdpm-field">
        <label>Civitai Browsing Level (31 = XXX)</label>
        <input type="text" id="sdpmTplBrowsingLevel" value="31" />
      </div>
    </div>

    <div class="sdpm-dropzone-grid">
      <div class="sdpm-dropzone" id="sdpmInjectDropzone" onclick="document.getElementById('sdpmInjectFileInput').click()">
        <input type="file" id="sdpmInjectFileInput" accept="image/*" multiple style="display:none" onchange="window.sdpmHandleInjectFiles(this.files)" />
        <h3>➕ Drop Future Images Here to Convert to PNG &amp; Inject Civitai.red Metadata</h3>
        <p>Batch-converts <code>.jpg</code>, <code>.jpeg</code>, <code>.webp</code>, <code>.png</code> to PNG, injects binary <code>tEXt["parameters"]</code> + CRC32, saves directly to <code>civitai_ready_png/</code> via WordPress REST API, and provides one-click download.</p>
      </div>

      <div class="sdpm-dropzone inspect-only" id="sdpmInspectDropzone" onclick="document.getElementById('sdpmInspectFileInput').click()">
        <input type="file" id="sdpmInspectFileInput" accept=".png,.jpg,.jpeg,.webp" style="display:none" onchange="window.sdpmHandleInspectFiles(this.files)" />
        <h3>🔍 Drop Any Image Here to Inspect Raw Binary Chunks (Read-Only)</h3>
        <p>Reads binary PNG <code>tEXt</code> chunk offsets &amp; CRC32 or JPEG/WebP EXIF <code>0x9286 UserComment</code> directly in browser memory.</p>
      </div>
    </div>

    <div id="sdpm-live-inspect-result"></div>

    <div id="sdpm-injected-gallery">
      <div class="sdpm-injected-header">
        <h3 style="margin:0;color:#4ade80;font-size:16px;">Newly Processed Images (<span id="sdpm-injected-count">0</span>)</h3>
        <div class="sdpm-btn-row">
          <button class="sdpm-btn primary" onclick="window.sdpmDownloadAllInjected()">⬇ Download All Newly Embedded PNGs</button>
          <button class="sdpm-btn danger" onclick="window.sdpmClearInjectedList()">🗑 Clear Newly Processed List</button>
        </div>
      </div>
      <div class="sdpm-cards-grid" id="sdpmInjectedCardsGrid"></div>
    </div>
  </div>

  <div class="sdpm-toolbar">
    <h2 style="margin:0;font-size:18px;color:#fff;">2. Verified Civitai.red-Ready PNG Gallery (<span id="sdpm-gallery-heading-count"><?php echo count($records); ?></span> Images)</h2>
    <div class="sdpm-toolbar-actions">
      <input type="text" class="sdpm-search-box" id="sdpmSearchBox" placeholder="Filter by filename, seed, prompt, hash..." oninput="window.sdpmRenderCards()" />
      <button class="sdpm-btn danger" id="sdpmClearGalleryBtn" onclick="window.sdpmClearAllGallery()">🗑 Clear All Displayed Gallery</button>
      <button class="sdpm-btn" id="sdpmRestoreGalleryBtn" onclick="window.sdpmRestoreGallery()" style="display:none;">↺ Restore Default 10 Images</button>
    </div>
  </div>

  <div class="sdpm-cards-grid" id="sdpmCardsGrid"></div>

  <script>
    (function() {
      const ALL_RECORDS = <?php echo $records_json; ?>;
      const REST_SAVE_URL = <?php echo wp_json_encode($rest_save_url); ?>;
      const REST_STATE_URL = <?php echo wp_json_encode($rest_state_url); ?>;
      let galleryCleared = <?php echo $initial_cleared ? 'true' : 'false'; ?> || localStorage.getItem('sdpm_gallery_cleared') === '1';
      let hiddenFilenames = new Set(<?php echo $hidden_json; ?>);
      try {
        const localHidden = JSON.parse(localStorage.getItem('sdpm_hidden_filenames') || '[]');
        localHidden.forEach(f => hiddenFilenames.add(f));
      } catch (e) {}

      const DEFAULT_CIVITAI_RESOURCES = JSON.stringify([
        { type: "checkpoint", modelVersionId: 357609, modelName: "Juggernaut XL", modelVersionName: "v9+RDPhoto2-Lightning_4S" },
        { type: "checkpoint", modelVersionId: 290640, modelName: "Pony Diffusion V6 XL", modelVersionName: "V6 (start with this one)" },
        { type: "lora", weight: 0.8, modelVersionId: 135867, modelName: "Detail Tweaker XL", modelVersionName: "v1.0" }
      ]);
      const INJECTED_ITEMS = [];

      const CRC_TABLE = new Uint32Array(256);
      for (let n = 0; n < 256; n++) {
        let c = n;
        for (let k = 0; k < 8; k++) {
          c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
        }
        CRC_TABLE[n] = c >>> 0;
      }
      function crc32(bytes) {
        let c = 0xffffffff;
        for (let i = 0; i < bytes.length; i++) {
          c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
        }
        return (c ^ 0xffffffff) >>> 0;
      }

      function createPngTextChunk(keyword, text) {
        const keyBytes = new TextEncoder().encode(keyword);
        const valBytes = new TextEncoder().encode(text);
        const dataLen = keyBytes.length + 1 + valBytes.length;
        const chunk = new Uint8Array(12 + dataLen);
        const dv = new DataView(chunk.buffer);
        dv.setUint32(0, dataLen, false);
        chunk[4] = 0x74; chunk[5] = 0x45; chunk[6] = 0x58; chunk[7] = 0x74;
        chunk.set(keyBytes, 8);
        chunk[8 + keyBytes.length] = 0;
        chunk.set(valBytes, 8 + keyBytes.length + 1);
        const crc = crc32(chunk.subarray(4, 8 + dataLen));
        dv.setUint32(8 + dataLen, crc, false);
        return chunk;
      }

      function injectTextChunksIntoPngBuffer(pngArrayBuffer, chunksMap) {
        const src = new Uint8Array(pngArrayBuffer);
        if (src.length < 33 || src[0] !== 0x89 || src[1] !== 0x50) {
          throw new Error('Invalid PNG buffer');
        }
        const ihdrLen = new DataView(pngArrayBuffer).getUint32(8, false);
        const insertOffset = 8 + 12 + ihdrLen;
        const extraChunks = [];
        for (const [k, v] of Object.entries(chunksMap)) {
          extraChunks.push(createPngTextChunk(k, v));
        }
        const extraTotal = extraChunks.reduce((acc, c) => acc + c.length, 0);
        const out = new Uint8Array(src.length + extraTotal);
        out.set(src.subarray(0, insertOffset), 0);
        let ptr = insertOffset;
        for (const c of extraChunks) {
          out.set(c, ptr);
          ptr += c.length;
        }
        out.set(src.subarray(insertOffset), ptr);
        return out.buffer;
      }

      function parsePngBinaryBuffer(buf) {
        const dv = new DataView(buf);
        const u8 = new Uint8Array(buf);
        let offset = 8;
        const chunks = [];
        let foundParams = '';
        let paramOffset = null;
        let paramCrc = null;
        let paramCrcValid = false;
        while (offset + 8 <= u8.length) {
          const len = dv.getUint32(offset, false);
          const type = String.fromCharCode(u8[offset+4], u8[offset+5], u8[offset+6], u8[offset+7]);
          const payload = u8.slice(offset + 8, offset + 8 + len);
          const storedCrc = dv.getUint32(offset + 8 + len, false) >>> 0;
          const calcCrc = crc32(u8.subarray(offset + 4, offset + 8 + len));
          const crcHex = '0x' + storedCrc.toString(16).padStart(8, '0');
          const crcValid = storedCrc === calcCrc;
          if (type === 'tEXt') {
            const nul = payload.indexOf(0);
            if (nul !== -1) {
              const key = new TextDecoder('latin1').decode(payload.slice(0, nul));
              const val = new TextDecoder('utf-8').decode(payload.slice(nul + 1));
              chunks.push({ type, keyword: key, offset, length: len, crc_hex: crcHex, crc_valid: crcValid });
              if (key === 'parameters') {
                foundParams = val;
                paramOffset = offset;
                paramCrc = crcHex;
                paramCrcValid = crcValid;
              }
            }
          } else {
            chunks.push({ type, offset, length: len, crc_hex: crcHex, crc_valid: crcValid });
          }
          offset += 12 + len;
          if (type === 'IEND') break;
        }
        return { chunks, foundParams, paramOffset, paramCrc, paramCrcValid };
      }

      // Strip all metadata from an image URL and download a clean PNG
      window.sdpmStripMetadataAndDownload = async function(imgSrc, filename) {
        const img = await new Promise((resolve, reject) => {
          const im = new Image();
          im.crossOrigin = 'anonymous';
          im.onload = () => resolve(im);
          im.onerror = reject;
          im.src = imgSrc;
        });
        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth || img.width;
        canvas.height = img.naturalHeight || img.height;
        canvas.getContext('2d').drawImage(img, 0, 0);
        const cleanBlob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        const url = URL.createObjectURL(cleanBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename.replace(/\.png$/i, '') + '_clean_no_metadata.png';
        document.body.appendChild(a);
        a.click();
        a.remove();
      };

      window.sdpmClearAllGallery = async function() {
        galleryCleared = true;
        localStorage.setItem('sdpm_gallery_cleared', '1');
        window.sdpmRenderCards();
        try {
          await fetch(REST_STATE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'clear_all' })
          });
        } catch (e) {}
      };

      window.sdpmRestoreGallery = async function() {
        galleryCleared = false;
        hiddenFilenames.clear();
        localStorage.setItem('sdpm_gallery_cleared', '0');
        localStorage.setItem('sdpm_hidden_filenames', '[]');
        window.sdpmRenderCards();
        try {
          await fetch(REST_STATE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'restore_all' })
          });
        } catch (e) {}
      };

      window.sdpmRemoveSingleCard = async function(filename) {
        hiddenFilenames.add(filename);
        localStorage.setItem('sdpm_hidden_filenames', JSON.stringify(Array.from(hiddenFilenames)));
        window.sdpmRenderCards();
        try {
          await fetch(REST_STATE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'hide_one', filename })
          });
        } catch (e) {}
      };

      window.sdpmClearInjectedList = function() {
        INJECTED_ITEMS.length = 0;
        document.getElementById('sdpm-injected-gallery').style.display = 'none';
        renderInjectedGallery();
      };

      window.sdpmRemoveInjectedItem = function(idx) {
        INJECTED_ITEMS.splice(idx, 1);
        if (INJECTED_ITEMS.length === 0) {
          document.getElementById('sdpm-injected-gallery').style.display = 'none';
        }
        renderInjectedGallery();
      };

      window.sdpmApplyPreset = function() {
        const val = document.getElementById('sdpmPresetSelect').value;
        if (val === 'photoreal_male') {
          document.getElementById('sdpmTplPos').value = 'score_9, score_8_up, score_7_up, masterpiece, best quality, ultra-detailed photorealistic portrait of a handsome young East Asian man, expressive eyes, natural skin pores, studio lighting, 85mm f/1.4 lens, raw photo, uncensored, mature aesthetic <lora:add-detail-xl:0.8>';
          document.getElementById('sdpmTplModel').value = 'Juggernaut_XL_v9';
          document.getElementById('sdpmTplHash').value = 'e4a30e4607';
        } else if (val === 'photoreal_female') {
          document.getElementById('sdpmTplPos').value = 'score_9, score_8_up, score_7_up, masterpiece, best quality, ultra-detailed photorealistic portrait of a gorgeous young woman, expressive eyes, natural skin texture, soft studio lighting, 85mm f/1.4 lens, raw photo, uncensored, mature aesthetic <lora:add-detail-xl:0.8>';
          document.getElementById('sdpmTplModel').value = 'Juggernaut_XL_v9';
          document.getElementById('sdpmTplHash').value = 'e4a30e4607';
        } else if (val === 'anime_pony') {
          document.getElementById('sdpmTplPos').value = 'score_9, score_8_up, score_7_up, source_anime, masterpiece, best quality, ultra-detailed illustration, vibrant lighting, uncensored, mature rating <lora:add-detail-xl:0.8>';
          document.getElementById('sdpmTplModel').value = 'ponyDiffusionV6XL_v6StartWithThisOne';
          document.getElementById('sdpmTplHash').value = '67ab2fd8ec';
        }
      };

      function buildParametersBlock(width, height, fileName) {
        const pos = document.getElementById('sdpmTplPos').value.trim();
        const neg = document.getElementById('sdpmTplNeg').value.trim();
        const model = document.getElementById('sdpmTplModel').value.trim() || 'Juggernaut_XL_v9';
        const hash = document.getElementById('sdpmTplHash').value.trim() || 'e4a30e4607';
        const sampler = document.getElementById('sdpmTplSampler').value.trim() || 'DPM++ 2M Karras';
        const parts = (document.getElementById('sdpmTplStepsCfg').value || '30 / 7 / 2').split('/').map(s => s.trim());
        const steps = parts[0] || '30';
        const cfg = parts[1] || '7';
        const clipSkip = parts[2] || '2';
        let seed = document.getElementById('sdpmTplSeed').value.trim();
        if (!seed || seed.toLowerCase() === 'auto') {
          let h = 2166136261;
          const s = fileName + ':' + width + 'x' + height + ':' + Date.now();
          for (let i = 0; i < s.length; i++) {
            h ^= s.charCodeAt(i);
            h = Math.imul(h, 16777619);
          }
          seed = String((Math.abs(h) % 8999999999) + 1000000000);
        }
        const bl = parseInt(document.getElementById('sdpmTplBrowsingLevel').value.trim() || '31', 10) || 31;
        const civitaiMeta = JSON.stringify({ nsfw: true, browsingLevel: bl, matureContent: true, allowMature: true, source: 'civitai.red' });
        const kvLine = `Steps: ${steps}, Sampler: ${sampler}, Schedule type: Karras, CFG scale: ${cfg}, Seed: ${seed}, Size: ${width}x${height}, Model hash: ${hash}, Model: ${model}, Clip skip: ${clipSkip}, Lora hashes: "add-detail-xl: 9c783c8ce46c", Version: f2.0.1v1.10.1-previous-635-gf5330788, Civitai resources: ${DEFAULT_CIVITAI_RESOURCES}, Civitai metadata: ${civitaiMeta}`;
        return {
          raw: `${pos}\nNegative prompt: ${neg}\n${kvLine}`,
          civitaiMeta,
          parsed: {
            'Positive prompt': pos,
            'Negative prompt': neg,
            'Steps': steps,
            'Sampler': sampler,
            'CFG scale': cfg,
            'Seed': seed,
            'Size': `${width}x${height}`,
            'Model hash': hash,
            'Model': model,
            'Clip skip': clipSkip
          }
        };
      }

      window.sdpmHandleInjectFiles = async function(fileList) {
        if (!fileList || !fileList.length) return;
        document.getElementById('sdpm-injected-gallery').style.display = 'block';

        for (const file of Array.from(fileList)) {
          const dataUrl = await new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = e => resolve(e.target.result);
            r.onerror = reject;
            r.readAsDataURL(file);
          });

          const img = await new Promise((resolve, reject) => {
            const im = new Image();
            im.onload = () => resolve(im);
            im.onerror = reject;
            im.src = dataUrl;
          });

          const width = img.naturalWidth || img.width;
          const height = img.naturalHeight || img.height;
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          canvas.getContext('2d').drawImage(img, 0, 0);

          const pngBlob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
          const rawPngBuf = await pngBlob.arrayBuffer();
          const stem = file.name.replace(/\.[^/.]+$/, '');
          const outFileName = stem + '.png';
          const built = buildParametersBlock(width, height, file.name);

          const injectedBuf = injectTextChunksIntoPngBuffer(rawPngBuf, {
            'parameters': built.raw,
            'Civitai resources': DEFAULT_CIVITAI_RESOURCES,
            'Civitai metadata': built.civitaiMeta,
            'Software': 'Automatic1111 / Stable Diffusion WebUI Forge'
          });

          const verified = parsePngBinaryBuffer(injectedBuf);
          const finalBlob = new Blob([injectedBuf], { type: 'image/png' });
          const downloadUrl = URL.createObjectURL(finalBlob);

          let savedDiskStatus = 'Ready for browser download';
          try {
            const b64 = await new Promise(resolve => {
              const fr = new FileReader();
              fr.onload = () => resolve(fr.result.split(',')[1]);
              fr.readAsDataURL(finalBlob);
            });
            const resp = await fetch(REST_SAVE_URL, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ filename: outFileName, base64_png: b64 })
            });
            if (resp.ok) {
              const rjson = await resp.json();
              savedDiskStatus = 'Saved to: ' + rjson.saved_path;
            }
          } catch (e) {}

          INJECTED_ITEMS.unshift({
            filename: outFileName,
            origFilename: file.name,
            width,
            height,
            size_str: `${width}x${height}`,
            file_size: injectedBuf.byteLength,
            downloadUrl,
            savedDiskStatus,
            paramOffset: verified.paramOffset,
            paramCrc: verified.paramCrc,
            paramCrcValid: verified.paramCrcValid,
            chunks: verified.chunks,
            parameters_raw: verified.foundParams,
            parsed: built.parsed
          });
        }
        renderInjectedGallery();
      };

      function escapeHtml(str) {
        return String(str || '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;');
      }

      function renderInjectedGallery() {
        const grid = document.getElementById('sdpmInjectedCardsGrid');
        document.getElementById('sdpm-injected-count').textContent = String(INJECTED_ITEMS.length);
        grid.innerHTML = '';
        INJECTED_ITEMS.forEach((item, idx) => {
          const p = item.parsed;
          const card = document.createElement('div');
          card.className = 'sdpm-image-card';
          card.style.borderColor = '#22c55e';
          card.innerHTML = `
            <div class="sdpm-card-top">
              <div class="sdpm-thumb-wrap">
                <img src="${item.downloadUrl}" alt="${escapeHtml(item.filename)}" />
              </div>
              <div class="sdpm-meta-head">
                <h3>${escapeHtml(item.filename)} <span style="font-size:11px;color:#94a3b8;">(from ${escapeHtml(item.origFilename)})</span></h3>
                <div class="sdpm-badge-row">
                  <span class="sdpm-badge sdpm-badge-png">NEW PNG (${item.size_str})</span>
                  <span class="sdpm-badge sdpm-badge-adult">CIVITAI.RED XXX I2V READY</span>
                  <span class="sdpm-badge sdpm-badge-crc">PNG tEXt @${item.paramOffset}B (CRC ${item.paramCrc} ${item.paramCrcValid ? '✓' : '✗'})</span>
                </div>
                <div class="sdpm-kv-mini">
                  <div><span class="k">Model: </span><span class="v">${escapeHtml(p['Model'])}</span></div>
                  <div><span class="k">Hash: </span><span class="v">${escapeHtml(p['Model hash'])}</span></div>
                  <div><span class="k">Sampler: </span><span class="v">${escapeHtml(p['Sampler'])}</span></div>
                  <div><span class="k">Steps / CFG: </span><span class="v">${escapeHtml(p['Steps'])} / ${escapeHtml(p['CFG scale'])}</span></div>
                  <div><span class="k">Seed: </span><span class="v">${escapeHtml(p['Seed'])}</span></div>
                  <div><span class="k">Size: </span><span class="v">${escapeHtml(p['Size'])}</span></div>
                </div>
                <div style="margin-top:8px;font-size:11px;color:#4ade80;font-family:var(--mono);">${escapeHtml(item.savedDiskStatus)}</div>
              </div>
            </div>
            <div class="sdpm-card-body">
              <div>
                <div class="sdpm-section-title">Embedded Positive Prompt</div>
                <div class="sdpm-prompt-box">${escapeHtml(p['Positive prompt'])}</div>
              </div>
              <details class="sdpm-raw-details">
                <summary>Verified Binary PNG tEXt["parameters"] Payload (${item.chunks.length} chunks)</summary>
                <pre class="sdpm-raw-pre">${escapeHtml(item.parameters_raw)}\n\n--- Binary Chunk Table ---\n${escapeHtml(JSON.stringify(item.chunks, null, 2))}</pre>
              </details>
              <div class="sdpm-btn-row">
                <a class="sdpm-btn primary" href="${item.downloadUrl}" download="${escapeHtml(item.filename)}">⬇ Download ${escapeHtml(item.filename)}</a>
                <button class="sdpm-btn danger" onclick="window.sdpmRemoveInjectedItem(${idx})">✕ Remove</button>
              </div>
            </div>
          `;
          grid.appendChild(card);
        });
      }

      window.sdpmDownloadAllInjected = function() {
        INJECTED_ITEMS.forEach((item, i) => {
          setTimeout(() => {
            const a = document.createElement('a');
            a.href = item.downloadUrl;
            a.download = item.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
          }, i * 250);
        });
      };

      window.sdpmCopyText = function(idx) {
        const raw = ALL_RECORDS[idx].parameters_raw;
        navigator.clipboard.writeText(raw);
        const btn = document.getElementById('sdpm-copy-btn-' + idx);
        const old = btn.textContent;
        btn.textContent = 'Copied A1111 Parameters!';
        setTimeout(() => btn.textContent = old, 1800);
      };

      window.sdpmRenderCards = function() {
        const q = (document.getElementById('sdpmSearchBox').value || '').toLowerCase();
        const grid = document.getElementById('sdpmCardsGrid');
        grid.innerHTML = '';

        const visibleRecords = galleryCleared
          ? []
          : ALL_RECORDS.filter(r => !hiddenFilenames.has(r.filename));

        document.getElementById('sdpm-stat-count').textContent = visibleRecords.length + ' PNGs';
        document.getElementById('sdpm-gallery-heading-count').textContent = String(visibleRecords.length);

        const clearBtn = document.getElementById('sdpmClearGalleryBtn');
        const restoreBtn = document.getElementById('sdpmRestoreGalleryBtn');
        clearBtn.style.display = visibleRecords.length > 0 ? 'inline-flex' : 'none';
        restoreBtn.style.display = (galleryCleared || hiddenFilenames.size > 0) ? 'inline-flex' : 'none';

        if (visibleRecords.length === 0) {
          grid.innerHTML = `
            <div class="sdpm-empty-state">
              <h3 style="margin:0 0 8px 0;color:#fff;font-size:16px;">Displayed PNG Gallery Cleared</h3>
              <p style="margin:0 0 14px 0;font-size:13px;">The preloaded gallery cards have been cleared from display. Drag &amp; drop any new images into Section 1 above, or click Restore if you want the 10 preloaded images back.</p>
              <button class="sdpm-btn" onclick="window.sdpmRestoreGallery()">↺ Restore Default 10 Images</button>
            </div>
          `;
          return;
        }

        ALL_RECORDS.forEach((r, idx) => {
          if (galleryCleared || hiddenFilenames.has(r.filename)) return;
          const hay = (r.filename + ' ' + r.parameters_raw + ' ' + r.sha256).toLowerCase();
          if (q && !hay.includes(q)) return;

          const p = r.parsed || {};
          const imgSrc = r.web_src;
          const card = document.createElement('div');
          card.className = 'sdpm-image-card';
          card.innerHTML = `
            <div class="sdpm-card-top">
              <div class="sdpm-thumb-wrap">
                <img src="${imgSrc}" alt="${escapeHtml(r.filename)}" loading="lazy" />
              </div>
              <div class="sdpm-meta-head">
                <h3>${escapeHtml(r.filename)}</h3>
                <div class="sdpm-badge-row">
                  <span class="sdpm-badge sdpm-badge-png">${r.format} (${r.size_str})</span>
                  <span class="sdpm-badge sdpm-badge-adult">CIVITAI.RED XXX I2V READY</span>
                  <span class="sdpm-badge sdpm-badge-crc">PNG tEXt @${r.png_param_chunk_offset}B (CRC ${r.png_param_chunk_crc} ✓)</span>
                </div>
                <div class="sdpm-kv-mini">
                  <div><span class="k">Model: </span><span class="v">${escapeHtml(p['Model'] || '-')}</span></div>
                  <div><span class="k">Hash: </span><span class="v">${escapeHtml(p['Model hash'] || '-')}</span></div>
                  <div><span class="k">Sampler: </span><span class="v">${escapeHtml(p['Sampler'] || '-')}</span></div>
                  <div><span class="k">Steps / CFG: </span><span class="v">${escapeHtml(p['Steps'] || '-')} / ${escapeHtml(p['CFG scale'] || '-')}</span></div>
                  <div><span class="k">Seed: </span><span class="v">${escapeHtml(p['Seed'] || '-')}</span></div>
                  <div><span class="k">Size: </span><span class="v">${escapeHtml(p['Size'] || r.size_str)}</span></div>
                  <div><span class="k">Clip skip: </span><span class="v">${escapeHtml(p['Clip skip'] || '2')}</span></div>
                  <div><span class="k">SHA-256: </span><span class="v">${r.sha256.slice(0, 12)}…</span></div>
                </div>
              </div>
            </div>
            <div class="sdpm-card-body">
              <div>
                <div class="sdpm-section-title">Positive Prompt (Automatic1111 + Pony/SDXL Adult Tags)</div>
                <div class="sdpm-prompt-box">${escapeHtml(p['Positive prompt'] || '')}</div>
              </div>
              <div>
                <div class="sdpm-section-title">Negative Prompt</div>
                <div class="sdpm-prompt-box neg">${escapeHtml(p['Negative prompt'] || '')}</div>
              </div>
              <details class="sdpm-raw-details">
                <summary>Inspect Raw Embedded "parameters" Chunk &amp; Binary PNG Chunk Ledger (${r.png_chunks_summary.length} chunks)</summary>
                <pre class="sdpm-raw-pre">${escapeHtml(r.parameters_raw)}\n\n--- Binary Chunk Table ---\n${escapeHtml(JSON.stringify(r.png_chunks_summary, null, 2))}</pre>
              </details>
              <div class="sdpm-btn-row">
                <a class="sdpm-btn primary" href="${imgSrc}" download="${escapeHtml(r.filename)}">⬇ Download PNG</a>
                <button class="sdpm-btn" id="sdpm-copy-btn-${idx}" onclick="window.sdpmCopyText(${idx})">Copy A1111 Parameters</button>
                <button class="sdpm-btn warn" onclick="window.sdpmStripMetadataAndDownload('${imgSrc}', '${escapeHtml(r.filename)}')">🧹 Strip Metadata (Clean PNG)</button>
                <button class="sdpm-btn danger" onclick="window.sdpmRemoveSingleCard('${escapeHtml(r.filename)}')">✕ Remove from Display</button>
              </div>
            </div>
          `;
          grid.appendChild(card);
        });
      };

      const injDz = document.getElementById('sdpmInjectDropzone');
      injDz.addEventListener('dragover', e => { e.preventDefault(); injDz.classList.add('dragover'); });
      injDz.addEventListener('dragleave', () => injDz.classList.remove('dragover'));
      injDz.addEventListener('drop', e => {
        e.preventDefault();
        injDz.classList.remove('dragover');
        if (e.dataTransfer.files.length) window.sdpmHandleInjectFiles(e.dataTransfer.files);
      });

      const insDz = document.getElementById('sdpmInspectDropzone');
      insDz.addEventListener('dragover', e => { e.preventDefault(); insDz.classList.add('dragover'); });
      insDz.addEventListener('dragleave', () => insDz.classList.remove('dragover'));
      insDz.addEventListener('drop', e => {
        e.preventDefault();
        insDz.classList.remove('dragover');
        if (e.dataTransfer.files.length) window.sdpmHandleInspectFiles(e.dataTransfer.files);
      });

      window.sdpmHandleInspectFiles = function(files) {
        const file = files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function(evt) {
          const buf = evt.target.result;
          const u8 = new Uint8Array(buf);
          const out = document.getElementById('sdpm-live-inspect-result');
          out.style.display = 'block';

          if (u8.length > 8 && u8[0] === 0x89 && u8[1] === 0x50 && u8[2] === 0x4E && u8[3] === 0x47) {
            const parsed = parsePngBinaryBuffer(buf);
            const summary = parsed.chunks.map(c => c.keyword ? `${c.type}[${c.keyword}] @${c.offset}B (CRC ${c.crc_hex} ${c.crc_valid ? '✓' : '✗'})` : `${c.type} @${c.offset}B`).join(' -> ');
            out.textContent = `[LIVE BINARY PNG INSPECTION: ${file.name} (${file.size} bytes)]\n` +
              `Chunks Found: ${summary}\n\n` +
              (parsed.foundParams ? `[EMBEDDED 'parameters' CHUNK VERIFIED]:\n${parsed.foundParams}` : `[WARNING]: No 'parameters' tEXt chunk found in ${file.name}. Drop it on the Left Box to convert & inject!`);
          } else {
            let pos = -1;
            for (let i = 0; i < u8.length - 8; i++) {
              if (u8[i]===0x55 && u8[i+1]===0x4E && u8[i+2]===0x49 && u8[i+3]===0x43 && u8[i+4]===0x4F && u8[i+5]===0x44 && u8[i+6]===0x45 && u8[i+7]===0x00) {
                pos = i;
                break;
              }
            }
            if (pos !== -1) {
              const slice = u8.slice(pos + 8, Math.min(u8.length, pos + 8 + 4096));
              const decoded = new TextDecoder('utf-16be').decode(slice).split('\0')[0];
              out.textContent = `[LIVE BINARY EXIF 0x9286 INSPECTION: ${file.name} (${file.size} bytes)]\n` +
                `Found UNICODE UserComment @${pos}B:\n\n${decoded}`;
            } else {
              out.textContent = `[LIVE BINARY INSPECTION: ${file.name}] No PNG tEXt or EXIF UNICODE UserComment found. Drop it on the Left Box to convert to PNG & inject Civitai.red metadata!`;
            }
          }
        };
        reader.readAsArrayBuffer(file);
      };

      window.sdpmRenderCards();
    })();
  </script>
</div>
<!--/noptimize-->
        <?php
        return (string) ob_get_clean();
    }
}

register_activation_hook(SDPM_PLUGIN_FILE, ['SDPM_Plugin', 'activate']);
SDPM_Plugin::instance();
