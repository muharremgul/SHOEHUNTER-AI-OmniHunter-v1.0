package com.shoehunter.radar;

import android.Manifest;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Rect;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.annotation.NonNull;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ExperimentalGetImage;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.ListenableFuture;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Native, offline CameraX + ML Kit OCR selection screen.
 *
 * Live results are intentionally frozen before selection: this keeps drawn boxes,
 * the captured preview and the user's multi-selection on the same camera frame.
 */
public final class OcrScanActivity extends ComponentActivity {
    public static final String EXTRA_PAYLOAD_JSON = "shoehunter_ocr_payload_json";

    private static final int CAMERA_PERMISSION_REQUEST = 401;
    private static final long ANALYSIS_INTERVAL_MS = 280L;
    private static final int COLOR_BACKGROUND = Color.rgb(9, 9, 11);
    private static final int COLOR_SURFACE = Color.rgb(24, 24, 27);
    private static final int COLOR_TEXT = Color.rgb(250, 250, 250);
    private static final int COLOR_MUTED = Color.rgb(161, 161, 170);
    private static final int COLOR_ACCENT = Color.rgb(204, 255, 0);

    private final ExecutorService cameraExecutor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean processingFrame = new AtomicBoolean(false);
    private final Map<Integer, CheckBox> lineCheckboxes = new HashMap<>();
    private final List<OcrOverlayView.OcrBlock> latestBlocks = new ArrayList<>();

