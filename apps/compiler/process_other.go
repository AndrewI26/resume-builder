//go:build !unix

package main

import (
	"os/exec"
	"time"
)

// superviseProcessGroup is a no-op where process groups are not available.
// The service is deployed on Linux; this exists so the package still builds
// elsewhere.
func superviseProcessGroup(cmd *exec.Cmd, grace time.Duration) {
	cmd.WaitDelay = grace
}
