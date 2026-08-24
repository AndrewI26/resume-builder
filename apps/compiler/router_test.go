package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

const testToken = "test-token"

func testRouter(t *testing.T, engineBody string) http.Handler {
	t.Helper()

	compiler := NewCompiler(stubEngine(t, engineBody), 5*time.Second, 1)
	return newRouter(compiler, testToken, 1<<20)
}

func post(t *testing.T, handler http.Handler, body, token string) *httptest.ResponseRecorder {
	t.Helper()

	request := httptest.NewRequest(http.MethodPost, "/compile", strings.NewReader(body))
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}

	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, request)
	return recorder
}

func TestHealthzNeedsNoToken(t *testing.T) {
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/healthz", nil)

	testRouter(t, writesPDF).ServeHTTP(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Errorf("got %d, want 200", recorder.Code)
	}
}

func TestCompileReturnsAPDF(t *testing.T) {
	recorder := post(t, testRouter(t, writesPDF), `\documentclass{article}`, testToken)

	if recorder.Code != http.StatusOK {
		t.Fatalf("got %d, want 200", recorder.Code)
	}
	if got := recorder.Header().Get("Content-Type"); got != "application/pdf" {
		t.Errorf("Content-Type %q, want application/pdf", got)
	}
	if !strings.HasPrefix(recorder.Body.String(), "%PDF") {
		t.Error("body is not a PDF")
	}
}

func TestCompileRejectsAMissingToken(t *testing.T) {
	recorder := post(t, testRouter(t, writesPDF), `\documentclass{article}`, "")

	if recorder.Code != http.StatusUnauthorized {
		t.Errorf("got %d, want 401", recorder.Code)
	}
}

func TestCompileRejectsAWrongToken(t *testing.T) {
	recorder := post(t, testRouter(t, writesPDF), `\documentclass{article}`, "not-the-token")

	if recorder.Code != http.StatusUnauthorized {
		t.Errorf("got %d, want 401", recorder.Code)
	}
}

func TestCompileRejectsAnEmptyBody(t *testing.T) {
	recorder := post(t, testRouter(t, writesPDF), "   \n  ", testToken)

	if recorder.Code != http.StatusBadRequest {
		t.Errorf("got %d, want 400", recorder.Code)
	}
}

func TestCompileRejectsAnOversizedBody(t *testing.T) {
	compiler := NewCompiler(stubEngine(t, writesPDF), 5*time.Second, 1)
	handler := newRouter(compiler, testToken, 64)

	recorder := post(t, handler, strings.Repeat("x", 500), testToken)

	if recorder.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("got %d, want 413", recorder.Code)
	}
}

func TestCompileReportsABadDocumentAsUnprocessable(t *testing.T) {
	handler := testRouter(t, "echo 'Undefined control sequence' >&2\nexit 1\n")

	recorder := post(t, handler, `\nope`, testToken)

	if recorder.Code != http.StatusUnprocessableEntity {
		t.Fatalf("got %d, want 422", recorder.Code)
	}
	if !strings.Contains(recorder.Body.String(), "Undefined control sequence") {
		t.Error("the engine's log did not reach the caller")
	}
}

func TestCompileRejectsAGetRequest(t *testing.T) {
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/compile", nil)
	request.Header.Set("Authorization", "Bearer "+testToken)

	testRouter(t, writesPDF).ServeHTTP(recorder, request)

	if recorder.Code == http.StatusOK {
		t.Error("a GET reached the compile handler")
	}
}