    private PreviewView previewView;
    private ImageView frozenFrameView;
    private OcrOverlayView overlayView;
    private TextView statusView;
    private TextView selectionView;
    private TextView candidateOverlay;
    private LinearLayout lineList;
    private Button freezeButton;
    private Button transferButton;
    private TextRecognizer recognizer;
    private ProcessCameraProvider cameraProvider;
    private Bitmap frozenBitmap;
    private volatile boolean frozen;
    private boolean cameraStarted;
    private boolean syncingCheckboxes;
    private long lastAnalysisAt;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(COLOR_BACKGROUND);
        getWindow().setNavigationBarColor(COLOR_BACKGROUND);
        recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
        buildLayout();

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED) {
            startCamera();
        } else {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION_REQUEST);
        }
    }

    private void buildLayout() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(COLOR_BACKGROUND);

        previewView = new PreviewView(this);
        previewView.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        previewView.setScaleType(PreviewView.ScaleType.FILL_CENTER);
        previewView.setContentDescription(getString(R.string.ocr_live_help));
        root.addView(previewView, matchParent());

        frozenFrameView = new ImageView(this);
        frozenFrameView.setScaleType(ImageView.ScaleType.FIT_XY);
        frozenFrameView.setVisibility(View.GONE);
        frozenFrameView.setContentDescription("Dondurulmuş OCR karesi");
        root.addView(frozenFrameView, matchParent());

        overlayView = new OcrOverlayView(this);
        overlayView.setSelectionListener(this::onOverlaySelectionChanged);
        root.addView(overlayView, matchParent());

        statusView = new TextView(this);
        statusView.setText(R.string.ocr_live_help);
        statusView.setTextColor(COLOR_TEXT);
        statusView.setTextSize(14);
        statusView.setPadding(dp(14), dp(10), dp(14), dp(10));
        statusView.setBackgroundColor(Color.argb(220, 9, 9, 11));
        statusView.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        FrameLayout.LayoutParams statusParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.TOP);
        root.addView(statusView, statusParams);

        candidateOverlay = new TextView(this);
        candidateOverlay.setTextColor(COLOR_BACKGROUND);
        candidateOverlay.setTextSize(13);
        candidateOverlay.setPadding(dp(12), dp(7), dp(12), dp(7));
        candidateOverlay.setBackgroundColor(Color.argb(235, 204, 255, 0));
        candidateOverlay.setVisibility(View.GONE);
        candidateOverlay.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        FrameLayout.LayoutParams candidateParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.TOP | Gravity.CENTER_HORIZONTAL);
        candidateParams.topMargin = dp(58);
        root.addView(candidateOverlay, candidateParams);

        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(10), dp(8), dp(10), dp(10));
        panel.setBackgroundColor(Color.argb(242, 24, 24, 27));
        FrameLayout.LayoutParams panelParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM);
        root.addView(panel, panelParams);

        TextView offline = new TextView(this);
        offline.setText(R.string.ocr_offline_notice);
        offline.setTextColor(COLOR_MUTED);
        offline.setTextSize(10);
        panel.addView(offline, fullWidthWrap());

        selectionView = new TextView(this);
        selectionView.setText(getString(R.string.ocr_selection_count, 0, 0));
        selectionView.setTextColor(COLOR_TEXT);
        selectionView.setTextSize(12);
        selectionView.setPadding(0, dp(5), 0, dp(5));
        selectionView.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        panel.addView(selectionView, fullWidthWrap());

        ScrollView lineScroll = new ScrollView(this);
        lineScroll.setFillViewport(false);
        lineList = new LinearLayout(this);
        lineList.setOrientation(LinearLayout.VERTICAL);
        lineScroll.addView(lineList, fullWidthWrap());
        LinearLayout.LayoutParams lineScrollParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(126));
        panel.addView(lineScroll, lineScrollParams);

        HorizontalScrollView controlScroll = new HorizontalScrollView(this);
        controlScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.setGravity(Gravity.CENTER_VERTICAL);
        controlScroll.addView(controls, new HorizontalScrollView.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        Button cancel = makeButton(getString(R.string.ocr_cancel));
        cancel.setOnClickListener(view -> finish());
        controls.addView(cancel);

        freezeButton = makeButton(getString(R.string.ocr_freeze));
        freezeButton.setOnClickListener(view -> toggleFreeze());
        controls.addView(freezeButton);

        Button selectAll = makeButton(getString(R.string.ocr_select_all));
        selectAll.setOnClickListener(view -> {
            if (!frozen) {
                Toast.makeText(this, R.string.ocr_freeze_first, Toast.LENGTH_SHORT).show();
                return;
            }
            overlayView.selectAll();
        });
        controls.addView(selectAll);

        Button clear = makeButton(getString(R.string.ocr_clear));
        clear.setOnClickListener(view -> overlayView.clearSelection());
        controls.addView(clear);

        transferButton = makeButton(getString(R.string.ocr_send_to_radar));
        transferButton.setEnabled(false);
        transferButton.setOnClickListener(view -> transferSelection());
        controls.addView(transferButton);

        panel.addView(controlScroll, fullWidthWrap());
        setContentView(root);
    }

    private void startCamera() {
        if (cameraStarted || isFinishing()) return;
        cameraStarted = true;
        ListenableFuture<ProcessCameraProvider> future = ProcessCameraProvider.getInstance(this);
        future.addListener(() -> {
            try {
                cameraProvider = future.get();
                Preview preview = new Preview.Builder().build();
                preview.setSurfaceProvider(previewView.getSurfaceProvider());
                ImageAnalysis analysis = new ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build();
                analysis.setAnalyzer(cameraExecutor, this::analyzeFrame);
                cameraProvider.unbindAll();
                cameraProvider.bindToLifecycle(
                        this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis);
            } catch (Exception error) {
                cameraStarted = false;
                statusView.setText(R.string.ocr_camera_failed);
                Toast.makeText(this, R.string.ocr_camera_failed, Toast.LENGTH_LONG).show();
            }
        }, ContextCompat.getMainExecutor(this));
    }

    @ExperimentalGetImage
    private void analyzeFrame(ImageProxy imageProxy) {
        long now = System.currentTimeMillis();
        if (frozen || now - lastAnalysisAt < ANALYSIS_INTERVAL_MS
                || !processingFrame.compareAndSet(false, true)) {
            imageProxy.close();
            return;
        }
        lastAnalysisAt = now;
        if (imageProxy.getImage() == null) {
            processingFrame.set(false);
            imageProxy.close();
            return;
        }

        int rotation = imageProxy.getImageInfo().getRotationDegrees();
        int sourceWidth = imageProxy.getWidth();
        int sourceHeight = imageProxy.getHeight();
        int uprightWidth = rotation == 90 || rotation == 270 ? sourceHeight : sourceWidth;
        int uprightHeight = rotation == 90 || rotation == 270 ? sourceWidth : sourceHeight;
        InputImage image = InputImage.fromMediaImage(imageProxy.getImage(), rotation);
        recognizer.process(image)
                .addOnSuccessListener(result -> publishResult(result, uprightWidth, uprightHeight))
                .addOnFailureListener(error -> runOnUiThread(
                        () -> statusView.setText(R.string.ocr_no_text)))
                .addOnCompleteListener(task -> {
                    processingFrame.set(false);
                    imageProxy.close();
                });
    }

    private void publishResult(Text result, int imageWidth, int imageHeight) {
        List<OcrOverlayView.OcrBlock> blocks = new ArrayList<>();
        int index = 0;
        for (Text.TextBlock textBlock : result.getTextBlocks()) {
            for (Text.Line line : textBlock.getLines()) {
                Rect bounds = line.getBoundingBox();
                String value = line.getText() == null ? "" : line.getText().trim();
                if (bounds == null || value.isEmpty()) continue;
                Float confidence = line.getConfidence();
                blocks.add(new OcrOverlayView.OcrBlock(
                        index++, value, bounds, confidence == null ? 0f : confidence));
            }
        }
        runOnUiThread(() -> {
            if (frozen || isFinishing()) return;
            latestBlocks.clear();
            latestBlocks.addAll(blocks);
            overlayView.setBlocks(blocks, imageWidth, imageHeight);
            List<String> liveLines = new ArrayList<>();
            for (OcrOverlayView.OcrBlock block : blocks) liveLines.add(block.text);
            String brand = OcrSelectionPayload.findBrand(liveLines);
            String productCode = OcrSelectionPayload.findProductCode(liveLines);
            String gtin = OcrSelectionPayload.findGtin(liveLines);
            String price = OcrSelectionPayload.findPriceText(liveLines);
            List<String> candidateParts = new ArrayList<>();
            if (brand != null) candidateParts.add(brand);
            if (productCode != null) candidateParts.add(productCode);
            if (gtin != null) candidateParts.add("GTIN " + gtin);
            if (price != null) candidateParts.add(price);
            if (candidateParts.isEmpty()) {
                candidateOverlay.setVisibility(View.GONE);
            } else {
                candidateOverlay.setText(getString(R.string.camera_candidate_prefix)
                        + " · " + String.join(" · ", candidateParts));
                candidateOverlay.setVisibility(View.VISIBLE);
            }
            statusView.setText(blocks.isEmpty()
                    ? getString(R.string.ocr_no_text)
                    : getString(R.string.ocr_live_help) + " (" + blocks.size() + ")");
        });
    }

    private void toggleFreeze() {
        if (!frozen) {
            if (latestBlocks.isEmpty()) {
                Toast.makeText(this, R.string.ocr_no_text, Toast.LENGTH_SHORT).show();
                return;
            }
            frozen = true;
            frozenBitmap = previewView.getBitmap();
            if (frozenBitmap != null) {
                frozenFrameView.setImageBitmap(frozenBitmap);
                frozenFrameView.setVisibility(View.VISIBLE);
            } else {
                Toast.makeText(this, R.string.ocr_capture_failed, Toast.LENGTH_LONG).show();
            }
            overlayView.setSelectionEnabled(true);
            freezeButton.setText(R.string.ocr_resume);
            buildLineCheckboxes();
            statusView.setText("Kutulara veya aşağıdaki satırlara dokunarak metni seçin.");
        } else {
            frozen = false;
            overlayView.setSelectionEnabled(false);
            overlayView.clearSelection();
            lineCheckboxes.clear();
            lineList.removeAllViews();
            releaseFrozenBitmap();
            freezeButton.setText(R.string.ocr_freeze);
            statusView.setText(R.string.ocr_live_help);
        }
    }

    private void buildLineCheckboxes() {
        lineCheckboxes.clear();
        lineList.removeAllViews();
        for (OcrOverlayView.OcrBlock block : latestBlocks) {
            CheckBox checkbox = new CheckBox(this);
            checkbox.setText((block.index + 1) + ". " + block.text);
            checkbox.setTextColor(COLOR_TEXT);
            checkbox.setTextSize(13);
            checkbox.setButtonTintList(android.content.res.ColorStateList.valueOf(COLOR_ACCENT));
            checkbox.setContentDescription("OCR satırı " + (block.index + 1) + ": " + block.text);
            checkbox.setTag(block.index);
            checkbox.setOnCheckedChangeListener((button, checked) -> {
                if (!syncingCheckboxes) overlayView.setSelected(block.index, checked);
            });
            lineCheckboxes.put(block.index, checkbox);
            lineList.addView(checkbox, fullWidthWrap());
        }
    }

    private void onOverlaySelectionChanged(Set<Integer> selectedIndexes) {
        syncingCheckboxes = true;
        for (Map.Entry<Integer, CheckBox> entry : lineCheckboxes.entrySet()) {
            entry.getValue().setChecked(selectedIndexes.contains(entry.getKey()));
        }
        syncingCheckboxes = false;

        List<String> selectedText = selectedText();
        selectionView.setText(getString(
                R.string.ocr_selection_count, selectedText.size(), latestBlocks.size()));
        String preview = OcrSelectionPayload.joinSelected(selectedText);
        if (!preview.isEmpty()) {
            selectionView.setText(selectionView.getText() + "\n"
                    + getString(R.string.ocr_selected_preview,
                    preview.length() > 180 ? preview.substring(0, 180) + "…" : preview));
        }
        transferButton.setEnabled(!selectedText.isEmpty());
    }

    private List<String> selectedText() {
        List<String> values = new ArrayList<>();
        for (OcrOverlayView.OcrBlock block : overlayView.getSelectedBlocks()) {
            values.add(block.text);
        }
        return values;
    }

    private void transferSelection() {
        List<OcrOverlayView.OcrBlock> selectedBlocks = overlayView.getSelectedBlocks();
        List<String> lines = selectedText();
        String selectedText = OcrSelectionPayload.joinSelected(lines);
        if (selectedText.isEmpty()) return;

        try {
            JSONObject payload = new JSONObject();
            payload.put("selected_text", selectedText);
            payload.put("source", "android_mlkit_text_recognition");
            payload.put("offline_recognition", true);
            payload.put("image_stored", false);

            JSONArray textBlocks = new JSONArray();
            for (OcrOverlayView.OcrBlock block : selectedBlocks) {
                JSONObject row = new JSONObject();
                row.put("text", block.text);
                row.put("confidence", block.confidence);
                textBlocks.put(row);
            }
            payload.put("text_blocks", textBlocks);

            String productCode = OcrSelectionPayload.findProductCode(lines);
            String gtin = OcrSelectionPayload.findGtin(lines);
            String brand = OcrSelectionPayload.findBrand(lines);
            JSONArray productCodes = new JSONArray();
            if (productCode != null) productCodes.put(productCode);
            payload.put("product_codes", productCodes);
            if (brand != null) payload.put("brand", brand);

            JSONObject identifiers = new JSONObject();
            if (productCode != null) identifiers.put("product_code", productCode);
            if (gtin != null) identifiers.put("barcode", gtin);
            payload.put("source_identifiers", identifiers);

            Intent result = new Intent();
            result.putExtra(EXTRA_PAYLOAD_JSON, payload.toString());
            setResult(RESULT_OK, result);
            finish();
        } catch (JSONException error) {
            Toast.makeText(this, R.string.scan_failed, Toast.LENGTH_LONG).show();
        }
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != CAMERA_PERMISSION_REQUEST) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startCamera();
        } else {
            showPermissionDialog();
        }
    }

    private void showPermissionDialog() {
        new AlertDialog.Builder(this)
                .setTitle(R.string.ocr_title)
                .setMessage(R.string.ocr_camera_permission)
                .setPositiveButton(R.string.ocr_open_settings, (dialog, which) -> {
                    Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                    intent.setData(Uri.parse("package:" + getPackageName()));
                    startActivity(intent);
                })
                .setNegativeButton(R.string.ocr_cancel, (dialog, which) -> finish())
                .setOnCancelListener(dialog -> finish())
                .show();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!cameraStarted && ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED) {
            startCamera();
        }
    }

    @Override
    protected void onDestroy() {
        frozen = true;
        if (cameraProvider != null) cameraProvider.unbindAll();
        cameraExecutor.shutdown();
        recognizer.close();
        releaseFrozenBitmap();
        super.onDestroy();
    }

    private void releaseFrozenBitmap() {
        frozenFrameView.setImageDrawable(null);
        frozenFrameView.setVisibility(View.GONE);
        if (frozenBitmap != null && !frozenBitmap.isRecycled()) frozenBitmap.recycle();
        frozenBitmap = null;
    }

    private Button makeButton(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setMinHeight(dp(48));
        button.setTextSize(12);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(dp(3), dp(3), dp(3), dp(3));
        button.setLayoutParams(params);
        return button;
    }

    private FrameLayout.LayoutParams matchParent() {
        return new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
    }

    private LinearLayout.LayoutParams fullWidthWrap() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
