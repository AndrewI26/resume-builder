package tui

import (
	"errors"
	"os"
	"unicode/utf8"
)

const maxFileSize = 2 << 20 // 2 MiB

var ErrBinaryOrInvalidUTF8 = errors.New("file is not valid UTF-8 text")
var ErrFileTooLarge = errors.New("file too large")

func loadFile(path string) (string, error) {
	fi, err := os.Stat(path)
	if err != nil {
		return "", err
	}
	if fi.IsDir() {
		return "", errors.New("is a directory")
	}
	if fi.Size() > maxFileSize {
		return "", ErrFileTooLarge
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	if !utf8.Valid(b) {
		return "", ErrBinaryOrInvalidUTF8
	}
	return string(b), nil
}

func saveFile(path string, content string) error {
	mode := os.FileMode(0o644)
	if fi, err := os.Stat(path); err == nil && !fi.IsDir() {
		mode = fi.Mode().Perm()
	}
	return os.WriteFile(path, []byte(content), mode)
}
