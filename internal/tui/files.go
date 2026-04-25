package tui

import (
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/charmbracelet/bubbles/list"
)

// fileItem implements list.Item for directory entries.
type fileItem struct {
	title string
	path  string
	isDir bool
}

func (f fileItem) Title() string       { return f.title }
func (f fileItem) Description() string { return "" }
func (f fileItem) FilterValue() string { return f.title }

// headingItem is a non-interactive section label in the list (cursor skips it; Enter ignored).
// FilterValue uses an unlikely token so fuzzy search rarely matches; custom Filter also drops headings.
type headingItem struct{ label string }

func (h headingItem) Title() string       { return h.label }
func (h headingItem) Description() string { return "" }
func (h headingItem) FilterValue() string { return "\u200c\u200csection:" + h.label }

// containedInRoot reports whether path equals root or is a subdirectory of root.
func containedInRoot(path, root string) bool {
	path = filepath.Clean(path)
	root = filepath.Clean(root)
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return false
	}
	if rel == "." {
		return true
	}
	return !strings.HasPrefix(rel, "..")
}

// readDirItems returns list items for cwd, constrained to stay under root (both absolute).
func readDirItems(cwd, root string) ([]list.Item, error) {
	cwd = filepath.Clean(cwd)
	root = filepath.Clean(root)
	if !containedInRoot(cwd, root) {
		return nil, fs.ErrNotExist
	}

	var items []list.Item
	if cwd != root {
		parent := filepath.Dir(cwd)
		if !containedInRoot(parent, root) {
			parent = root
		}
		items = append(items, fileItem{title: "..", path: parent, isDir: true})
	}

	entries, err := os.ReadDir(cwd)
	if err != nil {
		return nil, err
	}

	type named struct {
		name  string
		path  string
		isDir bool
	}
	var dirs, files []named
	for _, e := range entries {
		name := e.Name()
		full := filepath.Join(cwd, name)
		if e.IsDir() {
			dirs = append(dirs, named{name: name + "/", path: full, isDir: true})
		} else {
			files = append(files, named{name: name, path: full, isDir: false})
		}
	}
	sort.Slice(dirs, func(i, j int) bool { return dirs[i].name < dirs[j].name })
	sort.Slice(files, func(i, j int) bool { return files[i].name < files[j].name })

	if len(dirs) > 0 {
		items = append(items, headingItem{label: "Directories"})
		for _, d := range dirs {
			items = append(items, fileItem{title: d.name, path: d.path, isDir: d.isDir})
		}
	}
	if len(files) > 0 {
		items = append(items, headingItem{label: "Files"})
		for _, f := range files {
			items = append(items, fileItem{title: f.name, path: f.path, isDir: f.isDir})
		}
	}
	return items, nil
}

// IsHeading reports whether the list item is a section heading.
func IsHeading(it list.Item) bool {
	if it == nil {
		return false
	}
	_, ok := it.(headingItem)
	return ok
}
