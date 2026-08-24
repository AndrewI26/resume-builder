//go:build unix

package main

import (
	"os/exec"
	"syscall"
	"time"
)

// superviseProcessGroup arranges for a cancelled run to take its whole
// process tree with it.
//
// Killing only the direct child is not enough. The engine spawns helpers, and
// they inherit the pipe this service reads output from — so `Wait` would block
// on a grandchild that is still running long after the timeout passed, and the
// limit would not be a limit at all. Putting the child in its own process
// group means one signal reaches all of them.
func superviseProcessGroup(cmd *exec.Cmd, grace time.Duration) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

	cmd.Cancel = func() error {
		// the negative pid addresses the group rather than the one process
		return syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
	}

	// a backstop for output pipes still held open after the kill, so Wait
	// always returns
	cmd.WaitDelay = grace
}
