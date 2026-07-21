package com.shoehunter.radar;

/** Center-crop coordinate conversion shared by the live camera overlay and unit tests. */
final class OcrGeometry {
    private OcrGeometry() {
    }

    static float[] mapRect(
            float left, float top, float right, float bottom,
            int imageWidth, int imageHeight, int viewWidth, int viewHeight) {
        float safeImageWidth = Math.max(1, imageWidth);
        float safeImageHeight = Math.max(1, imageHeight);
        float scale = Math.max(viewWidth / safeImageWidth, viewHeight / safeImageHeight);
        float offsetX = (viewWidth - safeImageWidth * scale) / 2f;
        float offsetY = (viewHeight - safeImageHeight * scale) / 2f;
        return new float[]{
                left * scale + offsetX,
                top * scale + offsetY,
                right * scale + offsetX,
                bottom * scale + offsetY
        };
    }
}
