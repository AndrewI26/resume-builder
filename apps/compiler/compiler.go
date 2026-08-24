package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

// ErrBusy is returned when every compile slot is taken and the caller's
// context expired before one freed up.
var ErrBusy = errors.New("no compile slot available")

// CompileFailed carries a non-zero exit from the TeX engine along with
// whatever it said about why. It is a bad document, not a broken service.
type CompileFailed struct {
	Log string
}

func (e *CompileFailed) Error() string {
	return "compilation failed"
}

// Compiler runs a TeX engine over a document, one temporary directory at a
// time.
//
// The engine has to be pdfTeX. The template calls \pdfgentounicode, a pdfTeX
// primitive, to emit the glyph-to-Unicode map that makes the PDF readable by
// applicant tracking systems — which for a resume is close to the whole point.
// XeTeX-based engines such as Tectonic reject it.
//
// Running someone else's document is the job here, so the run is fenced in
// three ways: -no-shell-escape stops it executing commands, openin_any and
// openout_any in paranoid mode stop it reading or writing outside its own
// directory, and the whole thing happens in a container as an unprivileged
// user with nothing else on disk.
type Compiler struct {
	// path to the pdflatex binary
	Bin string
	// wall-clock limit for one run; a document that loops is killed
	Timeout time.Duration

	// bounds how many engines run at once. Each one is CPU- and memory-hungry,
	// so an unbounded queue would take the container down under load.
	slots chan struct{}
}

func NewCompiler(bin string, timeout time.Duration, concurrency int) *Compiler {
	return &Compiler{
		Bin:     bin,
		Timeout: timeout,
		slots:   make(chan struct{}, concurrency),
	}
}

// Compile turns LaTeX source into a PDF.
//
// Everything the run touches lives in a directory created for it and removed
// afterwards, so two requests cannot see each other's files and nothing
// accumulates between them.
func (c *Compiler) Compile(ctx context.Context, source []byte) ([]byte, error) {
	select {
	case c.slots <- struct{}{}:
		defer func() { <-c.slots }()
	case <-ctx.Done():
		return nil, ErrBusy
	}

	dir, err := os.MkdirTemp("", "compile-*")
	if err != nil {
		return nil, fmt.Errorf("creating work directory: %w", err)
	}
	defer os.RemoveAll(dir)

	if err := os.WriteFile(filepath.Join(dir, "main.tex"), source, 0o600); err != nil {
		return nil, fmt.Errorf("writing source: %w", err)
	}

	ctx, cancel := context.WithTimeout(ctx, c.Timeout)
	defer cancel()

	var stderr bytes.Buffer
	cmd := exec.CommandContext(ctx, c.Bin,
		// never stop to ask a human a question; there is nobody at the terminal
		"-interaction=nonstopmode",
		// give up on the first error rather than cascading through hundreds
		"-halt-on-error",
		// no \write18, no matter what the document contains
		"-no-shell-escape",
		// paths stay relative to cmd.Dir below. Paranoid mode refuses absolute
		// ones outright, including the input file's own path, so naming them
		// relatively is what lets the engine read its own input.
		"-output-directory=.",
		"main.tex",
	)
	cmd.Dir = dir
	cmd.Stderr = &stderr
	cmd.Stdout = nil
	superviseProcessGroup(cmd, 5*time.Second)
	// a deliberately small environment: the child inherits nothing this
	// service was started with, so a stray secret in the container's env
	// cannot reach a document that goes looking for it
	cmd.Env = []string{
		"PATH=/usr/local/bin:/usr/bin:/bin",
		"HOME=" + dir,
		"TMPDIR=" + dir,
		// TeX wants somewhere writable for generated font files; pointing it at
		// the throwaway directory keeps runs from sharing any state
		"TEXMFVAR=" + dir,
		// paranoid mode: the document cannot read a file outside its own
		// directory and the TeX tree, nor write outside its own directory.
		// This is what stops `\input{/etc/passwd}` from reaching the PDF.
		"openin_any=p",
		"openout_any=p",
		// pins the timestamp TeX bakes in, so identical input gives an
		// identical file and the result can be cached by hash
		"SOURCE_DATE_EPOCH=0",
		"FORCE_SOURCE_DATE=1",
	}

	runErr := cmd.Run()

	if ctx.Err() == context.DeadlineExceeded {
		return nil, &CompileFailed{Log: "timed out after " + c.Timeout.String()}
	}
	if runErr != nil {
		return nil, &CompileFailed{Log: c.diagnostics(dir, stderr.String())}
	}

	pdf, err := os.ReadFile(filepath.Join(dir, "main.pdf"))
	if err != nil {
		// a zero exit with no PDF means the engine gave up quietly
		return nil, &CompileFailed{Log: c.diagnostics(dir, stderr.String())}
	}

	return pdf, nil
}

// diagnostics gathers whatever the engine had to say about a failure.
//
// pdfTeX writes almost everything to main.log rather than stderr, so stderr
// alone usually explains nothing.
func (c *Compiler) diagnostics(dir, stderr string) string {
	log, err := os.ReadFile(filepath.Join(dir, "main.log"))
	if err != nil {
		return stderr
	}

	// the log opens with pages of configuration; the failure is at the end
	const tail = 4000
	if len(log) > tail {
		log = log[len(log)-tail:]
	}

	if stderr == "" {
		return string(log)
	}
	return stderr + "\n" + string(log)
}
