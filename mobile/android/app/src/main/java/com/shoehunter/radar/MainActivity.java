package com.shoehunter.radar;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Parcelable;
import android.provider.MediaStore;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.PermissionRequest;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import com.google.mlkit.vision.barcode.common.Barcode;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanner;
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions;
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning;

import org.json.JSONException;
import org.json.JSONObject;

import java.net.URI;
import java.net.URISyntaxException;

public class MainActivity extends Activity {
    private static final String PREFS = "shoehunter_mobile";
    private static final String PREF_SERVER_URL = "server_url";
    private static final int FILE_CHOOSER_REQUEST = 101;
    private static final int OCR_SCANNER_REQUEST = 102;

    private static final int COLOR_BACKGROUND = Color.rgb(9, 9, 11);
    private static final int COLOR_SURFACE = Color.rgb(24, 24, 27);
    private static final int COLOR_TEXT = Color.rgb(250, 250, 250);
    private static final int COLOR_MUTED = Color.rgb(161, 161, 170);
    private static final int COLOR_ACCENT = Color.rgb(204, 255, 0);

    private SharedPreferences preferences;
    private WebView webView;
    private ProgressBar progressBar;
    private LinearLayout errorPanel;
    private TextView errorDetail;
    private TextView serverLabel;
    private ValueCallback<Uri[]> pendingFileChooser;
    private Uri pendingCameraUri;
    private String serverUrl;
    private boolean mainFrameFailed;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureWindow();
        preferences = getSharedPreferences(PREFS, MODE_PRIVATE);
        serverUrl = normalizeServerUrl(preferences.getString(PREF_SERVER_URL, BuildConfig.DEFAULT_SERVER_URL));
        buildLayout();
        configureWebView();

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else if (!preferences.contains(PREF_SERVER_URL)) {
            showServerDialog(true);
        } else {
            loadHome();
        }
    }

    private void configureWindow() {
        Window window = getWindow();
        window.setStatusBarColor(COLOR_BACKGROUND);
        window.setNavigationBarColor(COLOR_BACKGROUND);
    }

    private void buildLayout() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(COLOR_BACKGROUND);

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(14), 0, dp(6), 0);
        toolbar.setBackgroundColor(COLOR_BACKGROUND);
        root.addView(toolbar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(48)));

        LinearLayout titleGroup = new LinearLayout(this);
        titleGroup.setOrientation(LinearLayout.VERTICAL);
        titleGroup.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.addView(titleGroup, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 1f));

        TextView title = new TextView(this);
        title.setText(R.string.app_name);
        title.setTextColor(COLOR_TEXT);
        title.setTextSize(16);
        title.setTypeface(title.getTypeface(), android.graphics.Typeface.BOLD);
        titleGroup.addView(title);

        serverLabel = new TextView(this);
        serverLabel.setTextColor(COLOR_MUTED);
        serverLabel.setTextSize(10);
        serverLabel.setSingleLine(true);
        titleGroup.addView(serverLabel);

        TextView refreshButton = toolbarButton("↻", getString(R.string.refresh));
        refreshButton.setOnClickListener(v -> reloadCurrent());
        toolbar.addView(refreshButton, new LinearLayout.LayoutParams(dp(48), dp(48)));

        TextView scanButton = toolbarButton("▣", getString(R.string.scan_barcode));
        scanButton.setOnClickListener(v -> openNativeBarcodeScanner());
        toolbar.addView(scanButton, new LinearLayout.LayoutParams(dp(48), dp(48)));

        TextView ocrButton = toolbarButton("Aa", getString(R.string.scan_text));
        ocrButton.setTextSize(15);
        ocrButton.setTypeface(ocrButton.getTypeface(), android.graphics.Typeface.BOLD);
        ocrButton.setOnClickListener(v -> openNativeOcrScanner());
        toolbar.addView(ocrButton, new LinearLayout.LayoutParams(dp(48), dp(48)));

        TextView settingsButton = toolbarButton("⚙", getString(R.string.server_settings));
        settingsButton.setOnClickListener(v -> showServerDialog(false));
        toolbar.addView(settingsButton, new LinearLayout.LayoutParams(dp(48), dp(48)));

        FrameLayout content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        webView = new WebView(this);
        webView.setBackgroundColor(COLOR_BACKGROUND);
        content.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        progressBar.setProgressTintList(android.content.res.ColorStateList.valueOf(COLOR_ACCENT));
        FrameLayout.LayoutParams progressParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(3), Gravity.TOP);
        content.addView(progressBar, progressParams);

        errorPanel = createErrorPanel();
        errorPanel.setVisibility(View.GONE);
        content.addView(errorPanel, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        setContentView(root);
        updateServerLabel();
    }

    private TextView toolbarButton(String symbol, String description) {
        TextView button = new TextView(this);
        button.setText(symbol);
        button.setTextColor(COLOR_TEXT);
        button.setTextSize(24);
        button.setGravity(Gravity.CENTER);
        button.setContentDescription(description);
        button.setBackgroundResource(android.R.drawable.list_selector_background);
        return button;
    }

    private LinearLayout createErrorPanel() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setGravity(Gravity.CENTER);
        panel.setPadding(dp(28), dp(28), dp(28), dp(28));
        panel.setBackgroundColor(COLOR_BACKGROUND);

        TextView icon = new TextView(this);
        icon.setText("⌁");
        icon.setTextColor(COLOR_ACCENT);
        icon.setTextSize(48);
        icon.setGravity(Gravity.CENTER);
        panel.addView(icon, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView heading = new TextView(this);
        heading.setText(R.string.connection_failed);
        heading.setTextColor(COLOR_TEXT);
        heading.setTextSize(22);
        heading.setGravity(Gravity.CENTER);
        heading.setTypeface(heading.getTypeface(), android.graphics.Typeface.BOLD);
        LinearLayout.LayoutParams headingParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        headingParams.topMargin = dp(10);
        panel.addView(heading, headingParams);

        errorDetail = new TextView(this);
        errorDetail.setTextColor(COLOR_MUTED);
        errorDetail.setTextSize(14);
        errorDetail.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams detailParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        detailParams.topMargin = dp(10);
        detailParams.bottomMargin = dp(22);
        panel.addView(errorDetail, detailParams);

        Button retry = new Button(this);
        retry.setText(R.string.try_again);
        retry.setOnClickListener(v -> loadHome());
        panel.addView(retry, centeredButtonParams());

        Button settings = new Button(this);
        settings.setText(R.string.server_settings);
        settings.setOnClickListener(v -> showServerDialog(false));
        panel.addView(settings, centeredButtonParams());

        Button network = new Button(this);
        network.setText(R.string.network_settings);
        network.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS)));
        panel.addView(network, centeredButtonParams());
        return panel;
    }

    private LinearLayout.LayoutParams centeredButtonParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                Math.min(dp(320), getResources().getDisplayMetrics().widthPixels - dp(48)),
                ViewGroup.LayoutParams.WRAP_CONTENT);
        params.topMargin = dp(8);
        params.gravity = Gravity.CENTER_HORIZONTAL;
        return params;
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setSupportZoom(false);
        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(true);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        settings.setUserAgentString(settings.getUserAgentString()
                + " ShoeHunterAndroid/" + BuildConfig.VERSION_NAME);

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new AppWebViewClient());
        webView.setWebChromeClient(new AppWebChromeClient());
        webView.setDownloadListener(new AppDownloadListener());
    }

    private void openNativeBarcodeScanner() {
        GmsBarcodeScannerOptions options = new GmsBarcodeScannerOptions.Builder()
                .setBarcodeFormats(
                        Barcode.FORMAT_EAN_13,
                        Barcode.FORMAT_EAN_8,
                        Barcode.FORMAT_UPC_A,
                        Barcode.FORMAT_UPC_E,
                        Barcode.FORMAT_CODE_128,
                        Barcode.FORMAT_QR_CODE,
                        Barcode.FORMAT_DATA_MATRIX)
                .enableAutoZoom()
                .build();
        GmsBarcodeScanner scanner = GmsBarcodeScanning.getClient(this, options);
        scanner.startScan()
                .addOnSuccessListener(this::deliverNativeBarcode)
                .addOnCanceledListener(() -> Toast.makeText(
                        this, R.string.scan_cancelled, Toast.LENGTH_SHORT).show())
                .addOnFailureListener(error -> Toast.makeText(
                        this, R.string.scan_failed, Toast.LENGTH_LONG).show());
    }

    private void openNativeOcrScanner() {
        startActivityForResult(
                new Intent(this, OcrScanActivity.class), OCR_SCANNER_REQUEST);
    }

    private void deliverNativeBarcode(Barcode barcode) {
        String value = barcode.getRawValue();
        if (value == null || value.trim().isEmpty()) return;
        try {
            JSONObject payload = new JSONObject();
            payload.put("value", value.trim());
            payload.put("format", barcode.getFormat());
            payload.put("value_type", barcode.getValueType());
            String script = "(function(){sessionStorage.setItem('shoehunterNativeScan',"
                    + JSONObject.quote(payload.toString())
                    + ");window.location.assign('/radar');})()";
            webView.evaluateJavascript(script, null);
        } catch (JSONException error) {
            Toast.makeText(this, R.string.scan_failed, Toast.LENGTH_LONG).show();
        }
    }

    private void deliverNativeOcr(Intent data) {
        String rawPayload = data == null
                ? null : data.getStringExtra(OcrScanActivity.EXTRA_PAYLOAD_JSON);
        if (rawPayload == null || rawPayload.trim().isEmpty()) return;
        try {
            JSONObject payload = new JSONObject(rawPayload);
            String selectedText = payload.optString("selected_text", "").trim();
            if (selectedText.isEmpty()) return;

            JSONObject identifiers = payload.optJSONObject("source_identifiers");
            String barcode = identifiers == null ? "" : identifiers.optString("barcode", "");
            String productCode = identifiers == null ? "" : identifiers.optString("product_code", "");
            JSONObject exactScan = null;
            if (!barcode.isEmpty() || !productCode.isEmpty()) {
                exactScan = new JSONObject();
                exactScan.put("value", !barcode.isEmpty() ? barcode : productCode);
                exactScan.put("format", !barcode.isEmpty() ? "OCR_GTIN" : "OCR_PRODUCT_CODE");
                exactScan.put("value_type", "OCR_IDENTITY");
            }

            StringBuilder script = new StringBuilder("(function(){");
            script.append("sessionStorage.setItem('shoehunterNativeOcr',")
                    .append(JSONObject.quote(payload.toString())).append(");");
            script.append("sessionStorage.setItem('shoehunterLastNativeOcr',")
                    .append(JSONObject.quote(payload.toString())).append(");");
            if (exactScan != null) {
                script.append("sessionStorage.setItem('shoehunterNativeScan',")
                        .append(JSONObject.quote(exactScan.toString())).append(");");
            }
            script.append("window.location.assign('/radar');})()");
            webView.evaluateJavascript(script.toString(), null);
        } catch (JSONException error) {
            Toast.makeText(this, R.string.scan_failed, Toast.LENGTH_LONG).show();
        }
    }

    private void applyPendingNativeOcr() {
        String script = "(function(){"
                + "var raw=sessionStorage.getItem('shoehunterNativeOcr');if(!raw)return 'empty';"
                + "var payload;try{payload=JSON.parse(raw);}catch(e){sessionStorage.removeItem('shoehunterNativeOcr');return 'invalid';}"
                + "window.dispatchEvent(new CustomEvent('shoehunter:native-ocr',{detail:payload}));"
                + "var tries=0;function apply(){"
                + "var input=document.getElementById('radar-product-query');"
                + "if(input){var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');"
                + "if(setter&&setter.set){setter.set.call(input,payload.selected_text||'');}else{input.value=payload.selected_text||'';}"
                + "input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));"
                + "input.focus();input.scrollIntoView({behavior:'smooth',block:'center'});"
                + "sessionStorage.removeItem('shoehunterNativeOcr');return;}"
                + "if(tries===0){var buttons=Array.prototype.slice.call(document.querySelectorAll('button'));"
                + "var create=buttons.find(function(button){return (button.textContent||'').indexOf('Yeni Radar')>=0;});if(create)create.click();}"
                + "tries+=1;if(tries<32)setTimeout(apply,150);}setTimeout(apply,100);return 'scheduled';})()";
        webView.evaluateJavascript(script, null);
    }

    private void showServerDialog(boolean firstLaunch) {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(serverUrl);
        input.setSelectAllOnFocus(true);
        input.setHint("http://192.168.1.50:3000");
        input.setPadding(dp(18), dp(10), dp(18), dp(10));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(R.string.server_settings)
                .setMessage(R.string.server_help)
                .setView(input)
                .setPositiveButton(R.string.save_and_connect, null)
                .setNegativeButton(firstLaunch ? R.string.exit : android.R.string.cancel,
                        (d, which) -> {
                            if (firstLaunch) finish();
                        })
                .create();
        dialog.setCanceledOnTouchOutside(!firstLaunch);
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE)
                .setOnClickListener(v -> {
                    String normalized = normalizeServerUrl(input.getText().toString());
                    if (!isValidServerUrl(normalized)) {
                        input.setError(getString(R.string.invalid_server_url));
                        return;
                    }
                    serverUrl = normalized;
                    preferences.edit().putString(PREF_SERVER_URL, serverUrl).apply();
                    updateServerLabel();
                    dialog.dismiss();
                    loadHome();
                }));
        dialog.show();
    }

    private String normalizeServerUrl(String raw) {
        String value = raw == null ? "" : raw.trim();
        while (value.endsWith("/")) value = value.substring(0, value.length() - 1);
        return value;
    }

    private boolean isValidServerUrl(String candidate) {
        try {
            URI uri = new URI(candidate);
            return ("http".equalsIgnoreCase(uri.getScheme()) || "https".equalsIgnoreCase(uri.getScheme()))
                    && uri.getHost() != null;
        } catch (URISyntaxException ignored) {
            return false;
        }
    }

    private String homeUrl() {
        try {
            URI uri = new URI(serverUrl);
            String path = uri.getPath();
            if (path == null || path.isEmpty() || "/".equals(path)) {
                return serverUrl + BuildConfig.DEFAULT_START_PATH;
            }
        } catch (URISyntaxException ignored) {
            // Validation happens before this method is called.
        }
        return serverUrl;
    }

    private void loadHome() {
        if (!isNetworkAvailable()) {
            showError(getString(R.string.no_network));
            return;
        }
        mainFrameFailed = false;
        errorPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        progressBar.setVisibility(View.VISIBLE);
        webView.loadUrl(homeUrl());
    }

    private void reloadCurrent() {
        if (errorPanel.getVisibility() == View.VISIBLE || webView.getUrl() == null) {
            loadHome();
        } else {
            webView.reload();
        }
    }

    private boolean isNetworkAvailable() {
        ConnectivityManager manager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        Network network = manager.getActiveNetwork();
        if (network == null) return false;
        NetworkCapabilities capabilities = manager.getNetworkCapabilities(network);
        return capabilities != null && (
                capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                        || capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)
                        || capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
                        || capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN));
    }

    private void updateServerLabel() {
        if (serverLabel != null) serverLabel.setText(serverUrl);
    }

    private void showError(String detail) {
        mainFrameFailed = true;
        progressBar.setVisibility(View.GONE);
        webView.setVisibility(View.GONE);
        errorDetail.setText(getString(R.string.error_detail_format, detail, serverUrl));
        errorPanel.setVisibility(View.VISIBLE);
    }

    private boolean isAppServer(Uri uri) {
        try {
            URI configured = new URI(serverUrl);
            int configuredPort = configured.getPort() >= 0
                    ? configured.getPort() : ("https".equalsIgnoreCase(configured.getScheme()) ? 443 : 80);
            int targetPort = uri.getPort() >= 0
                    ? uri.getPort() : ("https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80);
            return configured.getHost() != null
                    && configured.getHost().equalsIgnoreCase(uri.getHost())
                    && configuredPort == targetPort;
        } catch (URISyntaxException ignored) {
            return false;
        }
    }

    private boolean openExternal(Uri uri) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
            return true;
        } catch (ActivityNotFoundException error) {
            Toast.makeText(this, R.string.no_app_for_link, Toast.LENGTH_SHORT).show();
            return true;
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    public void onBackPressed() {
        if (errorPanel.getVisibility() == View.VISIBLE) {
            loadHome();
        } else if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == OCR_SCANNER_REQUEST) {
            if (resultCode == RESULT_OK) deliverNativeOcr(data);
            return;
        }
        if (requestCode != FILE_CHOOSER_REQUEST || pendingFileChooser == null) return;
        Uri[] result = null;
        boolean usedCamera = false;
        if (resultCode == RESULT_OK) {
            result = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            if ((result == null || result.length == 0) && pendingCameraUri != null) {
                result = new Uri[]{pendingCameraUri};
                usedCamera = true;
            }
        }
        pendingFileChooser.onReceiveValue(result);
        pendingFileChooser = null;
        if (!usedCamera) deletePendingCameraUri();
        pendingCameraUri = null;
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.setWebChromeClient(null);
            webView.setWebViewClient(null);
            webView.destroy();
        }
        deletePendingCameraUri();
        super.onDestroy();
    }

    private final class AppWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            String scheme = uri.getScheme();
            if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) {
                return !isAppServer(uri) && openExternal(uri);
            }
            return openExternal(uri);
        }

        @Override
        public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
            mainFrameFailed = false;
            errorPanel.setVisibility(View.GONE);
            webView.setVisibility(View.VISIBLE);
            progressBar.setVisibility(View.VISIBLE);
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            progressBar.setVisibility(View.GONE);
            if (!mainFrameFailed) {
                errorPanel.setVisibility(View.GONE);
                webView.setVisibility(View.VISIBLE);
                if (url != null && url.contains("/radar")) applyPendingNativeOcr();
            }
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request.isForMainFrame()) {
                showError(getString(R.string.web_error_format, error.getErrorCode(), error.getDescription()));
            }
        }

        @Override
        public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
            if (request.isForMainFrame() && response.getStatusCode() >= 400) {
                showError(getString(R.string.http_error_format, response.getStatusCode()));
            }
        }

    }

    private final class AppWebChromeClient extends WebChromeClient {
        @Override
        public void onProgressChanged(WebView view, int newProgress) {
            progressBar.setProgress(newProgress);
            progressBar.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
        }

        @Override
        public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> filePathCallback,
                                         FileChooserParams fileChooserParams) {
            if (pendingFileChooser != null) pendingFileChooser.onReceiveValue(null);
            deletePendingCameraUri();
            pendingFileChooser = filePathCallback;
            Intent intent;
            try {
                Intent pickerIntent = fileChooserParams.createIntent();
                pickerIntent.addCategory(Intent.CATEGORY_OPENABLE);
                Intent chooser = Intent.createChooser(pickerIntent, getString(R.string.choose_photo));
                Intent cameraIntent = createCameraIntent();
                if (cameraIntent != null) {
                    chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS, new Parcelable[]{cameraIntent});
                }
                intent = chooser;
                startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                return true;
            } catch (ActivityNotFoundException error) {
                deletePendingCameraUri();
                pendingFileChooser = null;
                Toast.makeText(MainActivity.this, R.string.no_file_picker, Toast.LENGTH_SHORT).show();
                return false;
            }
        }

        @Override
        public void onPermissionRequest(PermissionRequest request) {
            // The current web app does not need camera/microphone/geolocation.
            // Deny unexpected web permissions instead of granting them broadly.
            request.deny();
        }
    }

    private Intent createCameraIntent() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null;
        Intent camera = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        if (camera.resolveActivity(getPackageManager()) == null) return null;
        ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME, "shoehunter-label-" + System.currentTimeMillis() + ".jpg");
        values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
        values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/ShoeHunter");
        pendingCameraUri = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
        if (pendingCameraUri == null) return null;
        camera.putExtra(MediaStore.EXTRA_OUTPUT, pendingCameraUri);
        camera.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
        return camera;
    }

    private void deletePendingCameraUri() {
        if (pendingCameraUri == null) return;
        try {
            getContentResolver().delete(pendingCameraUri, null, null);
        } catch (Exception ignored) {
            // Best-effort cleanup for a cancelled camera capture.
        }
    }

    private final class AppDownloadListener implements DownloadListener {
        @Override
        public void onDownloadStart(String url, String userAgent, String contentDisposition,
                                    String mimeType, long contentLength) {
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                Toast.makeText(MainActivity.this, R.string.unsupported_download, Toast.LENGTH_SHORT).show();
                return;
            }
            try {
                String fileName = URLUtil.guessFileName(url, contentDisposition, mimeType);
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
                request.setMimeType(mimeType);
                request.addRequestHeader("User-Agent", userAgent);
                String cookies = CookieManager.getInstance().getCookie(url);
                if (cookies != null) request.addRequestHeader("Cookie", cookies);
                request.setTitle(fileName);
                request.setDescription(getString(R.string.downloading));
                request.setNotificationVisibility(
                        DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName);
                } else {
                    request.setDestinationInExternalFilesDir(
                            MainActivity.this, Environment.DIRECTORY_DOWNLOADS, fileName);
                }
                DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                manager.enqueue(request);
                Toast.makeText(MainActivity.this, R.string.download_started, Toast.LENGTH_SHORT).show();
            } catch (Exception error) {
                Toast.makeText(MainActivity.this, R.string.download_failed, Toast.LENGTH_LONG).show();
            }
        }
    }
}
