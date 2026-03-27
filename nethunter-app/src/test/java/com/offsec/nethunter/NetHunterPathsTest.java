package com.offsec.nethunter;

import com.offsec.nethunter.utils.NetHunterPaths;

import org.junit.Test;

import java.io.File;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

/**
 * Unit tests for {@link NetHunterPaths}.
 *
 * <p>Validates constant values, architecture-based path selection, and
 * path composition helpers without requiring Android runtime or root access.
 */
public class NetHunterPathsTest {

    // -------------------------------------------------------------------------
    // Constant sanity checks
    // -------------------------------------------------------------------------

    @Test
    public void nhSystemRoot_correctValue() {
        assertEquals("/data/local/nhsystem", NetHunterPaths.NH_SYSTEM_ROOT);
    }

    @Test
    public void chrootArm64_containsNhSystemRoot() {
        assertTrue(NetHunterPaths.CHROOT_ARM64.startsWith(NetHunterPaths.NH_SYSTEM_ROOT));
        assertTrue(NetHunterPaths.CHROOT_ARM64.contains("arm64"));
    }

    @Test
    public void chrootArmhf_containsNhSystemRoot() {
        assertTrue(NetHunterPaths.CHROOT_ARMHF.startsWith(NetHunterPaths.NH_SYSTEM_ROOT));
        assertTrue(NetHunterPaths.CHROOT_ARMHF.contains("armhf"));
    }

    @Test
    public void chrootAmd64_containsNhSystemRoot() {
        assertTrue(NetHunterPaths.CHROOT_AMD64.startsWith(NetHunterPaths.NH_SYSTEM_ROOT));
        assertTrue(NetHunterPaths.CHROOT_AMD64.contains("amd64"));
    }

    @Test
    public void chrootI386_containsNhSystemRoot() {
        assertTrue(NetHunterPaths.CHROOT_I386.startsWith(NetHunterPaths.NH_SYSTEM_ROOT));
        assertTrue(NetHunterPaths.CHROOT_I386.contains("i386"));
    }

    // -------------------------------------------------------------------------
    // Script and config paths are non-null and non-empty
    // -------------------------------------------------------------------------

    @Test
    public void bootkaliScript_notEmpty() {
        assertNotNull(NetHunterPaths.BOOTKALI_SCRIPT);
        assertFalse(NetHunterPaths.BOOTKALI_SCRIPT.isEmpty());
    }

    @Test
    public void logsDir_notEmpty() {
        assertNotNull(NetHunterPaths.LOGS_DIR);
        assertFalse(NetHunterPaths.LOGS_DIR.isEmpty());
    }

    @Test
    public void logFile_containsLogsDir() {
        assertTrue(NetHunterPaths.LOG_FILE.startsWith(NetHunterPaths.LOGS_DIR));
    }

    @Test
    public void configPaths_nonNull() {
        assertNotNull(NetHunterPaths.WPA_SUPPLICANT_CONF);
        assertNotNull(NetHunterPaths.RESOLV_CONF);
    }

    // -------------------------------------------------------------------------
    // getChrootPath – returns a non-null path that starts with NH_SYSTEM_ROOT
    // -------------------------------------------------------------------------

    @Test
    public void getChrootPath_notNull() {
        assertNotNull(NetHunterPaths.getChrootPath());
    }

    @Test
    public void getChrootPath_startsWithNhSystemRoot() {
        String path = NetHunterPaths.getChrootPath();
        assertTrue("Chroot path must be under nhsystem",
                path.startsWith(NetHunterPaths.NH_SYSTEM_ROOT));
    }

    @Test
    public void getChrootPath_isOneOfKnownValues() {
        String path = NetHunterPaths.getChrootPath();
        boolean known = path.equals(NetHunterPaths.CHROOT_ARM64)
                || path.equals(NetHunterPaths.CHROOT_ARMHF)
                || path.equals(NetHunterPaths.CHROOT_AMD64)
                || path.equals(NetHunterPaths.CHROOT_I386);
        assertTrue("getChrootPath should return one of the known chroot paths", known);
    }

    // -------------------------------------------------------------------------
    // inChroot
    // -------------------------------------------------------------------------

    @Test
    public void inChroot_prependsChrootPath() {
        String result = NetHunterPaths.inChroot("/etc/resolv.conf");
        assertTrue(result.startsWith(NetHunterPaths.getChrootPath()));
        assertTrue(result.endsWith("/etc/resolv.conf"));
    }

    @Test
    public void inChroot_composedCorrectly() {
        String expected = NetHunterPaths.getChrootPath() + "/root/.bashrc";
        assertEquals(expected, NetHunterPaths.inChroot("/root/.bashrc"));
    }

    // -------------------------------------------------------------------------
    // isChrootInstalled
    // -------------------------------------------------------------------------

    @Test
    public void isChrootInstalled_returnsFalseOnHost() {
        // On a CI host /data/local/nhsystem does not exist
        assertFalse("Chroot should not be installed in CI environment",
                NetHunterPaths.isChrootInstalled());
    }

    // -------------------------------------------------------------------------
    // exists
    // -------------------------------------------------------------------------

    @Test
    public void exists_rootDir_returnsTrue() {
        assertTrue("Root directory must exist", NetHunterPaths.exists("/"));
    }

    @Test
    public void exists_nonExistentPath_returnsFalse() {
        assertFalse(NetHunterPaths.exists("/this/path/definitely/does/not/exist/xyz123"));
    }
}
