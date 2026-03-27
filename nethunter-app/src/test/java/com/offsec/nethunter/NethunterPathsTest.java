package com.offsec.nethunter;

import com.offsec.nethunter.utils.NethunterPaths;

import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

/**
 * Unit tests for {@link NethunterPaths} constants.
 *
 * <p>These tests verify that all path constants are well-formed and follow
 * the expected conventions (non-null, non-empty, absolute paths starting
 * with '/', and child paths rooted under their declared parent).</p>
 */
public class NethunterPathsTest {

    // ------------------------------------------------------------------
    // Non-null / non-empty
    // ------------------------------------------------------------------

    @Test
    public void nhSystemPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.NH_SYSTEM_PATH);
    }

    @Test
    public void chrootPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.CHROOT_PATH);
    }

    @Test
    public void chrootPathArm_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.CHROOT_PATH_ARM);
    }

    @Test
    public void scriptsPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.SCRIPTS_PATH);
    }

    @Test
    public void bootkaliScript_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.BOOTKALI_SCRIPT);
    }

    @Test
    public void checkServices_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.CHECK_SERVICES);
    }

    @Test
    public void nhFilesPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.NH_FILES_PATH);
    }

    @Test
    public void configsPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.CONFIGS_PATH);
    }

    @Test
    public void wlanConf_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.WLAN_CONF);
    }

    @Test
    public void duckscriptsPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.DUCKSCRIPTS_PATH);
    }

    @Test
    public void modulesPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.MODULES_PATH);
    }

    @Test
    public void gpsSocketPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.GPS_SOCKET_PATH);
    }

    @Test
    public void initdPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.INITD_PATH);
    }

    @Test
    public void nhInitdScript_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.NH_INITD_SCRIPT);
    }

    @Test
    public void logPath_isNotNullOrEmpty() {
        assertNotNullOrEmpty(NethunterPaths.LOG_PATH);
    }

    // ------------------------------------------------------------------
    // All paths must be absolute (start with '/')
    // ------------------------------------------------------------------

    @Test
    public void allPaths_areAbsolute() {
        assertAbsolutePath(NethunterPaths.NH_SYSTEM_PATH);
        assertAbsolutePath(NethunterPaths.CHROOT_PATH);
        assertAbsolutePath(NethunterPaths.CHROOT_PATH_ARM);
        assertAbsolutePath(NethunterPaths.SCRIPTS_PATH);
        assertAbsolutePath(NethunterPaths.BOOTKALI_SCRIPT);
        assertAbsolutePath(NethunterPaths.CHECK_SERVICES);
        assertAbsolutePath(NethunterPaths.NH_FILES_PATH);
        assertAbsolutePath(NethunterPaths.CONFIGS_PATH);
        assertAbsolutePath(NethunterPaths.WLAN_CONF);
        assertAbsolutePath(NethunterPaths.DUCKSCRIPTS_PATH);
        assertAbsolutePath(NethunterPaths.MODULES_PATH);
        assertAbsolutePath(NethunterPaths.GPS_SOCKET_PATH);
        assertAbsolutePath(NethunterPaths.INITD_PATH);
        assertAbsolutePath(NethunterPaths.NH_INITD_SCRIPT);
        assertAbsolutePath(NethunterPaths.LOG_PATH);
    }

    // ------------------------------------------------------------------
    // Child paths must be rooted under their declared parent
    // ------------------------------------------------------------------

    @Test
    public void chrootPath_isUnderNhSystemPath() {
        assertTrue("CHROOT_PATH should be under NH_SYSTEM_PATH",
            NethunterPaths.CHROOT_PATH.startsWith(NethunterPaths.NH_SYSTEM_PATH));
    }

    @Test
    public void bootkaliScript_isUnderScriptsPath() {
        assertTrue("BOOTKALI_SCRIPT should be under SCRIPTS_PATH",
            NethunterPaths.BOOTKALI_SCRIPT.startsWith(NethunterPaths.SCRIPTS_PATH));
    }

    @Test
    public void configsPath_isUnderNhFilesPath() {
        assertTrue("CONFIGS_PATH should be under NH_FILES_PATH",
            NethunterPaths.CONFIGS_PATH.startsWith(NethunterPaths.NH_FILES_PATH));
    }

    @Test
    public void wlanConf_isUnderConfigsPath() {
        assertTrue("WLAN_CONF should be under CONFIGS_PATH",
            NethunterPaths.WLAN_CONF.startsWith(NethunterPaths.CONFIGS_PATH));
    }

    @Test
    public void initdPath_isUnderChrootPath() {
        assertTrue("INITD_PATH should be under CHROOT_PATH",
            NethunterPaths.INITD_PATH.startsWith(NethunterPaths.CHROOT_PATH));
    }

    @Test
    public void nhInitdScript_isUnderInitdPath() {
        assertTrue("NH_INITD_SCRIPT should be under INITD_PATH",
            NethunterPaths.NH_INITD_SCRIPT.startsWith(NethunterPaths.INITD_PATH));
    }

    // ------------------------------------------------------------------
    // No paths should contain traversal sequences
    // ------------------------------------------------------------------

    @Test
    public void noPaths_containTraversalSequences() {
        String[] paths = {
            NethunterPaths.NH_SYSTEM_PATH, NethunterPaths.CHROOT_PATH,
            NethunterPaths.SCRIPTS_PATH, NethunterPaths.BOOTKALI_SCRIPT,
            NethunterPaths.NH_FILES_PATH, NethunterPaths.CONFIGS_PATH,
            NethunterPaths.WLAN_CONF, NethunterPaths.GPS_SOCKET_PATH,
            NethunterPaths.LOG_PATH
        };
        for (String path : paths) {
            assertFalse("Path must not contain '..': " + path, path.contains(".."));
        }
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private static void assertNotNullOrEmpty(String value) {
        assertNotNull("Path constant must not be null", value);
        assertFalse("Path constant must not be empty", value.isEmpty());
    }

    private static void assertAbsolutePath(String path) {
        assertTrue("Path must be absolute (start with '/'): " + path,
            path.startsWith("/"));
    }
}
