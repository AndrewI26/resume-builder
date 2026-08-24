package main

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

// stubEngine writes a shell script that stands in for pdflatex, so these
// tests exercise the process handling without needing a TeX installation.
func stubEngine(t *testing.T, body string) string {
	t.Helper()

	if runtime.GOOS == "windows" {
		t.Skip("the stub engine is a shell script")
	}

	path := filepath.Join(t.TempDir(), "engine.sh")
	script := "#!/bin/sh\n" +
		// kept before the loop below consumes them
		"ARGS=\"$*\"\n" +
		"while [ $# -gt 0 ]; do\n" +
		"  case \"$1\" in -output-directory=*) OUT=\"${1#-output-directory=}\" ;; esac\n" +
		"  shift\n" +
		"done\n" + body

	if err := os.WriteFile(path, []byte(script), 0o700); err != nil {
		t.Fatalf("writing stub engine: %v", err)
	}

	return path
}

const writesPDF = `printf '%%PDF-1.7 stub' > "$OUT/main.pdf"` + "\n"

func TestCompileReturnsThePDF(t *testing.T) {
	compiler := NewCompiler(stubEngine(t, writesPDF), 5*time.Second, 1)

	pdf, err := compiler.Compile(context.Background(), []byte(`\documentclass{article}`))
	if err != nil {
		t.Fatalf("Compile: %v", err)
	}

	if !strings.HasPrefix(string(pdf), "%PDF") {
		t.Errorf("got %q, want something starting with %%PDF", pdf)
	}
}

func TestCompileReportsANonZeroExitAsADocumentProblem(t *testing.T) {
	engine := stubEngine(t, "echo 'Undefined control sequence' >&2\nexit 1\n")
	compiler := NewCompiler(engine, 5*time.Second, 1)

	_, err := compiler.Compile(context.Background(), []byte(`\nope`))

	var failed *CompileFailed
	if !errors.As(err, &failed) {
		t.Fatalf("got %v, want a *CompileFailed", err)
	}
	if !strings.Contains(failed.Log, "Undefined control sequence") {
		t.Errorf("log %q does not carry the engine's complaint", failed.Log)
	}
}

func TestCompileTreatsAMissingPDFAsAFailure(t *testing.T) {
	// a zero exit that produced nothing must not read as success
	compiler := NewCompiler(stubEngine(t, "exit 0\n"), 5*time.Second, 1)

	_, err := compiler.Compile(context.Background(), []byte(`\documentclass{article}`))

	var failed *CompileFailed
	if !errors.As(err, &failed) {
		t.Fatalf("got %v, want a *CompileFailed", err)
	}
}

func TestCompileKillsARunThatOverrunsTheTimeout(t *testing.T) {
	compiler := NewCompiler(stubEngine(t, "sleep 10\n"), 200*time.Millisecond, 1)

	start := time.Now()
	_, err := compiler.Compile(context.Background(), []byte(`\loop`))
	elapsed := time.Since(start)

	var failed *CompileFailed
	if !errors.As(err, &failed) {
		t.Fatalf("got %v, want a *CompileFailed", err)
	}
	if !strings.Contains(failed.Log, "timed out") {
		t.Errorf("log %q does not say it timed out", failed.Log)
	}
	if elapsed > 5*time.Second {
		t.Errorf("took %v; the process was not killed promptly", elapsed)
	}
}

func TestCompileCleansUpItsWorkDirectory(t *testing.T) {
	before, err := filepath.Glob(filepath.Join(os.TempDir(), "compile-*"))
	if err != nil {
		t.Fatalf("Glob: %v", err)
	}

	compiler := NewCompiler(stubEngine(t, writesPDF), 5*time.Second, 1)
	if _, err := compiler.Compile(context.Background(), []byte(`\documentclass{article}`)); err != nil {
		t.Fatalf("Compile: %v", err)
	}

	after, err := filepath.Glob(filepath.Join(os.TempDir(), "compile-*"))
	if err != nil {
		t.Fatalf("Glob: %v", err)
	}
	if len(after) != len(before) {
		t.Errorf("left %d work directories behind", len(after)-len(before))
	}
}

func TestCompileDisablesShellEscape(t *testing.T) {
	// the flag is one of the controls that makes accepting a foreign document
	// safe, so its presence is asserted rather than assumed
	engine := stubEngine(t, `printf '%s' "$ARGS" > "$OUT/main.pdf"`+"\n")
	compiler := NewCompiler(engine, 5*time.Second, 1)

	args, err := compiler.Compile(context.Background(), []byte(`\documentclass{article}`))
	if err != nil {
		t.Fatalf("Compile: %v", err)
	}

	if !strings.Contains(string(args), "-no-shell-escape") {
		t.Errorf("args %q do not disable shell escape", args)
	}
}

func TestCompileForbidsReadingOutsideTheWorkDirectory(t *testing.T) {
	// paranoid mode is what stops a document reading arbitrary files
	engine := stubEngine(t, `env > "$OUT/main.pdf"`+"\n")
	compiler := NewCompiler(engine, 5*time.Second, 1)

	environment, err := compiler.Compile(context.Background(), []byte(`\documentclass{article}`))
	if err != nil {
		t.Fatalf("Compile: %v", err)
	}

	for _, want := range []string{"openin_any=p", "openout_any=p"} {
		if !strings.Contains(string(environment), want) {
			t.Errorf("environment does not set %s", want)
		}
	}
}

func TestCompileGivesTheChildAMinimalEnvironment(t *testing.T) {
	t.Setenv("A_SECRET_IN_THE_SERVICE_ENV", "hunter2")

	engine := stubEngine(t, `env > "$OUT/main.pdf"`+"\n")
	compiler := NewCompiler(engine, 5*time.Second, 1)

	captured, err := compiler.Compile(context.Background(), []byte(`\documentclass{article}`))
	if err != nil {
		t.Fatalf("Compile: %v", err)
	}

	if strings.Contains(string(captured), "hunter2") {
		t.Error("the service's own environment leaked into the engine")
	}
}

func TestCompileBoundsConcurrency(t *testing.T) {
	engine := stubEngine(t, "sleep 0.4\n"+writesPDF)
	compiler := NewCompiler(engine, 5*time.Second, 1)

	done := make(chan struct{}, 2)
	for range 2 {
		go func() {
			_, _ = compiler.Compile(context.Background(), []byte(`\documentclass{article}`))
			done <- struct{}{}
		}()
	}

	start := time.Now()
	<-done
	<-done

	// with one slot the two runs queue rather than overlap
	if time.Since(start) < 700*time.Millisecond {
		t.Error("the two compiles overlapped despite a single slot")
	}
}
