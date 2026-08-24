// Command compiler turns LaTeX source into a PDF over HTTP.
//
// It is deliberately the dumbest service in the stack: no database, no
// sessions, no knowledge of resumes. It takes a .tex, runs a sandboxed TeX
// engine over it and hands back the bytes. Everything that decides *what* to
// compile lives upstream, which is what keeps this one small enough to
// reason about as a security boundary.
//
// It is not meant to face the internet. Only the API calls it, over the
// internal network, with a shared token.
package main

import (
	"errors"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"
)

type config struct {
	Port        string
	Token       string
	Bin         string
	Timeout     time.Duration
	MaxBytes    int64
	Concurrency int
}

func loadConfig() (config, error) {
	cfg := config{
		Port:        env("PORT", "8100"),
		Token:       os.Getenv("COMPILER_TOKEN"),
		Bin:         env("LATEX_BIN", "pdflatex"),
		Timeout:     20 * time.Second,
		MaxBytes:    1 << 20,
		Concurrency: 2,
	}

	if cfg.Token == "" {
		return cfg, errors.New("COMPILER_TOKEN must be set")
	}

	if raw := os.Getenv("COMPILE_TIMEOUT_SECONDS"); raw != "" {
		seconds, err := strconv.Atoi(raw)
		if err != nil {
			return cfg, errors.New("COMPILE_TIMEOUT_SECONDS must be a whole number of seconds")
		}
		cfg.Timeout = time.Duration(seconds) * time.Second
	}

	if raw := os.Getenv("COMPILE_CONCURRENCY"); raw != "" {
		concurrency, err := strconv.Atoi(raw)
		if err != nil || concurrency < 1 {
			return cfg, errors.New("COMPILE_CONCURRENCY must be a positive whole number")
		}
		cfg.Concurrency = concurrency
	}

	return cfg, nil
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

// probeHealth asks the local server whether it is up, and reports the exit
// code a health check should use.
//
// This lives in the binary rather than in the container's HEALTHCHECK line
// because the runtime image has no curl and its /bin/sh is dash, which has no
// /dev/tcp. Probing from Go needs neither.
func probeHealth(port string) int {
	client := &http.Client{Timeout: 2 * time.Second}

	response, err := client.Get("http://127.0.0.1:" + port + "/healthz")
	if err != nil {
		fmt.Fprintf(os.Stderr, "healthcheck: %v\n", err)
		return 1
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		fmt.Fprintf(os.Stderr, "healthcheck: status %d\n", response.StatusCode)
		return 1
	}

	return 0
}

func main() {
	healthcheck := flag.Bool("healthcheck", false, "probe the running server and exit")
	flag.Parse()

	if *healthcheck {
		os.Exit(probeHealth(env("PORT", "8100")))
	}

	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("configuration: %v", err)
	}

	compiler := NewCompiler(cfg.Bin, cfg.Timeout, cfg.Concurrency)

	server := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: newRouter(compiler, cfg.Token, cfg.MaxBytes),
		// a compile can legitimately take a while, so the write timeout has to
		// clear the engine's own limit rather than race it
		ReadHeaderTimeout: 5 * time.Second,
		WriteTimeout:      cfg.Timeout + 15*time.Second,
	}

	log.Printf("compiler listening on :%s (engine %q, %d at a time)", cfg.Port, cfg.Bin, cfg.Concurrency)
	if err := server.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("server: %v", err)
	}
}
