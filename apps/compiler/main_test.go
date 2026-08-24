package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
)

// serveOnLoopback starts a server on a real loopback port, since probeHealth
// dials 127.0.0.1 by design rather than taking an address.
func serveOnLoopback(t *testing.T, handler http.Handler) string {
	t.Helper()

	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)

	parsed, err := url.Parse(server.URL)
	if err != nil {
		t.Fatalf("parsing test server URL: %v", err)
	}
	return parsed.Port()
}

func TestProbeHealthSucceedsAgainstAHealthyServer(t *testing.T) {
	port := serveOnLoopback(t, newRouter(
		NewCompiler(stubEngine(t, writesPDF), 0, 1), "token", 1<<20,
	))

	if code := probeHealth(port); code != 0 {
		t.Errorf("got exit %d, want 0", code)
	}
}

func TestProbeHealthFailsWhenNothingIsListening(t *testing.T) {
	// port 1 is reserved and nothing will be on it
	if code := probeHealth("1"); code == 0 {
		t.Error("got exit 0 for a port with no server")
	}
}

func TestProbeHealthFailsOnANonOKStatus(t *testing.T) {
	port := serveOnLoopback(t, http.HandlerFunc(
		func(w http.ResponseWriter, r *http.Request) {
			http.Error(w, "nope", http.StatusInternalServerError)
		},
	))

	if code := probeHealth(port); code == 0 {
		t.Error("got exit 0 for a failing server")
	}
}

func TestProbeHealthNeedsNoToken(t *testing.T) {
	// the health endpoint must stay reachable without credentials, or the
	// container could never report itself healthy
	port := serveOnLoopback(t, newRouter(
		NewCompiler(stubEngine(t, writesPDF), 0, 1), "a-token-the-probe-does-not-know", 1<<20,
	))

	if code := probeHealth(port); code != 0 {
		t.Errorf("got exit %d, want 0", code)
	}
}
