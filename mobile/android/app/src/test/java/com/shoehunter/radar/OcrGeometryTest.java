package com.shoehunter.radar;

import static org.junit.Assert.assertArrayEquals;

import org.junit.Test;

public class OcrGeometryTest {
    @Test
    public void mapsImageCoordinatesIntoCenterCropPreviewCoordinates() {
        assertArrayEquals(
                new float[]{0f, 40f, 200f, 160f},
                OcrGeometry.mapRect(25, 10, 75, 40, 100, 50, 200, 200),
                0.001f);
    }

    @Test
    public void preservesCoordinatesWhenAspectRatiosMatch() {
        assertArrayEquals(
                new float[]{20f, 40f, 100f, 120f},
                OcrGeometry.mapRect(10, 20, 50, 60, 100, 100, 200, 200),
                0.001f);
    }
}
