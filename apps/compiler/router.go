package main

import (
	"crypto/subtle"
	"errors"
	"io"
	"log"
	"net/http"
	"strings"
)

func newRouter(compiler *Compiler, token string, maxBytes int64) http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, "ok\n")
	})

	mux.Handle("POST /compile", requireToken(token, compileHandler(compiler, maxBytes)))

	return mux
}

// requireToken gates a handler on a shared bearer token.
//
// The service should not be reachable from outside the internal network in
// the first place; this is the second lock, for the day a port mapping is
// added by accident.
func requireToken(token string, next http.Handler) http.Handler {
	want := []byte("Bearer " + token)

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got := []byte(r.Header.Get("Authorization"))

		// constant time, so a caller cannot learn the token a byte at a time
		// by measuring how long the comparison takes
		if subtle.ConstantTimeCompare(got, want) != 1 {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func compileHandler(compiler *Compiler, maxBytes int64) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// caps the read before anything is buffered, so an endless body cannot
		// exhaust memory
		source, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxBytes))
		if err != nil {
			http.Error(w, "source too large", http.StatusRequestEntityTooLarge)
			return
		}

		if len(strings.TrimSpace(string(source))) == 0 {
			http.Error(w, "empty source", http.StatusBadRequest)
			return
		}

		pdf, err := compiler.Compile(r.Context(), source)
		if err != nil {
			var failed *CompileFailed
			switch {
			case errors.As(err, &failed):
				// the document is at fault, not the service. The log goes back
				// so the caller can surface something useful.
				w.Header().Set("Content-Type", "text/plain; charset=utf-8")
				w.WriteHeader(http.StatusUnprocessableEntity)
				_, _ = io.WriteString(w, failed.Log)
			case errors.Is(err, ErrBusy):
				http.Error(w, "busy", http.StatusServiceUnavailable)
			default:
				log.Printf("compile: %v", err)
				http.Error(w, "compilation error", http.StatusInternalServerError)
			}
			return
		}

		w.Header().Set("Content-Type", "application/pdf")
		w.Header().Set("Content-Disposition", `inline; filename="resume.pdf"`)
		if _, err := w.Write(pdf); err != nil {
			log.Printf("writing pdf: %v", err)
		}
	})
}
