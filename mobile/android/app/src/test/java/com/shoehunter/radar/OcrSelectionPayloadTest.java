package com.shoehunter.radar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.Arrays;

public class OcrSelectionPayloadTest {
    @Test
    public void selectedLinesKeepReadingOrderAndDropDuplicates() {
        assertEquals(
                "Adidas TRAIL RUNNING JR5220",
                OcrSelectionPayload.joinSelected(Arrays.asList(
                        " Adidas ", "TRAIL  RUNNING", "adidas", "JR5220")));
    }

    @Test
    public void exactProductCodesAreExtractedFromApprovedLines() {
        assertEquals("JR5220", OcrSelectionPayload.findProductCode(
                Arrays.asList("TRAIL RUNNING", "JR5220", "EU 44")));
        assertEquals("HV8113-200", OcrSelectionPayload.findProductCode(
                Arrays.asList("NIKE", "HV8113-200", "EUR 42.5")));
        assertNull(OcrSelectionPayload.findProductCode(
                Arrays.asList("TRAIL RUNNING", "EU 44")));
    }

    @Test
    public void gtinIsAcceptedOnlyWithAValidCheckDigit() {
        assertTrue(OcrSelectionPayload.isValidGtin("4067904494690"));
        assertEquals("4067904494690", OcrSelectionPayload.findGtin(
                Arrays.asList("EAN", "4067904494690")));
        assertNull(OcrSelectionPayload.findGtin(Arrays.asList("4067904494691")));
    }

    @Test
    public void commonRetailBrandsAreCanonicalized() {
        assertEquals("Under Armour", OcrSelectionPayload.findBrand(
                Arrays.asList("UNDER ARMOUR", "3027000-107")));
        assertEquals("Adidas", OcrSelectionPayload.findBrand(
                Arrays.asList("adidas", "JR5220")));
    }

    @Test
    public void liveCandidateOverlayExtractsAVisiblePriceWithoutInventingOne() {
        assertEquals("24.999 TL", OcrSelectionPayload.findPriceText(
                Arrays.asList("NORDMENDE", "24.999 TL")));
        assertNull(OcrSelectionPayload.findPriceText(
                Arrays.asList("NORDMENDE", "Q65NM1105")));
    }
}
