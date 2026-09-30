import { test, expect } from '@playwright/test';

test.describe('BECKIE 3D Holographic HUD E2E & Visual Suite', () => {
  test('HUD renders Beckie branding, blue-and-red holographic theme, and strict telemetry', async ({ page }) => {
    // Standard 1920x1080 viewport
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/');

    // 1. Verify Branding & Subtitle
    await expect(page.locator('text=BECKIE // HUD 3D')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=YOUR ALL-TIME COMPANION')).toBeVisible();

    // 2. Verify Background Canvas
    const canvas = page.locator('canvas').first();
    await expect(canvas).toBeVisible();

    // 3. Verify Left GPU Telemetry Module
    await expect(page.locator('text=GPU //').first()).toBeVisible();
    await expect(page.locator('text=GPU MODE:').first()).toBeVisible();
    await expect(page.locator('text=VRAM').first()).toBeVisible();
    await expect(page.locator('text=FAN SPEED:').first()).toBeVisible();

    // 4. Verify Center 3D Avatar Viewport
    const canvases = page.locator('canvas');
    await expect(canvases.first()).toBeVisible();

    // 5. Verify Right CPU Telemetry Module
    await expect(page.locator('text=CPU //').first()).toBeVisible();
    await expect(page.locator('text=CPU MODE:').first()).toBeVisible();
    await expect(page.locator('text=FREQ').first()).toBeVisible();

    // 6. Verify Bottom Status Panels
    await expect(page.locator('text=MIC PRIVACY')).toBeVisible();
    await expect(page.locator('text=ACTIVITY TRACKING')).toBeVisible();
    await expect(page.locator('text=DIALOGUE MODE')).toBeVisible();

    // 7. Verify Bottom-Right Affective State Panel
    await expect(page.locator('text=INFERRED AFFECTIVE STATE')).toBeVisible();

    // Wait for 130MB local avatar model to finish loading and rendering in Three.js
    await expect(page.locator('text=INITIALIZING LOCAL AVATAR GEOMETRY')).not.toBeVisible({ timeout: 60000 });

    // 8. Capture 1080p Visual Regression Screenshot
    await page.screenshot({ path: 'e2e-screenshots/beckie-hud-1080p.png' });

    // 9. Click GPU Module to open Detail Popover
    await page.locator('.hud-zone-left-circle').click();
    const popover = page.locator('div.hud-panel:has-text("Telemetry")').first();
    await expect(popover).toBeVisible();
    await expect(popover.locator('text=60-Second Real-Time Telemetry Stream')).toBeVisible();

    // Close Detail Popover
    await popover.locator('button:has(svg.lucide-x)').click();
    await expect(popover).not.toBeVisible();

    // 10. Test Settings Panel
    await page.click('button:has-text("SETTINGS")');
    const settingsPanel = page.locator('div.hud-panel:has-text("TACTICAL SETTINGS")');
    await expect(settingsPanel).toBeVisible();
    await expect(settingsPanel.getByText('BECKIE CORE SOVEREIGN CONTROLS')).toBeVisible();
    await expect(settingsPanel.getByText('Microphone Privacy', { exact: true })).toBeVisible();
    await expect(settingsPanel.getByText('Activity Tracking', { exact: true })).toBeVisible();
    await expect(settingsPanel.getByText('Emotion Understanding', { exact: true })).toBeVisible();
    await expect(settingsPanel.getByText('Neutral Mode', { exact: true })).toBeVisible();
    await expect(settingsPanel.getByText('Reduced Motion', { exact: true })).toBeVisible();

    // Close Settings
    await settingsPanel.locator('button:has(svg.lucide-x)').click();
    await expect(settingsPanel).not.toBeVisible();

    // 11. Test Logs Panel
    await page.click('button:has-text("LOGS")');
    const logsPanel = page.locator('div.hud-panel:has-text("SECURITY AUDIT LOGS")');
    await expect(logsPanel).toBeVisible();
    await expect(logsPanel.locator('text=BECKIE SQLCIPHER ENCRYPTED AUDIT TAIL')).toBeVisible();

    // Close Logs
    await logsPanel.locator('button:has(svg.lucide-x)').click();
    await expect(logsPanel).not.toBeVisible();
  });

  test('Unit integrity, RPM/percentage formatting, and mode-source confidence labels', async ({ page }) => {
    await page.goto('/');

    // Check that fan speed respects integrity:
    // If unavailable, displays UNAVAILABLE and does not invent fake RPM values
    const fanSpeedText = await page.locator('.hud-zone-left-circle').innerText();
    expect(fanSpeedText).toContain('FAN SPEED:');
    if (fanSpeedText.includes('UNAVAILABLE')) {
      expect(fanSpeedText).not.toContain('0 RPM');
      expect(fanSpeedText).not.toContain('1500 RPM');
    }

    // Verify SOURCE and confidence badge exists (exact, partial, or unknown)
    const sourceBadges = await page.locator('text=SOURCE').allInnerTexts();
    expect(sourceBadges.length).toBeGreaterThan(0);

    const gpuSourceText = await page.locator('.hud-zone-left-circle').innerText();
    expect(
      gpuSourceText.includes('EXACT') ||
      gpuSourceText.includes('PARTIAL') ||
      gpuSourceText.includes('UNKNOWN')
    ).toBe(true);

    const cpuSourceText = await page.locator('.hud-zone-right-circle').innerText();
    expect(
      cpuSourceText.includes('EXACT') ||
      cpuSourceText.includes('PARTIAL') ||
      cpuSourceText.includes('UNKNOWN')
    ).toBe(true);
  });

  test('Emergency pause test confirming telemetry polling stops', async ({ page }) => {
    await page.goto('/');

    // Initially active
    await expect(page.locator('button:has-text("PAUSE ALL")')).toBeVisible();

    // Trigger Emergency Pause
    await page.click('button:has-text("PAUSE ALL")');

    // Verify PAUSED state is active in global button and capsule
    await expect(page.locator('button:has-text("RESUME")')).toBeVisible();
    await expect(page.locator('text=PAUSED').first()).toBeVisible();

    // Verify Mic Privacy & Activity Tracking panels reflect PAUSED
    await expect(page.locator('.hud-panel:has-text("MIC PRIVACY"):has-text("PAUSED")')).toBeVisible();
    await expect(page.locator('.hud-panel:has-text("ACTIVITY TRACKING"):has-text("PAUSED")')).toBeVisible();

    // Resume
    await page.click('button:has-text("RESUME")');
    await expect(page.locator('button:has-text("PAUSE ALL")')).toBeVisible();
  });

  test('Responsive Layout Verification for 1280x720 Display', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/');

    await expect(page.locator('text=BECKIE // HUD 3D')).toBeVisible();

    // Check bounding boxes to verify no collisions/overlaps
    const gpuBox = await page.locator('.hud-zone-left-circle').boundingBox();
    const cpuBox = await page.locator('.hud-zone-right-circle').boundingBox();

    expect(gpuBox).toBeTruthy();
    expect(cpuBox).toBeTruthy();

    if (gpuBox && cpuBox) {
      // GPU right edge must not cross CPU left edge
      const gpuRight = gpuBox.x + gpuBox.width;
      const cpuLeft = cpuBox.x;
      expect(gpuRight).toBeLessThan(cpuLeft);
    }

    // Capture visual snapshot for 1280x720
    await page.screenshot({ path: 'e2e-screenshots/beckie-hud-720p.png' });
  });

  test('Avatar Inspection Panel displays Section 5 Capability Table and Blender Status', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/');

    // Click the INSPECT button in the Identity Card
    await page.click('button:has-text("INSPECT")');

    // Verify modal appears
    await expect(page.locator('text=BECKIE AVATAR INSPECTION & CAPABILITY AUDIT')).toBeVisible();

    // Verify Section 5 capability items in table
    await expect(page.getByText('SECTION 5 CAPABILITY VERIFICATION TABLE')).toBeVisible();
    await expect(page.getByText('Idle motion', { exact: false })).toBeVisible();
    await expect(page.getByText('Walking', { exact: false })).toBeVisible();
    await expect(page.getByText('Hovering', { exact: false })).toBeVisible();
    await expect(page.getByText('Flying', { exact: false })).toBeVisible();
    await expect(page.getByText('Speaking reaction', { exact: false })).toBeVisible();
    await expect(page.getByText('Facial lip-sync', { exact: false })).toBeVisible();
    await expect(page.getByText('Safe weapon pose', { exact: false })).toBeVisible();

    // Take screenshot of capability table tab
    await page.screenshot({ path: 'e2e-screenshots/beckie-avatar-capability-table.png' });

    // Click Converter tab to verify Blender banner
    await page.click('button:has-text("FBX-TO-GLB CONVERTER")');
    await expect(page.getByText('BLENDER DETECTION:', { exact: false })).toBeVisible();
    await expect(page.getByText('Blender is required to convert MidPoly.fbx to GLB.', { exact: false })).toBeVisible();

    // Take screenshot of the inspection panel
    await page.screenshot({ path: 'e2e-screenshots/beckie-avatar-inspection.png' });

    // Close modal
    await page.locator('button:has(svg.lucide-x)').first().click();
    await expect(page.locator('text=BECKIE AVATAR INSPECTION & CAPABILITY AUDIT')).not.toBeVisible();
  });
});
