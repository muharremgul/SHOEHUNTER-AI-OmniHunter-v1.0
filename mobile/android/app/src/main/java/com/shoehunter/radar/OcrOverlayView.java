package com.shoehunter.radar;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** Draws ML Kit text lines over CameraX and lets the user select multiple regions. */
public final class OcrOverlayView extends View {
    public interface SelectionListener {
        void onSelectionChanged(Set<Integer> selectedIndexes);
    }

    public static final class OcrBlock {
        final int index;
        final String text;
        final Rect bounds;
        final float confidence;

        OcrBlock(int index, String text, Rect bounds, float confidence) {
            this.index = index;
            this.text = text;
            this.bounds = new Rect(bounds);
            this.confidence = confidence;
        }
    }

    private final Paint strokePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fillPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint numberPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final List<OcrBlock> blocks = new ArrayList<>();
    private final Set<Integer> selectedIndexes = new LinkedHashSet<>();
    private int imageWidth = 1;
    private int imageHeight = 1;
    private boolean selectionEnabled;
    private SelectionListener selectionListener;

    public OcrOverlayView(Context context) {
        this(context, null);
    }

    public OcrOverlayView(Context context, AttributeSet attrs) {
        super(context, attrs);
        setClickable(true);
        setFocusable(true);
        numberPaint.setColor(Color.BLACK);
        numberPaint.setTextSize(dp(12));
        numberPaint.setFakeBoldText(true);
        setContentDescription("Canlı OCR metin alanları");
    }

    void setSelectionListener(SelectionListener listener) {
        selectionListener = listener;
    }

    void setBlocks(List<OcrBlock> nextBlocks, int width, int height) {
        blocks.clear();
        blocks.addAll(nextBlocks == null ? Collections.emptyList() : nextBlocks);
        imageWidth = Math.max(1, width);
        imageHeight = Math.max(1, height);
        selectedIndexes.clear();
        updateAccessibilityDescription();
        invalidate();
        notifySelection();
    }

    void setSelectionEnabled(boolean enabled) {
        selectionEnabled = enabled;
        setFocusable(enabled);
        updateAccessibilityDescription();
    }

    void setSelected(int index, boolean selected) {
        if (selected) selectedIndexes.add(index);
        else selectedIndexes.remove(index);
        updateAccessibilityDescription();
        invalidate();
        notifySelection();
    }

    void selectAll() {
        selectedIndexes.clear();
        for (OcrBlock block : blocks) selectedIndexes.add(block.index);
        updateAccessibilityDescription();
        invalidate();
        notifySelection();
    }

    void clearSelection() {
        selectedIndexes.clear();
        updateAccessibilityDescription();
        invalidate();
        notifySelection();
    }

    List<OcrBlock> getSelectedBlocks() {
        List<OcrBlock> selected = new ArrayList<>();
        for (OcrBlock block : blocks) {
            if (selectedIndexes.contains(block.index)) selected.add(block);
        }
        return selected;
    }

    List<OcrBlock> getBlocks() {
        return new ArrayList<>(blocks);
    }

    Set<Integer> getSelectedIndexes() {
        return new LinkedHashSet<>(selectedIndexes);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        for (OcrBlock block : blocks) {
            RectF mapped = map(block.bounds);
            boolean selected = selectedIndexes.contains(block.index);
            int border = selected ? Color.rgb(204, 255, 0) : Color.rgb(56, 189, 248);
            int fill = selected ? Color.argb(76, 204, 255, 0) : Color.argb(35, 56, 189, 248);
            fillPaint.setStyle(Paint.Style.FILL);
            fillPaint.setColor(fill);
            strokePaint.setStyle(Paint.Style.STROKE);
            strokePaint.setStrokeWidth(selected ? dp(3) : dp(2));
            strokePaint.setColor(border);
            canvas.drawRoundRect(mapped, dp(3), dp(3), fillPaint);
            canvas.drawRoundRect(mapped, dp(3), dp(3), strokePaint);

            if (selectionEnabled) {
                float badgeSize = dp(20);
                RectF badge = new RectF(
                        mapped.left, mapped.top,
                        mapped.left + badgeSize, mapped.top + badgeSize);
                fillPaint.setColor(border);
                canvas.drawOval(badge, fillPaint);
                String number = String.valueOf(block.index + 1);
                float textWidth = numberPaint.measureText(number);
                canvas.drawText(number, badge.centerX() - textWidth / 2f,
                        badge.centerY() - (numberPaint.ascent() + numberPaint.descent()) / 2f,
                        numberPaint);
            }
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (!selectionEnabled) return true;
        if (event.getAction() != MotionEvent.ACTION_UP) return true;
        performClick();
        int hit = findHit(event.getX(), event.getY());
        if (hit >= 0) setSelected(hit, !selectedIndexes.contains(hit));
        return true;
    }

    @Override
    public boolean performClick() {
        super.performClick();
        return true;
    }

    private int findHit(float x, float y) {
        float tolerance = dp(12);
        int bestIndex = -1;
        float bestArea = Float.MAX_VALUE;
        for (OcrBlock block : blocks) {
            RectF mapped = map(block.bounds);
            RectF target = new RectF(
                    mapped.left - tolerance, mapped.top - tolerance,
                    mapped.right + tolerance, mapped.bottom + tolerance);
            float area = target.width() * target.height();
            if (target.contains(x, y) && area < bestArea) {
                bestArea = area;
                bestIndex = block.index;
            }
        }
        return bestIndex;
    }

    private RectF map(Rect bounds) {
        float[] values = OcrGeometry.mapRect(
                bounds.left, bounds.top, bounds.right, bounds.bottom,
                imageWidth, imageHeight, getWidth(), getHeight());
        return new RectF(values[0], values[1], values[2], values[3]);
    }

    private void updateAccessibilityDescription() {
        String mode = selectionEnabled ? "seçime açık" : "canlı tarama";
        setContentDescription("OCR alanları: " + blocks.size() + " bulundu, "
                + selectedIndexes.size() + " seçili, " + mode);
    }

    private void notifySelection() {
        if (selectionListener != null) {
            selectionListener.onSelectionChanged(getSelectedIndexes());
        }
    }

    private float dp(int value) {
        return value * getResources().getDisplayMetrics().density;
    }
}
